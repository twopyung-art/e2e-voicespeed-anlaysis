"""
T0/T1/T2/T3 할당 핵심 로직

타임라인:
  [사용자음성] → T0 → [음성인식음] → T1 → [중간음①] → T2 → [중간음②] → T3 → [최종응답]

중간음 횟수별 처리:
  0회: T1=음성인식음~최종응답, T2=0, T3=0
  1회: T1=음성인식음~중간음①, T2=0, T3=중간음①~최종응답
  2회: T1=음성인식음~중간음①, T2=중간음①~중간음②, T3=중간음②~최종응답
  3회: 위와 동일, 3번째 중간음 무시

E2E = T1 + T2 + T3  (T0 제외)

감지 방식:
  - reference/ 폴더에 기준 음원 파일이 있으면 cross-correlation 기반 정밀 감지
  - 기준 음원이 없으면 RMS 에너지 기반 위치 추정 (폴백)
"""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import os

from core.audio_loader import load_audio, normalize_audio
from core.segment_detector import get_audio_segments
import config


@dataclass
class AnalysisResult:
    file_path: str
    file_name: str
    command: str                        # 폴더명 (명령어)
    T0: float = 0.0                     # 사용자음성끝 ~ 음성인식음 시작 (초)
    T1: float = 0.0                     # 음성인식음 ~ 첫 중간음 or 최종응답 (초)
    T2: float = 0.0                     # 중간음① ~ 중간음② (초, 없으면 0)
    T3: float = 0.0                     # 마지막 중간음 ~ 최종응답 (초, 없으면 0)
    E2E: float = 0.0                    # T1 + T2 + T3
    audio_duration: float = 0.0        # 전체 오디오 길이 (초)
    segments: list = field(default_factory=list)
    rms_db: Optional[np.ndarray] = None
    times: Optional[np.ndarray] = None
    threshold: float = 0.0
    segment_labels: list = field(default_factory=list)  # 각 구간 레이블
    detection_mode: str = "rms"         # "reference" or "rms"
    error: Optional[str] = None


def analyze(file_path: str) -> AnalysisResult:
    """
    오디오 파일을 분석하여 T0/T1/T2/T3 및 E2E를 계산합니다.

    기준 음원 파일(reference/)이 있으면 cross-correlation으로 정밀 감지하고,
    없으면 RMS 에너지 기반 위치 추정(폴백)을 사용합니다.
    """
    file_name = os.path.basename(file_path)
    command = os.path.basename(os.path.dirname(file_path))

    result = AnalysisResult(
        file_path=file_path,
        file_name=file_name,
        command=command,
    )

    try:
        y, sr = load_audio(file_path)
        y = normalize_audio(y)
        result.audio_duration = len(y) / sr

        detection = get_audio_segments(y)
        result.rms_db = detection["rms_db"]
        result.times = detection["times"]
        result.threshold = detection["threshold"]

        # ── 기준 음원 감지 시도 ──────────────────────────────────────
        from core.reference_detector import get_detector
        detector = get_detector()

        if detector.available:
            _analyze_with_reference(result, y, detection, detector)
        else:
            _analyze_with_rms(result, detection)

    except Exception as e:
        result.error = str(e)

    return result


# ── 기준 음원 기반 분석 ────────────────────────────────────────────────

def _analyze_with_reference(result: AnalysisResult, y: np.ndarray,
                             detection: dict, detector) -> None:
    """
    cross-correlation으로 인식음/중간음 위치를 찾은 후
    RMS 구간에서 '사용자음성'과 '최종응답'을 결정합니다.
    """
    result.detection_mode = "reference"
    ref_result = detector.detect(y)

    recog_hits  = ref_result["recognition"]   # [{"start","end","score"}, ...]
    middle_hits = ref_result["middle"]

    rms_segments = detection["segments"]

    # ── 사용자 음성 찾기 ─────────────────────────────────────────
    # 인식음보다 앞에 있는 RMS 구간 중 첫 번째
    user_voice_seg = None
    recog_start = recog_hits[0]["start"] if recog_hits else None

    if recog_start is not None:
        # 인식음 시작보다 이전에 끝나는 RMS 구간 중 마지막 → 사용자 음성
        candidates = [s for s in rms_segments if s["end"] < recog_start - 0.05]
        if candidates:
            user_voice_seg = candidates[-1]

    if user_voice_seg is None:
        # 인식음 이전 구간을 찾지 못하면: RMS 구간 첫 번째 사용
        if rms_segments:
            user_voice_seg = rms_segments[0]

    # ── 최종응답 찾기 ────────────────────────────────────────────
    # 기준: 인식음/중간음 이후에 있는 RMS 구간 중 마지막 유의미한 구간
    # 인식음의 마지막 등장 또는 중간음의 마지막 등장 이후 구간
    last_ref_end = 0.0
    if recog_hits:
        last_ref_end = max(last_ref_end, recog_hits[-1]["end"])
    if middle_hits:
        last_ref_end = max(last_ref_end, middle_hits[-1]["end"])

    final_response_seg = None
    if last_ref_end > 0:
        # 마지막 기준음 이후에 시작하는 RMS 구간 중 첫 번째 → 최종응답
        after = [s for s in rms_segments if s["start"] > last_ref_end + 0.05]
        if after:
            final_response_seg = after[0]

    if final_response_seg is None:
        # 폴백: RMS 구간의 마지막 구간
        after_recog = [s for s in rms_segments
                       if recog_start is None or s["start"] > (recog_start + 0.1)]
        if after_recog:
            final_response_seg = after_recog[-1]
        elif rms_segments:
            final_response_seg = rms_segments[-1]

    # 사용자음성과 최종응답이 같은 구간이면 오류
    if (user_voice_seg is not None and final_response_seg is not None
            and user_voice_seg is final_response_seg):
        final_response_seg = None

    # ── 충분한 구간이 없으면 에러 ────────────────────────────────
    if user_voice_seg is None or final_response_seg is None:
        result.error = "구간 감지 실패: 사용자음성 또는 최종응답을 찾지 못했습니다."
        return

    # ── T0/T1/T2/T3 계산 ─────────────────────────────────────────
    # 인식음 (첫 번째 등장)
    if recog_hits:
        recog_seg = recog_hits[0]
    else:
        # 인식음 없음: T0=0, T1=사용자음성끝~최종응답
        T0 = 0.0
        T1 = max(0.0, final_response_seg["start"] - user_voice_seg["end"])
        T2 = 0.0
        T3 = 0.0
        _set_result_no_recog(result, user_voice_seg, final_response_seg, T0, T1, T2, T3)
        return

    T0 = max(0.0, recog_seg["start"] - user_voice_seg["end"])

    # 유효 중간음: 인식음 이후, 최종응답 이전
    valid_middles = [
        m for m in middle_hits
        if m["start"] > recog_seg["end"] - 0.05
        and m["start"] < final_response_seg["start"] - 0.05
    ]
    # 최대 2개만 사용
    valid_middles = valid_middles[:2]

    n_mid = len(valid_middles)

    if n_mid == 0:
        T1 = max(0.0, final_response_seg["start"] - recog_seg["start"])
        T2 = 0.0
        T3 = 0.0
    elif n_mid == 1:
        mid1 = valid_middles[0]
        T1 = max(0.0, mid1["start"] - recog_seg["start"])
        T2 = 0.0
        T3 = max(0.0, final_response_seg["start"] - mid1["start"])
    else:  # n_mid == 2
        mid1 = valid_middles[0]
        mid2 = valid_middles[1]
        T1 = max(0.0, mid1["start"] - recog_seg["start"])
        T2 = max(0.0, mid2["start"] - mid1["start"])
        T3 = max(0.0, final_response_seg["start"] - mid2["start"])

    result.T0 = round(T0, 3)
    result.T1 = round(T1, 3)
    result.T2 = round(T2, 3)
    result.T3 = round(T3, 3)
    result.E2E = round(T1 + T2 + T3, 3)

    # ── 구간/레이블 목록 구성 (이미지 표시용) ─────────────────────
    segments = [user_voice_seg, recog_seg]
    labels   = ["사용자음성", "음성인식음"]

    for i, m in enumerate(valid_middles):
        segments.append(m)
        labels.append(f"중간음{'①②'[i]}")

    segments.append(final_response_seg)
    labels.append("최종응답")

    result.segments = segments
    result.segment_labels = labels


def _set_result_no_recog(result, user_voice_seg, final_response_seg,
                         T0, T1, T2, T3):
    result.T0 = round(T0, 3)
    result.T1 = round(T1, 3)
    result.T2 = round(T2, 3)
    result.T3 = round(T3, 3)
    result.E2E = round(T1 + T2 + T3, 3)
    result.segments = [user_voice_seg, final_response_seg]
    result.segment_labels = ["사용자음성", "최종응답"]


# ── RMS 에너지 기반 폴백 분석 ──────────────────────────────────────────

def _analyze_with_rms(result: AnalysisResult, detection: dict) -> None:
    """
    기준 음원이 없을 때 RMS 구간 순서로 T0/T1/T2/T3를 추정합니다.

    구간 순서 (index):
        0: 사용자 음성
        1: 음성인식음
        2: 중간음① (선택적)
        3: 중간음② (선택적)
        4: 최종응답
    """
    result.detection_mode = "rms"
    segments = detection["segments"]

    # 최대 MAX_SEGMENTS개까지만 사용
    segments = segments[:config.MAX_SEGMENTS]
    result.segments = segments

    if len(segments) < 2:
        result.error = (
            f"구간 감지 실패: 활성 구간이 {len(segments)}개뿐입니다. "
            "(최소 2개 필요: 사용자음성 + 최종응답)"
        )
        return

    n = len(segments)

    # 레이블 부여
    if n == 2:
        labels = ["사용자음성", "최종응답"]
    elif n == 3:
        labels = ["사용자음성", "음성인식음", "최종응답"]
    elif n == 4:
        labels = ["사용자음성", "음성인식음", "중간음①", "최종응답"]
    else:  # n >= 5
        if n > 5:
            segments = segments[:4] + [segments[-1]]
            n = 5
        labels = ["사용자음성", "음성인식음", "중간음①", "중간음②", "최종응답"]

    result.segment_labels = labels
    result.segments = segments

    user_voice      = segments[0]
    final_response  = segments[-1]

    # T0
    if n >= 3:
        recognition_sound = segments[1]
        T0 = recognition_sound["start"] - user_voice["end"]
    else:
        T0 = final_response["start"] - user_voice["end"]
    T0 = max(0.0, T0)

    # T1/T2/T3
    if n == 2:
        T1 = final_response["start"] - user_voice["end"]
        T2 = 0.0
        T3 = 0.0
    elif n == 3:
        recognition_sound = segments[1]
        T1 = final_response["start"] - recognition_sound["start"]
        T2 = 0.0
        T3 = 0.0
    elif n == 4:
        recognition_sound = segments[1]
        middle1 = segments[2]
        T1 = middle1["start"] - recognition_sound["start"]
        T2 = 0.0
        T3 = final_response["start"] - middle1["start"]
    else:  # n == 5
        recognition_sound = segments[1]
        middle1 = segments[2]
        middle2 = segments[3]
        T1 = middle1["start"] - recognition_sound["start"]
        T2 = middle2["start"] - middle1["start"]
        T3 = final_response["start"] - middle2["start"]

    result.T0  = round(max(0.0, T0), 3)
    result.T1  = round(max(0.0, T1), 3)
    result.T2  = round(max(0.0, T2), 3)
    result.T3  = round(max(0.0, T3), 3)
    result.E2E = round(result.T1 + result.T2 + result.T3, 3)

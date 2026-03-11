"""
RMS 에너지 기반 음성/침묵 구간 감지 모듈
"""
import numpy as np
import librosa
import config


def compute_rms_db(y: np.ndarray, frame_length: int = None, hop_length: int = None) -> tuple:
    """
    오디오 신호의 RMS 에너지를 dBFS 단위로 계산합니다.

    Returns:
        (rms_db: np.ndarray, times: np.ndarray)
        - rms_db: 프레임별 dBFS 값 (음수, 클수록 큰 소리)
        - times: 각 프레임의 시간(초)
    """
    if frame_length is None:
        frame_length = config.FRAME_LENGTH
    if hop_length is None:
        hop_length = config.HOP_LENGTH

    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    # 0 방지 후 dBFS 변환
    rms = np.maximum(rms, 1e-10)
    rms_db = 20 * np.log10(rms)

    times = librosa.frames_to_time(
        np.arange(len(rms_db)),
        sr=config.SAMPLE_RATE,
        hop_length=hop_length
    )
    return rms_db, times


def compute_threshold(rms_db: np.ndarray) -> float:
    """
    배경소음 기반 적응형 임계값을 계산합니다.
    하위 NOISE_PERCENTILE% 분위수 + THRESHOLD_OFFSET_DB
    """
    noise_floor = np.percentile(rms_db, config.NOISE_PERCENTILE)
    return noise_floor + config.THRESHOLD_OFFSET_DB


def detect_active_segments(rms_db: np.ndarray, times: np.ndarray, threshold: float) -> list:
    """
    임계값을 초과하는 활성 구간을 감지합니다.

    Returns:
        [{"start": float, "end": float}, ...]  # 시간(초) 단위
    """
    active = rms_db >= threshold
    segments = []
    in_segment = False
    start_time = 0.0

    for i, (is_active, t) in enumerate(zip(active, times)):
        if is_active and not in_segment:
            in_segment = True
            start_time = t
        elif not is_active and in_segment:
            in_segment = False
            segments.append({"start": start_time, "end": t})

    # 마지막 구간이 끝까지 이어질 경우
    if in_segment:
        segments.append({"start": start_time, "end": times[-1]})

    return segments


def merge_close_segments(segments: list, max_gap: float = None) -> list:
    """
    max_gap(초) 이하의 간격으로 분리된 구간을 하나로 병합합니다.
    """
    if max_gap is None:
        max_gap = config.MAX_MERGE_GAP

    if len(segments) <= 1:
        return segments

    merged = [segments[0].copy()]
    for seg in segments[1:]:
        gap = seg["start"] - merged[-1]["end"]
        if gap <= max_gap:
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(seg.copy())

    return merged


def filter_by_duration(segments: list, min_duration: float = None) -> list:
    """
    최소 지속시간 이하의 짧은 구간(잡음)을 제거합니다.
    """
    if min_duration is None:
        min_duration = config.MIN_SEGMENT_DURATION

    return [s for s in segments if (s["end"] - s["start"]) >= min_duration]


def get_audio_segments(y: np.ndarray) -> dict:
    """
    오디오에서 활성 구간을 감지하는 전체 파이프라인.

    Returns:
        {
            "rms_db": np.ndarray,
            "times": np.ndarray,
            "threshold": float,
            "segments": [{"start": float, "end": float}, ...]
        }
    """
    rms_db, times = compute_rms_db(y)
    threshold = compute_threshold(rms_db)
    raw_segments = detect_active_segments(rms_db, times, threshold)
    merged = merge_close_segments(raw_segments)
    filtered = filter_by_duration(merged)

    return {
        "rms_db": rms_db,
        "times": times,
        "threshold": threshold,
        "segments": filtered,
    }

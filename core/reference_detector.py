"""
기준 음원 기반 세그먼트 감지 모듈

reference/ 폴더에 아래 파일을 배치하면 cross-correlation으로 정확히 감지합니다:
  - recognition_sound.wav  (인식음 — 사용자 음성 인식 후 나오는 짧은 음)
  - middle_sound.wav       (중간음 — 응답 전 나오는 처리음)

파일이 없으면 자동으로 None 처리되며, waveform_analyzer가 폴백 모드로 동작합니다.
"""

import os
import numpy as np
import librosa
from scipy.signal import correlate, find_peaks
import config

# 지원 확장자
_AUDIO_EXTS = {".wav", ".m4a", ".mp3", ".flac", ".aac", ".ogg"}

# 기준 파일 이름 (확장자 제외)
RECOG_STEM  = "recognition_sound"
MIDDLE_STEM = "middle_sound"


def _find_file(directory: str, stem: str) -> str | None:
    """stem 이름으로 기준 파일을 찾습니다 (확장자 무관)."""
    if not os.path.isdir(directory):
        return None
    for fname in os.listdir(directory):
        name, ext = os.path.splitext(fname)
        if name == stem and ext.lower() in _AUDIO_EXTS:
            return os.path.join(directory, fname)
    return None


class ReferenceDetector:
    """
    기준 음원 파일을 로드하고 대상 오디오에서 패턴 발생 위치를 찾습니다.
    """

    def __init__(self, reference_dir: str = None):
        if reference_dir is None:
            reference_dir = config.REFERENCE_DIR

        self.recognition_template: np.ndarray | None = None
        self.middle_template: np.ndarray | None = None
        self.available = False
        self.reference_dir = reference_dir

        self._load(reference_dir)

    def _load(self, ref_dir: str):
        recog_path  = _find_file(ref_dir, RECOG_STEM)
        middle_path = _find_file(ref_dir, MIDDLE_STEM)

        if recog_path:
            try:
                self.recognition_template, _ = librosa.load(
                    recog_path, sr=config.SAMPLE_RATE, mono=True)
            except Exception:
                pass

        if middle_path:
            try:
                self.middle_template, _ = librosa.load(
                    middle_path, sr=config.SAMPLE_RATE, mono=True)
            except Exception:
                pass

        self.available = (
            self.recognition_template is not None
            or self.middle_template is not None
        )

    # ── 핵심: normalized cross-correlation 기반 위치 탐색 ──────────────

    def find_template(
        self,
        audio: np.ndarray,
        template: np.ndarray,
        threshold: float = None,
    ) -> list:
        """
        audio 안에서 template 패턴이 나타나는 위치를 반환합니다.

        Args:
            audio:     검색 대상 오디오 (float32, sr=16kHz)
            template:  기준 음원 (float32, sr=16kHz)
            threshold: 상관계수 임계값 (0~1, 기본 config.REFERENCE_THRESHOLD)

        Returns:
            [{"start": float, "end": float, "score": float}, ...]  (초 단위)
        """
        if template is None or len(template) == 0:
            return []
        if threshold is None:
            threshold = config.REFERENCE_THRESHOLD

        sr   = config.SAMPLE_RATE
        tlen = len(template)

        # 피크 정규화
        a = audio    / (np.max(np.abs(audio))    + 1e-10)
        t = template / (np.max(np.abs(template)) + 1e-10)

        # Normalized cross-correlation
        corr = correlate(a, t, mode="full")

        # 로컬 에너지 기반 정규화
        t_energy   = float(np.sqrt(np.sum(t ** 2)))
        a_sq_conv  = np.convolve(a ** 2, np.ones(tlen, dtype=np.float32), mode="full")
        norm_denom = t_energy * np.sqrt(np.maximum(a_sq_conv, 1e-10))
        corr_norm  = corr / norm_denom

        # 피크 탐지 (최소 간격: template 길이의 절반)
        peaks, _ = find_peaks(
            corr_norm,
            height=threshold,
            distance=max(1, tlen // 2),
        )

        results = []
        for p in peaks:
            start_sample = p - tlen + 1
            if start_sample < 0:
                continue
            results.append({
                "start": round(start_sample / sr, 4),
                "end":   round((start_sample + tlen) / sr, 4),
                "score": round(float(corr_norm[p]), 4),
            })

        return sorted(results, key=lambda x: x["start"])

    def detect(self, audio: np.ndarray) -> dict:
        """
        오디오에서 인식음과 중간음의 발생 위치를 모두 반환합니다.

        Returns:
            {
                "recognition": [{"start", "end", "score"}, ...],
                "middle":      [{"start", "end", "score"}, ...],
                "recog_loaded":  bool,
                "middle_loaded": bool,
            }
        """
        return {
            "recognition":  self.find_template(audio, self.recognition_template),
            "middle":       self.find_template(audio, self.middle_template),
            "recog_loaded":  self.recognition_template is not None,
            "middle_loaded": self.middle_template is not None,
        }

    def status(self) -> dict:
        """기준 파일 로드 상태를 반환합니다."""
        return {
            "available":     self.available,
            "recog_loaded":  self.recognition_template is not None,
            "middle_loaded": self.middle_template is not None,
            "reference_dir": self.reference_dir,
        }


# 전역 싱글턴 (앱 시작 시 한 번만 로드)
_detector: ReferenceDetector | None = None


def get_detector() -> ReferenceDetector:
    global _detector
    if _detector is None:
        _detector = ReferenceDetector()
    return _detector


def reload_detector():
    """reference/ 파일 변경 후 재로드합니다."""
    global _detector
    _detector = ReferenceDetector()
    return _detector

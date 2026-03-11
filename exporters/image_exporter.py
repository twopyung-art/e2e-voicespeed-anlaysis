"""
파형 분석 이미지 저장 모듈
- 파형 + RMS 에너지 + T0/T1/T2/T3 컬러 음영 표시
- PNG 파일로 저장
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")  # GUI 없이 파일 저장
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import librosa
import config

# ── 한국어 폰트 설정 ──────────────────────────────────────────────────
def _setup_korean_font():
    """Windows/macOS/Linux에서 한국어를 지원하는 폰트를 자동으로 설정합니다."""
    candidates = [
        "Malgun Gothic",       # Windows
        "AppleGothic",         # macOS
        "NanumGothic",         # Linux (설치된 경우)
        "NanumBarunGothic",
        "Gulim",
        "Dotum",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            plt.rcParams["font.family"] = font
            plt.rcParams["axes.unicode_minus"] = False
            return
    # 후보 없으면 유니코드 마이너스 기호만 수정
    plt.rcParams["axes.unicode_minus"] = False

_setup_korean_font()

# 구간별 색상
COLORS = {
    "사용자음성":  ("#6B7280", 0.25),   # 회색
    "T0":         ("#F59E0B", 0.20),   # 노랑 (침묵)
    "음성인식음": ("#3B82F6", 0.35),   # 파랑
    "T1":         ("#8B5CF6", 0.20),   # 보라
    "중간음①":   ("#10B981", 0.35),   # 초록
    "T2":         ("#8B5CF6", 0.20),   # 보라
    "중간음②":   ("#10B981", 0.35),   # 초록
    "T3":         ("#8B5CF6", 0.20),   # 보라
    "최종응답":   ("#EF4444", 0.35),   # 빨강
}


def _add_span(ax, x_start, x_end, color, alpha, label=None):
    ax.axvspan(x_start, x_end, color=color, alpha=alpha, label=label)


def export_waveform(result, y: np.ndarray, output_dir: str = None) -> str:
    """
    파형 분석 이미지를 저장합니다.

    Args:
        result: AnalysisResult 인스턴스
        y: 오디오 신호 배열
        output_dir: 저장 디렉토리 (None이면 config.IMAGES_DIR/{command}/)

    Returns:
        저장된 이미지 파일 경로
    """
    if output_dir is None:
        safe_command = _safe_filename(result.command)
        output_dir = os.path.join(config.IMAGES_DIR, safe_command)
    os.makedirs(output_dir, exist_ok=True)

    safe_fname = os.path.splitext(_safe_filename(result.file_name))[0] + ".png"
    output_path = os.path.join(output_dir, safe_fname)

    sr = config.SAMPLE_RATE
    duration = result.audio_duration
    time_axis = np.linspace(0, duration, len(y))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    fig.patch.set_facecolor("#F8F7FF")
    for ax in (ax1, ax2):
        ax.set_facecolor("#FFFFFF")

    # ── 상단: 파형 ──────────────────────────────────────
    ax1.plot(time_axis, y, color="#5B21B6", linewidth=0.4, alpha=0.8)
    ax1.set_ylabel("진폭", fontsize=9)
    ax1.set_ylim(-1.1, 1.1)
    ax1.set_title(
        f"{result.command}  /  {result.file_name}\n"
        f"T0={result.T0:.3f}s  T1={result.T1:.3f}s  T2={result.T2:.3f}s  "
        f"T3={result.T3:.3f}s  E2E={result.E2E:.3f}s",
        fontsize=10, pad=8
    )

    # ── 하단: RMS 에너지 ─────────────────────────────────
    if result.rms_db is not None and result.times is not None:
        ax2.plot(result.times, result.rms_db, color="#7C3AED", linewidth=0.8)
        ax2.axhline(y=result.threshold, color="#EF4444", linewidth=1.0,
                    linestyle="--", label=f"임계값 ({result.threshold:.1f} dBFS)")
        ax2.set_ylabel("에너지 (dBFS)", fontsize=9)
        ax2.legend(fontsize=8, loc="upper right")

    ax2.set_xlabel("시간 (초)", fontsize=9)

    # ── 구간 음영 표시 ────────────────────────────────────
    segments = result.segments
    labels = result.segment_labels

    if segments and labels:
        _draw_segment_spans(ax1, ax2, segments, labels, result)

    plt.tight_layout(pad=1.5)
    plt.savefig(output_path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return output_path


def _draw_segment_spans(ax1, ax2, segments, labels, result):
    """각 구간과 T0/T1/T2/T3 침묵 구간에 컬러 음영을 추가합니다."""

    for i, (seg, label) in enumerate(zip(segments, labels)):
        color, alpha = COLORS.get(label, ("#94A3B8", 0.2))
        for ax in (ax1, ax2):
            _add_span(ax, seg["start"], seg["end"], color, alpha)
        # 구간 레이블 텍스트
        mid = (seg["start"] + seg["end"]) / 2
        ax1.text(mid, 0.95, label, ha="center", va="top",
                 fontsize=7, color="#1E1B4B",
                 transform=ax1.get_xaxis_transform())

    # T0 침묵 구간
    if len(segments) >= 2 and result.T0 > 0:
        t0_start = segments[0]["end"]
        t0_end = segments[1]["start"]
        color, alpha = COLORS["T0"]
        for ax in (ax1, ax2):
            _add_span(ax, t0_start, t0_end, color, alpha)
        mid = (t0_start + t0_end) / 2
        ax1.text(mid, 0.85, f"T0\n{result.T0:.2f}s", ha="center", va="top",
                 fontsize=7, color="#92400E",
                 transform=ax1.get_xaxis_transform())

    # T1 구간 레이블 (음성인식음 시작 ~ 중간음①or최종응답)
    _add_timing_label(ax1, segments, labels, result, "T1", result.T1)
    _add_timing_label(ax1, segments, labels, result, "T2", result.T2)
    _add_timing_label(ax1, segments, labels, result, "T3", result.T3)


def _add_timing_label(ax, segments, labels, result, key, value):
    """T1/T2/T3 값을 해당 구간 위에 표시합니다."""
    if value <= 0:
        return

    n = len(segments)
    x_start, x_end = None, None

    if key == "T1":
        if n >= 3:
            x_start = segments[1]["start"]
            x_end = segments[2]["start"] if n >= 4 else segments[-1]["start"]
    elif key == "T2":
        if n >= 4:
            x_start = segments[2]["start"]
            x_end = segments[3]["start"] if n >= 5 else segments[-1]["start"]
    elif key == "T3":
        if n >= 4:
            idx = 3 if n >= 5 else 2
            x_start = segments[idx]["start"]
            x_end = segments[-1]["start"]

    if x_start is not None and x_end is not None:
        color, alpha = COLORS.get(key, ("#8B5CF6", 0.15))
        ax.axvspan(x_start, x_end, color=color, alpha=alpha)
        mid = (x_start + x_end) / 2
        ax.text(mid, 0.75, f"{key}\n{value:.2f}s", ha="center", va="top",
                fontsize=7, color="#4C1D95",
                transform=ax.get_xaxis_transform())


def _safe_filename(name: str) -> str:
    """파일/폴더명에서 사용 불가 문자를 제거합니다."""
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name

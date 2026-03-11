import os

# ───────────────────────────────────────────
# 경로 설정
# ───────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
EXCEL_DIR = os.path.join(RESULTS_DIR, "excel")
IMAGES_DIR = os.path.join(RESULTS_DIR, "images")
JSON_DIR = os.path.join(RESULTS_DIR, "json")
REFERENCE_DIR = os.path.join(BASE_DIR, "reference")

# ───────────────────────────────────────────
# 오디오 분석 파라미터
# ───────────────────────────────────────────

# 리샘플링 주파수
SAMPLE_RATE = 16000

# RMS 에너지 계산 프레임 설정
FRAME_LENGTH = 512   # ~32ms at 16kHz
HOP_LENGTH = 128     # ~8ms at 16kHz

# 활성 구간 감지 임계값
NOISE_PERCENTILE = 10       # 배경소음 측정에 사용할 하위 분위수(%)
THRESHOLD_OFFSET_DB = 15    # 배경소음 대비 활성 판단 기준 오프셋 (dB)

# 구간 필터링
MIN_SEGMENT_DURATION = 0.15   # 최소 유효 구간 길이 (초) — 잡음 제거
MAX_MERGE_GAP = 0.08          # 이 시간(초) 이하의 침묵은 같은 구간으로 병합

# 구간 분류
# 파형에서 감지되는 구간 순서:
#   [0] 사용자 음성
#   [1] 음성인식음
#   [2] 중간음① (있을 수도 없을 수도)
#   [3] 중간음② (있을 수도 없을 수도)
#   [4] 최종응답
MAX_SEGMENTS = 5              # 최대 감지 구간 수

# ───────────────────────────────────────────
# 통계 설정
# ───────────────────────────────────────────
TRIM_COUNT = 1      # 최대/최소 각 몇 개씩 제외할지 (1 = 각 1개 제외 → 8회 평균)

# ───────────────────────────────────────────
# 기준 음원 감지 파라미터
# ───────────────────────────────────────────
# reference/ 폴더에 recognition_sound.*, middle_sound.* 파일을 배치하면
# cross-correlation으로 정확히 감지합니다.
REFERENCE_THRESHOLD = 0.55  # 기준 음원 매칭 임계값 (0~1, 낮출수록 더 많이 감지)

# ───────────────────────────────────────────
# E2E 등급 기준 (초)
# ───────────────────────────────────────────
E2E_GOOD_THRESHOLD = 3.0     # 3초 미만: 빠름 (초록)
E2E_WARN_THRESHOLD = 5.0     # 3~5초: 보통 (노랑)
# 5초 초과: 느림 (빨강)

# ───────────────────────────────────────────
# Flask 서버 설정
# ───────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 5000
DEBUG = False

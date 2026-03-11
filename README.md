# 음성 스피커 E2E 속도 자동 측정기

## 사전 준비

### 1. ffmpeg 설치 (필수 — m4a 파일 처리에 필요)

```bash
# 방법 1: winget 사용 (Windows 10/11)
winget install ffmpeg

# 방법 2: 수동 설치
# https://ffmpeg.org/download.html → Windows 빌드 다운로드
# 압축 해제 후 bin 폴더를 시스템 PATH에 추가

# 설치 확인
ffmpeg -version
```

### 2. Python 패키지 설치

```bash
cd d:\MyProject\Test001
pip install -r requirements.txt
```

---

## 오디오 파일 배치

`audio/` 폴더 안에 명령어별 폴더를 만들고 녹음 파일을 넣으세요:

```
audio/
  ├── Check tomorrow's schedule/
  │     ├── Calendar tomorrow 1.m4a
  │     ├── Calendar tomorrow 2.m4a
  │     └── ... (최대 10개)
  └── What's my schedule today/
        ├── Calendar today 1.m4a
        └── ...
```

---

## 실행

```bash
python app.py
```

브라우저에서 **http://localhost:8080** 접속 후 **▶ 분석 시작** 클릭

---

## T0/T1/T2/T3 정의

```
[사용자음성] → T0 → [음성인식음] → T1 → [중간음①] → T2 → [중간음②] → T3 → [최종응답]
```

| 구간 | 설명 |
|------|------|
| T0 | 사용자 음성 끝 ~ 음성인식음 시작 |
| T1 | 음성인식음 ~ 첫 번째 중간음 (없으면 최종응답까지) |
| T2 | 첫 번째 중간음 ~ 두 번째 중간음 (없으면 0) |
| T3 | 마지막 유효 중간음 ~ 최종응답 시작 (없으면 0) |
| **E2E** | **T1 + T2 + T3** |

- 중간음 0회: T1 = 음성인식음 ~ 최종응답, T2=0, T3=0
- 중간음 3회 이상: 3번째부터 무시, T2까지만 사용

---

## 출력물

| 파일 | 위치 |
|------|------|
| Excel 결과 | `results/excel/E2E_분석결과_YYYYMMDD_HHMMSS.xlsx` |
| JSON 결과 | `results/json/E2E_분석결과_YYYYMMDD_HHMMSS.json` |
| 파형 이미지 | `results/images/{명령어}/{파일명}.png` |

---

## 분석 파라미터 조정

[config.py](config.py) 에서 감지 민감도를 조정할 수 있습니다:

```python
THRESHOLD_OFFSET_DB = 15   # 높이면 더 큰 소리만 감지 (잡음 제거)
MIN_SEGMENT_DURATION = 0.15  # 최소 구간 길이 (초)
MAX_MERGE_GAP = 0.08         # 병합할 최대 침묵 간격 (초)
```

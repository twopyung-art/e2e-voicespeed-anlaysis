"""
오디오 파일 로드 및 폴더 스캔 모듈
- audio/ 하위 폴더 자동 탐색
- m4a/wav/mp3 등 다양한 포맷 지원 (librosa + ffmpeg 필요)
"""
import os
import numpy as np
import librosa
import config

# 지원 오디오 확장자 (ffmpeg가 설치된 경우 거의 모든 포맷 지원)
SUPPORTED_EXTENSIONS = {
    ".m4a", ".wav", ".mp3", ".flac", ".ogg", ".aac",
    ".wma", ".mp4", ".webm", ".caf", ".aiff", ".aif",
    ".opus", ".amr", ".3gp", ".3gpp",
}


def scan_audio_folder(base_path: str = None) -> dict:
    """
    audio/ 폴더 하위의 명령어 폴더를 스캔하여 파일 목록을 반환합니다.

    Returns:
        {
            "폴더명(명령어)": ["파일경로1", "파일경로2", ...],
            ...
        }
    """
    if base_path is None:
        base_path = config.AUDIO_DIR

    result = {}
    if not os.path.isdir(base_path):
        return result

    for folder_name in sorted(os.listdir(base_path)):
        folder_path = os.path.join(base_path, folder_name)
        if not os.path.isdir(folder_path):
            continue

        files = []
        for fname in sorted(os.listdir(folder_path)):
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                files.append(os.path.join(folder_path, fname))

        if files:
            result[folder_name] = files

    return result


def load_audio(file_path: str, sr: int = None) -> tuple:
    """
    오디오 파일을 로드하여 (y, sr) 형태로 반환합니다.

    Args:
        file_path: 오디오 파일 경로
        sr: 목표 샘플레이트 (None이면 config.SAMPLE_RATE 사용)

    Returns:
        (y: np.ndarray float32, sr: int)

    Raises:
        RuntimeError: 파일 로드 실패 시
    """
    if sr is None:
        sr = config.SAMPLE_RATE

    try:
        y, loaded_sr = librosa.load(file_path, sr=sr, mono=True)
        return y, loaded_sr
    except Exception as e:
        # pydub 폴백 시도
        try:
            from pydub import AudioSegment
            import io
            audio = AudioSegment.from_file(file_path)
            audio = audio.set_frame_rate(sr).set_channels(1)
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples /= (2 ** (audio.sample_width * 8 - 1))
            return samples, sr
        except Exception as e2:
            raise RuntimeError(
                f"오디오 파일 로드 실패: {file_path}\n"
                f"librosa 오류: {e}\n"
                f"pydub 오류: {e2}\n"
                f"ffmpeg가 설치되어 있는지 확인하세요."
            )


def normalize_audio(y: np.ndarray) -> np.ndarray:
    """피크 기준으로 -1.0 ~ 1.0 범위로 정규화합니다."""
    peak = np.max(np.abs(y))
    if peak > 0:
        return y / peak
    return y

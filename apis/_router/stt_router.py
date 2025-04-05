import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import numpy as np
import speechbrain as sb
import torch
import whisper
from huggingface_hub import HfApi
from ninja import Router
from ninja.files import UploadedFile
from pyannote.audio import Pipeline
from pydub import AudioSegment

from _core.settings import HF_TOKEN

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 프로젝트 루트 디렉토리 설정
PROJECT_ROOT = Path(__file__).parent.parent.parent
CACHE_DIR = PROJECT_ROOT / "model_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 환경 변수 설정 (symlink 경고 비활성화)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TORCH_HOME"] = str(CACHE_DIR / "torch")
os.environ["HF_HOME"] = str(CACHE_DIR / "huggingface")
os.environ["SPEECHBRAIN_CACHE_DIR"] = str(CACHE_DIR / "speechbrain")
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

# SpeechBrain 캐시 설정
sb.utils.fetching.FETCHING_STRATEGY = "DOWNLOAD"

stt_router = Router()

# HuggingFace API 초기화
hf_api = HfApi()

# 캐시 디렉토리 설정
CACHE_DIR = Path.home() / ".cache" / "whisper_diarization"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# HuggingFace 토큰 가져오기
try:
    token = HF_TOKEN
    if not token:
        logger.error("No HuggingFace token found. Please run 'huggingface-cli login'")
        raise ValueError("HuggingFace token not found")
    logger.info(f"HuggingFace token found: {token[:8]}...")
except Exception as e:
    logger.error(f"Error getting HuggingFace token: {e}")
    token = None

# 전역 변수로 모델들 미리 로드
try:
    logger.info("Loading Whisper model...")
    whisper_model = whisper.load_model("base")
    logger.info("Whisper model loaded successfully")

    logger.info("Loading diarization pipeline...")

    if not token:
        raise ValueError("HuggingFace token not found")

    # 문서에 나온대로 정확히 초기화
    diarization_pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1", use_auth_token=token
    )

    # GPU 사용 가능하면 GPU로 이동
    if torch.cuda.is_available():
        diarization_pipeline.to(torch.device("cuda"))

    logger.info("Diarization pipeline loaded successfully")

except Exception as e:
    logger.error(f"Error during model initialization: {e}")
    if "401" in str(e):
        logger.error("Authentication failed. Please check your token")
    elif "403" in str(e):
        logger.error(
            "Access forbidden. Please accept the model terms at: "
            "https://huggingface.co/pyannote/speaker-diarization-3.1"
        )
    diarization_pipeline = None


@lru_cache(maxsize=1)
def load_whisper_model() -> whisper.Whisper:
    """Whisper 모델을 로드하고 캐시"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return whisper.load_model("base", device=device)


def load_audio(file_path: str) -> np.ndarray:
    """오디오 파일을 로드하고 전처리"""
    audio = AudioSegment.from_file(file_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    samples = np.array(audio.get_array_of_samples())
    return samples.astype(np.float32) / 32768.0


@stt_router.post("/transcribe")
def transcribe(request: Any, audio_file: UploadedFile) -> Dict:
    if not diarization_pipeline:
        return {
            "status": "error",
            "message": "Diarization pipeline not initialized. Please check model access.",
            "detail": "InitializationError",
        }

    temp_path = f"temp/{audio_file.name}"
    audio_path = None

    try:
        os.makedirs("temp", exist_ok=True)

        # 파일 저장
        with open(temp_path, "wb") as buffer:
            buffer.write(audio_file.read())

        # 오디오 전처리 (16kHz, mono)
        audio = AudioSegment.from_file(temp_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio_path = temp_path.rsplit(".", 1)[0] + ".wav"
        audio.export(audio_path, format="wav")

        # Whisper로 텍스트 변환
        transcription = whisper_model.transcribe(
            audio_path, language="ko", task="transcribe", fp16=torch.cuda.is_available()
        )

        # 화자 구분 수행 (문서 예시대로)
        diarization = diarization_pipeline(audio_path)

        # 결과 포맷팅
        formatted_result = []

        # 화자별 발화 구간 처리
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            # 해당 시간대의 텍스트 찾기
            segment_text = []
            for trans_segment in transcription["segments"]:
                # 시간 겹침 확인
                if (
                    trans_segment["start"] >= turn.start
                    and trans_segment["start"] < turn.end
                ) or (
                    trans_segment["end"] > turn.start
                    and trans_segment["end"] <= turn.end
                ):
                    segment_text.append(trans_segment["text"])

            if segment_text:
                formatted_result.append(
                    {
                        "start": round(turn.start, 2),
                        "end": round(turn.end, 2),
                        "speaker": speaker,
                        "text": " ".join(segment_text).strip(),
                        "duration": round(turn.end - turn.start, 2),
                    }
                )

        # 전체 오디오 길이 계산 (milliseconds to seconds)
        total_duration = len(audio) / 1000.0

        return {
            "status": "success",
            "processing_time": transcription.get("processing_time", 0),
            "total_duration": round(total_duration, 2),
            "speaker_count": len(
                set(turn[2] for turn in diarization.itertracks(yield_label=True))
            ),
            "language": transcription.get("language", "ko"),
            "results": formatted_result,
        }

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return {"status": "error", "message": str(e), "detail": str(type(e).__name__)}

    finally:
        # 임시 파일 삭제
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)

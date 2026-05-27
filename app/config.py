from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default

    parsed = tuple(item.strip() for item in value.split(",") if item.strip())
    return parsed or default


@dataclass(frozen=True)
class Settings:
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "small")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    temp_dir: Path = Path(os.getenv("TRANSCRIPTION_TEMP_DIR", "tmp"))
    max_upload_size_mb: int = _get_env_int("MAX_UPLOAD_SIZE_MB", 25)
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_default_model: str = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5:7b")
    ollama_timeout_seconds: int = _get_env_int("OLLAMA_TIMEOUT_SECONDS", 180)
    ollama_keep_alive: str = os.getenv("OLLAMA_KEEP_ALIVE", "10m")
    tts_provider: str = os.getenv("TTS_PROVIDER", "piper")
    tts_default_voice: str = os.getenv("TTS_DEFAULT_VOICE", "pt_BR-faber-medium")
    tts_voices_dir: Path = Path(os.getenv("TTS_VOICES_DIR", "tmp/voices"))
    generated_audio_dir: Path = Path(os.getenv("TTS_AUDIO_DIR", "tmp/generated-audio"))
    tts_use_cuda: bool = _get_env_bool("TTS_USE_CUDA", False)
    tts_default_speed: float = _get_env_float("TTS_DEFAULT_SPEED", 1.0)
    tts_max_text_length: int = _get_env_int("TTS_MAX_TEXT_LENGTH", 4000)
    tts_audio_ttl_minutes: int = _get_env_int("TTS_AUDIO_TTL_MINUTES", 1440)
    tts_available_voices: tuple[str, ...] = _get_env_csv(
        "TTS_AVAILABLE_VOICES",
        (
            "pt_BR-faber-medium",
            "pt_BR-edresson-low",
            "pt_BR-cadu-medium",
            "pt_BR-jeff-medium",
        ),
    )
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    search_enabled: bool = _get_env_bool("SEARCH_ENABLED", True)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()

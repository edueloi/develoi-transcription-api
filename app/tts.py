from __future__ import annotations

import asyncio
import threading
import time
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError

from fastapi import HTTPException
from piper.config import SynthesisConfig
from piper.download_voices import download_voice
from piper.voice import PiperVoice

from app.config import settings

VOICE_METADATA = {
    # Masculinas pt-BR
    "pt_BR-faber-medium": {
        "label": "Faber",
        "locale": "pt-BR",
        "quality": "medium",
        "gender": "masculino",
    },
    "pt_BR-edresson-low": {
        "label": "Edresson",
        "locale": "pt-BR",
        "quality": "low",
        "gender": "masculino",
    },
    "pt_BR-cadu-medium": {
        "label": "Cadu",
        "locale": "pt-BR",
        "quality": "medium",
        "gender": "masculino",
    },
    "pt_BR-jeff-medium": {
        "label": "Jeff",
        "locale": "pt-BR",
        "quality": "medium",
        "gender": "masculino",
    },
}

_voice_cache: dict[str, PiperVoice] = {}
_voice_cache_lock = threading.Lock()


@dataclass(frozen=True)
class SynthesizedAudio:
    text: str
    voice: str
    audio_url: str
    sample_rate: int
    duration_seconds: float
    size_bytes: int


@dataclass(frozen=True)
class VoiceOption:
    id: str
    label: str
    locale: str
    quality: str
    downloaded: bool
    is_default: bool
    gender: str | None = None


def get_loaded_voices() -> list[str]:
    with _voice_cache_lock:
        return sorted(_voice_cache.keys())


def list_voice_options() -> list[VoiceOption]:
    from app.tts_edge import EDGE_VOICES, get_edge_voice_meta

    configured_names = [
        settings.tts_default_voice,
        *settings.tts_available_voices,
        *_list_downloaded_voice_names(),
    ]

    unique_names: list[str] = []
    seen: set[str] = set()
    for voice_name in configured_names:
        normalized_name = voice_name.strip()
        if not normalized_name or normalized_name in seen:
            continue
        seen.add(normalized_name)
        unique_names.append(normalized_name)

    piper_voices = [
        VoiceOption(
            id=voice_name,
            label=_build_voice_label(voice_name),
            locale=_get_voice_locale(voice_name),
            quality=_get_voice_quality(voice_name),
            downloaded=voice_is_downloaded(voice_name),
            is_default=voice_name == settings.tts_default_voice,
            gender=VOICE_METADATA.get(voice_name, {}).get("gender"),
        )
        for voice_name in unique_names
    ]

    edge_voices = [
        VoiceOption(
            id=v["id"],
            label=f"{v['label']} (Edge Neural)",
            locale=v["locale"],
            quality=v["quality"],
            downloaded=True,
            is_default=False,
            gender=v["gender"],
        )
        for v in EDGE_VOICES
    ]

    return piper_voices + edge_voices


def voice_is_downloaded(voice_name: str | None = None) -> bool:
    model_path, config_path = _get_voice_paths(_resolve_voice_name(voice_name))
    return model_path.exists() and config_path.exists()


def _safe_text(text: str) -> str:
    # Algumas vozes do Piper usam pipeline ASCII internamente.
    # Encode para latin-1 (cobre todos os caracteres pt-BR) e decodifica de volta,
    # substituindo qualquer caractere fora do range por equivalente ASCII (unidecode-like).
    import unicodedata
    return unicodedata.normalize("NFC", text)


async def synthesize_speech(
    *,
    text: str,
    voice_name: str | None = None,
    speaker_id: int | None = None,
    speed: float | None = None,
    volume: float | None = None,
) -> SynthesizedAudio:
    from app.tts_edge import is_edge_voice, synthesize_edge

    normalized_text = _safe_text(text.strip())
    if not normalized_text:
        raise HTTPException(status_code=422, detail="Informe um texto para gerar o áudio.")

    if len(normalized_text) > settings.tts_max_text_length:
        raise HTTPException(
            status_code=422,
            detail=(
                f"O texto excede o limite de {settings.tts_max_text_length} caracteres "
                "para síntese de voz."
            ),
        )

    resolved_voice = (voice_name or settings.tts_default_voice).strip()

    if is_edge_voice(resolved_voice):
        return await synthesize_edge(text=normalized_text, voice_id=resolved_voice, speed=speed)

    resolved_voice = _resolve_voice_name(voice_name)
    return await asyncio.to_thread(
        _synthesize_speech_sync,
        normalized_text,
        resolved_voice,
        speaker_id,
        speed,
        volume,
    )


def _synthesize_speech_sync(
    text: str,
    voice_name: str,
    speaker_id: int | None,
    speed: float | None,
    volume: float | None,
) -> SynthesizedAudio:
    _prepare_directories()
    _cleanup_generated_audio_dir()

    voice = _get_or_load_voice(voice_name)
    file_name = f"{uuid.uuid4().hex}.wav"
    file_path = settings.generated_audio_dir / file_name

    effective_speed = speed or settings.tts_default_speed
    effective_volume = volume or 1.0
    syn_config = SynthesisConfig(
        speaker_id=speaker_id,
        length_scale=1 / effective_speed,
        volume=effective_volume,
    )

    try:
        with wave.open(str(file_path), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=syn_config)
    except Exception as exc:  # pragma: no cover - engine/runtime failure
        raise HTTPException(
            status_code=500,
            detail="Falha ao sintetizar o áudio com o Piper.",
        ) from exc

    with wave.open(str(file_path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()

    duration_seconds = round(frame_count / sample_rate, 2) if sample_rate else 0.0
    size_bytes = file_path.stat().st_size

    return SynthesizedAudio(
        text=text,
        voice=voice_name,
        audio_url=f"/generated-audio/{file_name}",
        sample_rate=sample_rate,
        duration_seconds=duration_seconds,
        size_bytes=size_bytes,
    )


def _get_or_load_voice(voice_name: str) -> PiperVoice:
    cached_voice = _voice_cache.get(voice_name)
    if cached_voice is not None:
        return cached_voice

    with _voice_cache_lock:
        cached_voice = _voice_cache.get(voice_name)
        if cached_voice is not None:
            return cached_voice

        _ensure_voice_files(voice_name)
        model_path, config_path = _get_voice_paths(voice_name)

        try:
            voice = PiperVoice.load(
                model_path=model_path,
                config_path=config_path,
                use_cuda=settings.tts_use_cuda,
                download_dir=settings.tts_voices_dir,
            )
        except Exception as exc:  # pragma: no cover - engine/runtime failure
            raise HTTPException(
                status_code=500,
                detail="Não foi possível carregar a voz configurada do Piper.",
            ) from exc

        _voice_cache[voice_name] = voice
        return voice


def _ensure_voice_files(voice_name: str) -> None:
    model_path, config_path = _get_voice_paths(voice_name)
    if model_path.exists() and config_path.exists():
        return

    try:
        download_voice(voice_name, settings.tts_voices_dir)
    except HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Não foi possível baixar a voz '{voice_name}' do Piper. "
                f"Servidor respondeu com status {exc.code}."
            ),
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Não foi possível baixar a voz '{voice_name}'. "
                "Verifique sua conexão com a internet para o primeiro download."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _get_voice_paths(voice_name: str) -> tuple[Path, Path]:
    return (
        settings.tts_voices_dir / f"{voice_name}.onnx",
        settings.tts_voices_dir / f"{voice_name}.onnx.json",
    )


def _resolve_voice_name(voice_name: str | None) -> str:
    resolved_voice = (voice_name or settings.tts_default_voice).strip()
    if not resolved_voice:
        raise HTTPException(status_code=422, detail="Nenhuma voz foi informada para o TTS.")

    if not _is_valid_voice_name(resolved_voice):
        raise HTTPException(status_code=422, detail="Nome de voz inválido para o Piper.")

    return resolved_voice


def _list_downloaded_voice_names() -> list[str]:
    if not settings.tts_voices_dir.exists():
        return []

    return sorted(
        voice_file.stem
        for voice_file in settings.tts_voices_dir.glob("*.onnx")
        if (settings.tts_voices_dir / f"{voice_file.stem}.onnx.json").exists()
    )


def _build_voice_label(voice_name: str) -> str:
    metadata = VOICE_METADATA.get(voice_name)
    if metadata is not None:
        return f"{metadata['label']} ({metadata['locale']}, {metadata['quality']})"

    parts = voice_name.split("-")
    speaker = parts[1].replace("_", " ").title() if len(parts) > 1 else voice_name
    return f"{speaker} ({_get_voice_locale(voice_name)}, {_get_voice_quality(voice_name)})"


def _get_voice_locale(voice_name: str) -> str:
    metadata = VOICE_METADATA.get(voice_name)
    if metadata is not None:
        return metadata["locale"]

    return voice_name.split("-")[0].replace("_", "-")


def _get_voice_quality(voice_name: str) -> str:
    metadata = VOICE_METADATA.get(voice_name)
    if metadata is not None:
        return metadata["quality"]

    parts = voice_name.split("-")
    return parts[-1] if parts else "unknown"


def _is_valid_voice_name(voice_name: str) -> bool:
    return all(character.isalnum() or character in "._-" for character in voice_name)


def _prepare_directories() -> None:
    settings.tts_voices_dir.mkdir(parents=True, exist_ok=True)
    settings.generated_audio_dir.mkdir(parents=True, exist_ok=True)


def _cleanup_generated_audio_dir() -> None:
    ttl_minutes = settings.tts_audio_ttl_minutes
    if ttl_minutes <= 0 or not settings.generated_audio_dir.exists():
        return

    cutoff = time.time() - (ttl_minutes * 60)
    for audio_file in settings.generated_audio_dir.glob("*.wav"):
        try:
            if audio_file.stat().st_mtime < cutoff:
                audio_file.unlink(missing_ok=True)
        except OSError:
            continue

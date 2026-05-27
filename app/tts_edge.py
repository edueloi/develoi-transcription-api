from __future__ import annotations

import time
import uuid
from pathlib import Path

import edge_tts
from fastapi import HTTPException

from app.config import settings
from app.tts import SynthesizedAudio

# Vozes Edge TTS disponíveis — apenas pt-BR (pt-PT tem bugs conhecidos com edge-tts)
EDGE_VOICES: list[dict] = [
    {
        "id": "edge:pt-BR-FranciscaNeural",
        "label": "Francisca",
        "locale": "pt-BR",
        "quality": "neural",
        "gender": "feminino",
        "provider": "edge",
    },
    {
        "id": "edge:pt-BR-ThalitaNeural",
        "label": "Thalita",
        "locale": "pt-BR",
        "quality": "neural",
        "gender": "feminino",
        "provider": "edge",
    },
    {
        "id": "edge:pt-BR-AntonioNeural",
        "label": "Antonio",
        "locale": "pt-BR",
        "quality": "neural",
        "gender": "masculino",
        "provider": "edge",
    },
]

# Mapa id -> nome da voz Edge
_EDGE_ID_MAP = {v["id"]: v["id"].replace("edge:", "") for v in EDGE_VOICES}


def is_edge_voice(voice_id: str) -> bool:
    return voice_id.startswith("edge:")


def get_edge_voice_meta(voice_id: str) -> dict | None:
    return next((v for v in EDGE_VOICES if v["id"] == voice_id), None)


async def synthesize_edge(
    *,
    text: str,
    voice_id: str,
    speed: float | None = None,
) -> SynthesizedAudio:
    edge_voice_name = _EDGE_ID_MAP.get(voice_id)
    if not edge_voice_name:
        raise HTTPException(status_code=422, detail=f"Voz Edge inválida: {voice_id}")

    settings.generated_audio_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_old_audio()

    # Edge TTS aceita rate como "+0%" (normal), "+20%" (mais rápido), "-20%" (mais lento)
    rate = _speed_to_rate(speed or 1.0)

    file_name = f"{uuid.uuid4().hex}.mp3"
    file_path = settings.generated_audio_dir / file_name

    try:
        communicate = edge_tts.Communicate(text=text, voice=edge_voice_name, rate=rate)
        await communicate.save(str(file_path))
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao sintetizar com Edge TTS. Verifique sua conexão. ({exc})",
        ) from exc

    if not file_path.exists() or file_path.stat().st_size == 0:
        raise HTTPException(status_code=502, detail="Edge TTS retornou áudio vazio.")

    size_bytes = file_path.stat().st_size

    return SynthesizedAudio(
        text=text,
        voice=voice_id,
        audio_url=f"/generated-audio/{file_name}",
        sample_rate=24000,
        duration_seconds=0.0,
        size_bytes=size_bytes,
    )


def _speed_to_rate(speed: float) -> str:
    pct = round((speed - 1.0) * 100)
    if pct >= 0:
        return f"+{pct}%"
    return f"{pct}%"


def _cleanup_old_audio() -> None:
    ttl = settings.tts_audio_ttl_minutes
    if ttl <= 0 or not settings.generated_audio_dir.exists():
        return
    cutoff = time.time() - (ttl * 60)
    for f in settings.generated_audio_dir.glob("*.mp3"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
        except OSError:
            continue

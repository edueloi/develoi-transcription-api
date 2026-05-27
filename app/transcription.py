from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile
from faster_whisper import WhisperModel

from app.config import settings


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str


settings.temp_dir.mkdir(parents=True, exist_ok=True)

_model = WhisperModel(
    settings.whisper_model_size,
    compute_type=settings.whisper_compute_type,
)


def _build_temp_path(original_name: str | None) -> Path:
    suffix = Path(original_name or "").suffix.lower()
    if not suffix:
        suffix = ".bin"
    return settings.temp_dir / f"{uuid.uuid4()}{suffix}"


async def _save_upload_file(upload_file: UploadFile, destination: Path) -> None:
    bytes_written = 0

    with destination.open("wb") as buffer:
        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break

            bytes_written += len(chunk)
            if bytes_written > settings.max_upload_size_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"Arquivo maior que o limite de "
                        f"{settings.max_upload_size_mb} MB."
                    ),
                )

            buffer.write(chunk)


def transcribe_path(audio_path: Path) -> TranscriptionResult:
    segments, info = _model.transcribe(str(audio_path))
    text = " ".join(segment.text.strip() for segment in segments if segment.text).strip()

    return TranscriptionResult(
        text=text,
        language=info.language or "",
    )


async def transcribe_upload_file(upload_file: UploadFile) -> TranscriptionResult:
    temp_path = _build_temp_path(upload_file.filename)

    try:
        await _save_upload_file(upload_file, temp_path)
        return transcribe_path(temp_path)
    finally:
        await upload_file.close()
        if temp_path.exists():
            temp_path.unlink()

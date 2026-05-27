from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    text: str
    language: str


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = Field(...)
    content: str = Field(..., min_length=1)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str | None = None
    system: str | None = None
    temperature: float | None = Field(default=0.2, ge=0, le=2)
    keep_alive: str | None = None
    format: str | dict[str, Any] | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    model: str | None = None
    temperature: float | None = Field(default=0.2, ge=0, le=2)
    keep_alive: str | None = None
    format: str | dict[str, Any] | None = None


class SpeechSynthesisRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str | None = None
    speaker_id: int | None = Field(default=None, ge=0)
    speed: float | None = Field(default=1.0, ge=0.5, le=2)
    volume: float | None = Field(default=1.0, gt=0, le=2)


class ChatAndSpeakRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    model: str | None = None
    temperature: float | None = Field(default=0.2, ge=0, le=2)
    keep_alive: str | None = None
    format: str | dict[str, Any] | None = None
    voice: str | None = None
    speaker_id: int | None = Field(default=None, ge=0)
    speed: float | None = Field(default=1.0, ge=0.5, le=2)
    volume: float | None = Field(default=1.0, gt=0, le=2)


class GenerationResponse(BaseModel):
    model: str
    content: str
    done: bool
    done_reason: str | None = None
    total_duration: int | None = None
    load_duration: int | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None


class SpeechSynthesisResponse(BaseModel):
    text: str
    voice: str
    audio_url: str
    audio_format: str = "audio/wav"
    sample_rate: int
    duration_seconds: float
    size_bytes: int


class ChatAndSpeakResponse(BaseModel):
    generation: GenerationResponse
    speech: SpeechSynthesisResponse


class ModelInfo(BaseModel):
    name: str
    model: str
    size: int
    modified_at: str | None = None
    family: str | None = None
    parameter_size: str | None = None
    quantization_level: str | None = None


class ModelsResponse(BaseModel):
    models: list[ModelInfo]


class OllamaHealthResponse(BaseModel):
    status: str
    base_url: str
    model_count: int


class TTSHealthResponse(BaseModel):
    status: str
    provider: str
    default_voice: str
    voices_dir: str
    generated_audio_dir: str
    voice_ready: bool
    loaded_voices: list[str]


class TTSVoiceInfo(BaseModel):
    id: str
    label: str
    locale: str
    quality: str
    downloaded: bool
    is_default: bool
    gender: str | None = None


class TTSVoicesResponse(BaseModel):
    voices: list[TTSVoiceInfo]


class TranscribeAndGenerateResponse(BaseModel):
    transcription: TranscriptionResponse
    generation: GenerationResponse

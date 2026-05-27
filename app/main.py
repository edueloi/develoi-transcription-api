from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.ollama import chat, generate_text, list_models
from app.search import build_search_context, should_search, web_search
from app.schemas import (
    ChatAndSpeakRequest,
    ChatAndSpeakResponse,
    ChatRequest,
    GenerationResponse,
    GenerateRequest,
    ModelsResponse,
    OllamaHealthResponse,
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
    TTSHealthResponse,
    TTSVoiceInfo,
    TTSVoicesResponse,
    TranscribeAndGenerateResponse,
    TranscriptionResponse,
)
from app.transcription import transcribe_upload_file
from app.tts import (
    SynthesizedAudio,
    get_loaded_voices,
    list_voice_options,
    synthesize_speech,
    voice_is_downloaded,
)

app = FastAPI(
    title="Develoi Local AI API",
    version="0.2.0",
    description=(
        "API própria com transcrição local via Faster-Whisper, "
        "IA local via Ollama e voz local via Piper."
    ),
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
settings.generated_audio_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount(
    "/generated-audio",
    StaticFiles(directory=settings.generated_audio_dir),
    name="generated-audio",
)

DEFAULT_TRANSCRIPT_INSTRUCTION = (
    "Analise a transcrição abaixo em português do Brasil. "
    "Entregue um resumo objetivo, pontos principais, riscos ou alertas "
    "observáveis no texto e próximos passos sugeridos."
)


def _speech_response(result: SynthesizedAudio) -> SpeechSynthesisResponse:
    return SpeechSynthesisResponse(
        text=result.text,
        voice=result.voice,
        audio_url=result.audio_url,
        sample_rate=result.sample_rate,
        duration_seconds=result.duration_seconds,
        size_bytes=result.size_bytes,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "whisper_model": settings.whisper_model_size,
        "ollama_default_model": settings.ollama_default_model,
        "tts_provider": settings.tts_provider,
        "tts_default_voice": settings.tts_default_voice,
    }


@app.get("/ai/health", response_model=OllamaHealthResponse)
async def ollama_health() -> OllamaHealthResponse:
    models = await list_models()
    return OllamaHealthResponse(
        status="ok",
        base_url=settings.ollama_base_url,
        model_count=len(models),
    )


@app.get("/tts/health", response_model=TTSHealthResponse)
async def tts_health() -> TTSHealthResponse:
    return TTSHealthResponse(
        status="ok",
        provider=settings.tts_provider,
        default_voice=settings.tts_default_voice,
        voices_dir=str(settings.tts_voices_dir),
        generated_audio_dir=str(settings.generated_audio_dir),
        voice_ready=voice_is_downloaded(settings.tts_default_voice),
        loaded_voices=get_loaded_voices(),
    )


@app.get("/tts/voices", response_model=TTSVoicesResponse)
async def tts_voices() -> TTSVoicesResponse:
    return TTSVoicesResponse(
        voices=[
            TTSVoiceInfo(
                id=voice.id,
                label=voice.label,
                locale=voice.locale,
                quality=voice.quality,
                downloaded=voice.downloaded,
                is_default=voice.is_default,
                gender=voice.gender,
            )
            for voice in list_voice_options()
        ]
    )


@app.get("/ai/models", response_model=ModelsResponse)
async def ai_models() -> ModelsResponse:
    return ModelsResponse(models=await list_models())


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(file: UploadFile = File(...)) -> TranscriptionResponse:
    result = await transcribe_upload_file(file)
    return TranscriptionResponse(
        text=result.text,
        language=result.language,
    )


@app.post("/tts/synthesize", response_model=SpeechSynthesisResponse)
async def tts_synthesize(request: SpeechSynthesisRequest) -> SpeechSynthesisResponse:
    result = await synthesize_speech(
        text=request.text,
        voice_name=request.voice,
        speaker_id=request.speaker_id,
        speed=request.speed,
        volume=request.volume,
    )
    return _speech_response(result)


@app.post("/ai/generate", response_model=GenerationResponse)
async def ai_generate(request: GenerateRequest) -> GenerationResponse:
    return await generate_text(
        prompt=request.prompt,
        model=request.model,
        system=request.system,
        temperature=request.temperature,
        keep_alive=request.keep_alive,
        response_format=request.format,
    )


@app.post("/ai/chat", response_model=GenerationResponse)
async def ai_chat(request: ChatRequest) -> GenerationResponse:
    from app.schemas import ChatMessage as CM
    messages = list(request.messages)

    last_user = next((m for m in reversed(messages) if m.role == "user"), None)
    if last_user and settings.search_enabled and should_search(last_user.content):
        search_result = await web_search(last_user.content)
        if search_result:
            context = build_search_context(last_user.content, search_result)
            enriched = CM(role="user", content=f"{context}\n\nPergunta: {last_user.content}")
            messages = [enriched if m is last_user else m for m in messages]

    return await chat(
        messages=messages,
        model=request.model,
        temperature=request.temperature,
        keep_alive=request.keep_alive,
        response_format=request.format,
    )


@app.post("/ai/chat-and-speak", response_model=ChatAndSpeakResponse)
async def ai_chat_and_speak(request: ChatAndSpeakRequest) -> ChatAndSpeakResponse:
    generation = await chat(
        messages=request.messages,
        model=request.model,
        temperature=request.temperature,
        keep_alive=request.keep_alive,
        response_format=request.format,
    )

    content = generation.content.strip()
    if not content:
        raise HTTPException(
            status_code=502,
            detail="O modelo retornou uma resposta vazia para a síntese de voz.",
        )

    speech = await synthesize_speech(
        text=content,
        voice_name=request.voice,
        speaker_id=request.speaker_id,
        speed=request.speed,
        volume=request.volume,
    )

    return ChatAndSpeakResponse(
        generation=generation,
        speech=_speech_response(speech),
    )


@app.post("/ai/transcribe-and-generate", response_model=TranscribeAndGenerateResponse)
async def ai_transcribe_and_generate(
    file: UploadFile = File(...),
    instruction: str = Form(DEFAULT_TRANSCRIPT_INSTRUCTION),
    model: str | None = Form(default=None),
    system: str | None = Form(default=None),
    temperature: float = Form(default=0.2),
) -> TranscribeAndGenerateResponse:
    transcription = await transcribe_upload_file(file)

    generation = await generate_text(
        prompt=(
            f"{instruction.strip()}\n\n"
            f"Transcrição:\n{transcription.text}"
        ),
        model=model,
        system=system,
        temperature=temperature,
        keep_alive=None,
        response_format=None,
    )

    return TranscribeAndGenerateResponse(
        transcription=TranscriptionResponse(
            text=transcription.text,
            language=transcription.language,
        ),
        generation=generation,
    )


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")

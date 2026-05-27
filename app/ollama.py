from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings
from app.schemas import ChatMessage, GenerationResponse, ModelInfo


def _build_options(temperature: float | None) -> dict[str, Any] | None:
    if temperature is None:
        return None
    return {"temperature": temperature}


async def _request(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timeout = httpx.Timeout(settings.ollama_timeout_seconds)

    try:
        async with httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=timeout,
        ) as client:
            response = await client.request(method, path, json=json)
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Ollama não está acessível. "
                f"Verifique se está rodando em {settings.ollama_base_url}."
            ),
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Ollama excedeu o tempo limite da requisição.",
        ) from exc

    if response.status_code >= 400:
        try:
            error_body = response.json()
        except ValueError:
            error_body = response.text

        raise HTTPException(
            status_code=502,
            detail={
                "message": "Ollama retornou erro.",
                "status_code": response.status_code,
                "body": error_body,
            },
        )

    return response.json()


def _normalize_generation_response(payload: dict[str, Any], content_key: str) -> GenerationResponse:
    return GenerationResponse(
        model=payload.get("model", ""),
        content=payload.get(content_key, "") or "",
        done=bool(payload.get("done", False)),
        done_reason=payload.get("done_reason"),
        total_duration=payload.get("total_duration"),
        load_duration=payload.get("load_duration"),
        prompt_eval_count=payload.get("prompt_eval_count"),
        eval_count=payload.get("eval_count"),
    )


async def list_models() -> list[ModelInfo]:
    payload = await _request("GET", "/api/tags")
    models: list[ModelInfo] = []

    for item in payload.get("models", []):
        details = item.get("details") or {}
        models.append(
            ModelInfo(
                name=item.get("name", ""),
                model=item.get("model", ""),
                size=item.get("size", 0),
                modified_at=item.get("modified_at"),
                family=details.get("family"),
                parameter_size=details.get("parameter_size"),
                quantization_level=details.get("quantization_level"),
            )
        )

    return models


async def generate_text(
    *,
    prompt: str,
    model: str | None,
    system: str | None,
    temperature: float | None,
    keep_alive: str | None,
    response_format: str | dict[str, Any] | None,
) -> GenerationResponse:
    payload: dict[str, Any] = {
        "model": model or settings.ollama_default_model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": keep_alive or settings.ollama_keep_alive,
    }
    options = _build_options(temperature)
    if options:
        payload["options"] = options
    if system:
        payload["system"] = system
    if response_format is not None:
        payload["format"] = response_format

    response = await _request("POST", "/api/generate", json=payload)
    return _normalize_generation_response(response, "response")


async def chat(
    *,
    messages: list[ChatMessage],
    model: str | None,
    temperature: float | None,
    keep_alive: str | None,
    response_format: str | dict[str, Any] | None,
) -> GenerationResponse:
    payload: dict[str, Any] = {
        "model": model or settings.ollama_default_model,
        "messages": [message.model_dump() for message in messages],
        "stream": False,
        "keep_alive": keep_alive or settings.ollama_keep_alive,
    }
    options = _build_options(temperature)
    if options:
        payload["options"] = options
    if response_format is not None:
        payload["format"] = response_format

    response = await _request("POST", "/api/chat", json=payload)
    response["message"] = response.get("message") or {}
    response["content"] = response["message"].get("content", "")
    return _normalize_generation_response(response, "content")

from __future__ import annotations

import httpx

from app.config import settings

_TAVILY_URL = "https://api.tavily.com/search"

_SEARCH_TRIGGERS = (
    "atual", "atualmente", "hoje", "agora", "recente", "último", "última",
    "2024", "2025", "2026", "notícia", "notícias", "preço", "cotação",
    "quem é", "quem foi", "aconteceu", "lançou", "lançamento", "novo",
    "nova", "eleição", "resultado", "placar", "clima", "temperatura",
    "quando", "qual é o", "qual é a",
)


def should_search(text: str) -> bool:
    if not settings.tavily_api_key:
        return False
    lower = text.lower()
    return any(trigger in lower for trigger in _SEARCH_TRIGGERS)


async def web_search(query: str, max_results: int = 4) -> str:
    if not settings.tavily_api_key:
        return ""

    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": True,
        "include_raw_content": False,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(_TAVILY_URL, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return ""

    parts: list[str] = []

    answer = data.get("answer", "").strip()
    if answer:
        parts.append(f"Resposta direta: {answer}")

    for result in data.get("results", [])[:max_results]:
        title = result.get("title", "").strip()
        content = result.get("content", "").strip()
        url = result.get("url", "").strip()
        if title and content:
            parts.append(f"- {title}: {content} ({url})")

    return "\n".join(parts)


def build_search_context(query: str, search_result: str) -> str:
    if not search_result:
        return ""
    return (
        f"[Contexto obtido via busca na web para: \"{query}\"]\n"
        f"{search_result}\n"
        f"[Fim do contexto de busca — use essas informações para responder com precisão]"
    )

"""LLM access through the backend (Groq). The LLM never touches the database directly."""
from __future__ import annotations

import json
import time
from typing import Any

from groq import AsyncGroq

from app.config import settings

_client: AsyncGroq | None = None
status: dict[str, Any] = {"ok": None, "error": None, "model": settings.groq_model, "checked_at": None}


class LLMUnavailable(RuntimeError):
    pass


def _get() -> AsyncGroq:
    global _client
    if not settings.llm_configured:
        raise LLMUnavailable("GROQ_API_KEY is not set in backend/.env")
    if _client is None:
        # Retries honour Groq's retry-after on rate limits (free tier: 8k tokens/minute).
        _client = AsyncGroq(api_key=settings.groq_api_key, max_retries=2, timeout=30.0)
    return _client


def _model_options(model: str) -> dict[str, Any]:
    """Reasoning models spend completion tokens on reasoning; keep it short and out of the reply."""
    if model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low"}
    if model.startswith("qwen/"):
        return {"reasoning_format": "hidden"}
    return {}


async def complete_json(system: str, user: str, max_tokens: int = 1400) -> dict[str, Any]:
    """Ask the model for a single JSON object. Raises LLMUnavailable on any failure."""
    try:
        response = await _get().chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=max_tokens,
            **_model_options(settings.groq_model),
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        status.update(ok=True, error=None, checked_at=time.time())
        return data
    except LLMUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        message = str(exc).splitlines()[0][:240] if str(exc) else exc.__class__.__name__
        status.update(ok=False, error=message, checked_at=time.time())
        raise LLMUnavailable(message) from exc


async def ping() -> dict[str, Any]:
    # models.retrieve() URL-encodes the "/" in ids like "openai/gpt-oss-120b" and gets a 404, so check the list.
    try:
        available = {m.id for m in (await _get().models.list()).data}
        if settings.groq_model in available:
            status.update(ok=True, error=None, checked_at=time.time())
        else:
            status.update(ok=False, checked_at=time.time(),
                          error=f"Model '{settings.groq_model}' is not available to this Groq key; set GROQ_MODEL in backend/.env")
    except Exception as exc:  # noqa: BLE001
        status.update(ok=False, error=str(exc).splitlines()[0][:240], checked_at=time.time())
    return dict(status)

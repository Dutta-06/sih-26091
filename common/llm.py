"""Optional language-model client for the reasoning periphery.

TDD Section 2: language models interpret and explain deterministic outputs but
never compute or alter them. Callers always build a deterministic template
first and pass it as ``fallback``; the model may only rephrase/expand it. On any
failure the fallback is returned together with ``source="deterministic_template"``
so the UI can show which path produced the text.
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

TextSource = Literal["llm", "deterministic_template"]


def explain(system: str, prompt: str, fallback: str) -> tuple[str, TextSource]:
    if settings.llm_provider == "none":
        return fallback, "deterministic_template"
    try:
        resp = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={"model": settings.ollama_model, "system": system, "prompt": prompt, "stream": False},
            timeout=settings.llm_timeout_seconds,
        )
        resp.raise_for_status()
        text = (resp.json().get("response") or "").strip()
        if not text:
            raise ValueError("empty LLM response")
        return text, "llm"
    except Exception as exc:  # degrade to the deterministic explanation, never to invented text
        logger.warning("LLM explanation unavailable (%s); using deterministic template", exc)
        return fallback, "deterministic_template"

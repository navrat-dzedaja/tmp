"""Local Ollama backend for digest summarization, via its HTTP API."""
from __future__ import annotations

import json
import logging

import httpx

from .base import LLMBackend
from .prompt import DIGEST_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class OllamaBackend(LLMBackend):
    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    def summarize(self, matches: list[dict]) -> str:
        prompt = f"Here is the match data as JSON:\n\n{json.dumps(matches, indent=2)}"
        try:
            resp = httpx.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": DIGEST_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
        except Exception:
            logger.exception("Ollama request failed (base_url=%s, model=%s)", self._base_url, self._model)
            raise

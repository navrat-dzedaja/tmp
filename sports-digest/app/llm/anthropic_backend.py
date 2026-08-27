"""Anthropic Claude backend for digest summarization."""
from __future__ import annotations

import json
import logging

import anthropic

from .base import LLMBackend
from .prompt import DIGEST_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class AnthropicBackend(LLMBackend):
    def __init__(self, api_key: str | None, model: str):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def summarize(self, matches: list[dict]) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1500,
            system=DIGEST_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Here is the match data as JSON:\n\n{json.dumps(matches, indent=2)}",
                }
            ],
        )
        text_parts = [block.text for block in response.content if block.type == "text"]
        return "\n".join(text_parts).strip()

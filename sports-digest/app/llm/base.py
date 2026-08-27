"""LLM backend interface - both providers implement this."""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMBackend(ABC):
    @abstractmethod
    def summarize(self, matches: list[dict]) -> str:
        """Turn a list of match-context dicts into a short digest text."""
        raise NotImplementedError

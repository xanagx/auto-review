from __future__ import annotations
from abc import ABC, abstractmethod


class ModelBackend(ABC):
    """Abstract interface for LLM backends."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        """Generates a text completion given system and user prompts."""
        pass

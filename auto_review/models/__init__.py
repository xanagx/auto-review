from __future__ import annotations
import os
from typing import Optional
from auto_review.models.base import ModelBackend
from auto_review.models.gemini import GeminiBackend
from auto_review.models.openai_compat import OpenAICompatBackend
from auto_review.models.anthropic_provider import AnthropicBackend
from auto_review.models.mock_backend import MockBackend


def get_model_backend(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> ModelBackend:
    """Factory to instantiate the appropriate LLM backend."""
    chosen_provider = (provider or os.environ.get("LLM_PROVIDER") or "gemini").lower()

    if chosen_provider == "gemini":
        return GeminiBackend(api_key=api_key, model=model_name or "gemini-2.5-flash")
    elif chosen_provider in ("openai", "openai-compat", "ollama", "vllm", "deepseek"):
        return OpenAICompatBackend(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
            model=model_name or "gpt-4o"
        )
    elif chosen_provider == "anthropic":
        return AnthropicBackend(api_key=api_key, model=model_name or "claude-3-5-sonnet-20241022")
    elif chosen_provider in ("mock", "dry-run", "test"):
        return MockBackend()
    else:
        raise ValueError(
            f"Unsupported LLM provider: '{chosen_provider}'. "
            "Supported providers: 'gemini', 'openai' (or 'ollama'/'vllm'), 'anthropic', 'mock'."
        )

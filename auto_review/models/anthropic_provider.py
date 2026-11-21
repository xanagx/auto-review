from __future__ import annotations
import os
import json
import urllib.request
import urllib.error
from auto_review.models.base import ModelBackend


class AnthropicBackend(ModelBackend):
    """Anthropic Claude model provider using messages API."""

    def __init__(self, api_key: str | None = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = os.environ.get("ANTHROPIC_MODEL", model)
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable or argument is required.")

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 4096,
            "temperature": temperature,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                contents = resp_json.get("content", [])
                texts = [c.get("text", "") for c in contents if c.get("type") == "text"]
                return "".join(texts)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic API request failed ({e.code}): {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"Anthropic connection error: {e}") from e

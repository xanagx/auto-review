from __future__ import annotations
import os
import json
import urllib.request
import urllib.error
from auto_review.models.base import ModelBackend


class OpenAICompatBackend(ModelBackend):
    """
    OpenAI-compatible model provider.
    Works with OpenAI, Ollama (http://localhost:11434/v1), vLLM, DeepSeek, LocalAI, etc.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o"
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "no-key")
        self.base_url = (os.environ.get("OPENAI_API_BASE") or os.environ.get("OPENAI_BASE_URL") or base_url).rstrip("/")
        self.model = os.environ.get("OPENAI_MODEL", model)

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                choices = resp_json.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI-compat API request failed ({e.code}): {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"OpenAI-compat connection error: {e}") from e

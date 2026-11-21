from __future__ import annotations
import os
import json
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Config:
    default_provider: str = "gemini"
    gemini_model: str = "gemini-2.5-flash"
    openai_model: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    min_confidence: int = 7
    enable_critic: bool = True
    p4port: Optional[str] = None
    p4client: Optional[str] = None
    p4user: Optional[str] = None
    swarm_url: Optional[str] = None

    @classmethod
    def load(cls, config_path: str = ".auto_review/config.json") -> Config:
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception:
                pass
        return cls()

    def save(self, config_path: str = ".auto_review/config.json"):
        os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

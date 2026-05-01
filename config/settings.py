"""Load settings from environment (.env via python-dotenv optional in Phase 0.1)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    llm_api_key: str
    llm_base_url: str


def load_settings() -> Settings:
    return Settings(
        database_url=_get(
            "ZHIWEITONG_DATABASE_URL",
            "sqlite+aiosqlite:///./var/zhiweitong.db",
        ),
        redis_url=_get("ZHIWEITONG_REDIS_URL", "redis://localhost:6379/0"),
        llm_api_key=_get("ZHIWEITONG_LLM_API_KEY", ""),
        llm_base_url=_get(
            "ZHIWEITONG_LLM_BASE_URL",
            "https://api.openai.com/v1",
        ),
    )

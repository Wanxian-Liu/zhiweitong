"""Load settings from process environment.

启动时从仓库根目录的 ``.env`` 注入变量（不覆盖已存在的环境变量），再读取配置。
清单与说明：``.env.example``、``docs/ops-runbook.md``。

测试套件默认设置 ``ZHIWEITONG_SKIP_DOTENV=1``（见 ``tests/conftest.py``），避免本机 ``.env`` 干扰断言。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_repo_dotenv() -> None:
    """Load ``<repo>/.env`` if present. Existing ``os.environ`` entries win (``override=False``)."""
    if os.environ.get("ZHIWEITONG_SKIP_DOTENV") == "1":
        return
    load_dotenv(REPO_ROOT / ".env", override=False)


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    llm_api_key: str
    llm_base_url: str


def load_settings() -> Settings:
    load_repo_dotenv()
    # 延迟导入，避免 ``config.settings`` 与 ``core`` 包初始化循环依赖
    from core.observability import configure_zhiweitong_logging

    configure_zhiweitong_logging()
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

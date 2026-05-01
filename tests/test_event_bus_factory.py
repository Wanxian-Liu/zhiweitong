"""create_event_bus 与 ZHIWEITONG_EVENT_BUS_BACKEND 环境变量。"""

from __future__ import annotations

import pytest

from config.settings import Settings
from core.event_bus import EventBus
from core.event_bus_factory import create_event_bus
from core.redis_event_bus import RedisEventBus


def _settings(**kwargs: str) -> Settings:
    return Settings(
        database_url=kwargs.get("database_url", "sqlite+aiosqlite:///./t.db"),
        redis_url=kwargs.get("redis_url", "redis://localhost:6379/0"),
        llm_api_key=kwargs.get("llm_api_key", ""),
        llm_base_url=kwargs.get("llm_base_url", "https://example.invalid"),
    )


def test_create_event_bus_defaults_to_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZHIWEITONG_EVENT_BUS_BACKEND", raising=False)
    bus = create_event_bus(_settings())
    assert isinstance(bus, EventBus)
    assert not isinstance(bus, RedisEventBus)


def test_create_event_bus_redis_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHIWEITONG_EVENT_BUS_BACKEND", "redis")
    bus = create_event_bus(_settings(redis_url="redis://127.0.0.1:6379/1"))
    assert isinstance(bus, RedisEventBus)


def test_create_event_bus_redis_requires_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHIWEITONG_EVENT_BUS_BACKEND", "redis")
    with pytest.raises(ValueError, match="REDIS_URL"):
        create_event_bus(_settings(redis_url=""))


def test_create_event_bus_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHIWEITONG_EVENT_BUS_BACKEND", "kafka")
    with pytest.raises(ValueError, match="Unknown"):
        create_event_bus(_settings())

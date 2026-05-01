"""按配置构造内存总线或 Redis Pub/Sub 总线。"""

from __future__ import annotations

import os

from config.settings import Settings, load_settings

from core.event_bus import EventBus
from core.redis_event_bus import RedisEventBus

AnyEventBus = EventBus | RedisEventBus


def create_event_bus(settings: Settings | None = None) -> AnyEventBus:
    """返回事件总线实例。

    * ``ZHIWEITONG_EVENT_BUS_BACKEND=memory``（默认）：进程内 :class:`EventBus`。
    * ``ZHIWEITONG_EVENT_BUS_BACKEND=redis``：:class:`RedisEventBus`，需有效 ``redis_url``。

    频道名：``ZHIWEITONG_REDIS_BUS_CHANNEL``（默认 ``zhiweitong:events``）。
    """
    settings = settings or load_settings()
    backend = os.environ.get("ZHIWEITONG_EVENT_BUS_BACKEND", "memory").strip().lower()
    if backend == "redis":
        if not (settings.redis_url or "").strip():
            msg = "ZHIWEITONG_EVENT_BUS_BACKEND=redis requires a non-empty ZHIWEITONG_REDIS_URL"
            raise ValueError(msg)
        channel = os.environ.get("ZHIWEITONG_REDIS_BUS_CHANNEL", "zhiweitong:events").strip() or "zhiweitong:events"
        return RedisEventBus(settings.redis_url, channel=channel)
    if backend != "memory":
        msg = f"Unknown ZHIWEITONG_EVENT_BUS_BACKEND={backend!r}; use 'memory' or 'redis'"
        raise ValueError(msg)
    return EventBus()

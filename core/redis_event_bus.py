"""Redis Pub/Sub 版事件总线：与 :class:`core.event_bus.EventBus` 相同的 ``publish`` / ``subscribe`` / ``aclose`` 语义。

消息载荷为单频道 JSON：``{"t": "<topic>", "e": <event dict>}``；订阅侧用
:func:`core.event_bus.topic_matches` 做与内存总线一致的模式匹配（含前缀 ``*`` 与 fnmatch）。

多进程部署时，所有实例须使用相同的 ``redis_url`` 与 ``channel``。
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

from core.event_bus import EventCallback, topic_matches
from core.observability import zt_log_extra

logger = logging.getLogger(__name__)

RedisFactory = Callable[[str], Any]


class _Sub:
    __slots__ = ("subscription_id", "pattern", "callback")

    def __init__(self, subscription_id: str, pattern: str, callback: EventCallback) -> None:
        self.subscription_id = subscription_id
        self.pattern = pattern
        self.callback = callback


class RedisEventBus:
    """跨进程总线：发布到单一 Redis channel，本地按 ``topic_matches`` 分发。"""

    def __init__(
        self,
        redis_url: str,
        *,
        channel: str = "zhiweitong:events",
        redis_factory: RedisFactory | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._channel = channel
        self._factory: RedisFactory = redis_factory or self._default_factory
        self._subs: dict[str, _Sub] = {}
        self._closed = False
        self._redis_pub: Any = None
        self._redis_sub: Any = None
        self._reader_task: asyncio.Task[None] | None = None
        self._reader_lock = asyncio.Lock()

    @staticmethod
    def _default_factory(url: str) -> Any:
        import redis.asyncio as redis_mod

        return redis_mod.from_url(url, decode_responses=True)

    async def _ensure_pub(self) -> Any:
        if self._redis_pub is None:
            r = self._factory(self._redis_url)
            self._redis_pub = await r if inspect.isawaitable(r) else r
        return self._redis_pub

    async def _start_reader(self) -> None:
        async with self._reader_lock:
            if self._closed:
                return
            if self._reader_task is not None and not self._reader_task.done():
                return
            self._reader_task = asyncio.create_task(
                self._reader_loop(),
                name="zhiweitong-redis-bus-reader",
            )

    async def _reader_loop(self) -> None:
        pubsub: Any = None
        try:
            r = self._factory(self._redis_url)
            self._redis_sub = await r if inspect.isawaitable(r) else r
            pubsub = self._redis_sub.pubsub()
            await pubsub.subscribe(self._channel)
            logger.info(
                "redis_event_bus reader listening channel=%s",
                self._channel,
                extra=zt_log_extra(
                    component="redis_event_bus",
                    outcome="reader_started",
                    bus_channel=self._channel,
                ),
            )
            async for raw in pubsub.listen():
                if self._closed:
                    break
                if raw.get("type") != "message":
                    continue
                data = raw.get("data")
                if not isinstance(data, str):
                    continue
                try:
                    obj = json.loads(data)
                    topic = obj["t"]
                    event = obj["e"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    logger.warning(
                        "redis bus invalid payload on channel=%s",
                        self._channel,
                        extra=zt_log_extra(
                            component="redis_event_bus",
                            outcome="payload_invalid",
                            bus_channel=self._channel,
                        ),
                    )
                    continue
                for sub in list(self._subs.values()):
                    if not topic_matches(sub.pattern, topic):
                        continue
                    t_cb = time.perf_counter()
                    try:
                        await sub.callback(topic, event)
                    except Exception:
                        dt_cb = (time.perf_counter() - t_cb) * 1000.0
                        _cid = event.get("correlation_id") if isinstance(event, dict) else None
                        logger.exception(
                            "subscriber failed topic=%s pattern=%s sub_id=%s duration_ms=%.1f",
                            topic,
                            sub.pattern,
                            sub.subscription_id,
                            dt_cb,
                            extra=zt_log_extra(
                                component="redis_event_bus",
                                outcome="subscriber_failed",
                                duration_ms=dt_cb,
                                bus_channel=self._channel,
                                subscription_id=sub.subscription_id,
                                topic=topic,
                                correlation_id=str(_cid) if _cid is not None else None,
                            ),
                        )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "redis bus reader terminated with error",
                extra=zt_log_extra(
                    component="redis_event_bus",
                    outcome="reader_stopped_error",
                    bus_channel=self._channel,
                ),
            )
        finally:
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe(self._channel)
                except Exception:
                    logger.debug("pubsub unsubscribe failed", exc_info=True)
                try:
                    close = getattr(pubsub, "aclose", None) or getattr(pubsub, "close", None)
                    if close is not None:
                        res = close()
                        if inspect.isawaitable(res):
                            await res
                except Exception:
                    logger.debug("pubsub close failed", exc_info=True)
            if self._redis_sub is not None:
                try:
                    await self._redis_sub.aclose()
                except Exception:
                    logger.debug("redis sub client aclose failed", exc_info=True)
                self._redis_sub = None

    async def publish(self, topic: str, event: dict[str, Any]) -> None:
        if self._closed:
            raise RuntimeError("EventBus is closed")
        r = await self._ensure_pub()
        payload = json.dumps({"t": topic, "e": dict(event)}, ensure_ascii=False, default=str)
        t0 = time.perf_counter()
        await r.publish(self._channel, payload)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        _cid = event.get("correlation_id")
        logger.debug(
            "redis_event_bus publish_ok channel=%s topic=%s duration_ms=%.1f",
            self._channel,
            topic,
            dt_ms,
            extra=zt_log_extra(
                component="redis_event_bus",
                outcome="publish_ok",
                duration_ms=dt_ms,
                bus_channel=self._channel,
                topic=topic,
                correlation_id=str(_cid) if _cid is not None else None,
            ),
        )

    async def subscribe(self, pattern: str, callback: EventCallback) -> str:
        if not inspect.iscoroutinefunction(callback):
            raise TypeError("callback must be an async function")
        if self._closed:
            raise RuntimeError("EventBus is closed")
        await self._start_reader()
        sid = str(uuid.uuid4())
        self._subs[sid] = _Sub(sid, pattern, callback)
        return sid

    def unsubscribe(self, subscription_id: str) -> bool:
        return self._subs.pop(subscription_id, None) is not None

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._subs.clear()
        if self._reader_task is not None and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        self._reader_task = None
        if self._redis_pub is not None:
            try:
                await self._redis_pub.aclose()
            except Exception:
                logger.debug("redis pub client aclose failed", exc_info=True)
            self._redis_pub = None

    async def __aenter__(self) -> RedisEventBus:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

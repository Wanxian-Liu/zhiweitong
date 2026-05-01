"""Async event bus: asyncio.Queue transport, wildcard subscribe, isolated subscriber errors.

跨进程部署时使用 :class:`core.redis_event_bus.RedisEventBus`（单频道 JSON + 本地 ``topic_matches``）；
由 :func:`core.event_bus_factory.create_event_bus` 按 ``ZHIWEITONG_EVENT_BUS_BACKEND`` 选择实现。
``publish`` / ``subscribe`` / ``unsubscribe`` / ``aclose`` 签名保持稳定。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from core.observability import zt_log_extra

logger = logging.getLogger(__name__)

EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


def topic_matches(pattern: str, topic: str) -> bool:
    """Return True if ``topic`` matches subscription ``pattern``.

    Rules:
    - Exact string match.
    - If ``pattern`` ends with a single trailing ``*`` (and no other ``*``),
      match ``topic.startswith(pattern[:-1])``.
    - If ``pattern == "*"``, match any topic.
    - Otherwise use :func:`fnmatch.fnmatch` for glob patterns (e.g. ``/a/*/b``).
    """
    if pattern == "*":
        return True
    if "*" not in pattern:
        return topic == pattern
    if pattern.endswith("*") and pattern.count("*") == 1:
        prefix = pattern[:-1]
        return topic.startswith(prefix)
    import fnmatch

    return fnmatch.fnmatch(topic, pattern)


class _Subscription:
    __slots__ = ("subscription_id", "pattern", "callback")

    def __init__(
        self,
        subscription_id: str,
        pattern: str,
        callback: EventCallback,
    ) -> None:
        self.subscription_id = subscription_id
        self.pattern = pattern
        self.callback = callback


class EventBus:
    """In-process async event bus backed by :class:`asyncio.Queue`.

    A background task dispatches messages. The task is started on the first
    :meth:`publish` or :meth:`subscribe` call inside a running event loop
    (``__init__`` cannot always attach to a loop in sync code).
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()
        self._subs: dict[str, _Subscription] = {}
        self._closed = False
        self._dispatch_task: asyncio.Task[None] | None = None

    def _start_dispatch_loop(self) -> None:
        if self._closed:
            raise RuntimeError("EventBus is closed")
        if self._dispatch_task is not None and not self._dispatch_task.done():
            return
        self._dispatch_task = asyncio.create_task(
            self._dispatch_loop(),
            name="zhiweitong-event-bus-dispatch",
        )

    async def _ensure_started(self) -> None:
        self._start_dispatch_loop()

    async def publish(self, topic: str, event: dict[str, Any]) -> None:
        """Enqueue one event for ``topic``; subscribers are invoked asynchronously."""
        if self._closed:
            raise RuntimeError("EventBus is closed")
        await self._ensure_started()
        await self._queue.put((topic, dict(event)))

    async def subscribe(self, pattern: str, callback: EventCallback) -> str:
        """Register an async callback for topics matching ``pattern``.

        Returns a ``subscription_id`` for :meth:`unsubscribe`.
        """
        if not inspect.iscoroutinefunction(callback):
            raise TypeError("callback must be an async function")
        if self._closed:
            raise RuntimeError("EventBus is closed")
        await self._ensure_started()
        sid = str(uuid.uuid4())
        self._subs[sid] = _Subscription(sid, pattern, callback)
        return sid

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove subscription; return False if id was unknown."""
        return self._subs.pop(subscription_id, None) is not None

    async def aclose(self) -> None:
        """Stop dispatch loop; safe to call multiple times."""
        if self._closed:
            return
        self._closed = True
        if self._dispatch_task is not None and not self._dispatch_task.done():
            await self._queue.put(None)
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        self._dispatch_task = None
        self._subs.clear()

    async def _dispatch_loop(self) -> None:
        while True:
            item = await self._queue.get()
            if item is None:
                break
            topic, event = item
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
                            component="event_bus",
                            outcome="subscriber_failed",
                            duration_ms=dt_cb,
                            subscription_id=sub.subscription_id,
                            topic=topic,
                            correlation_id=str(_cid) if _cid is not None else None,
                        ),
                    )

    async def __aenter__(self) -> EventBus:
        await self._ensure_started()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

"""RedisEventBus：用注入的 fake Redis 验证发布/订阅与 topic_matches 一致。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import pytest

from core.observability import ZT_BUS_CHANNEL, ZT_CORRELATION_ID, ZT_OUTCOME, ZT_SUBSCRIPTION_ID, ZT_TOPIC
from core.redis_event_bus import RedisEventBus


class _FakePubSub:
    def __init__(self, queue: asyncio.Queue[dict[str, Any] | None]) -> None:
        self._q = queue

    async def subscribe(self, _ch: str) -> None:
        return None

    async def listen(self):
        while True:
            raw = await self._q.get()
            if raw is None:
                break
            yield raw

    async def unsubscribe(self, _ch: str) -> None:
        return None

    async def aclose(self) -> None:
        return None


class FakeAsyncRedis:
    """同一实例上 publish 入队、pubsub.listen 出队，模拟单进程 Redis Pub/Sub。"""

    def __init__(self) -> None:
        self._q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))
        await self._q.put({"type": "message", "data": message})

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self._q)

    async def aclose(self) -> None:
        return None

    async def inject_listener_message(self, raw: dict[str, Any]) -> None:
        """向 reader 的 pubsub 队列注入一条 ``listen()`` 消息（用于异常载荷测试）。"""
        await self._q.put(raw)


def test_redis_event_bus_publish_payload_shape() -> None:
    async def _run() -> None:
        fake = FakeAsyncRedis()
        bus = RedisEventBus("redis://unused", channel="t-ch", redis_factory=lambda _u: fake)
        await bus.publish("topic-a", {"k": 1})
        assert len(fake.published) == 1
        assert fake.published[0][0] == "t-ch"
        assert json.loads(fake.published[0][1]) == {"t": "topic-a", "e": {"k": 1}}
        await bus.aclose()

    asyncio.run(_run())


def test_redis_event_bus_reader_started_has_zt_outcome(caplog: pytest.LogCaptureFixture) -> None:
    async def _run() -> None:
        fake = FakeAsyncRedis()
        bus = RedisEventBus("redis://unused", channel="bus-zt", redis_factory=lambda _u: fake)

        async def _cb(_t: str, _e: dict[str, Any]) -> None:
            return None

        with caplog.at_level(logging.INFO, logger="core.redis_event_bus"):
            await bus.subscribe("/x*", _cb)
            await asyncio.sleep(0.06)
        await bus.aclose()

    asyncio.run(_run())
    started = [
        r
        for r in caplog.records
        if getattr(r, ZT_OUTCOME, None) == "reader_started"
        and getattr(r, ZT_BUS_CHANNEL, None) == "bus-zt"
    ]
    assert len(started) == 1


def test_redis_event_bus_publish_ok_debug_has_zt(caplog: pytest.LogCaptureFixture) -> None:
    async def _run() -> None:
        fake = FakeAsyncRedis()
        bus = RedisEventBus("redis://unused", channel="pub-ch", redis_factory=lambda _u: fake)
        with caplog.at_level(logging.DEBUG, logger="core.redis_event_bus"):
            await bus.publish(
                "topic-a",
                {"correlation_id": "c-redis-1", "k": 1},
            )
        await bus.aclose()

    asyncio.run(_run())
    ok_recs = [r for r in caplog.records if getattr(r, ZT_OUTCOME, None) == "publish_ok"]
    assert len(ok_recs) == 1
    assert getattr(ok_recs[0], ZT_TOPIC, None) == "topic-a"
    assert getattr(ok_recs[0], ZT_CORRELATION_ID, None) == "c-redis-1"


def test_redis_event_bus_payload_invalid_has_zt(caplog: pytest.LogCaptureFixture) -> None:
    async def _run() -> None:
        fake = FakeAsyncRedis()
        bus = RedisEventBus("redis://unused", channel="inv-ch", redis_factory=lambda _u: fake)

        async def _cb(_t: str, _e: dict[str, Any]) -> None:
            return None

        with caplog.at_level(logging.WARNING, logger="core.redis_event_bus"):
            await bus.subscribe("/*", _cb)
            await asyncio.sleep(0.05)
            await fake.inject_listener_message({"type": "message", "data": "not-json"})
            await asyncio.sleep(0.05)
        await bus.aclose()

    asyncio.run(_run())
    bad = [r for r in caplog.records if getattr(r, ZT_OUTCOME, None) == "payload_invalid"]
    assert len(bad) == 1
    assert getattr(bad[0], ZT_BUS_CHANNEL, None) == "inv-ch"


def test_redis_event_bus_subscriber_failed_has_zt(caplog: pytest.LogCaptureFixture) -> None:
    async def _run() -> None:
        fake = FakeAsyncRedis()
        bus = RedisEventBus("redis://unused", channel="fail-ch", redis_factory=lambda _u: fake)

        async def boom(_t: str, _e: dict[str, Any]) -> None:
            raise RuntimeError("cb boom")

        with caplog.at_level(logging.ERROR, logger="core.redis_event_bus"):
            await bus.subscribe("/智维通*", boom)
            await asyncio.sleep(0.05)
            await bus.publish(
                "/智维通/城市乳业/x",
                {"correlation_id": "c-fail", "ok": True},
            )
            await asyncio.sleep(0.08)
        await bus.aclose()

    asyncio.run(_run())
    fail_recs = [r for r in caplog.records if getattr(r, ZT_OUTCOME, None) == "subscriber_failed"]
    assert len(fail_recs) == 1
    assert getattr(fail_recs[0], ZT_TOPIC, None) == "/智维通/城市乳业/x"
    assert getattr(fail_recs[0], ZT_CORRELATION_ID, None) == "c-fail"
    assert getattr(fail_recs[0], ZT_SUBSCRIPTION_ID, None)


def test_redis_event_bus_prefix_subscription_delivers() -> None:
    async def _run() -> None:
        fake = FakeAsyncRedis()
        bus = RedisEventBus("redis://unused", channel="bus", redis_factory=lambda _u: fake)
        received: list[tuple[str, dict[str, Any]]] = []

        async def on_msg(topic: str, event: dict[str, Any]) -> None:
            received.append((topic, event))

        await bus.subscribe("/智维通/城市乳业*", on_msg)
        await asyncio.sleep(0.05)
        await bus.publish("/智维通/城市乳业/生产中心/排产/result", {"ok": True})
        for _ in range(100):
            if received:
                break
            await asyncio.sleep(0.01)
        assert len(received) == 1
        assert received[0][0] == "/智维通/城市乳业/生产中心/排产/result"
        assert received[0][1] == {"ok": True}
        await bus.aclose()

    asyncio.run(_run())


def test_redis_event_bus_unsubscribe_stops_delivery() -> None:
    async def _run() -> None:
        fake = FakeAsyncRedis()
        bus = RedisEventBus("redis://unused", channel="bus", redis_factory=lambda _u: fake)
        hits: list[str] = []

        async def on_msg(topic: str, _event: dict[str, Any]) -> None:
            hits.append(topic)

        sid = await bus.subscribe("exact-topic", on_msg)
        await asyncio.sleep(0.05)
        await bus.publish("exact-topic", {"a": 1})
        for _ in range(100):
            if hits:
                break
            await asyncio.sleep(0.01)
        assert hits == ["exact-topic"]

        assert bus.unsubscribe(sid) is True
        await bus.publish("exact-topic", {"a": 2})
        await asyncio.sleep(0.05)
        assert hits == ["exact-topic"]
        await bus.aclose()

    asyncio.run(_run())

"""Tests for core.event_bus."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from core.event_bus import EventBus, topic_matches


@pytest.mark.parametrize(
    ("pattern", "topic", "expected"),
    [
        ("/a/b", "/a/b", True),
        ("/a/b", "/a/c", False),
        ("/智维通/城市乳业/*", "/智维通/城市乳业/快消板块/command", True),
        ("/智维通/城市乳业/*", "/智维通/城市乳业", False),
        ("*", "/anything", True),
        ("/x/*/z", "/x/y/z", True),
        ("/x/*/z", "/x/y/w", False),
    ],
)
def test_topic_matches(pattern: str, topic: str, expected: bool) -> None:
    assert topic_matches(pattern, topic) is expected


def test_publish_delivers_exact_topic() -> None:
    async def _run() -> None:
        bus = EventBus()
        received: list[tuple[str, dict[str, Any]]] = []

        async def cb(t: str, e: dict[str, Any]) -> None:
            received.append((t, e))

        await bus.subscribe("/智维通/城市乳业/test/command", cb)
        await bus.publish("/智维通/城市乳业/test/command", {"k": 1})
        await asyncio.sleep(0.01)
        assert len(received) == 1
        assert received[0][0] == "/智维通/城市乳业/test/command"
        assert received[0][1] == {"k": 1}
        await bus.aclose()

    asyncio.run(_run())


def test_wildcard_prefix_subscription() -> None:
    async def _run() -> None:
        bus = EventBus()
        topics: list[str] = []

        async def cb(t: str, _e: dict[str, Any]) -> None:
            topics.append(t)

        await bus.subscribe("/智维通/城市乳业/*", cb)
        await bus.publish("/智维通/城市乳业/a/result", {})
        await bus.publish("/智维通/其他/result", {})
        await asyncio.sleep(0.01)
        assert topics == ["/智维通/城市乳业/a/result"]
        await bus.aclose()

    asyncio.run(_run())


def test_multiple_subscribers() -> None:
    async def _run() -> None:
        bus = EventBus()
        counts: list[int] = []

        async def cb1(_t: str, _e: dict[str, Any]) -> None:
            counts.append(1)

        async def cb2(_t: str, _e: dict[str, Any]) -> None:
            counts.append(2)

        await bus.subscribe("/t", cb1)
        await bus.subscribe("/t", cb2)
        await bus.publish("/t", {})
        await asyncio.sleep(0.01)
        assert sorted(counts) == [1, 2]
        await bus.aclose()

    asyncio.run(_run())


def test_subscriber_error_does_not_block_others() -> None:
    async def _run() -> None:
        bus = EventBus()
        ok: list[str] = []

        async def bad(_t: str, _e: dict[str, Any]) -> None:
            raise ValueError("boom")

        async def good(_t: str, _e: dict[str, Any]) -> None:
            ok.append("ok")

        await bus.subscribe("/e", bad)
        await bus.subscribe("/e", good)
        await bus.publish("/e", {})
        await asyncio.sleep(0.05)
        assert ok == ["ok"]
        await bus.aclose()

    asyncio.run(_run())


def test_unsubscribe() -> None:
    async def _run() -> None:
        bus = EventBus()
        hits: list[int] = []

        async def cb(_t: str, _e: dict[str, Any]) -> None:
            hits.append(1)

        sid = await bus.subscribe("/x", cb)
        assert bus.unsubscribe(sid) is True
        assert bus.unsubscribe(sid) is False
        await bus.publish("/x", {})
        await asyncio.sleep(0.01)
        assert hits == []
        await bus.aclose()

    asyncio.run(_run())


def test_publish_after_close_raises() -> None:
    async def _run() -> None:
        bus = EventBus()
        await bus.aclose()
        with pytest.raises(RuntimeError, match="closed"):
            await bus.publish("/t", {})

    asyncio.run(_run())


def test_subscribe_rejects_sync_callback() -> None:
    async def _run() -> None:
        bus = EventBus()

        def sync_cb(_t: str, _e: dict[str, Any]) -> None:
            pass

        with pytest.raises(TypeError, match="async"):
            await bus.subscribe("/t", sync_cb)  # type: ignore[arg-type]
        await bus.aclose()

    asyncio.run(_run())


def test_context_manager_closes() -> None:
    async def _run() -> None:
        async with EventBus() as bus:
            await bus.publish("/t", {})
        await bus.aclose()

    asyncio.run(_run())

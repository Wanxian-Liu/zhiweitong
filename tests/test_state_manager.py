"""Tests for core.state_manager."""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from core.state_manager import StateManager


def test_save_and_get_roundtrip() -> None:
    async def _run() -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            url = f"sqlite+aiosqlite:///{path}"
            sm = StateManager(database_url=url)
            await sm.init_schema()
            eid = "/智维通/城市乳业/快消板块/order_skill/ord-1"
            await sm.save_state(eid, {"qty": 3, "nested": {"a": 1}}, "order_skill")
            got = await sm.get_state(eid)
            assert got == {"qty": 3, "nested": {"a": 1}}
            await sm.aclose()
        finally:
            os.unlink(path)

    asyncio.run(_run())


def test_get_missing_returns_none() -> None:
    async def _run() -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            sm = StateManager(database_url=f"sqlite+aiosqlite:///{path}")
            await sm.init_schema()
            assert await sm.get_state("nope") is None
            await sm.aclose()
        finally:
            os.unlink(path)

    asyncio.run(_run())


def test_upsert_updates_audit_fields() -> None:
    async def _run() -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            sm = StateManager(database_url=f"sqlite+aiosqlite:///{path}")
            await sm.init_schema()
            eid = "/智维通/城市乳业/x/s1/i1"
            await sm.save_state(eid, {"v": 1}, "skill_a")
            await sm.save_state(eid, {"v": 2}, "skill_b")
            got = await sm.get_state(eid)
            assert got == {"v": 2}
            from sqlalchemy.ext.asyncio import AsyncSession
            from core.state_manager import StateRecord

            async with sm._session_factory() as session:  # noqa: SLF001
                assert isinstance(session, AsyncSession)
                r = await session.get(StateRecord, eid)
                assert r is not None
                assert r.skill_id == "skill_b"
                assert r.updated_at is not None
            await sm.aclose()
        finally:
            os.unlink(path)

    asyncio.run(_run())


def test_context_manager() -> None:
    async def _run() -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            url = f"sqlite+aiosqlite:///{path}"
            async with StateManager(database_url=url) as sm:
                await sm.save_state("e1", {}, "s")
                assert await sm.get_state("e1") == {}
        finally:
            os.unlink(path)

    asyncio.run(_run())

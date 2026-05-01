"""Tests for core.sandbox."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import patch

import pytest

from core.sandbox import CoverageError, SandboxReport, StubEventBus, StubStateManager, run_sandbox
from core.skill_base import SkillBase


def test_stub_state_roundtrip() -> None:
    async def _run() -> None:
        sm = StubStateManager()
        await sm.save_state("e1", {"a": 1}, "sk")
        assert await sm.get_state("e1") == {"a": 1}
        assert await sm.get_state("missing") is None
        await sm.aclose()

    asyncio.run(_run())


def test_stub_bus_records_and_dispatches() -> None:
    seen: list[tuple[str, dict]] = []

    async def _run() -> None:
        bus = StubEventBus()

        async def cb(topic: str, event: dict) -> None:
            seen.append((topic, event))

        await bus.subscribe("org_path/*", cb)
        await bus.publish("org_path/x/y", {"k": 1})
        assert bus.published == [("org_path/x/y", {"k": 1})]
        assert seen == [("org_path/x/y", {"k": 1})]
        await bus.aclose()

    asyncio.run(_run())


def test_run_sandbox_factory_high_coverage(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)

    async def _run() -> SandboxReport:
        def factory() -> SkillBase:
            from tests.fixtures.sandbox_ok_skill import OkSandboxSkill

            return OkSandboxSkill()

        with patch.object(SkillBase, "validate_skill", wraps=SkillBase.validate_skill) as m_val:
            rep = await run_sandbox(
                [{"q": 42}],
                skill_factory=factory,
                coverage_skill_module="tests.fixtures.sandbox_ok_skill",
            )
            m_val.assert_called()
        return rep

    report = asyncio.run(_run())
    assert report.passed == 1
    assert report.failed == 0
    assert report.cases[0].result == {"echo": 42}
    assert report.coverage_percent >= 90.0
    assert len(caplog.records) == 0


def test_run_sandbox_partial_coverage_raises() -> None:
    async def _run() -> None:
        def factory() -> SkillBase:
            from tests.fixtures.sandbox_partial_skill import PartialSandboxSkill

            return PartialSandboxSkill()

        with pytest.raises(CoverageError) as ei:
            await run_sandbox(
                [{}],
                skill_factory=factory,
                coverage_skill_module="tests.fixtures.sandbox_partial_skill",
                coverage_threshold=90.0,
            )
        assert ei.value.percent < 90.0
        assert ei.value.report.failed == 0

    asyncio.run(_run())


def test_run_sandbox_failure_case_count() -> None:
    async def _run() -> SandboxReport:
        def factory() -> SkillBase:
            from tests.fixtures.sandbox_boom_skill import BoomSandboxSkill

            return BoomSandboxSkill()

        return await run_sandbox(
            [{"a": 1}, {"b": 2}],
            skill_factory=factory,
            enforce_coverage=False,
        )

    report = asyncio.run(_run())
    assert report.passed == 0
    assert report.failed == 2


def test_attach_sandbox_sync_and_bus_publish() -> None:
    async def _run() -> SandboxReport:
        def factory() -> SkillBase:
            from tests.fixtures.sandbox_attach_skill import AttachSandboxSkill

            return AttachSandboxSkill()

        return await run_sandbox(
            [{"x": 1}],
            skill_factory=factory,
            coverage_skill_module="tests.fixtures.sandbox_attach_skill",
        )

    report = asyncio.run(_run())
    assert report.event_bus is not None
    assert report.event_bus.published == [("t1", {"x": 1})]
    assert report.state_manager is not None


def test_bad_return_type_fails_case() -> None:
    async def _run() -> SandboxReport:
        def factory() -> SkillBase:
            from tests.fixtures.sandbox_bad_return_skill import BadReturnSandboxSkill

            return BadReturnSandboxSkill()

        return await run_sandbox(
            [{}],
            skill_factory=factory,
            enforce_coverage=False,
        )

    report = asyncio.run(_run())
    assert report.failed == 1
    assert "TypeError" in (report.cases[0].error or "")


def test_xor_skill_arguments() -> None:
    async def _run() -> None:
        with pytest.raises(ValueError, match="exactly one"):
            await run_sandbox([], skill=None, skill_factory=None, enforce_coverage=False)

    asyncio.run(_run())


def test_premade_skill_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)

    async def _run() -> None:
        from tests.fixtures.sandbox_ok_skill import OkSandboxSkill

        skill = OkSandboxSkill()
        await run_sandbox(
            [{}],
            skill=skill,
            enforce_coverage=False,
        )

    asyncio.run(_run())
    assert any("prefer skill_factory" in r.message for r in caplog.records)

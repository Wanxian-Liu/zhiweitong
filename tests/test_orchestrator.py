"""Tests for core.orchestrator."""

from __future__ import annotations

import asyncio
import tempfile
from typing import Any

import pytest

from config.settings import Settings
from core.event_bus import EventBus
from core.orchestrator import GoalReport, Orchestrator, PlanStep, _extract_json_object, command_topic, result_topic
from core.org_tree import OrgTree
from core.skill_base import SkillBase, minimal_skill_meta
from core.skill_registry import SkillRegistry
from core.state_manager import StateManager
from shared.models import EventEnvelope
from shared.system_topics import EVOLUTION_REVIEW


@pytest.fixture
def tmp_db_url() -> str:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        p = f.name
    return f"sqlite+aiosqlite:///{p}"


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    SkillRegistry._reset_singleton_for_tests()
    yield
    SkillRegistry._reset_singleton_for_tests()


class LeafSkill(SkillBase):
    META = minimal_skill_meta(
        skill_id="leaf_qc",
        name="快消叶岗",
        org_path="/智维通/城市乳业/快消板块",
    )

    async def execute(self, event: dict) -> dict:
        return {"ok": True}


def test_topic_helpers() -> None:
    assert command_topic("/智维通/城市乳业/快消板块") == "/智维通/城市乳业/快消板块/command"
    assert result_topic("/智维通/城市乳业/快消板块") == "/智维通/城市乳业/快消板块/result"


def test_extract_json_fenced() -> None:
    raw = '```json\n{"steps":[]}\n```'
    assert _extract_json_object(raw) == {"steps": []}


def test_process_goal_with_plan_provider(tmp_db_url: str) -> None:
    async def _run() -> None:
        bus = EventBus()
        sm = StateManager(database_url=tmp_db_url)
        await sm.init_schema()
        reg = SkillRegistry()
        reg.register(LeafSkill())

        class DummyKS:
            async def store(
                self,
                tags: list[str],
                content: str,
                metadata: dict[str, Any],
                *,
                org_path: str | None = None,
            ) -> str:
                return "doc-1"

        tree = OrgTree()
        tree.load_many({"/智维通/城市乳业": {}, "/智维通/城市乳业/快消板块": {}})

        async def plan(_: str) -> list[PlanStep]:
            return [
                PlanStep(
                    skill_path="/智维通/城市乳业/快消板块",
                    action="ping",
                    params={"x": 1},
                ),
            ]

        async def cmd_worker(topic: str, event: dict[str, Any]) -> None:
            if not str(topic).endswith("/command"):
                return
            base = str(topic)[: -len("/command")]
            out = EventEnvelope(
                correlation_id=event["correlation_id"],
                org_path=event["org_path"],
                skill_id=event["skill_id"],
                payload={"ok": True, "summary": {"echo": event.get("payload", {}).get("action")}},
            )
            await bus.publish(f"{base}/result", out.model_dump())

        await bus.subscribe("/智维通/城市乳业*", cmd_worker)

        orch = Orchestrator(
            bus,
            sm,
            reg,
            DummyKS(),
            tree,
            settings=Settings(
                database_url=tmp_db_url,
                redis_url="",
                llm_api_key="",
                llm_base_url="https://example.invalid",
            ),
            plan_provider=plan,
            step_timeout=5.0,
        )
        try:
            report = await orch.process_goal("noop")
        finally:
            await bus.aclose()
            await sm.aclose()

        assert isinstance(report, GoalReport)
        assert report.ok
        assert len(report.steps) == 1
        assert report.steps[0].ok
        assert report.steps[0].summary.get("echo") == "ping"

    asyncio.run(_run())


def test_abort_on_failure_stops_later_steps(tmp_db_url: str) -> None:
    async def _run() -> None:
        bus = EventBus()
        sm = StateManager(database_url=tmp_db_url)
        await sm.init_schema()
        reg = SkillRegistry()

        class StrictLeaf(SkillBase):
            META = minimal_skill_meta(
                skill_id="strict_leaf",
                name="严格叶岗",
                org_path="/智维通/城市乳业/严格岗",
            )

            async def execute(self, event: dict) -> dict:
                return {"ok": True}

        StrictLeaf.META.compliance.forbidden_operations = ["abort_on_failure"]
        reg.register(StrictLeaf())
        reg.register(LeafSkill())

        class DummyKS:
            async def store(
                self,
                tags: list[str],
                content: str,
                metadata: dict[str, Any],
                *,
                org_path: str | None = None,
            ) -> str:
                return "doc-1"

        tree = OrgTree()
        tree.load_many(
            {
                "/智维通/城市乳业": {},
                "/智维通/城市乳业/严格岗": {},
                "/智维通/城市乳业/快消板块": {},
            },
        )

        async def plan(_: str) -> list[PlanStep]:
            return [
                PlanStep(skill_path="/智维通/城市乳业/严格岗", action="a", params={}),
                PlanStep(skill_path="/智维通/城市乳业/快消板块", action="b", params={}),
            ]

        async def cmd_worker(topic: str, event: dict[str, Any]) -> None:
            if not str(topic).endswith("/command"):
                return
            base = str(topic)[: -len("/command")]
            payload: dict[str, Any] = {"ok": True, "summary": {"n": 2}}
            if event.get("payload", {}).get("action") == "a":
                payload = {"ok": False, "error": "planned_fail", "summary": {}}
            out = EventEnvelope(
                correlation_id=event["correlation_id"],
                org_path=event["org_path"],
                skill_id=event["skill_id"],
                payload=payload,
            )
            await bus.publish(f"{base}/result", out.model_dump())

        await bus.subscribe("/智维通/城市乳业*", cmd_worker)

        orch = Orchestrator(
            bus,
            sm,
            reg,
            DummyKS(),
            tree,
            settings=Settings(
                database_url=tmp_db_url,
                redis_url="",
                llm_api_key="",
                llm_base_url="https://example.invalid",
            ),
            plan_provider=plan,
            step_timeout=5.0,
        )
        try:
            report = await orch.process_goal("multi")
        finally:
            await bus.aclose()
            await sm.aclose()

        assert not report.ok
        assert len(report.steps) == 1
        assert report.steps[0].action == "a"

    asyncio.run(_run())


def test_trigger_evolution_publishes_review(tmp_db_url: str) -> None:
    async def _run() -> None:
        bus = EventBus()
        sm = StateManager(database_url=tmp_db_url)
        await sm.init_schema()
        reg = SkillRegistry()
        reg.register(LeafSkill())

        stored: list[tuple[list[str], str]] = []

        class DummyKS:
            async def store(
                self,
                tags: list[str],
                content: str,
                metadata: dict[str, Any],
                *,
                org_path: str | None = None,
            ) -> str:
                stored.append((tags, content))
                return "ev-doc"

        tree = OrgTree()
        tree.load_many({"/智维通/城市乳业": {}, "/智维通/城市乳业/快消板块": {}})

        review_events: list[dict[str, Any]] = []

        async def on_rev(topic: str, event: dict[str, Any]) -> None:
            if topic == EVOLUTION_REVIEW:
                review_events.append(event)

        await bus.subscribe(EVOLUTION_REVIEW, on_rev)

        orch = Orchestrator(
            bus,
            sm,
            reg,
            DummyKS(),
            tree,
            settings=Settings(
                database_url=tmp_db_url,
                redis_url="",
                llm_api_key="",
                llm_base_url="https://example.invalid",
            ),
            plan_provider=lambda _: [],
        )
        try:
            doc_id = await orch.trigger_evolution("leaf_qc")
        finally:
            await bus.aclose()
            await sm.aclose()

        assert doc_id == "ev-doc"
        assert stored
        assert review_events
        assert review_events[0]["payload"]["knowledge_doc_id"] == "ev-doc"

    asyncio.run(_run())


def test_process_goal_requires_llm_key_without_provider(tmp_db_url: str) -> None:
    async def _run() -> None:
        bus = EventBus()
        sm = StateManager(database_url=tmp_db_url)
        await sm.init_schema()
        reg = SkillRegistry()
        reg.register(LeafSkill())

        class DummyKS:
            async def store(
                self,
                tags: list[str],
                content: str,
                metadata: dict[str, Any],
                *,
                org_path: str | None = None,
            ) -> str:
                return "x"

        tree = OrgTree()
        tree.load_many({"/智维通/城市乳业": {}, "/智维通/城市乳业/快消板块": {}})

        orch = Orchestrator(
            bus,
            sm,
            reg,
            DummyKS(),
            tree,
            settings=Settings(
                database_url=tmp_db_url,
                redis_url="",
                llm_api_key="",
                llm_base_url="https://example.invalid",
            ),
        )
        try:
            report = await orch.process_goal("x")
        finally:
            await bus.aclose()
            await sm.aclose()

        assert not report.ok
        assert report.planner_error

    asyncio.run(_run())

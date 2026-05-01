"""EvolutionEngine (Phase 3.2) — /system/errors → optimization review."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from core.event_bus import EventBus
from core.evolution import (
    AUDIT_SKILL_ORG_PATH,
    EvolutionEngine,
    EvolutionProposal,
    EvolutionThresholds,
    merge_execution_patch,
)
from core.skill_base import SkillBase, minimal_skill_meta
from core.skill_registry import SkillRegistry
from shared.models import EventEnvelope
from shared.system_topics import EVOLUTION_REVIEW, SYSTEM_ERRORS


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    SkillRegistry._reset_singleton_for_tests()
    yield
    SkillRegistry._reset_singleton_for_tests()


class _DummyKnowledgeStore:
    _n = 0

    async def store(
        self,
        tags: list[str],
        content: str,
        metadata: dict[str, Any],
        *,
        org_path: str | None = None,
    ) -> str:
        _ = (tags, content, metadata, org_path)
        _DummyKnowledgeStore._n += 1
        return f"doc-{_DummyKnowledgeStore._n}"


class LeafSkill(SkillBase):
    META = minimal_skill_meta(
        skill_id="leaf_qc",
        name="快消叶岗",
        org_path="/智维通/城市乳业/快消板块",
    )

    async def execute(self, event: dict) -> dict:
        return {"ok": True}


def test_merge_execution_patch_updates_decision_rule() -> None:
    meta = minimal_skill_meta(
        skill_id="x",
        name="n",
        org_path="/智维通/城市乳业/快消板块",
    )
    out = merge_execution_patch(meta, {"decision_rule": "new_rule"})
    assert out.execution.decision_rule == "new_rule"
    assert meta.execution.decision_rule != "new_rule"


def test_evolution_publishes_optimization_review_after_errors() -> None:
    async def _run() -> None:
        bus = EventBus()
        reg = SkillRegistry()
        reg.register(LeafSkill())
        reviews: list[dict[str, Any]] = []

        async def on_rev(topic: str, ev: dict[str, Any]) -> None:
            if topic == EVOLUTION_REVIEW:
                reviews.append(ev)

        await bus.subscribe(EVOLUTION_REVIEW, on_rev)
        eng = EvolutionEngine(
            bus=bus,
            knowledge=_DummyKnowledgeStore(),
            registry=reg,
            thresholds=EvolutionThresholds(min_errors_in_window=3, window_sec=60.0),
            review_cooldown_sec=1.0,
        )
        await eng.start()
        org = "/智维通/城市乳业/快消板块"
        for i in range(3):
            await bus.publish(
                SYSTEM_ERRORS,
                EventEnvelope(
                    correlation_id=f"c{i}",
                    org_path=org,
                    skill_id="leaf_qc",
                    payload={"error": "e", "latency_ms": 1.0},
                ).model_dump(),
            )
        for _ in range(80):
            await asyncio.sleep(0.02)
            if reviews:
                break
        assert len(reviews) == 1
        assert reviews[0]["payload"]["kind"] == "optimization_review"
        assert reviews[0]["payload"]["target_skill_id"] == "leaf_qc"
        assert reviews[0]["org_path"] == AUDIT_SKILL_ORG_PATH
        await eng.stop()
        await bus.aclose()

    asyncio.run(_run())


def test_evolution_skips_review_when_regression_fails() -> None:
    async def _run() -> None:
        bus = EventBus()
        reg = SkillRegistry()
        reg.register(LeafSkill())
        reviews: list[dict[str, Any]] = []

        async def on_rev(topic: str, ev: dict[str, Any]) -> None:
            if topic == EVOLUTION_REVIEW:
                reviews.append(ev)

        await bus.subscribe(EVOLUTION_REVIEW, on_rev)

        async def fail_regression(*_: Any, **__: Any):
            return False, None

        eng = EvolutionEngine(
            bus=bus,
            knowledge=_DummyKnowledgeStore(),
            registry=reg,
            thresholds=EvolutionThresholds(min_errors_in_window=2, window_sec=60.0),
            review_cooldown_sec=1.0,
            regression=fail_regression,
        )
        await eng.start()
        org = "/智维通/城市乳业/快消板块"
        for i in range(2):
            await bus.publish(
                SYSTEM_ERRORS,
                EventEnvelope(
                    correlation_id=f"f{i}",
                    org_path=org,
                    skill_id="leaf_qc",
                    payload={"error": "e"},
                ).model_dump(),
            )
        await asyncio.sleep(0.3)
        assert reviews == []
        await eng.stop()
        await bus.aclose()

    asyncio.run(_run())


def test_evolution_custom_optimizer_patch_in_review() -> None:
    class FixedOpt:
        async def propose(self, *, skill_id: str, org_path: str, error_events: list[dict[str, Any]]):
            _ = org_path
            return EvolutionProposal(
                rationale="custom",
                execution_patch={"token_budget": 999},
            )

    async def _run() -> None:
        bus = EventBus()
        reg = SkillRegistry()
        reg.register(LeafSkill())
        reviews: list[dict[str, Any]] = []

        async def on_rev(topic: str, ev: dict[str, Any]) -> None:
            if topic == EVOLUTION_REVIEW:
                reviews.append(ev)

        await bus.subscribe(EVOLUTION_REVIEW, on_rev)
        eng = EvolutionEngine(
            bus=bus,
            knowledge=_DummyKnowledgeStore(),
            registry=reg,
            optimizer=FixedOpt(),
            thresholds=EvolutionThresholds(min_errors_in_window=1, window_sec=60.0),
            review_cooldown_sec=1.0,
        )
        await eng.start()
        await bus.publish(
            SYSTEM_ERRORS,
            EventEnvelope(
                correlation_id="lat",
                org_path="/智维通/城市乳业/快消板块",
                skill_id="leaf_qc",
                payload={"error": "slow", "latency_ms": 99_999.0},
            ).model_dump(),
        )
        for _ in range(60):
            await asyncio.sleep(0.02)
            if reviews:
                break
        assert len(reviews) == 1
        assert reviews[0]["payload"]["proposed_execution_patch"]["token_budget"] == 999
        await eng.stop()
        await bus.aclose()

    asyncio.run(_run())

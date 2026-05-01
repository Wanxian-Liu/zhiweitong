"""SkillCommandGateway + EvolutionEngine 串联。"""

from __future__ import annotations

import asyncio
import tempfile

import pytest

from core.event_bus import EventBus
from core.evolution import AUDIT_SKILL_ORG_PATH, EvolutionEngine, EvolutionThresholds
from core.orchestrator import result_topic
from core.skill_base import SkillBase, minimal_skill_meta
from core.skill_command_gateway import SkillCommandGateway, resolve_skill_for_command_topic
from core.skill_registry import SkillRegistry
from core.state_manager import StateManager
from shared.models import EventEnvelope
from shared.system_topics import SYSTEM_ERRORS
from skills.general_office.audit_review import ORG_PATH as AUDIT_ORG
from skills.general_office.audit_review import AuditReviewSkill


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


def test_audit_org_path_matches_evolution_constant() -> None:
    assert AUDIT_ORG == AUDIT_SKILL_ORG_PATH


def test_resolve_skill_for_command_topic_exact() -> None:
    reg = SkillRegistry()
    reg.register(AuditReviewSkill())
    topic = f"{AUDIT_ORG}/command"
    s = resolve_skill_for_command_topic(reg, topic)
    assert s is not None
    assert s.meta.skill_id == "gov_audit_review"


class LeafSkill(SkillBase):
    META = minimal_skill_meta(
        skill_id="leaf_qc",
        name="快消叶岗",
        org_path="/智维通/城市乳业/快消板块",
    )

    async def execute(self, event: dict) -> dict:
        return {"ok": True}


class _DummyKnowledgeStore:
    _n = 0

    async def store(
        self,
        tags: list[str],
        content: str,
        metadata: dict,
        *,
        org_path: str | None = None,
    ) -> str:
        _ = (tags, content, metadata, org_path)
        _DummyKnowledgeStore._n += 1
        return f"doc-{_DummyKnowledgeStore._n}"


def test_gateway_runs_audit_after_evolution_command(tmp_db_url: str) -> None:
    async def _run() -> None:
        bus = EventBus()
        sm = StateManager(database_url=tmp_db_url)
        await sm.init_schema()
        reg = SkillRegistry()
        reg.register(LeafSkill())
        reg.register(AuditReviewSkill())

        results: list[dict] = []

        async def on_result(topic: str, ev: dict) -> None:
            if topic == result_topic(AUDIT_ORG):
                results.append(ev)

        await bus.subscribe(result_topic(AUDIT_ORG), on_result)

        gw = SkillCommandGateway(bus, reg, sm)
        await gw.start()

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
                    correlation_id=f"e{i}",
                    org_path=org,
                    skill_id="leaf_qc",
                    payload={"error": "fail", "latency_ms": 1.0},
                ).model_dump(),
            )

        for _ in range(100):
            await asyncio.sleep(0.02)
            if results:
                break

        assert len(results) == 1
        payload = results[0].get("payload") or {}
        assert payload.get("verdict") == "pending_human"
        assert payload.get("summary", {}).get("target_skill_id") == "leaf_qc"

        await eng.stop()
        await gw.stop()
        await bus.aclose()
        await sm.aclose()

    asyncio.run(_run())

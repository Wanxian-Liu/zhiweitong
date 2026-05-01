"""EvolutionPromotion — idempotent snapshot on /system/evolution/approved."""

from __future__ import annotations

import asyncio
import tempfile
from typing import Any

import pytest

from core.event_bus import EventBus
from core.evolution_promotion import EvolutionPromotion, _promotion_entity_id
from core.state_manager import StateManager
from shared.models import EventEnvelope
from shared.system_topics import EVOLUTION_APPROVED


@pytest.fixture
def tmp_db_url() -> str:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        p = f.name
    return f"sqlite+aiosqlite:///{p}"


class RecordingKnowledge:
    def __init__(self) -> None:
        self.stores: list[tuple[list[str], str, dict[str, Any], str | None]] = []

    async def store(
        self,
        tags: list[str],
        content: str,
        metadata: dict[str, Any],
        *,
        org_path: str | None = None,
    ) -> str:
        self.stores.append((tags, content, metadata, org_path))
        return f"promo-doc-{len(self.stores)}"


def test_promotion_entity_id_stable() -> None:
    a = _promotion_entity_id("s1", "k1", "c1")
    b = _promotion_entity_id("s1", "k1", "c1")
    c = _promotion_entity_id("s1", "k1", "c2")
    assert a == b
    assert a != c


def test_evolution_promotion_stores_once_idempotent(tmp_db_url: str) -> None:
    async def _run() -> None:
        bus = EventBus()
        sm = StateManager(database_url=tmp_db_url)
        await sm.init_schema()
        ks = RecordingKnowledge()
        prom = EvolutionPromotion(bus, ks, sm)
        await prom.start()

        ev = EventEnvelope(
            correlation_id="bus-1",
            org_path="/智维通/城市乳业/总经办/审计审核岗",
            skill_id="gov_audit_review",
            payload={
                "kind": "audit_decision",
                "decision": "approved",
                "audit_correlation_id": "audit-a",
                "target_skill_id": "leaf_qc",
                "knowledge_doc_id": "evo-case-1",
                "proposed_execution_patch": {"decision_rule": "v-next"},
                "proposed_meta_preview": {"org_path": "/智维通/城市乳业/快消板块", "skill_id": "leaf_qc"},
                "rationale": "test",
            },
        ).model_dump()

        await bus.publish(EVOLUTION_APPROVED, ev)
        await asyncio.sleep(0.15)
        assert len(ks.stores) == 1
        assert "leaf_qc" in ks.stores[0][0]
        assert ks.stores[0][3] == "/智维通/城市乳业/快消板块"

        ent = _promotion_entity_id("leaf_qc", "evo-case-1", "audit-a")
        row = await sm.get_state(ent)
        assert row is not None
        assert row.get("promoted") is True

        await bus.publish(EVOLUTION_APPROVED, ev)
        await asyncio.sleep(0.15)
        assert len(ks.stores) == 1

        await prom.stop()
        await bus.aclose()
        await sm.aclose()

    asyncio.run(_run())


def test_evolution_promotion_ignores_non_audit_payload(tmp_db_url: str) -> None:
    async def _run() -> None:
        bus = EventBus()
        sm = StateManager(database_url=tmp_db_url)
        await sm.init_schema()
        ks = RecordingKnowledge()
        prom = EvolutionPromotion(bus, ks, sm)
        await prom.start()

        await bus.publish(
            EVOLUTION_APPROVED,
            EventEnvelope(
                correlation_id="x",
                org_path="/智维通/城市乳业",
                skill_id="x",
                payload={"kind": "wrong"},
            ).model_dump(),
        )
        await asyncio.sleep(0.1)
        assert ks.stores == []

        await prom.stop()
        await bus.aclose()
        await sm.aclose()

    asyncio.run(_run())

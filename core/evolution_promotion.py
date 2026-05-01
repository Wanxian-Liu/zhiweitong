"""Subscribe to ``/system/evolution/approved`` and persist an idempotent promotion snapshot to Knowledge + State.

This is the minimal «metadata landing» step before codegen or registry overrides: operators
and future automation can read the knowledge doc and apply patches out-of-band.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any

from core.event_bus import EventBus
from core.observability import zt_log_extra
from core.orchestrator import KnowledgeStoreLike
from core.state_manager import StateManager
from shared.system_topics import EVOLUTION_APPROVED

logger = logging.getLogger(__name__)

_PROMOTION_SKILL_ID = "evolution_promotion"


def _promotion_entity_id(target_skill_id: str, knowledge_doc_id: str, audit_correlation_id: str) -> str:
    raw = f"{target_skill_id}\n{knowledge_doc_id}\n{audit_correlation_id}".encode("utf-8")
    h = hashlib.sha256(raw).hexdigest()
    return f"/system/evolution/promotion_applied/{h}"


class EvolutionPromotion:
    """Idempotent handler for approved evolution patches (knowledge snapshot + state marker)."""

    def __init__(
        self,
        bus: EventBus,
        knowledge: KnowledgeStoreLike,
        state: StateManager,
    ) -> None:
        self._bus = bus
        self._knowledge = knowledge
        self._state = state
        self._sub_id: str | None = None

    async def start(self) -> str:
        async def _cb(topic: str, event: dict[str, Any]) -> None:
            asyncio.create_task(self._handle_approved(event))

        self._sub_id = await self._bus.subscribe(EVOLUTION_APPROVED, _cb)
        logger.info("EvolutionPromotion subscribed %s id=%s", EVOLUTION_APPROVED, self._sub_id)
        return self._sub_id

    async def stop(self) -> None:
        if self._sub_id is not None:
            self._bus.unsubscribe(self._sub_id)
            self._sub_id = None

    async def _handle_approved(self, event: dict[str, Any]) -> None:
        pl = dict(event.get("payload") or {})
        if pl.get("kind") != "audit_decision" or pl.get("decision") != "approved":
            return

        kid = str(pl.get("knowledge_doc_id") or "").strip()
        aid = str(pl.get("audit_correlation_id") or "").strip()
        sid = str(pl.get("target_skill_id") or "").strip()
        if not kid or not aid or not sid:
            _bcid = event.get("correlation_id")
            logger.warning(
                "evolution_promotion skip: missing ids payload=%s",
                pl,
                extra=zt_log_extra(
                    component="evolution_promotion",
                    outcome="skip_missing_ids",
                    skill_id=sid or None,
                    correlation_id=str(_bcid) if _bcid is not None else None,
                ),
            )
            return

        entity = _promotion_entity_id(sid, kid, aid)
        if await self._state.get_state(entity) is not None:
            logger.info("evolution_promotion skip duplicate entity=%s", entity)
            return

        preview = pl.get("proposed_meta_preview")
        org_path = "/智维通/城市乳业"
        if isinstance(preview, dict) and preview.get("org_path"):
            org_path = str(preview["org_path"])

        snapshot = {
            "source": "evolution_promotion",
            "target_skill_id": sid,
            "knowledge_doc_id": kid,
            "audit_correlation_id": aid,
            "proposed_execution_patch": pl.get("proposed_execution_patch"),
            "proposed_meta_preview": preview,
            "rationale": pl.get("rationale"),
            "bus_correlation_id": event.get("correlation_id"),
        }
        body = json.dumps(snapshot, ensure_ascii=False, indent=2)
        doc_id = await self._knowledge.store(
            ["evolution", "promotion", "approved", sid],
            body,
            {
                "kind": "promoted_execution_patch",
                "target_skill_id": sid,
                "source_knowledge_doc_id": kid,
                "audit_correlation_id": aid,
            },
            org_path=org_path,
        )
        await self._state.save_state(
            entity,
            {
                "promoted": True,
                "promotion_knowledge_doc_id": doc_id,
                "snapshot": snapshot,
            },
            _PROMOTION_SKILL_ID,
        )
        logger.info(
            "evolution_promotion applied target=%s promotion_doc=%s entity=%s",
            sid,
            doc_id,
            entity,
        )

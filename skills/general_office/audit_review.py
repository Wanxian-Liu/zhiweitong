"""审计审核岗 — 处理进化优化审核单（人工可否决）。"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.orchestrator import result_topic
from core.skill_base import (
    SkillBase,
    SkillCompliance,
    SkillExecution,
    SkillInterface,
    SkillKnowledge,
    SkillMeta,
    json_schema,
)
from shared.models import EventEnvelope
from shared.system_topics import EVOLUTION_APPROVED, EVOLUTION_REJECTED

ORG_PATH = "/智维通/城市乳业/总经办/审计审核岗"
SKILL_ID = "gov_audit_review"


class AuditReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    verdict: str
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class AuditReviewSkill(SkillBase):
    """接收 ``optimization_review`` 指令；默认 ``verdict=pending_human``，可由 ``reviewer_decision`` 显式批准/否决。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="审计审核岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(AuditReviewInput),
            output_schema=json_schema(AuditReviewOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=["payload.action", "payload.params"],
            error_codes=["E_AUDIT_UNKNOWN_ACTION", "E_AUDIT_INVALID_REVIEW"],
        ),
        execution=SkillExecution(
            workflow_steps=["receive_review", "record_verdict", "publish_result"],
            decision_rule="if reviewer_decision absent then pending_human; else map approve|reject",
            token_budget=500,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["governance", "audit", "evolution"]),
    )

    def __init__(self, event_bus: Any | None = None, state_manager: Any | None = None) -> None:
        super().__init__()
        self._bus = event_bus
        self._state = state_manager

    def attach_sandbox(self, bus: Any, state_manager: Any) -> None:
        self._bus = bus
        self._state = state_manager

    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        if self._bus is None or self._state is None:
            raise RuntimeError("inject event_bus/state_manager or call attach_sandbox before execute")
        req = AuditReviewInput.model_validate(event)
        payload = dict(req.payload)
        action = str(payload.get("action") or "")
        params = dict(payload.get("params") or {})

        if action != "optimization_review":
            out = AuditReviewOutput(
                ok=False,
                verdict="error",
                error="E_AUDIT_UNKNOWN_ACTION",
                summary={"action": action},
            ).model_dump()
            await self._publish(req.correlation_id, out)
            return out

        review = dict(params.get("review") or {})
        if not review.get("kind"):
            out = AuditReviewOutput(
                ok=False,
                verdict="error",
                error="E_AUDIT_INVALID_REVIEW",
                summary={},
            ).model_dump()
            await self._publish(req.correlation_id, out)
            return out

        decision = params.get("reviewer_decision")
        if decision == "approve":
            verdict = "approved"
        elif decision == "reject":
            verdict = "rejected"
        else:
            verdict = "pending_human"

        target_skill_id = str(review.get("target_skill_id") or "")
        summary = {
            "verdict": verdict,
            "target_skill_id": target_skill_id,
            "knowledge_doc_id": review.get("knowledge_doc_id"),
            "proposed_execution_patch": review.get("proposed_execution_patch"),
        }
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(
            entity,
            {"audit": summary},
            self.meta.skill_id,
        )
        if verdict in ("approved", "rejected"):
            sys_topic = EVOLUTION_APPROVED if verdict == "approved" else EVOLUTION_REJECTED
            sys_payload: dict[str, Any] = {
                "kind": "audit_decision",
                "decision": verdict,
                "audit_correlation_id": req.correlation_id,
                "target_skill_id": target_skill_id,
                "knowledge_doc_id": review.get("knowledge_doc_id"),
                "proposed_execution_patch": review.get("proposed_execution_patch"),
                "proposed_meta_preview": review.get("proposed_meta_preview"),
                "rationale": review.get("rationale"),
            }
            sys_env = EventEnvelope(
                correlation_id=str(uuid.uuid4()),
                org_path=self.meta.org_path,
                skill_id=self.meta.skill_id,
                payload=sys_payload,
            )
            await self._bus.publish(sys_topic, sys_env.model_dump())
        out = AuditReviewOutput(ok=True, verdict=verdict, summary=summary).model_dump()
        await self._publish(req.correlation_id, out)
        return out

    async def _publish(self, correlation_id: str, skill_payload: dict[str, Any]) -> None:
        envelope = EventEnvelope(
            correlation_id=correlation_id,
            org_path=self.meta.org_path,
            skill_id=self.meta.skill_id,
            payload=skill_payload,
        )
        await self._bus.publish(result_topic(self.meta.org_path), envelope.model_dump())

"""批次放行 Skill — 生产中心（依赖质检结论的示意门闩）."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.command_payload import effective_skill_payload
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
from shared.integration_client import extra_headers_from_payload, merge_json_int_override
from shared.models import EventEnvelope
from shared.slice_l2 import l2_reconcile_block

ORG_PATH = "/智维通/城市乳业/生产中心/批次放行"
SKILL_ID = "prod_batch_release"
RULE_VERSION = "batch-release-gate-v1"


class BatchReleaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class BatchReleaseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    batch_id: str
    qc_cleared: bool
    release_committed: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class BatchReleaseSkill(SkillBase):
    """仅当 qc_cleared（质检已放行）为真时允许提交批次放行；否则阻断并提示人工。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="批次放行岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(BatchReleaseInput),
            output_schema=json_schema(BatchReleaseOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=[
                "payload.batch_id",
                "payload.qc_cleared",
                "payload.external_qc_cleared_url",
                "payload.external_request_headers",
            ],
            error_codes=["E_PROD_RELEASE_INVALID_PAYLOAD", "W_RELEASE_BLOCKED"],
        ),
        execution=SkillExecution(
            workflow_steps=["resolve_batch", "verify_qc_gate", "commit_release", "persist", "publish_result"],
            decision_rule="release_committed = qc_cleared",
            token_budget=1200,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["production", "release", "quality_gate"]),
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
        req = BatchReleaseInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        batch_id = str(payload.get("batch_id", "BATCH-DEFAULT"))
        qc_cleared = bool(payload.get("qc_cleared", False))
        fb = 1 if qc_cleared else 0
        ext_url = str(payload.get("external_qc_cleared_url") or "").strip()
        gate, l3_integration = await merge_json_int_override(
            ext_url,
            correlation_id=req.correlation_id,
            field="qc_cleared",
            fallback=fb,
            mode="mes_qc_gate_lookup",
            extra_headers=extra_headers_from_payload(payload),
        )
        qc_cleared = gate > 0
        release_committed = qc_cleared

        summary = {
            "rule_version": RULE_VERSION,
            "batch_id": batch_id,
            "qc_cleared": qc_cleared,
            "release_committed": release_committed,
            "l2_reconcile": l2_reconcile_block(
                "batch_release_snapshot",
                {"batch_id": batch_id},
                "release_committed",
                "放行 release_committed 须与质检结论 qc_cleared 一致；未放行不得进入下序或入库。",
            ),
            "exception_code": "W_RELEASE_BLOCKED" if not release_committed else None,
            "manual_handoff": (
                "质检未放行或结论缺失；补录检验结果或特采审批后再试。"
                if not release_committed
                else None
            ),
        }
        if l3_integration:
            summary["l3_integration"] = l3_integration
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(entity, summary, self.meta.skill_id)

        out = BatchReleaseOutput(
            ok=True,
            rule_version=RULE_VERSION,
            batch_id=batch_id,
            qc_cleared=qc_cleared,
            release_committed=release_committed,
            summary=summary,
        ).model_dump()
        envelope = EventEnvelope(
            correlation_id=req.correlation_id,
            org_path=self.meta.org_path,
            skill_id=self.meta.skill_id,
            payload=out,
        )
        await self._bus.publish(result_topic(self.meta.org_path), envelope.model_dump())
        return out

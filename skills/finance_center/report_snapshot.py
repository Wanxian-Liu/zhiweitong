"""报表快照 Skill — 财务中心（依赖试算结论的关账前示意门闩）."""

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

ORG_PATH = "/智维通/城市乳业/财务中心/报表快照"
SKILL_ID = "fin_report_snapshot"
RULE_VERSION = "fin-report-gate-v1"


class ReportSnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ReportSnapshotOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    period_id: str
    trial_cleared: bool
    report_publishable: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ReportSnapshotSkill(SkillBase):
    """仅当试算已平衡结论 trial_cleared 为真时允许生成可发布报表快照。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="报表快照岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(ReportSnapshotInput),
            output_schema=json_schema(ReportSnapshotOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=[
                "payload.period_id",
                "payload.trial_cleared",
                "payload.external_trial_cleared_url",
                "payload.external_request_headers",
            ],
            error_codes=["E_FIN_REPORT_INVALID_PAYLOAD", "W_FIN_REPORT_BLOCKED"],
        ),
        execution=SkillExecution(
            workflow_steps=["resolve_period", "verify_trial_gate", "snapshot_report", "persist", "publish_result"],
            decision_rule="report_publishable = trial_cleared",
            token_budget=2000,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["finance", "reporting", "closing"]),
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
        req = ReportSnapshotInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        period_id = str(payload.get("period_id", "PERIOD-DEFAULT"))
        trial_cleared = bool(payload.get("trial_cleared", False))
        fb = 1 if trial_cleared else 0
        ext_url = str(payload.get("external_trial_cleared_url") or "").strip()
        gate, l3_integration = await merge_json_int_override(
            ext_url,
            correlation_id=req.correlation_id,
            field="trial_cleared",
            fallback=fb,
            mode="fin_report_trial_gate_lookup",
            extra_headers=extra_headers_from_payload(payload),
        )
        trial_cleared = gate > 0
        report_publishable = trial_cleared

        summary = {
            "rule_version": RULE_VERSION,
            "period_id": period_id,
            "trial_cleared": trial_cleared,
            "report_publishable": report_publishable,
            "l2_reconcile": l2_reconcile_block(
                "report_snapshot_gate",
                {"period_id": period_id},
                "report_publishable",
                "报表可发布 report_publishable 须以试算通过 trial_cleared 为前提；同期间关账。",
            ),
            "exception_code": "W_FIN_REPORT_BLOCKED" if not report_publishable else None,
            "manual_handoff": (
                "试算未通过或结论未同步；完成试算平衡后再生成报表快照。"
                if not report_publishable
                else None
            ),
        }
        if l3_integration:
            summary["l3_integration"] = l3_integration
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(entity, summary, self.meta.skill_id)

        out = ReportSnapshotOutput(
            ok=True,
            rule_version=RULE_VERSION,
            period_id=period_id,
            trial_cleared=trial_cleared,
            report_publishable=report_publishable,
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

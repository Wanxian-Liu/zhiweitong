"""应收对账 Skill — 财务中心."""

from __future__ import annotations

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

ORG_PATH = "/智维通/城市乳业/财务中心/应收对账"
SKILL_ID = "fin_receivable_reconciliation"


class ReceivableReconciliationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ReceivableReconciliationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    receivable_total: float
    discrepancy_count: int
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ReceivableReconciliationSkill(SkillBase):
    """模拟应收汇总与差异计数；状态入 StateManager，结果经 EventBus 发布。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="应收对账岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(ReceivableReconciliationInput),
            output_schema=json_schema(ReceivableReconciliationOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=["payload.invoices", "payload.payments"],
            error_codes=["E_FIN_INVALID_PAYLOAD"],
        ),
        execution=SkillExecution(
            workflow_steps=["ingest_documents", "match_invoices", "compute_totals", "persist", "publish_result"],
            decision_rule="receivable_total = sum(invoices) - sum(payments); discrepancy_count = |invoices| mismatch heuristic",
            token_budget=2000,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["finance", "receivable", "reconciliation"]),
    )

    def __init__(self, event_bus: Any | None = None, state_manager: Any | None = None) -> None:
        super().__init__()
        self._bus = event_bus
        self._state = state_manager

    def attach_sandbox(self, bus: Any, state_manager: Any) -> None:
        """Inject stub bus/state for :func:`core.sandbox.run_sandbox`."""
        self._bus = bus
        self._state = state_manager

    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        if self._bus is None or self._state is None:
            raise RuntimeError("inject event_bus/state_manager or call attach_sandbox before execute")
        req = ReceivableReconciliationInput.model_validate(event)
        payload = dict(req.payload)
        invoices = payload.get("invoices")
        payments = payload.get("payments")
        inv_sum = float(sum(float(x) for x in invoices)) if isinstance(invoices, list) else 0.0
        pay_sum = float(sum(float(x) for x in payments)) if isinstance(payments, list) else 0.0
        receivable_total = round(inv_sum - pay_sum, 2)
        discrepancy_count = 0
        if isinstance(invoices, list) and isinstance(payments, list) and len(invoices) != len(payments):
            discrepancy_count = abs(len(invoices) - len(payments))

        summary = {
            "receivable_total": receivable_total,
            "discrepancy_count": discrepancy_count,
        }
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(
            entity,
            {"receivable_total": receivable_total, "discrepancy_count": discrepancy_count},
            self.meta.skill_id,
        )
        out = ReceivableReconciliationOutput(
            ok=True,
            receivable_total=receivable_total,
            discrepancy_count=discrepancy_count,
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

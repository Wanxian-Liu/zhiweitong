"""应付对账 Skill — 财务中心."""

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
from shared.integration_client import extra_headers_from_payload, merge_json_float_override
from shared.models import EventEnvelope
from shared.slice_l2 import l2_reconcile_block

ORG_PATH = "/智维通/城市乳业/财务中心/应付对账"
SKILL_ID = "fin_payable_reconciliation"
RULE_VERSION = "fin-ap-net-v1"


class PayableReconciliationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class PayableReconciliationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    payable_total: float
    discrepancy_count: int
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class PayableReconciliationSkill(SkillBase):
    """模拟应付（对供应商）未结余额与单据条数差异；状态入 StateManager，结果经 EventBus 发布。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="应付对账岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(PayableReconciliationInput),
            output_schema=json_schema(PayableReconciliationOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=[
                "payload.bills",
                "payload.payments",
                "payload.external_payable_total_url",
                "payload.external_request_headers",
            ],
            error_codes=["E_FIN_PAYABLE_INVALID_PAYLOAD", "W_FIN_AP_LINE_MISMATCH"],
        ),
        execution=SkillExecution(
            workflow_steps=["ingest_bills", "match_payments", "compute_payable", "persist", "publish_result"],
            decision_rule="payable_total = sum(bills) - sum(payments); discrepancy_count from |bills| vs |payments|",
            token_budget=2000,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["finance", "payable", "reconciliation", "ap"]),
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
        req = PayableReconciliationInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        bills = payload.get("bills")
        payments = payload.get("payments")
        bill_sum = float(sum(float(x) for x in bills)) if isinstance(bills, list) else 0.0
        pay_sum = float(sum(float(x) for x in payments)) if isinstance(payments, list) else 0.0
        payable_total = round(bill_sum - pay_sum, 2)
        ext_ap = str(payload.get("external_payable_total_url") or "").strip()
        payable_total, l3_integration = await merge_json_float_override(
            ext_ap,
            correlation_id=req.correlation_id,
            field="payable_total",
            fallback=payable_total,
            mode="fin_ap_net_lookup",
            extra_headers=extra_headers_from_payload(payload),
        )
        discrepancy_count = 0
        if isinstance(bills, list) and isinstance(payments, list) and len(bills) != len(payments):
            discrepancy_count = abs(len(bills) - len(payments))

        summary = {
            "rule_version": RULE_VERSION,
            "payable_total": payable_total,
            "discrepancy_count": discrepancy_count,
            "l2_reconcile": l2_reconcile_block(
                "ap_net_snapshot",
                {},
                "payable_total",
                "应付净额 = ∑应付单 − ∑付款；与总账/AP 子账同币种、同截点核对。",
            ),
            "exception_code": (
                "W_FIN_AP_LINE_MISMATCH" if discrepancy_count > 0 else None
            ),
            "manual_handoff": (
                "应付与付款笔数不一致或需逐笔匹配时人工复核。"
                if discrepancy_count > 0
                else None
            ),
        }
        if l3_integration:
            summary["l3_integration"] = l3_integration
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(
            entity,
            {"payable_total": payable_total, "discrepancy_count": discrepancy_count},
            self.meta.skill_id,
        )
        out = PayableReconciliationOutput(
            ok=True,
            rule_version=RULE_VERSION,
            payable_total=payable_total,
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

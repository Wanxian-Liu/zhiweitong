"""入库验收 Skill — 仓储物流."""

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
from shared.models import EventEnvelope
from shared.slice_l2 import l2_reconcile_block

ORG_PATH = "/智维通/城市乳业/仓储物流/入库验收"
SKILL_ID = "wh_inbound_receiving"
RULE_VERSION = "inbound-qty-match-v1"


class InboundReceivingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class InboundReceivingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    sku: str
    ordered_qty: int
    received_qty: int
    shortfall: int
    receipt_complete: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class InboundReceivingSkill(SkillBase):
    """模拟采购/调拨订单数量与实收数量比对，计算短缺与是否验收闭环。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="入库验收岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(InboundReceivingInput),
            output_schema=json_schema(InboundReceivingOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=["payload.sku", "payload.ordered_qty", "payload.received_qty"],
            error_codes=["E_WH_INBOUND_INVALID_PAYLOAD", "W_INBOUND_SHORTFALL"],
        ),
        execution=SkillExecution(
            workflow_steps=["resolve_asn", "count_received", "compare_ordered", "persist", "publish_result"],
            decision_rule="shortfall = max(0, ordered_qty - received_qty); receipt_complete when received_qty >= ordered_qty",
            token_budget=1200,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["warehouse", "inbound", "receiving", "logistics"]),
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
        req = InboundReceivingInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        sku = str(payload.get("sku", "SKU-DEFAULT"))
        ordered_qty = int(payload.get("ordered_qty", 0))
        received_qty = int(payload.get("received_qty", 0))
        shortfall = max(0, ordered_qty - received_qty)
        receipt_complete = received_qty >= ordered_qty

        summary = {
            "rule_version": RULE_VERSION,
            "sku": sku,
            "ordered_qty": ordered_qty,
            "received_qty": received_qty,
            "shortfall": shortfall,
            "receipt_complete": receipt_complete,
            "l2_reconcile": l2_reconcile_block(
                "warehouse_receipt_line",
                {"sku": sku},
                "received_qty",
                "实收 received_qty 与 ASN/采购单行 ordered_qty 核对；shortfall>0 需差异处理。",
            ),
            "exception_code": "W_INBOUND_SHORTFALL" if shortfall > 0 else None,
            "manual_handoff": (
                "实收少于订购；请清点差异、补单或更新 received_qty 后重试验收。"
                if shortfall > 0
                else None
            ),
        }
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(entity, summary, self.meta.skill_id)

        out = InboundReceivingOutput(
            ok=True,
            rule_version=RULE_VERSION,
            sku=sku,
            ordered_qty=ordered_qty,
            received_qty=received_qty,
            shortfall=shortfall,
            receipt_complete=receipt_complete,
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

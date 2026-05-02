"""出库拣货 Skill — 仓储物流."""

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

ORG_PATH = "/智维通/城市乳业/仓储物流/出库拣货"
SKILL_ID = "wh_outbound_picking"
RULE_VERSION = "outbound-pick-qty-v1"


class OutboundPickingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class OutboundPickingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    sku: str
    requested_qty: int
    picked_qty: int
    shortfall: int
    pick_complete: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class OutboundPickingSkill(SkillBase):
    """模拟出库单需求件数与实拣件数比对，计算未拣足与是否可封单。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="出库拣货岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(OutboundPickingInput),
            output_schema=json_schema(OutboundPickingOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=[
                "payload.sku",
                "payload.requested_qty",
                "payload.picked_qty",
                "payload.external_picked_qty_url",
                "payload.external_request_headers",
            ],
            error_codes=["E_WH_OUTBOUND_INVALID_PAYLOAD", "W_OUTBOUND_SHORTFALL"],
        ),
        execution=SkillExecution(
            workflow_steps=["resolve_wave", "locate_sku", "pick_confirm", "persist", "publish_result"],
            decision_rule="shortfall = max(0, requested_qty - picked_qty); pick_complete when picked_qty >= requested_qty",
            token_budget=1200,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["warehouse", "outbound", "picking", "logistics"]),
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
        req = OutboundPickingInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        sku = str(payload.get("sku", "SKU-DEFAULT"))
        requested_qty = int(payload.get("requested_qty", 0))
        picked_qty = int(payload.get("picked_qty", 0))
        ext_url = str(payload.get("external_picked_qty_url") or "").strip()
        picked_qty, l3_integration = await merge_json_int_override(
            ext_url,
            correlation_id=req.correlation_id,
            field="picked_qty",
            fallback=picked_qty,
            mode="wms_picked_qty_lookup",
            extra_headers=extra_headers_from_payload(payload),
        )
        shortfall = max(0, requested_qty - picked_qty)
        pick_complete = picked_qty >= requested_qty

        summary = {
            "rule_version": RULE_VERSION,
            "sku": sku,
            "requested_qty": requested_qty,
            "picked_qty": picked_qty,
            "shortfall": shortfall,
            "pick_complete": pick_complete,
            "l2_reconcile": l2_reconcile_block(
                "warehouse_pick_line",
                {"sku": sku},
                "picked_qty",
                "实拣 picked_qty 与出库单 requested_qty 核对；shortfall>0 时未完成拣货。",
            ),
            "exception_code": "W_OUTBOUND_SHORTFALL" if shortfall > 0 else None,
            "manual_handoff": (
                "拣货短少；补拣或调整出库单数量后重试。"
                if shortfall > 0
                else None
            ),
        }
        if l3_integration:
            summary["l3_integration"] = l3_integration
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(entity, summary, self.meta.skill_id)

        out = OutboundPickingOutput(
            ok=True,
            rule_version=RULE_VERSION,
            sku=sku,
            requested_qty=requested_qty,
            picked_qty=picked_qty,
            shortfall=shortfall,
            pick_complete=pick_complete,
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

"""库存管理 Skill — 仓储物流."""

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

ORG_PATH = "/智维通/城市乳业/仓储物流/库存管理"
SKILL_ID = "wh_inventory_management"
RULE_VERSION = "inv-threshold-v1"


class InventoryManagementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class InventoryManagementOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    sku: str
    quantity_on_hand: int
    reorder_suggested: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class InventoryManagementSkill(SkillBase):
    """模拟 SKU 现存量与是否触发补货建议。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="库存管理岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(InventoryManagementInput),
            output_schema=json_schema(InventoryManagementOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=[
                "payload.sku",
                "payload.quantity_on_hand",
                "payload.reorder_threshold",
                "payload.external_quantity_on_hand_url",
                "payload.external_request_headers",
            ],
            error_codes=["E_WH_INVALID_PAYLOAD", "I_REORDER_SUGGESTED"],
        ),
        execution=SkillExecution(
            workflow_steps=["resolve_sku", "read_levels", "apply_threshold", "persist_snapshot", "publish_result"],
            decision_rule="reorder_suggested when quantity_on_hand < reorder_threshold (default 100)",
            token_budget=1200,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["warehouse", "inventory", "logistics"]),
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
        req = InventoryManagementInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        sku = str(payload.get("sku", "SKU-MILK-1L"))
        qoh = int(payload.get("quantity_on_hand", 0))
        ext_url = str(payload.get("external_quantity_on_hand_url") or "").strip()
        qoh, l3_integration = await merge_json_int_override(
            ext_url,
            correlation_id=req.correlation_id,
            field="quantity_on_hand",
            fallback=qoh,
            mode="wms_quantity_on_hand_lookup",
            extra_headers=extra_headers_from_payload(payload),
        )
        threshold = int(payload.get("reorder_threshold", 100))
        reorder_suggested = qoh < threshold

        summary = {
            "rule_version": RULE_VERSION,
            "sku": sku,
            "quantity_on_hand": qoh,
            "reorder_suggested": reorder_suggested,
            "l2_reconcile": l2_reconcile_block(
                "sku_on_hand_snapshot",
                {"sku": sku, "reorder_threshold": threshold},
                "quantity_on_hand",
                "现存量与 WMS 台账同一 SKU、同一截点核对；低于 reorder_threshold 时给出补货提示。",
            ),
            "exception_code": "I_REORDER_SUGGESTED" if reorder_suggested else None,
            "manual_handoff": (
                "库存低于阈值，可按内部补货/请购流程处理（业务自定）。"
                if reorder_suggested
                else None
            ),
        }
        if l3_integration:
            summary["l3_integration"] = l3_integration
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(entity, summary, self.meta.skill_id)

        out = InventoryManagementOutput(
            ok=True,
            rule_version=RULE_VERSION,
            sku=sku,
            quantity_on_hand=qoh,
            reorder_suggested=reorder_suggested,
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

"""库内调拨 Skill — 仓储物流（可用量校验示意）."""

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

ORG_PATH = "/智维通/城市乳业/仓储物流/库内调拨"
SKILL_ID = "wh_stock_transfer"
RULE_VERSION = "transfer-qty-availability-v1"


class StockTransferInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class StockTransferOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    sku: str
    from_location: str
    to_location: str
    quantity: int
    available_at_source: int
    shortfall: int
    transfer_complete: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class StockTransferSkill(SkillBase):
    """调拨数量不得超过源库位可用量；短少时异常码与出库拣货语义一致方向。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="库内调拨岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(StockTransferInput),
            output_schema=json_schema(StockTransferOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=[
                "payload.sku",
                "payload.from_location",
                "payload.to_location",
                "payload.quantity",
                "payload.available_at_source",
                "payload.external_available_at_source_url",
                "payload.external_request_headers",
            ],
            error_codes=["E_WH_TRANSFER_INVALID_PAYLOAD", "W_TRANSFER_SHORTFALL"],
        ),
        execution=SkillExecution(
            workflow_steps=["resolve_locations", "check_availability", "commit_transfer", "persist", "publish_result"],
            decision_rule="shortfall = max(0, quantity - available_at_source); complete when shortfall == 0",
            token_budget=1200,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["warehouse", "transfer", "inventory", "logistics"]),
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
        req = StockTransferInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        sku = str(payload.get("sku", "SKU-DEFAULT"))
        from_location = str(payload.get("from_location", "BIN-SRC"))
        to_location = str(payload.get("to_location", "BIN-DST"))
        quantity = int(payload.get("quantity", 0))
        available_at_source = int(payload.get("available_at_source", 0))
        ext_url = str(payload.get("external_available_at_source_url") or "").strip()
        available_at_source, l3_integration = await merge_json_int_override(
            ext_url,
            correlation_id=req.correlation_id,
            field="available_at_source",
            fallback=available_at_source,
            mode="wms_available_at_source_lookup",
            extra_headers=extra_headers_from_payload(payload),
        )
        shortfall = max(0, quantity - available_at_source)
        transfer_complete = shortfall == 0

        summary = {
            "rule_version": RULE_VERSION,
            "sku": sku,
            "from_location": from_location,
            "to_location": to_location,
            "quantity": quantity,
            "available_at_source": available_at_source,
            "shortfall": shortfall,
            "transfer_complete": transfer_complete,
            "l2_reconcile": l2_reconcile_block(
                "transfer_commit_snapshot",
                {"sku": sku, "from_location": from_location, "to_location": to_location},
                "quantity",
                "调拨 quantity 与源库位 available_at_source 同 SKU、同截点核对；短少时不可封账。",
            ),
            "exception_code": "W_TRANSFER_SHORTFALL" if shortfall > 0 else None,
            "manual_handoff": (
                "源库位可用量不足；补货、改调拨量或释放锁定后再执行。"
                if shortfall > 0
                else None
            ),
        }
        if l3_integration:
            summary["l3_integration"] = l3_integration
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(entity, summary, self.meta.skill_id)

        out = StockTransferOutput(
            ok=True,
            rule_version=RULE_VERSION,
            sku=sku,
            from_location=from_location,
            to_location=to_location,
            quantity=quantity,
            available_at_source=available_at_source,
            shortfall=shortfall,
            transfer_complete=transfer_complete,
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

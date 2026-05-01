"""Order processing skill for quick consumption domain."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.event_bus import EventBus
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
from core.state_manager import StateManager
from shared.models import EventEnvelope

ORG_PATH = "/智维通/城市乳业/快消板块/订单处理"
SKILL_ID = "qc_order_processing"


class OrderProcessingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class OrderProcessingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    order_no: str
    order_volume: int
    status: str
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class OrderProcessingSkill(SkillBase):
    """Create a normalized order record and report summary."""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="快消订单处理岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(OrderProcessingInput),
            output_schema=json_schema(OrderProcessingOutput),
            required_input_fields=["correlation_id", "payload"],
            optional_input_fields=["payload.order_no", "payload.quantity"],
            error_codes=["E_ORDER_INVALID_PAYLOAD"],
        ),
        execution=SkillExecution(
            workflow_steps=["validate_input", "normalize_order", "persist_state", "publish_result"],
            decision_rule="If order_no missing, generate deterministic fallback from correlation_id.",
            token_budget=1500,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["quick_consumption", "order", "fulfillment"]),
    )

    def __init__(self, event_bus: EventBus, state_manager: StateManager) -> None:
        super().__init__()
        self._bus = event_bus
        self._state = state_manager

    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        req = OrderProcessingInput.model_validate(event)
        payload = dict(req.payload)
        quantity = int(payload.get("quantity", 0))
        order_no = str(payload.get("order_no") or f"ORD-{uuid.uuid5(uuid.NAMESPACE_DNS, req.correlation_id).hex[:8]}")
        status = "processed"

        summary = {
            "order_no": order_no,
            "order_volume": quantity,
            "order_status": status,
        }
        state_entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(
            state_entity,
            {
                "order_no": order_no,
                "quantity": quantity,
                "status": status,
            },
            self.meta.skill_id,
        )

        out = OrderProcessingOutput(
            ok=True,
            order_no=order_no,
            order_volume=quantity,
            status=status,
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

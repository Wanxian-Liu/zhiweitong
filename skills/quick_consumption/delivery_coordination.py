"""Delivery coordination skill for quick consumption domain."""

from __future__ import annotations

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

ORG_PATH = "/智维通/城市乳业/快消板块/配送协调"
SKILL_ID = "qc_delivery_coordination"


class DeliveryCoordinationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class DeliveryCoordinationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    order_no: str
    delivery_status: str
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class DeliveryCoordinationSkill(SkillBase):
    """Coordinate delivery schedule for processed orders."""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="快消配送协调岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(DeliveryCoordinationInput),
            output_schema=json_schema(DeliveryCoordinationOutput),
            required_input_fields=["correlation_id", "payload.order_no"],
            optional_input_fields=["payload.address"],
            error_codes=["E_DELIVERY_INVALID_PAYLOAD"],
        ),
        execution=SkillExecution(
            workflow_steps=["receive_task", "build_schedule", "persist_state", "publish_result"],
            decision_rule="When order_no exists, mark delivery_status as scheduled.",
            token_budget=1000,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["quick_consumption", "delivery", "logistics"]),
    )

    def __init__(self, event_bus: EventBus, state_manager: StateManager) -> None:
        super().__init__()
        self._bus = event_bus
        self._state = state_manager

    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        req = DeliveryCoordinationInput.model_validate(event)
        payload = dict(req.payload)
        order_no = str(payload.get("order_no", ""))
        delivery_status = "scheduled" if order_no else "pending_order"
        summary = {
            "order_no": order_no,
            "delivery_status": delivery_status,
        }

        state_entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(
            state_entity,
            {"order_no": order_no, "delivery_status": delivery_status},
            self.meta.skill_id,
        )

        out = DeliveryCoordinationOutput(
            ok=True,
            order_no=order_no,
            delivery_status=delivery_status,
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

"""B2C online operation skill for quick consumption domain."""

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

ORG_PATH = "/智维通/城市乳业/快消板块/B2C线上运营"
SKILL_ID = "qc_b2c_online_operation"


class B2COnlineOperationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class B2COnlineOperationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    channel: str
    anomaly_count: int
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class B2COnlineOperationSkill(SkillBase):
    """Analyze online order signals and emit channel summary."""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="快消B2C线上运营岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(B2COnlineOperationInput),
            output_schema=json_schema(B2COnlineOperationOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=["payload.channel", "payload.anomaly_signals"],
            error_codes=["E_B2C_INVALID_INPUT"],
        ),
        execution=SkillExecution(
            workflow_steps=["receive_task", "analyze_channel_signals", "persist_state", "publish_result"],
            decision_rule="Count anomaly_signals list length; defaults to zero.",
            token_budget=1000,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["quick_consumption", "b2c", "operation"]),
    )

    def __init__(self, event_bus: EventBus, state_manager: StateManager) -> None:
        super().__init__()
        self._bus = event_bus
        self._state = state_manager

    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        req = B2COnlineOperationInput.model_validate(event)
        payload = dict(req.payload)
        anomalies = payload.get("anomaly_signals", [])
        anomaly_count = len(anomalies) if isinstance(anomalies, list) else 0
        channel = str(payload.get("channel", "community_group_buy"))
        summary = {
            "channel": channel,
            "anomaly_count": anomaly_count,
        }
        state_entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(
            state_entity,
            {"channel": channel, "anomaly_count": anomaly_count},
            self.meta.skill_id,
        )

        out = B2COnlineOperationOutput(
            ok=True,
            channel=channel,
            anomaly_count=anomaly_count,
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

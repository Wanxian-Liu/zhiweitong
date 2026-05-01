"""Quick consumption supervisor skill."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.event_bus import EventBus
from core.orchestrator import command_topic, result_topic
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
from skills.quick_consumption.b2c_online_operation import ORG_PATH as B2C_ORG_PATH, SKILL_ID as B2C_SKILL_ID
from skills.quick_consumption.delivery_coordination import (
    ORG_PATH as DELIVERY_ORG_PATH,
    SKILL_ID as DELIVERY_SKILL_ID,
)
from skills.quick_consumption.order_processing import ORG_PATH as ORDER_ORG_PATH, SKILL_ID as ORDER_SKILL_ID

ORG_PATH = "/智维通/城市乳业/快消板块"
SKILL_ID = "qc_supervisor"


class QuickConsumptionSupervisorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class QuickConsumptionSupervisorOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    order_volume: int
    delivery_status: str
    anomaly_count: int
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class QuickConsumptionSupervisorSkill(SkillBase):
    """Decompose fast-moving consumer tasks and aggregate subordinate reports."""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="快消主管岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(QuickConsumptionSupervisorInput),
            output_schema=json_schema(QuickConsumptionSupervisorOutput),
            required_input_fields=["correlation_id", "payload"],
            optional_input_fields=["payload.order_no", "payload.quantity", "payload.channel"],
            error_codes=["E_QC_SUPERVISOR_TIMEOUT", "E_QC_SUPERVISOR_BAD_INPUT"],
        ),
        execution=SkillExecution(
            workflow_steps=["receive_task", "split_subtasks", "dispatch_subtasks", "collect_results", "aggregate_report"],
            decision_rule="Always fan out to B2C, order processing, and delivery coordination via EventBus.",
            token_budget=2500,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["quick_consumption", "supervisor", "dispatch"]),
    )

    def __init__(self, event_bus: EventBus, state_manager: StateManager, step_timeout: float = 10.0) -> None:
        super().__init__()
        self._bus = event_bus
        self._state = state_manager
        self._step_timeout = step_timeout

    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        req = QuickConsumptionSupervisorInput.model_validate(event)
        task_id = req.correlation_id or str(uuid.uuid4())
        payload = dict(req.payload)
        state_entity = f"{self.meta.org_path}/{self.meta.skill_id}/{task_id}"
        await self._state.save_state(state_entity, {"stage": "dispatching", "payload": payload}, self.meta.skill_id)

        expected: dict[str, asyncio.Future[dict[str, Any]]] = {
            B2C_SKILL_ID: asyncio.get_running_loop().create_future(),
            ORDER_SKILL_ID: asyncio.get_running_loop().create_future(),
            DELIVERY_SKILL_ID: asyncio.get_running_loop().create_future(),
        }

        async def _on_result(_: str, incoming: dict[str, Any]) -> None:
            correlation = str(incoming.get("correlation_id", ""))
            if correlation != task_id:
                return
            skill_id = str(incoming.get("skill_id", ""))
            fut = expected.get(skill_id)
            if fut is None or fut.done():
                return
            fut.set_result(dict(incoming.get("payload", {})))

        sub_id = await self._bus.subscribe(f"{ORG_PATH}/*/result", _on_result)
        try:
            await self._publish_subtask(B2C_ORG_PATH, B2C_SKILL_ID, task_id, {"channel": payload.get("channel"), "anomaly_signals": payload.get("anomaly_signals", [])})
            await self._publish_subtask(
                ORDER_ORG_PATH,
                ORDER_SKILL_ID,
                task_id,
                {"order_no": payload.get("order_no"), "quantity": payload.get("quantity", 0)},
            )
            await self._publish_subtask(
                DELIVERY_ORG_PATH,
                DELIVERY_SKILL_ID,
                task_id,
                {"order_no": payload.get("order_no"), "address": payload.get("address", "")},
            )
            gathered = await asyncio.wait_for(asyncio.gather(*expected.values()), timeout=self._step_timeout)
        except asyncio.TimeoutError:
            out = QuickConsumptionSupervisorOutput(
                ok=False,
                order_volume=0,
                delivery_status="timeout",
                anomaly_count=0,
                error="E_QC_SUPERVISOR_TIMEOUT",
                summary={},
            ).model_dump()
            await self._state.save_state(state_entity, {"stage": "timeout"}, self.meta.skill_id)
            await self._publish_result(task_id, out)
            return out
        finally:
            self._bus.unsubscribe(sub_id)

        by_skill = {B2C_SKILL_ID: gathered[0], ORDER_SKILL_ID: gathered[1], DELIVERY_SKILL_ID: gathered[2]}
        order_summary = dict(by_skill[ORDER_SKILL_ID].get("summary", {}))
        delivery_summary = dict(by_skill[DELIVERY_SKILL_ID].get("summary", {}))
        b2c_summary = dict(by_skill[B2C_SKILL_ID].get("summary", {}))
        summary = {
            "order_no": order_summary.get("order_no", delivery_summary.get("order_no", "")),
            "order_volume": int(order_summary.get("order_volume", 0)),
            "delivery_status": str(delivery_summary.get("delivery_status", "pending")),
            "anomaly_count": int(b2c_summary.get("anomaly_count", 0)),
        }
        out = QuickConsumptionSupervisorOutput(
            ok=True,
            order_volume=summary["order_volume"],
            delivery_status=summary["delivery_status"],
            anomaly_count=summary["anomaly_count"],
            summary=summary,
        ).model_dump()
        await self._state.save_state(state_entity, {"stage": "done", "summary": summary}, self.meta.skill_id)
        await self._publish_result(task_id, out)
        return out

    async def _publish_subtask(self, org_path: str, skill_id: str, correlation_id: str, payload: dict[str, Any]) -> None:
        envelope = EventEnvelope(
            correlation_id=correlation_id,
            org_path=org_path,
            skill_id=skill_id,
            payload=payload,
        )
        await self._bus.publish(command_topic(org_path), envelope.model_dump())

    async def _publish_result(self, correlation_id: str, payload: dict[str, Any]) -> None:
        envelope = EventEnvelope(
            correlation_id=correlation_id,
            org_path=self.meta.org_path,
            skill_id=self.meta.skill_id,
            payload=payload,
        )
        await self._bus.publish(result_topic(self.meta.org_path), envelope.model_dump())

"""排产 Skill — 生产中心."""

from __future__ import annotations

import uuid
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

ORG_PATH = "/智维通/城市乳业/生产中心/排产"
SKILL_ID = "prod_production_scheduling"
RULE_VERSION = "sched-demand-to-plan-v1"


class ProductionSchedulingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ProductionSchedulingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    batch_id: str
    planned_units: int
    line_id: str
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ProductionSchedulingSkill(SkillBase):
    """根据需求数量生成批次与产线分配（模拟）。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="排产岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(ProductionSchedulingInput),
            output_schema=json_schema(ProductionSchedulingOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=[
                "payload.demand_units",
                "payload.line_id",
                "payload.external_planned_units_url",
                "payload.external_request_headers",
            ],
            error_codes=["E_PROD_INVALID_PAYLOAD"],
        ),
        execution=SkillExecution(
            workflow_steps=["read_demand", "check_capacity", "allocate_line", "persist_plan", "publish_result"],
            decision_rule="planned_units = demand_units or 0; batch_id deterministic from correlation_id",
            token_budget=1500,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["production", "scheduling", "manufacturing"]),
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
        req = ProductionSchedulingInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        demand = int(payload.get("demand_units", 0))
        line_id = str(payload.get("line_id", "LINE-A1"))
        batch_id = f"BATCH-{uuid.uuid5(uuid.NAMESPACE_DNS, req.correlation_id).hex[:10].upper()}"
        planned_units = max(demand, 0)
        ext_url = str(payload.get("external_planned_units_url") or "").strip()
        planned_units, l3_integration = await merge_json_int_override(
            ext_url,
            correlation_id=req.correlation_id,
            field="planned_units",
            fallback=planned_units,
            mode="mes_planned_units_lookup",
            extra_headers=extra_headers_from_payload(payload),
        )

        summary = {
            "rule_version": RULE_VERSION,
            "batch_id": batch_id,
            "planned_units": planned_units,
            "line_id": line_id,
            "l2_reconcile": l2_reconcile_block(
                "production_plan_snapshot",
                {"batch_id": batch_id, "line_id": line_id},
                "planned_units",
                "与排产/MES 台账按 batch_id + line_id 核对计划产量（planned_units）。",
            ),
            "exception_code": None,
            "manual_handoff": None,
        }
        if l3_integration:
            summary["l3_integration"] = l3_integration
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(entity, summary, self.meta.skill_id)

        out = ProductionSchedulingOutput(
            ok=True,
            rule_version=RULE_VERSION,
            batch_id=batch_id,
            planned_units=planned_units,
            line_id=line_id,
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

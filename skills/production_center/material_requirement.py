"""物料需求 Skill — 生产中心（BOM 简化为「单位成品耗用原料整数倍」）。"""

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

ORG_PATH = "/智维通/城市乳业/生产中心/物料需求"
SKILL_ID = "prod_material_requirement"
# L1：与手册「可演示 / 可对账演进」一致；规则变更时递增并保留兼容说明。
RULE_VERSION = "mrp-single-level-v1"


class MaterialRequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class MaterialRequirementOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    fg_sku: str
    planned_fg_units: int
    raw_per_fg: int
    raw_stock: int
    required_raw_qty: int
    shortage_qty: int
    mrp_feasible: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class MaterialRequirementSkill(SkillBase):
    """按计划产量与 BOM 倍率估算原料需求，并与现存量比对是否可开工。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="物料需求岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(MaterialRequirementInput),
            output_schema=json_schema(MaterialRequirementOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=[
                "payload.fg_sku",
                "payload.planned_fg_units",
                "payload.raw_per_fg",
                "payload.raw_stock",
            ],
            error_codes=["E_PROD_MRP_INVALID_PAYLOAD", "W_MRP_NET_SHORTAGE"],
        ),
        execution=SkillExecution(
            workflow_steps=["resolve_fg", "expand_bom", "compute_gross_req", "net_against_stock", "publish_result"],
            decision_rule="required_raw_qty = planned_fg_units * raw_per_fg; shortage = max(0, required - raw_stock)",
            token_budget=1500,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["production", "mrp", "bom", "materials"]),
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
        req = MaterialRequirementInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        fg_sku = str(payload.get("fg_sku", "FG-DEFAULT"))
        planned_fg = max(int(payload.get("planned_fg_units", 0)), 0)
        raw_per = max(int(payload.get("raw_per_fg", 1)), 0)
        raw_stock = max(int(payload.get("raw_stock", 0)), 0)
        required_raw_qty = planned_fg * raw_per
        shortage_qty = max(0, required_raw_qty - raw_stock)
        mrp_feasible = raw_stock >= required_raw_qty

        summary = {
            "rule_version": RULE_VERSION,
            "fg_sku": fg_sku,
            "planned_fg_units": planned_fg,
            "raw_per_fg": raw_per,
            "raw_stock": raw_stock,
            "required_raw_qty": required_raw_qty,
            "shortage_qty": shortage_qty,
            "mrp_feasible": mrp_feasible,
            "l2_reconcile": l2_reconcile_block(
                "material_net_requirement",
                {"fg_sku": fg_sku},
                "required_raw_qty",
                "毛需求=planned_fg_units×raw_per_fg，与 WMS/ERP 原料现存量（raw_stock）同粒度核对。",
            ),
            "exception_code": (
                "W_MRP_NET_SHORTAGE" if not mrp_feasible else None
            ),
            "manual_handoff": (
                "原料净需求大于现存量；请采购/调拨补足 shortage_qty 后重跑本步。"
                if not mrp_feasible
                else None
            ),
        }
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(entity, summary, self.meta.skill_id)

        out = MaterialRequirementOutput(
            ok=True,
            rule_version=RULE_VERSION,
            fg_sku=fg_sku,
            planned_fg_units=planned_fg,
            raw_per_fg=raw_per,
            raw_stock=raw_stock,
            required_raw_qty=required_raw_qty,
            shortage_qty=shortage_qty,
            mrp_feasible=mrp_feasible,
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

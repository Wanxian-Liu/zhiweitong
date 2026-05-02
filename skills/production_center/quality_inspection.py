"""质量检验 Skill — 生产中心（抽检缺陷阈值示意）."""

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

ORG_PATH = "/智维通/城市乳业/生产中心/质量检验"
SKILL_ID = "prod_quality_inspection"
RULE_VERSION = "qc-defect-threshold-v1"


class QualityInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class QualityInspectionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    batch_id: str
    units_inspected: int
    defect_units: int
    max_defect_units: int
    qc_pass: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class QualityInspectionSkill(SkillBase):
    """抽检缺陷件数与允许上限比对；超阈值则批次不合格。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="质量检验岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(QualityInspectionInput),
            output_schema=json_schema(QualityInspectionOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=[
                "payload.batch_id",
                "payload.units_inspected",
                "payload.defect_units",
                "payload.max_defect_units",
                "payload.external_defect_units_url",
                "payload.external_request_headers",
            ],
            error_codes=["E_PROD_QC_INVALID_PAYLOAD", "W_QC_BATCH_REJECT"],
        ),
        execution=SkillExecution(
            workflow_steps=["resolve_batch", "sample_inspect", "count_defects", "compare_threshold", "persist", "publish_result"],
            decision_rule="qc_pass when defect_units <= max_defect_units",
            token_budget=1200,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["production", "quality", "qc"]),
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
        req = QualityInspectionInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        batch_id = str(payload.get("batch_id", "BATCH-DEFAULT"))
        units_inspected = int(payload.get("units_inspected", 0))
        defect_units = int(payload.get("defect_units", 0))
        max_defect_units = int(payload.get("max_defect_units", 0))
        ext_url = str(payload.get("external_defect_units_url") or "").strip()
        defect_units, l3_integration = await merge_json_int_override(
            ext_url,
            correlation_id=req.correlation_id,
            field="defect_units",
            fallback=defect_units,
            mode="lims_defect_units_lookup",
            extra_headers=extra_headers_from_payload(payload),
        )
        qc_pass = defect_units <= max_defect_units

        summary = {
            "rule_version": RULE_VERSION,
            "batch_id": batch_id,
            "units_inspected": units_inspected,
            "defect_units": defect_units,
            "max_defect_units": max_defect_units,
            "qc_pass": qc_pass,
            "l2_reconcile": l2_reconcile_block(
                "qc_batch_snapshot",
                {"batch_id": batch_id},
                "defect_units",
                "缺陷件数 defect_units 与批次标准 max_defect_units 同 batch_id、同检验批核对。",
            ),
            "exception_code": "W_QC_BATCH_REJECT" if not qc_pass else None,
            "manual_handoff": (
                "质检不合格；隔离批次、返工或报废审批后再放行。"
                if not qc_pass
                else None
            ),
        }
        if l3_integration:
            summary["l3_integration"] = l3_integration
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(
            entity,
            {
                "batch_id": batch_id,
                "units_inspected": units_inspected,
                "defect_units": defect_units,
                "max_defect_units": max_defect_units,
                "qc_pass": qc_pass,
            },
            self.meta.skill_id,
        )
        out = QualityInspectionOutput(
            ok=True,
            rule_version=RULE_VERSION,
            batch_id=batch_id,
            units_inspected=units_inspected,
            defect_units=defect_units,
            max_defect_units=max_defect_units,
            qc_pass=qc_pass,
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

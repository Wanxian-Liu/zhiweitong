"""库存盘点 Skill — 仓储物流（账实比对示意）."""

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

ORG_PATH = "/智维通/城市乳业/仓储物流/库存盘点"
SKILL_ID = "wh_cycle_count"
RULE_VERSION = "cycle-count-variance-v1"


class CycleCountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CycleCountOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    sku: str
    book_qty: int
    counted_qty: int
    variance_qty: int
    cycle_balanced: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class CycleCountSkill(SkillBase):
    """账存 book_qty 与实盘 counted_qty 比对；差异非零时打异常码便于人工复盘。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="库存盘点岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(CycleCountInput),
            output_schema=json_schema(CycleCountOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=[
                "payload.sku",
                "payload.book_qty",
                "payload.counted_qty",
                "payload.external_counted_qty_url",
                "payload.external_request_headers",
            ],
            error_codes=["E_WH_CYCLE_INVALID_PAYLOAD", "W_CYCLE_COUNT_VARIANCE"],
        ),
        execution=SkillExecution(
            workflow_steps=["resolve_sku", "load_book", "capture_count", "diff", "persist", "publish_result"],
            decision_rule="variance_qty = counted_qty - book_qty; cycle_balanced when variance_qty == 0",
            token_budget=1200,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["warehouse", "cycle_count", "inventory", "logistics"]),
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
        req = CycleCountInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        sku = str(payload.get("sku", "SKU-DEFAULT"))
        book_qty = int(payload.get("book_qty", 0))
        counted_qty = int(payload.get("counted_qty", 0))
        ext_url = str(payload.get("external_counted_qty_url") or "").strip()
        counted_qty, l3_integration = await merge_json_int_override(
            ext_url,
            correlation_id=req.correlation_id,
            field="counted_qty",
            fallback=counted_qty,
            mode="wms_counted_qty_lookup",
            extra_headers=extra_headers_from_payload(payload),
        )
        variance_qty = counted_qty - book_qty
        cycle_balanced = variance_qty == 0

        summary = {
            "rule_version": RULE_VERSION,
            "sku": sku,
            "book_qty": book_qty,
            "counted_qty": counted_qty,
            "variance_qty": variance_qty,
            "cycle_balanced": cycle_balanced,
            "l2_reconcile": l2_reconcile_block(
                "cycle_count_snapshot",
                {"sku": sku},
                "counted_qty",
                "实盘 counted_qty 与账存 book_qty 同 SKU、同截点核对；variance_qty≠0 时复盘盈亏与串码。",
            ),
            "exception_code": "W_CYCLE_COUNT_VARIANCE" if not cycle_balanced else None,
            "manual_handoff": (
                "账实不符；请复盘差异原因并调整账面或补录实盘。"
                if not cycle_balanced
                else None
            ),
        }
        if l3_integration:
            summary["l3_integration"] = l3_integration
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(
            entity,
            {
                "sku": sku,
                "book_qty": book_qty,
                "counted_qty": counted_qty,
                "variance_qty": variance_qty,
                "cycle_balanced": cycle_balanced,
            },
            self.meta.skill_id,
        )
        out = CycleCountOutput(
            ok=True,
            rule_version=RULE_VERSION,
            sku=sku,
            book_qty=book_qty,
            counted_qty=counted_qty,
            variance_qty=variance_qty,
            cycle_balanced=cycle_balanced,
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

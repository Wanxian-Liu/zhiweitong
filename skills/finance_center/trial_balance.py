"""试算平衡 Skill — 财务中心（借贷合计平衡示意）."""

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

ORG_PATH = "/智维通/城市乳业/财务中心/试算平衡"
SKILL_ID = "fin_trial_balance"
RULE_VERSION = "fin-trial-balance-v1"


class TrialBalanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class TrialBalanceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    rule_version: str
    debit_total: float
    credit_total: float
    tb_balanced: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class TrialBalanceSkill(SkillBase):
    """借贷方金额合计一致则试算平衡；示意规则可替换为科目级展开。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="试算平衡岗",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(TrialBalanceInput),
            output_schema=json_schema(TrialBalanceOutput),
            required_input_fields=["correlation_id"],
            optional_input_fields=["payload.debits", "payload.credits"],
            error_codes=["E_FIN_TRIAL_INVALID_PAYLOAD", "W_TRIAL_IMBALANCE"],
        ),
        execution=SkillExecution(
            workflow_steps=["ingest_lines", "sum_debits", "sum_credits", "compare", "persist", "publish_result"],
            decision_rule="tb_balanced when round(sum(debits),2) == round(sum(credits),2)",
            token_budget=2000,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["finance", "trial_balance", "gl"]),
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
        req = TrialBalanceInput.model_validate(event)
        payload = effective_skill_payload(dict(req.payload))
        debits = payload.get("debits")
        credits = payload.get("credits")
        debit_total = round(float(sum(float(x) for x in debits)), 2) if isinstance(debits, list) else 0.0
        credit_total = round(float(sum(float(x) for x in credits)), 2) if isinstance(credits, list) else 0.0
        tb_balanced = debit_total == credit_total

        summary = {
            "rule_version": RULE_VERSION,
            "debit_total": debit_total,
            "credit_total": credit_total,
            "tb_balanced": tb_balanced,
            "l2_reconcile": l2_reconcile_block(
                "trial_balance_snapshot",
                {},
                "debit_total",
                "借方合计 debit_total 与贷方合计 credit_total 同期间、同账套核对。",
            ),
            "exception_code": "W_TRIAL_IMBALANCE" if not tb_balanced else None,
            "manual_handoff": (
                "试算不平衡；逐科目查找差异或过账遗漏后重算。"
                if not tb_balanced
                else None
            ),
        }
        entity = f"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}"
        await self._state.save_state(
            entity,
            {"debit_total": debit_total, "credit_total": credit_total, "tb_balanced": tb_balanced},
            self.meta.skill_id,
        )
        out = TrialBalanceOutput(
            ok=True,
            rule_version=RULE_VERSION,
            debit_total=debit_total,
            credit_total=credit_total,
            tb_balanced=tb_balanced,
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

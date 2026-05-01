"""Tests for core.skill_base."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from core.skill_base import (
    SkillBase,
    SkillCompliance,
    SkillExecution,
    SkillInterface,
    SkillKnowledge,
    SkillMeta,
    RuntimeConstraints,
    json_schema,
    minimal_skill_meta,
)


def _valid_interface() -> SkillInterface:
    return SkillInterface(
        input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"y": {"type": "boolean"}}},
        error_codes=["E1"],
    )


def _valid_execution() -> SkillExecution:
    return SkillExecution(
        workflow_steps=["a", "b"],
        decision_rule="rule-1",
        token_budget=100,
        api_call_budget=5,
    )


def test_skill_meta_roundtrip_json() -> None:
    m = SkillMeta(
        skill_id="s1",
        name="测试岗",
        org_path="/智维通/城市乳业/快消板块",
        supervisor="ai_ceo",
        interface=_valid_interface(),
        execution=_valid_execution(),
        compliance=SkillCompliance(),
        knowledge=SkillKnowledge(tags=["t"]),
        runtime=RuntimeConstraints(),
    )
    raw = m.model_dump_json()
    m2 = SkillMeta.model_validate_json(raw)
    assert m2.skill_id == "s1"
    assert m2.supervisor == "ai_ceo"


def test_org_path_validation() -> None:
    with pytest.raises(ValidationError):
        SkillMeta(
            skill_id="s",
            name="n",
            org_path="/wrong/路径",
            interface=_valid_interface(),
            execution=_valid_execution(),
            compliance=SkillCompliance(),
            knowledge=SkillKnowledge(),
        )


def test_validate_skill_static() -> None:
    m = minimal_skill_meta(
        skill_id="x",
        name="n",
        org_path="/智维通/城市乳业/x",
    )
    SkillBase.validate_skill(m)


def test_validate_skill_rejects_bad_runtime() -> None:
    m = minimal_skill_meta(skill_id="x", name="n", org_path="/智维通/城市乳业/x")
    data = m.model_dump()
    data["runtime"] = {"stateless": True, "communication": "direct"}
    with pytest.raises(ValidationError):
        SkillMeta.model_validate(data)


def test_json_schema_helper() -> None:
    from pydantic import BaseModel

    class M(BaseModel):
        a: int

    s = json_schema(M)
    assert s["title"] == "M"


def test_subclass_without_meta_raises() -> None:
    with pytest.raises(TypeError, match="META"):

        class Bad(SkillBase):  # type: ignore[misc]
            async def execute(self, event: dict) -> dict:
                return {}


def test_concrete_skill_instantiate() -> None:
    class Ok(SkillBase):
        META = minimal_skill_meta(
            skill_id="ok",
            name="OK",
            org_path="/智维通/城市乳业/快消板块",
        )

        async def execute(self, event: dict) -> dict:
            return {"ok": True}

    s = Ok()
    assert s.meta.skill_id == "ok"


def test_execute_runs() -> None:
    class Ok(SkillBase):
        META = minimal_skill_meta(
            skill_id="ok",
            name="OK",
            org_path="/智维通/城市乳业/快消板块",
        )

        async def execute(self, event: dict) -> dict:
            return {"echo": event}

    async def _run() -> None:
        s = Ok()
        out = await s.execute({"q": 1})
        assert out == {"echo": {"q": 1}}

    asyncio.run(_run())

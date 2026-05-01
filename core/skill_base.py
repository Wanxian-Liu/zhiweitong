"""Skill six-layer metadata (OpenCLAW) and abstract :class:`SkillBase`."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AI_CEO = "ai_ceo"


class SkillInterface(BaseModel):
    """接口层：JSON Schema + 字段/错误码清单（可序列化）。"""

    model_config = ConfigDict(extra="forbid")

    input_schema: dict[str, Any] = Field(
        ...,
        description="JSON Schema for execute() input payload (e.g. from BaseModel.model_json_schema()).",
    )
    output_schema: dict[str, Any] = Field(
        ...,
        description="JSON Schema for execute() return dict.",
    )
    required_input_fields: list[str] = Field(default_factory=list)
    optional_input_fields: list[str] = Field(default_factory=list)
    error_codes: list[str] = Field(default_factory=list)


class SkillExecution(BaseModel):
    """执行层：流程、决策规则描述、预算。"""

    model_config = ConfigDict(extra="forbid")

    workflow_steps: list[str] = Field(..., min_length=1)
    decision_rule: str = Field(
        ...,
        description="LLM prompt fragment or rule identifier / DSL string.",
    )
    token_budget: int = Field(..., ge=0)
    api_call_budget: int = Field(..., ge=0)


class SkillCompliance(BaseModel):
    """合规层。"""

    model_config = ConfigDict(extra="forbid")

    forbidden_operations: list[str] = Field(default_factory=list)
    audit_enabled: bool = True


class SkillKnowledge(BaseModel):
    """知识层：业务标签（权限/场景匹配）。"""

    model_config = ConfigDict(extra="forbid")

    tags: list[str] = Field(default_factory=list)


class RuntimeConstraints(BaseModel):
    """运行时约束（OpenCLAW 固定项）。"""

    model_config = ConfigDict(extra="forbid")

    stateless: Literal[True] = True
    communication: Literal["event_bus"] = "event_bus"


class SkillMeta(BaseModel):
    """六层元数据组合 + 基础字段。"""

    model_config = ConfigDict(extra="forbid")

    skill_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    org_path: str = Field(..., min_length=1)
    supervisor: Literal["ai_ceo"] = "ai_ceo"
    interface: SkillInterface
    execution: SkillExecution
    compliance: SkillCompliance
    knowledge: SkillKnowledge
    runtime: RuntimeConstraints = Field(default_factory=RuntimeConstraints)

    @field_validator("org_path")
    @classmethod
    def org_path_must_be_under_root(cls, v: str) -> str:
        root = "/智维通/城市乳业"
        if v != root and not v.startswith(root + "/"):
            raise ValueError(f"org_path must be {root!r} or a child path, got {v!r}")
        return v


class SkillBase(ABC):
    """无状态 Skill：子类定义 ``META`` 并实现 ``execute``。"""

    META: SkillMeta

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        meta = getattr(cls, "META", None)
        if meta is None:
            raise TypeError(f"{cls.__name__} must define class attribute META: SkillMeta")
        if not isinstance(meta, SkillMeta):
            raise TypeError(f"{cls.__name__}.META must be a SkillMeta instance")

    def __init__(self) -> None:
        type(self).validate_skill(type(self).META)

    @property
    def meta(self) -> SkillMeta:
        return type(self).META

    @staticmethod
    def validate_skill(meta: SkillMeta) -> None:
        """校验元数据完整性；失败抛出 ``ValueError``。"""
        errs: list[str] = []
        if meta.supervisor != AI_CEO:
            errs.append(f"supervisor must be {AI_CEO!r}")
        if meta.runtime.stateless is not True:
            errs.append("runtime.stateless must be True")
        if meta.runtime.communication != "event_bus":
            errs.append('runtime.communication must be "event_bus"')
        if not meta.interface.input_schema:
            errs.append("interface.input_schema must be non-empty")
        if not meta.interface.output_schema:
            errs.append("interface.output_schema must be non-empty")
        if not meta.execution.workflow_steps:
            errs.append("execution.workflow_steps must be non-empty")
        if errs:
            raise ValueError("; ".join(errs))

    @abstractmethod
    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        """处理一条事件；无状态，副作用仅通过注入依赖（后续 Phase）。"""


def json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """从 Pydantic 模型生成 ``input_schema`` / ``output_schema`` 用的 JSON Schema。"""
    return model.model_json_schema()


class _MinimalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str = ""


class _MinimalOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool = True


def minimal_skill_meta(
    *,
    skill_id: str,
    name: str,
    org_path: str,
) -> SkillMeta:
    """测试/占位用最小合法 :class:`SkillMeta`。"""
    return SkillMeta(
        skill_id=skill_id,
        name=name,
        org_path=org_path,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema(_MinimalIn),
            output_schema=json_schema(_MinimalOut),
            error_codes=["E_TEST"],
        ),
        execution=SkillExecution(
            workflow_steps=["receive", "respond"],
            decision_rule="noop",
            token_budget=1000,
            api_call_budget=10,
        ),
        compliance=SkillCompliance(),
        knowledge=SkillKnowledge(tags=["test"]),
    )

"""Skill file generation helpers for OpenCLAW CLI (Phase 3.1)."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any


OPENCLAW_FILE_HEADER = """# OPENCLAW-GENERATED — 六层 Skill 元数据约束请勿随意删减。
# Source: zhiweitong CLI (create-skill / batch-register).
"""

ROOT_PREFIX = "/智维通/城市乳业"


def skill_id_to_class_name(skill_id: str) -> str:
    """``my_skill`` → ``MySkill`` (append ``Skill`` in templates)."""
    parts = re.split(r"[-_]+", skill_id.strip())
    pascal = "".join(p.title() for p in parts if p)
    if not pascal:
        raise ValueError(f"invalid skill_id: {skill_id!r}")
    if not pascal.endswith("Skill"):
        pascal = f"{pascal}Skill"
    return pascal


def batch_stub_class_name(i: int, skill_id: str) -> str:
    cls = f"_BatchStub{i}_{skill_id_to_class_name(skill_id)}"
    return cls[:-4] if cls.endswith("SkillSkill") else cls


def ensure_org_path(path: str) -> str:
    p = path.strip()
    if not p.startswith("/"):
        p = "/" + p
    if p != ROOT_PREFIX and not p.startswith(ROOT_PREFIX + "/"):
        raise ValueError(f"org_path must be {ROOT_PREFIX!r} or a child path, got {path!r}")
    return p


def render_new_skill_py(*, skill_id: str, name_zh: str, org_path: str, class_name: str) -> str:
    org_path = ensure_org_path(org_path)
    safe_id = skill_id.strip()
    in_model = f"{class_name.removesuffix('Skill')}Input"
    out_model = f"{class_name.removesuffix('Skill')}Output"
    base = class_name.removesuffix("Skill")
    if base == class_name:
        in_model = "SkillInput"
        out_model = "SkillOutput"
    return f'''{OPENCLAW_FILE_HEADER}
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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

ORG_PATH = "{org_path}"
SKILL_ID = "{safe_id}"


class {in_model}(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class {out_model}(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class {class_name}(SkillBase):
    """{name_zh} — 请在此补充业务逻辑。"""

    META = SkillMeta(
        skill_id=SKILL_ID,
        name="{name_zh}",
        org_path=ORG_PATH,
        supervisor="ai_ceo",
        interface=SkillInterface(
            input_schema=json_schema({in_model}),
            output_schema=json_schema({out_model}),
            required_input_fields=["correlation_id"],
            optional_input_fields=["payload.action"],
            error_codes=["E_STUB"],
        ),
        execution=SkillExecution(
            workflow_steps=["receive", "process_stub", "persist", "publish_result"],
            decision_rule="stub — replace with real rules",
            token_budget=2000,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(forbidden_operations=["direct_skill_call"], audit_enabled=True),
        knowledge=SkillKnowledge(tags=["{safe_id}", "stub"]),
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
        req = {in_model}.model_validate(event)
        payload = dict(req.payload)
        summary = {{"action": payload.get("action"), "stub": True}}
        entity = f"{{self.meta.org_path}}/{{self.meta.skill_id}}/{{req.correlation_id}}"
        await self._state.save_state(entity, summary, self.meta.skill_id)
        out = {out_model}(ok=True, summary=summary).model_dump()
        envelope = EventEnvelope(
            correlation_id=req.correlation_id,
            org_path=self.meta.org_path,
            skill_id=self.meta.skill_id,
            payload=out,
        )
        await self._bus.publish(result_topic(self.meta.org_path), envelope.model_dump())
        return out
'''


def test_slug(skill_id: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", skill_id.strip()).strip("_")
    return s or "skill"


def render_test_skeleton(*, skill_id: str, import_package: str, class_name: str, org_path: str) -> str:
    org_path = ensure_org_path(org_path)
    slug = test_slug(skill_id)
    return f'''{OPENCLAW_FILE_HEADER}
from __future__ import annotations

import asyncio

from core.sandbox import run_sandbox
from skills.{import_package}.{skill_id} import {class_name}


def _env(cid: str = "t1") -> dict:
    return {{
        "schema_version": "1",
        "correlation_id": cid,
        "org_path": "{org_path}",
        "skill_id": "{skill_id}",
        "payload": {{"action": "ping"}},
    }}


def test_{slug}_meta_valid() -> None:
    s = {class_name}()
    assert s.meta.skill_id == "{skill_id}"


def test_{slug}_sandbox_coverage() -> None:
    async def _run() -> None:
        def factory():
            return {class_name}()

        rep = await run_sandbox(
            [_env()],
            skill_factory=factory,
            coverage_skill_module="skills.{import_package}.{skill_id}",
        )
        assert rep.passed == 1 and rep.failed == 0
        assert rep.coverage_percent >= 90.0

    asyncio.run(_run())
'''


def parse_batch_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")
        fields = {h.strip().lower(): h for h in reader.fieldnames}
        for req in ("skill_id", "name", "org_path"):
            if req not in fields:
                raise ValueError(f"CSV must contain column: {req}")
        rows: list[dict[str, str]] = []
        for raw in reader:
            row = {fields[k]: (raw.get(fields[k]) or "").strip() for k in fields}
            if not row.get(fields["skill_id"]):
                continue
            rows.append(
                {
                    "skill_id": row[fields["skill_id"]],
                    "name": row[fields["name"]],
                    "org_path": row[fields["org_path"]],
                },
            )
        return rows


def render_batch_register_py(rows: list[dict[str, str]]) -> str:
    lines = [
        OPENCLAW_FILE_HEADER.rstrip(),
        '"""Batch stub skills from CSV — replace bodies before production."""',
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "from pydantic import BaseModel, ConfigDict, Field",
        "",
        "from core.orchestrator import result_topic",
        "from core.skill_base import (",
        "    SkillBase,",
        "    SkillCompliance,",
        "    SkillExecution,",
        "    SkillInterface,",
        "    SkillKnowledge,",
        "    SkillMeta,",
        "    json_schema,",
        ")",
        "from core.skill_registry import SkillRegistry",
        "from shared.models import EventEnvelope",
        "",
    ]
    for i, r in enumerate(rows):
        sid = r["skill_id"]
        name = r["name"].replace('"', '\\"')
        org = ensure_org_path(r["org_path"])
        cls = batch_stub_class_name(i, sid)
        in_m = f"_In{i}"
        out_m = f"_Out{i}"
        lines.extend(
            [
                "",
                f"class {in_m}(BaseModel):",
                '    model_config = ConfigDict(extra="forbid")',
                '    schema_version: str = "1"',
                "    correlation_id: str",
                "    org_path: str",
                "    skill_id: str",
                "    payload: dict[str, Any] = Field(default_factory=dict)",
                "",
                f"class {out_m}(BaseModel):",
                '    model_config = ConfigDict(extra="forbid")',
                "    ok: bool",
                "    summary: dict[str, Any] = Field(default_factory=dict)",
                "",
                f"class {cls}(SkillBase):",
                f'    """CSV row stub: {sid} — {name}"""',
                "    META = SkillMeta(",
                f'        skill_id="{sid}",',
                f'        name="{name}",',
                f'        org_path="{org}",',
                '        supervisor="ai_ceo",',
                "        interface=SkillInterface(",
                f"            input_schema=json_schema({in_m}),",
                f"            output_schema=json_schema({out_m}),",
                '            required_input_fields=["correlation_id"],',
                '            error_codes=["E_BATCH_STUB"],',
                "        ),",
                "        execution=SkillExecution(",
                '            workflow_steps=["stub"],',
                '            decision_rule="batch CSV stub",',
                "            token_budget=500,",
                "            api_call_budget=0,",
                "        ),",
                "        compliance=SkillCompliance(audit_enabled=True),",
                "        knowledge=SkillKnowledge(tags=[\"batch_stub\"]),",
                "    )",
                "",
                "    def __init__(self, event_bus: Any | None = None, state_manager: Any | None = None) -> None:",
                "        super().__init__()",
                "        self._bus = event_bus",
                "        self._state = state_manager",
                "",
                "    def attach_sandbox(self, bus: Any, state_manager: Any) -> None:",
                "        self._bus = bus",
                "        self._state = state_manager",
                "",
                "    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:",
                "        if self._bus is None or self._state is None:",
                '            raise RuntimeError("inject event_bus/state_manager or call attach_sandbox")',
                f"        req = {in_m}.model_validate(event)",
                "        summary = {\"batch_stub\": True, \"skill_id\": self.meta.skill_id}",
                "        entity = f\"{self.meta.org_path}/{self.meta.skill_id}/{req.correlation_id}\"",
                "        await self._state.save_state(entity, summary, self.meta.skill_id)",
                f"        out = {out_m}(ok=True, summary=summary).model_dump()",
                "        envelope = EventEnvelope(",
                "            correlation_id=req.correlation_id,",
                "            org_path=self.meta.org_path,",
                "            skill_id=self.meta.skill_id,",
                "            payload=out,",
                "        )",
                "        await self._bus.publish(result_topic(self.meta.org_path), envelope.model_dump())",
                "        return out",
                "",
            ],
        )

    lines.extend(
        [
            "def register_batch(registry: SkillRegistry) -> None:",
            '    """Register all CSV-generated stub classes."""',
        ],
    )
    for i, r in enumerate(rows):
        cls = batch_stub_class_name(i, r["skill_id"])
        lines.append(f"    registry.register({cls}())")

    lines.append("")
    all_names = [f'"{batch_stub_class_name(i, r["skill_id"])}"' for i, r in enumerate(rows)]
    all_names.append('"register_batch"')
    lines.append(f"__all__ = [{', '.join(all_names)}]")
    return "\n".join(lines) + "\n"

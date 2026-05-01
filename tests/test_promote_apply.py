"""``promote-apply`` and :mod:`cli.promotion` splice helpers."""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.main import app
from cli.promotion import merged_execution_from_snapshot, parse_promotion_snapshot, splice_merged_execution_into_skill_source
from core.knowledge_store import KnowledgeStore
from core.skill_base import SkillBase, SkillCompliance, SkillExecution, SkillInterface, SkillKnowledge, SkillMeta, json_schema
from pydantic import BaseModel, ConfigDict

skip_no_chroma = pytest.mark.skipif(
    importlib.util.find_spec("chromadb") is None,
    reason="chromadb not installed",
)


class _MiniIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correlation_id: str


class _MiniOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


_MINI_SKILL_SRC = '''
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from core.skill_base import (
    SkillBase,
    SkillCompliance,
    SkillExecution,
    SkillInterface,
    SkillKnowledge,
    SkillMeta,
    json_schema,
)

ORG_PATH = "/智维通/城市乳业/财务中心/测试岗"
SKILL_ID = "fin_apply_splice_test"


class MiniIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correlation_id: str


class MiniOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


class MiniSkill(SkillBase):
    META = SkillMeta(
        skill_id=SKILL_ID,
        name="测",
        org_path=ORG_PATH,
        interface=SkillInterface(
            input_schema=json_schema(MiniIn),
            output_schema=json_schema(MiniOut),
            required_input_fields=["correlation_id"],
            optional_input_fields=[],
            error_codes=[],
        ),
        execution=SkillExecution(
            workflow_steps=["step_a", "step_b"],
            decision_rule="RULE_BEFORE_SPLICE",
            token_budget=100,
            api_call_budget=0,
        ),
        compliance=SkillCompliance(),
        knowledge=SkillKnowledge(),
    )
'''


def test_splice_merged_execution_into_skill_source() -> None:
    merged = SkillExecution(
        workflow_steps=["step_a", "step_b"],
        decision_rule="RULE_AFTER_SPLICE",
        token_budget=999,
        api_call_budget=1,
    )
    out = splice_merged_execution_into_skill_source(_MINI_SKILL_SRC, merged)
    assert "RULE_AFTER_SPLICE" in out
    assert "RULE_BEFORE_SPLICE" not in out
    assert "token_budget=999" in out
    assert "api_call_budget=1" in out
    assert ast.parse(out) is not None


def test_merged_execution_from_snapshot() -> None:
    class _C(SkillBase):
        META = SkillMeta(
            skill_id="x",
            name="n",
            org_path="/智维通/城市乳业/财务中心/测",
            interface=SkillInterface(
                input_schema=json_schema(_MiniIn),
                output_schema=json_schema(_MiniOut),
                required_input_fields=["correlation_id"],
                optional_input_fields=[],
                error_codes=[],
            ),
            execution=SkillExecution(
                workflow_steps=["a"],
                decision_rule="old",
                token_budget=1,
                api_call_budget=0,
            ),
            compliance=SkillCompliance(),
            knowledge=SkillKnowledge(),
        )

    snap = parse_promotion_snapshot(
        json.dumps(
            {
                "source": "evolution_promotion",
                "target_skill_id": "x",
                "proposed_execution_patch": {"decision_rule": "patched", "token_budget": 42},
            },
            ensure_ascii=False,
        ),
    )
    ex = merged_execution_from_snapshot(_C, snap)
    assert ex.decision_rule == "patched"
    assert ex.token_budget == 42
    assert ex.workflow_steps == ["a"]


@skip_no_chroma
def test_promote_apply_dry_run_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHIWEITONG_PROJECT_ROOT", str(tmp_path))
    skill_path = tmp_path / "mini_skill.py"
    skill_path.write_text(_MINI_SKILL_SRC, encoding="utf-8")

    chroma = tmp_path / "chroma"
    chroma.mkdir()

    async def _prep() -> str:
        ks = KnowledgeStore(persist_directory=chroma)
        snap = {
            "source": "evolution_promotion",
            "target_skill_id": "fin_apply_splice_test",
            "proposed_execution_patch": {
                "decision_rule": "RULE_FROM_PROMOTION_SNAPSHOT",
                "token_budget": 4242,
            },
        }
        return await ks.store(
            ["evolution", "promotion"],
            json.dumps(snap, ensure_ascii=False),
            {},
            org_path="/智维通/城市乳业/财务中心/测试岗",
        )

    doc_id = asyncio.run(_prep())
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "promote-apply",
            "--doc-id",
            doc_id,
            "--chroma-path",
            str(chroma),
            "--skill-file",
            str(skill_path),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "RULE_FROM_PROMOTION_SNAPSHOT" in result.stdout
    assert "RULE_BEFORE_SPLICE" in result.stdout
    assert skill_path.read_text(encoding="utf-8") == _MINI_SKILL_SRC


@skip_no_chroma
def test_promote_apply_write_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHIWEITONG_PROJECT_ROOT", str(tmp_path))
    skill_path = tmp_path / "mini_skill.py"
    skill_path.write_text(_MINI_SKILL_SRC, encoding="utf-8")

    chroma = tmp_path / "chroma"
    chroma.mkdir()

    async def _prep() -> str:
        ks = KnowledgeStore(persist_directory=chroma)
        snap = {
            "source": "evolution_promotion",
            "target_skill_id": "fin_apply_splice_test",
            "proposed_execution_patch": {"decision_rule": "WRITTEN_RULE"},
        }
        return await ks.store(
            ["evolution", "promotion"],
            json.dumps(snap, ensure_ascii=False),
            {},
            org_path="/智维通/城市乳业/财务中心/测试岗",
        )

    doc_id = asyncio.run(_prep())
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "promote-apply",
            "--doc-id",
            doc_id,
            "--chroma-path",
            str(chroma),
            "--skill-file",
            str(skill_path),
            "--write",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    after = skill_path.read_text(encoding="utf-8")
    assert "WRITTEN_RULE" in after
    assert "RULE_BEFORE_SPLICE" not in after
    backups = list(tmp_path.glob("mini_skill.py.promote-backup-*"))
    assert len(backups) == 1
    assert "RULE_BEFORE_SPLICE" in backups[0].read_text(encoding="utf-8")

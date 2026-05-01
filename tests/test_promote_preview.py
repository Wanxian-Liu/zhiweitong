"""CLI ``promote-preview`` and ``cli.promotion`` helpers."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.main import app
from cli.promotion import find_skill_py, parse_promotion_snapshot
from core.knowledge_store import KnowledgeStore

skip_no_chroma = pytest.mark.skipif(
    importlib.util.find_spec("chromadb") is None,
    reason="chromadb not installed",
)


def test_find_skill_py_fin_receivable() -> None:
    root = Path(__file__).resolve().parent.parent
    p = find_skill_py(root, "fin_receivable_reconciliation")
    assert p is not None
    assert p.name == "receivable_reconciliation.py"


def test_parse_promotion_snapshot() -> None:
    raw = json.dumps(
        {
            "source": "evolution_promotion",
            "target_skill_id": "x",
            "proposed_execution_patch": {"decision_rule": "r"},
        },
        ensure_ascii=False,
    )
    s = parse_promotion_snapshot(raw)
    assert s["target_skill_id"] == "x"


@skip_no_chroma
def test_promote_preview_cli_stdout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = Path(__file__).resolve().parent.parent
    monkeypatch.setenv("ZHIWEITONG_PROJECT_ROOT", str(repo))
    chroma = tmp_path / "chroma"
    chroma.mkdir()

    async def _prep() -> str:
        ks = KnowledgeStore(persist_directory=chroma)
        snap = {
            "source": "evolution_promotion",
            "target_skill_id": "fin_receivable_reconciliation",
            "knowledge_doc_id": "evo-1",
            "audit_correlation_id": "a1",
            "proposed_execution_patch": {
                "decision_rule": "cli_preview_patch_rule",
                "token_budget": 42,
            },
        }
        return await ks.store(
            ["evolution", "promotion", "approved", "fin_receivable_reconciliation"],
            json.dumps(snap, ensure_ascii=False),
            {"kind": "promoted_execution_patch"},
            org_path="/智维通/城市乳业/财务中心/应收对账",
        )

    doc_id = asyncio.run(_prep())
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["promote-preview", "--doc-id", doc_id, "--chroma-path", str(chroma)],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    out = result.stdout
    assert "cli_preview_patch_rule" in out
    assert "merged SkillExecution" in out
    assert "fin_receivable_reconciliation" in out

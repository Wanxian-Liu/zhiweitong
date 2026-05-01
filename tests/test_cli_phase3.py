"""Phase 3.1 CLI smoke tests (Typer + isolated project root)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_create_skill_writes_files(tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHIWEITONG_PROJECT_ROOT", str(tmp_path))
    (tmp_path / "cli").mkdir(parents=True)
    (tmp_path / "skills").mkdir()
    (tmp_path / "tests").mkdir()

    result = runner.invoke(
        app,
        [
            "create-skill",
            "--skill-id",
            "cli_test_skill",
            "--name-zh",
            "CLI测试",
            "--org-path",
            "/智维通/城市乳业/测试/cli",
            "--package",
            "cli_test_pkg",
            "--force",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    skill = tmp_path / "skills" / "cli_test_pkg" / "cli_test_skill.py"
    test_f = tmp_path / "tests" / "test_cli_test_skill.py"
    assert skill.is_file()
    assert test_f.is_file()
    assert "cli_test_skill" in skill.read_text(encoding="utf-8")
    assert "/智维通/城市乳业/测试/cli" in skill.read_text(encoding="utf-8")


def test_batch_register_writes_module(tmp_path: Path, runner: CliRunner) -> None:
    csv_path = tmp_path / "batch.csv"
    csv_path.write_text(
        textwrap.dedent(
            """\
            skill_id,name,org_path
            a_skill,A技能,/智维通/城市乳业/批次/a
            b_skill,B技能,/智维通/城市乳业/批次/b
            """
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        ["batch-register", str(csv_path), str(out_dir)],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    mod = out_dir / "batch_skills.py"
    assert mod.is_file()
    text = mod.read_text(encoding="utf-8")
    assert "_BatchStub0_ASkill" in text
    assert "a_skill" in text
    assert "register_batch" in text


def test_validate_existing_skill(tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use real repo root so an existing Phase-2 skill can be loaded."""
    root = Path(__file__).resolve().parent.parent
    monkeypatch.setenv("ZHIWEITONG_PROJECT_ROOT", str(root))
    skill_path = root / "skills" / "finance_center" / "receivable_reconciliation.py"
    if not skill_path.is_file():
        pytest.skip("receivable_reconciliation skill not present")
    result = runner.invoke(
        app,
        ["validate", str(skill_path), "--skip-sandbox"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr

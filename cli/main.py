"""智维通 CLI — OpenCLAW Phase 3.1 (create-skill, batch-register, validate)."""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
import re
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import typer

from cli.promotion import (
    build_preview_text,
    find_skill_py,
    format_apply_unified_diff,
    merged_execution_from_snapshot,
    parse_promotion_snapshot,
    splice_merged_execution_into_skill_source,
)
from cli.generators import (
    ensure_org_path,
    parse_batch_csv,
    render_batch_register_py,
    render_new_skill_py,
    render_test_skeleton,
    skill_id_to_class_name,
)
from core.knowledge_store import KnowledgeStore
from core.sandbox import SandboxReport, run_sandbox
from core.skill_base import SkillBase

app = typer.Typer(no_args_is_help=True, help="智维通 zhiweitong CLI (OpenCLAW)")


def _repo_root() -> Path:
    env = os.environ.get("ZHIWEITONG_PROJECT_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent


def _validate_skill_id(skill_id: str) -> str:
    s = skill_id.strip()
    if not re.match(r"^[a-z][a-z0-9_]*$", s):
        raise typer.BadParameter("skill_id must be snake_case: ^[a-z][a-z0-9_]*$")
    return s


def _find_skill_class(mod: ModuleType) -> type[SkillBase]:
    candidates: list[type[SkillBase]] = []
    for _n, obj in inspect.getmembers(mod, inspect.isclass):
        if obj is SkillBase or not issubclass(obj, SkillBase):
            continue
        if getattr(obj, "META", None) is None:
            continue
        candidates.append(obj)
    if not candidates:
        raise typer.BadParameter(f"no SkillBase subclass with META in {mod.__file__!r}")
    candidates.sort(key=lambda c: c.__name__)
    return candidates[0]


def _promote_resolve(
    doc_id: str,
    chroma_path: Path | None,
    skill_file: Path | None,
) -> tuple[dict[str, Any], Path, type[SkillBase]]:
    """Load promotion snapshot from Chroma and resolve the Skill module + class."""
    root = _repo_root()
    cp = chroma_path
    if cp is None:
        envp = os.environ.get("ZHIWEITONG_CHROMA_PATH")
        cp = Path(envp) if envp else root / "var" / "chroma"
    cp = cp.resolve()
    if not cp.is_dir():
        raise typer.BadParameter(f"Chroma persist directory not found: {cp}")

    async def _run_async() -> tuple[dict[str, Any], str]:
        ks = KnowledgeStore(persist_directory=cp)
        row = await ks.get_by_id(doc_id.strip())
        if row is None:
            raise typer.BadParameter(f"unknown doc_id: {doc_id!r}")
        snap = parse_promotion_snapshot(row["content"])
        sid = str(snap.get("target_skill_id") or "").strip()
        if not sid:
            raise typer.BadParameter("snapshot missing target_skill_id")
        return snap, sid

    snap, sid = asyncio.run(_run_async())

    spath: Path
    if skill_file is not None:
        spath = skill_file.resolve()
    else:
        found = find_skill_py(root, sid)
        if found is None:
            raise typer.BadParameter(
                f"cannot find skills/**/*.py for skill_id={sid!r}; pass --skill-file",
            )
        spath = found

    mod = _load_module_from_file(spath)
    cls = _find_skill_class(mod)
    return snap, spath, cls


def _load_module_from_file(py_file: Path) -> ModuleType:
    py_file = py_file.resolve()
    if not py_file.suffix == ".py" or not py_file.is_file():
        raise typer.BadParameter(f"not a Python file: {py_file}")
    name = f"_cli_validate_{py_file.stem}"
    spec = importlib.util.spec_from_file_location(name, py_file)
    if spec is None or spec.loader is None:
        raise typer.BadParameter(f"cannot load {py_file}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@app.command("version")
def version_cmd() -> None:
    """Print package name and version."""
    typer.echo("zhiweitong 0.1.0")


@app.command("create-skill")
def create_skill_cmd(
    skill_id: str | None = typer.Option(None, "--skill-id", help="snake_case，如 fin_new_role"),
    name_zh: str | None = typer.Option(None, "--name-zh", help="中文岗位名"),
    org_path: str | None = typer.Option(None, "--org-path", help="完整 org_path，如 /智维通/城市乳业/财务中心/新岗"),
    package: str | None = typer.Option(
        None,
        "--package",
        help="skills 下子目录（Python 包名），如 finance_center",
    ),
    class_name: str | None = typer.Option(
        None,
        "--class-name",
        help="类名，默认由 skill_id 推导并带 Skill 后缀",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="只打印，不写文件"),
    force: bool = typer.Option(False, "--force", help="覆盖已存在的文件"),
) -> None:
    """交互式或参数式生成六层元数据 Skill 模板与测试骨架。"""
    sid = skill_id or typer.prompt("skill_id (snake_case)")
    sid = _validate_skill_id(sid)
    nzh = name_zh or typer.prompt("中文岗位名")
    op = org_path or typer.prompt("org_path（须以 /智维通/城市乳业 为前缀）")
    pkg = package or typer.prompt("skills 子包名（如 finance_center）")
    pkg = pkg.strip()
    if not re.match(r"^[a-z][a-z0-9_]*$", pkg):
        raise typer.BadParameter("package must be a valid Python package name")
    cls_name = class_name.strip() if class_name else skill_id_to_class_name(sid)
    if not cls_name.endswith("Skill"):
        cls_name = f"{cls_name}Skill"

    root = _repo_root()
    skill_py = root / "skills" / pkg / f"{sid}.py"
    test_py = root / "tests" / f"test_{sid}.py"
    pkg_init = root / "skills" / pkg / "__init__.py"

    if skill_py.exists() and not force and not dry_run:
        raise typer.BadParameter(f"exists: {skill_py} (use --force)")
    if test_py.exists() and not force and not dry_run:
        raise typer.BadParameter(f"exists: {test_py} (use --force)")

    body = render_new_skill_py(skill_id=sid, name_zh=nzh, org_path=op, class_name=cls_name)
    test_body = render_test_skeleton(
        skill_id=sid,
        import_package=pkg,
        class_name=cls_name,
        org_path=ensure_org_path(op),
    )

    if dry_run:
        typer.echo(body)
        typer.echo("\n--- test ---\n")
        typer.echo(test_body)
        return

    skill_py.parent.mkdir(parents=True, exist_ok=True)
    if not pkg_init.exists():
        pkg_init.write_text(
            f'"""{pkg} Skills — add exports via __getattr__ if needed (OpenCLAW)."""\n',
            encoding="utf-8",
        )
    skill_py.write_text(body, encoding="utf-8")
    test_py.write_text(test_body, encoding="utf-8")
    typer.secho(f"Wrote {skill_py.relative_to(root)}", fg="green")
    typer.secho(f"Wrote {test_py.relative_to(root)}", fg="green")


@app.command("batch-register")
def batch_register_cmd(
    csv_path: Path = typer.Argument(..., exists=True, readable=True, help="CSV：skill_id,name,org_path"),
    out_dir: Path = typer.Argument(..., help="输出目录（将写入 batch_skills.py）"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """从 CSV 批量生成可 ``register_batch`` 的 Stub Skill 模块。"""
    rows = parse_batch_csv(csv_path)
    if not rows:
        raise typer.BadParameter("CSV has no data rows")
    text = render_batch_register_py(rows)
    out_dir = out_dir.resolve()
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "batch_skills.py"
        target.write_text(text, encoding="utf-8")
        typer.secho(f"Wrote {target}", fg="green")
    else:
        typer.echo(text)


@app.command("promote-preview")
def promote_preview_cmd(
    doc_id: str = typer.Option(..., "--doc-id", help="知识库中 evolution promotion 快照的 doc_id"),
    chroma_path: Path | None = typer.Option(
        None,
        "--chroma-path",
        help="Chroma 持久化目录；默认 $ZHIWEITONG_CHROMA_PATH 或 <repo>/var/chroma",
    ),
    skill_file: Path | None = typer.Option(
        None,
        "--skill-file",
        help="Skill 模块 .py；省略则在 skills/ 下按 skill_id 搜索",
    ),
    full_meta: bool = typer.Option(False, "--full-meta", help="额外输出完整合并后的 SkillMeta JSON"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="写入 Markdown 文件；默认打印到 stdout",
    ),
) -> None:
    """从 Chroma 中的 promotion 快照生成「合并后的 execution / META」审阅稿（不修改源码）。"""
    snap, spath, cls = _promote_resolve(doc_id, chroma_path, skill_file)
    sid = str(snap.get("target_skill_id") or "").strip()
    if cls.META.skill_id != sid:
        typer.secho(
            f"warning: file declares skill_id={cls.META.skill_id!r} snapshot has {sid!r}",
            fg="yellow",
            err=True,
        )

    text = build_preview_text(
        doc_id=doc_id.strip(),
        snapshot=snap,
        skill_path=spath,
        skill_cls=cls,
        full_meta=full_meta,
    )
    if output is not None:
        out = output.resolve()
        out.write_text(text, encoding="utf-8")
        typer.secho(f"Wrote {out}", fg="green")
    else:
        typer.echo(text)


@app.command("promote-apply")
def promote_apply_cmd(
    doc_id: str = typer.Option(..., "--doc-id", help="知识库中 evolution promotion 快照的 doc_id"),
    chroma_path: Path | None = typer.Option(
        None,
        "--chroma-path",
        help="Chroma 持久化目录；默认 $ZHIWEITONG_CHROMA_PATH 或 <repo>/var/chroma",
    ),
    skill_file: Path | None = typer.Option(
        None,
        "--skill-file",
        help="Skill 模块 .py；省略则在 skills/ 下按 skill_id 搜索",
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="写入技能文件（先备份为同目录 *.promote-backup-<unix_ts>）；省略则只打印 unified diff",
    ),
) -> None:
    """将快照中的 execution patch 应用到 Skill 源码中的 ``SkillExecution``（默认仅 diff）。"""
    snap, spath, cls = _promote_resolve(doc_id, chroma_path, skill_file)
    sid = str(snap.get("target_skill_id") or "").strip()
    if cls.META.skill_id != sid:
        typer.secho(
            f"warning: file declares skill_id={cls.META.skill_id!r} snapshot has {sid!r}",
            fg="yellow",
            err=True,
        )

    merged_ex = merged_execution_from_snapshot(cls, snap)
    before = spath.read_text(encoding="utf-8")
    try:
        after = splice_merged_execution_into_skill_source(before, merged_ex)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e

    if before == after:
        typer.secho("SkillExecution already matches merged snapshot; nothing to do.", fg="green")
        return

    try:
        label = str(spath.relative_to(_repo_root()))
    except ValueError:
        label = spath.name
    diff = format_apply_unified_diff(label, before, after)
    if not write:
        typer.echo(diff, nl=False)
        if not diff.endswith("\n"):
            typer.echo("")
        return

    backup = spath.with_name(f"{spath.name}.promote-backup-{int(time.time())}")
    backup.write_text(before, encoding="utf-8")
    spath.write_text(after, encoding="utf-8")
    typer.secho(f"Backup: {backup}", fg="green")
    typer.secho(f"Wrote: {spath}", fg="green")


@app.command("validate")
def validate_cmd(
    skill_file: Path = typer.Argument(..., help="Skill 模块 .py 路径"),
    skip_sandbox: bool = typer.Option(False, "--skip-sandbox", help="仅校验元数据"),
) -> None:
    """对单个 Skill 文件执行 ``validate_skill`` 与沙盒执行（覆盖率因预导入可能偏低，默认不强制 90%）。"""
    py_path = skill_file.resolve()
    mod = _load_module_from_file(py_path)
    cls = _find_skill_class(mod)
    SkillBase.validate_skill(cls.META)
    typer.secho(f"validate_skill OK: {cls.__name__} ({cls.META.skill_id})", fg="green")

    if skip_sandbox:
        return

    event: dict[str, Any] = {
        "schema_version": "1",
        "correlation_id": "cli-validate",
        "org_path": cls.META.org_path,
        "skill_id": cls.META.skill_id,
        "payload": {"action": "validate"},
    }

    async def _run() -> SandboxReport:
        def factory() -> SkillBase:
            return cls()

        return await run_sandbox(
            [event],
            skill_factory=factory,
            enforce_coverage=False,
        )

    rep = asyncio.run(_run())
    typer.echo(f"sandbox: passed={rep.passed} failed={rep.failed} coverage={rep.coverage_percent:.1f}%")
    if rep.failed:
        for c in rep.cases:
            if not c.ok:
                typer.secho(f"  case {c.index}: {c.error}", fg="red")
        raise typer.Exit(code=1)


def run() -> None:
    app()


if __name__ == "__main__":
    run()

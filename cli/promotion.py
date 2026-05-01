"""Helpers for ``promote-preview`` / ``promote-apply`` — locate Skill files and merge execution."""

from __future__ import annotations

import ast
import difflib
import json
from pathlib import Path
from typing import Any

from core.evolution import merge_execution_patch
from core.skill_base import SkillBase, SkillExecution, SkillMeta


def find_skill_py(repo_root: Path, skill_id: str) -> Path | None:
    """Find ``skills/**/*.py`` that declares ``skill_id`` (``SKILL_ID`` or ``skill_id=`` in META)."""
    sid = skill_id.strip()
    for path in sorted(repo_root.glob("skills/**/*.py")):
        if path.name.startswith("__"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if f'SKILL_ID = "{sid}"' in text or f"SKILL_ID = '{sid}'" in text:
            return path
        if f'skill_id="{sid}"' in text or f"skill_id='{sid}'" in text:
            return path
    return None


def parse_promotion_snapshot(content: str) -> dict[str, Any]:
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("promotion document content must be a JSON object")
    if data.get("source") != "evolution_promotion":
        raise ValueError("not an evolution_promotion snapshot (missing or wrong source)")
    return data


def build_preview_text(
    *,
    doc_id: str,
    snapshot: dict[str, Any],
    skill_path: Path,
    skill_cls: type[SkillBase],
    full_meta: bool,
) -> str:
    patch = snapshot.get("proposed_execution_patch") or {}
    if not isinstance(patch, dict):
        patch = {}
    merged: SkillMeta = merge_execution_patch(skill_cls.META, patch)
    lines: list[str] = [
        f"# promote-preview — {merged.skill_id}",
        "",
        "## Source",
        f"- knowledge doc_id: `{doc_id}`",
        f"- skill file: `{skill_path}`",
        f"- class: `{skill_cls.__name__}`",
        "",
        "## proposed_execution_patch (raw)",
        "```json",
        json.dumps(patch, ensure_ascii=False, indent=2),
        "```",
        "",
        "## merged SkillExecution (apply these fields to META.execution)",
        "```json",
        merged.execution.model_dump_json(indent=2),
        "```",
        "",
    ]
    if full_meta:
        lines += [
            "## full merged SkillMeta (advanced)",
            "```json",
            merged.model_dump_json(indent=2),
            "```",
            "",
        ]
    lines += [
        "## Manual apply",
        "1. Open the skill file above.",
        "2. Update `META.execution` to match **merged SkillExecution** (or replace full `META` if you use `--full-meta` output).",
        "3. Run `zhiweitong validate <skill_file.py>` before commit.",
        "",
    ]
    return "\n".join(lines)


def merged_execution_from_snapshot(skill_cls: type[SkillBase], snapshot: dict[str, Any]) -> SkillExecution:
    """Shallow-merge ``proposed_execution_patch`` into ``skill_cls.META.execution`` (same rules as preview)."""
    patch = snapshot.get("proposed_execution_patch") or {}
    if not isinstance(patch, dict):
        patch = {}
    merged = merge_execution_patch(skill_cls.META, patch)
    return merged.execution


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _skill_execution_ast(merged: SkillExecution) -> ast.Call:
    """Emit ``SkillExecution(...)`` as an AST call (keyword order stable)."""
    keywords: list[ast.keyword] = []
    for key in ("workflow_steps", "decision_rule", "token_budget", "api_call_budget"):
        v = getattr(merged, key)
        if key == "workflow_steps":
            val: ast.expr = ast.List(elts=[ast.Constant(s) for s in v], ctx=ast.Load())
        else:
            val = ast.Constant(v)
        keywords.append(ast.keyword(arg=key, value=val))
    return ast.Call(func=ast.Name(id="SkillExecution", ctx=ast.Load()), args=[], keywords=keywords)


def _find_meta_skill_execution_call(tree: ast.Module) -> ast.Call | None:
    """Locate the ``SkillExecution`` call used as ``execution=`` inside ``META = SkillMeta(...)``."""
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
                continue
            t = stmt.targets[0]
            if not isinstance(t, ast.Name) or t.id != "META":
                continue
            val = stmt.value
            if not isinstance(val, ast.Call) or not _is_name(val.func, "SkillMeta"):
                continue
            for kw in val.keywords:
                if kw.arg != "execution" or not isinstance(kw.value, ast.Call):
                    continue
                if _is_name(kw.value.func, "SkillExecution"):
                    return kw.value
    return None


def splice_merged_execution_into_skill_source(src: str, merged: SkillExecution) -> str:
    """Return source with the ``SkillExecution`` under ``META`` replaced by ``merged``.

    Preserves the rest of the file (including comments outside the replaced span).
    Only supports ``execution=SkillExecution(...)`` where the call uses the name ``SkillExecution``.
    """
    tree = ast.parse(src)
    old_exec = _find_meta_skill_execution_call(tree)
    if old_exec is None:
        msg = (
            "could not find `META = SkillMeta(..., execution=SkillExecution(...), ...)` "
            "with keyword `execution`"
        )
        raise ValueError(msg)
    old_text = ast.get_source_segment(src, old_exec)
    if old_text is None:
        raise ValueError("SkillExecution AST node has no source span")
    new_inner = ast.unparse(_skill_execution_ast(merged))
    lead = old_text[: len(old_text) - len(old_text.lstrip())]
    new_segment = lead + new_inner
    if src.count(old_text) != 1:
        raise ValueError("ambiguous SkillExecution source match; file needs manual edit")
    out = src.replace(old_text, new_segment, 1)
    try:
        ast.parse(out)
    except SyntaxError as e:
        raise ValueError(f"apply would produce invalid Python: {e}") from e
    return out


def format_apply_unified_diff(path_label: str, before: str, after: str) -> str:
    """Unified diff for ``promote-apply`` dry-run (stdout)."""
    return "".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"a/{path_label}",
            tofile=f"b/{path_label}",
        ),
    )

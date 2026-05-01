"""Helpers for ``promote-preview`` — locate Skill files and render merge preview text."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.evolution import merge_execution_patch
from core.skill_base import SkillBase, SkillMeta


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

"""Skill module with intentionally unreachable code for coverage threshold tests."""

from __future__ import annotations

from typing import Any

from core.skill_base import SkillBase, minimal_skill_meta


def _dead_helper() -> str:
    return "never called in sandbox"


class PartialSandboxSkill(SkillBase):
    META = minimal_skill_meta(
        skill_id="sandbox_partial",
        name="沙盒部分覆盖",
        org_path="/智维通/城市乳业/快消板块",
    )

    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        if event.get("hit_dead"):
            return {"x": _dead_helper()}
        return {"ok": True}

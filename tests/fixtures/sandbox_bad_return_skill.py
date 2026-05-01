"""Skill that returns non-dict (sandbox type guard)."""

from __future__ import annotations

from typing import Any

from core.skill_base import SkillBase, minimal_skill_meta


class BadReturnSandboxSkill(SkillBase):
    META = minimal_skill_meta(
        skill_id="badret",
        name="Bad",
        org_path="/智维通/城市乳业/快消板块",
    )

    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        return "nope"  # type: ignore[return-value]

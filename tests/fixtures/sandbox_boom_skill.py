"""Skill that always raises (sandbox failure counting)."""

from __future__ import annotations

from typing import Any

from core.skill_base import SkillBase, minimal_skill_meta


class BoomSandboxSkill(SkillBase):
    META = minimal_skill_meta(
        skill_id="boom",
        name="B",
        org_path="/智维通/城市乳业/快消板块",
    )

    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("boom")

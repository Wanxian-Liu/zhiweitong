"""Minimal Skill for sandbox coverage tests (aim for high line coverage of this file)."""

from __future__ import annotations

from typing import Any

from core.skill_base import SkillBase, minimal_skill_meta


class OkSandboxSkill(SkillBase):
    META = minimal_skill_meta(
        skill_id="sandbox_ok",
        name="沙盒 OK",
        org_path="/智维通/城市乳业/快消板块",
    )

    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        return {"echo": event.get("q", 0)}

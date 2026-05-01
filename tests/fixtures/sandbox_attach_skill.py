"""Skill that uses attach_sandbox + bus/state (sandbox integration)."""

from __future__ import annotations

from typing import Any

from core.sandbox import StubEventBus, StubStateManager
from core.skill_base import SkillBase, minimal_skill_meta


class AttachSandboxSkill(SkillBase):
    META = minimal_skill_meta(
        skill_id="attach_sandbox",
        name="Attach",
        org_path="/智维通/城市乳业/快消板块",
    )

    def attach_sandbox(self, bus: StubEventBus, state: StubStateManager) -> None:
        self._bus = bus
        self._state = state

    async def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        await self._bus.publish("t1", event)
        await self._state.save_state("k", event, self.meta.skill_id)
        return {"ok": True}

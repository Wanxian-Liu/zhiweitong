"""Dispatch ``org_path/.../command`` events to the Skill registered at that exact org_path."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.event_bus_factory import AnyEventBus
from core.observability import zt_log_extra
from core.skill_base import SkillBase
from core.skill_registry import SkillRegistry
from core.state_manager import StateManager

logger = logging.getLogger(__name__)


def _normalize_org_path(path: str) -> str:
    p = path.strip()
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/") or "/"


def resolve_skill_for_command_topic(registry: SkillRegistry, topic: str) -> SkillBase | None:
    """Return the unique skill whose ``meta.org_path`` equals the command topic's org path."""
    if not str(topic).endswith("/command"):
        return None
    org_path = _normalize_org_path(str(topic)[: -len("/command")])
    matches = [
        s
        for s in registry.find_by_org_path(org_path)
        if _normalize_org_path(s.meta.org_path) == org_path
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None
    logger.warning(
        "ambiguous org_path=%s for command topic=%s candidates=%s",
        org_path,
        topic,
        [s.meta.skill_id for s in matches],
        extra=zt_log_extra(
            component="skill_command_gateway_resolve",
            outcome="resolve_ambiguous",
        ),
    )
    return matches[0]


class SkillCommandGateway:
    """Background subscriber: ``/智维通/城市乳业*`` → filter ``*/command`` → :meth:`SkillBase.execute`."""

    def __init__(self, bus: AnyEventBus, registry: SkillRegistry, state: StateManager) -> None:
        self._bus = bus
        self._registry = registry
        self._state = state
        self._sub_id: str | None = None

    async def start(self) -> str:
        async def _route(topic: str, event: dict[str, Any]) -> None:
            if not str(topic).endswith("/command"):
                return
            skill = resolve_skill_for_command_topic(self._registry, topic)
            if skill is None:
                logger.debug("skill_command_gateway skip topic=%s", topic)
                return
            if hasattr(skill, "attach_sandbox"):
                skill.attach_sandbox(self._bus, self._state)
            _cid = event.get("correlation_id")
            _cid_s = str(_cid) if _cid is not None else None
            t0 = time.perf_counter()
            try:
                await skill.execute(event)
            except Exception:
                dt_ms = (time.perf_counter() - t0) * 1000.0
                logger.exception(
                    "skill_command_gateway execute failed skill_id=%s topic=%s duration_ms=%.1f",
                    skill.meta.skill_id,
                    topic,
                    dt_ms,
                    extra=zt_log_extra(
                        skill_id=skill.meta.skill_id,
                        correlation_id=_cid_s,
                        component="skill_command_gateway",
                        outcome="execute_failed",
                        duration_ms=dt_ms,
                    ),
                )
            else:
                dt_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(
                    "skill_command_gateway execute_ok skill_id=%s topic=%s duration_ms=%.1f",
                    skill.meta.skill_id,
                    topic,
                    dt_ms,
                    extra=zt_log_extra(
                        skill_id=skill.meta.skill_id,
                        correlation_id=_cid_s,
                        component="skill_command_gateway",
                        outcome="execute_ok",
                        duration_ms=dt_ms,
                    ),
                )

        self._sub_id = await self._bus.subscribe("/智维通/城市乳业*", _route)
        logger.info(
            "SkillCommandGateway started subscription=%s",
            self._sub_id,
            extra=zt_log_extra(component="skill_command_gateway"),
        )
        return self._sub_id

    async def stop(self) -> None:
        if self._sub_id is not None:
            self._bus.unsubscribe(self._sub_id)
            self._sub_id = None

"""Singleton Skill registry (OpenCLAW Phase 1.1)."""

from __future__ import annotations

import threading
from typing import ClassVar

from core.skill_base import AI_CEO, SkillBase


class SkillRegistry:
    """Thread-safe singleton registry of :class:`SkillBase` instances by ``skill_id``."""

    _instance: ClassVar[SkillRegistry | None] = None
    _singleton_lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls) -> SkillRegistry:
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._init_storage()
                    cls._instance = inst
        return cls._instance

    def _init_storage(self) -> None:
        self._lock = threading.RLock()
        self._by_id: dict[str, SkillBase] = {}

    @classmethod
    def _reset_singleton_for_tests(cls) -> None:
        """Clear singleton (tests only)."""
        with cls._singleton_lock:
            cls._instance = None

    def register(self, skill: SkillBase) -> None:
        """Register ``skill``; rejects duplicate ``skill_id`` or non-``ai_ceo`` supervisor."""
        meta = skill.meta
        if meta.supervisor != AI_CEO:
            raise ValueError(
                f"supervisor must be {AI_CEO!r}, got {meta.supervisor!r} for skill_id={meta.skill_id!r}",
            )
        SkillBase.validate_skill(meta)

        with self._lock:
            if meta.skill_id in self._by_id:
                raise ValueError(f"skill_id already registered: {meta.skill_id!r}")
            self._by_id[meta.skill_id] = skill

    def unregister(self, skill_id: str) -> None:
        """Remove a skill by id; raises ``KeyError`` if unknown."""
        with self._lock:
            if skill_id not in self._by_id:
                raise KeyError(f"unknown skill_id: {skill_id!r}")
            del self._by_id[skill_id]

    def get_skill(self, skill_id: str) -> SkillBase:
        """Return registered skill; raises ``KeyError`` if missing."""
        with self._lock:
            if skill_id not in self._by_id:
                raise KeyError(f"unknown skill_id: {skill_id!r}")
            return self._by_id[skill_id]

    def find_by_org_path(self, org_path: str) -> list[SkillBase]:
        """Skills whose ``org_path`` equals ``org_path`` or is a direct/indirect child of it."""
        q = _normalize_org_path(org_path)
        with self._lock:
            skills = list(self._by_id.values())
        out: list[SkillBase] = []
        for s in skills:
            p = _normalize_org_path(s.meta.org_path)
            if p == q or p.startswith(q + "/"):
                out.append(s)
        out.sort(key=lambda x: (x.meta.org_path, x.meta.skill_id))
        return out

    def list_skill_ids(self) -> list[str]:
        """All registered ``skill_id`` values (sorted)."""
        with self._lock:
            return sorted(self._by_id.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._by_id)


def _normalize_org_path(path: str) -> str:
    p = path.strip()
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/") or "/"

"""生产中心 Skills (Phase 2)."""

from __future__ import annotations

from typing import Any

__all__ = ["ProductionSchedulingSkill"]


def __getattr__(name: str) -> Any:
    if name == "ProductionSchedulingSkill":
        from skills.production_center.production_scheduling import ProductionSchedulingSkill

        return ProductionSchedulingSkill
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

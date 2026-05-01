"""生产中心 Skills (Phase 2)."""

from __future__ import annotations

from typing import Any

__all__ = [
    "BatchReleaseSkill",
    "MaterialRequirementSkill",
    "ProductionSchedulingSkill",
    "QualityInspectionSkill",
]


def __getattr__(name: str) -> Any:
    if name == "BatchReleaseSkill":
        from skills.production_center.batch_release import BatchReleaseSkill

        return BatchReleaseSkill
    if name == "MaterialRequirementSkill":
        from skills.production_center.material_requirement import MaterialRequirementSkill

        return MaterialRequirementSkill
    if name == "ProductionSchedulingSkill":
        from skills.production_center.production_scheduling import ProductionSchedulingSkill

        return ProductionSchedulingSkill
    if name == "QualityInspectionSkill":
        from skills.production_center.quality_inspection import QualityInspectionSkill

        return QualityInspectionSkill
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

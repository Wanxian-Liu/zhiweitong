"""仓储物流 Skills (Phase 2)."""

from __future__ import annotations

from typing import Any

__all__ = ["InventoryManagementSkill"]


def __getattr__(name: str) -> Any:
    if name == "InventoryManagementSkill":
        from skills.warehouse_logistics.inventory_management import InventoryManagementSkill

        return InventoryManagementSkill
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""仓储物流 Skills (Phase 2)."""

from __future__ import annotations

from typing import Any

__all__ = ["InboundReceivingSkill", "InventoryManagementSkill", "OutboundPickingSkill"]


def __getattr__(name: str) -> Any:
    if name == "InboundReceivingSkill":
        from skills.warehouse_logistics.inbound_receiving import InboundReceivingSkill

        return InboundReceivingSkill
    if name == "InventoryManagementSkill":
        from skills.warehouse_logistics.inventory_management import InventoryManagementSkill

        return InventoryManagementSkill
    if name == "OutboundPickingSkill":
        from skills.warehouse_logistics.outbound_picking import OutboundPickingSkill

        return OutboundPickingSkill
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""仓储物流 Skills (Phase 2)."""

from __future__ import annotations

from typing import Any

__all__ = [
    "CycleCountSkill",
    "InboundReceivingSkill",
    "InventoryManagementSkill",
    "OutboundPickingSkill",
    "StockTransferSkill",
]


def __getattr__(name: str) -> Any:
    if name == "CycleCountSkill":
        from skills.warehouse_logistics.cycle_count import CycleCountSkill

        return CycleCountSkill
    if name == "InboundReceivingSkill":
        from skills.warehouse_logistics.inbound_receiving import InboundReceivingSkill

        return InboundReceivingSkill
    if name == "InventoryManagementSkill":
        from skills.warehouse_logistics.inventory_management import InventoryManagementSkill

        return InventoryManagementSkill
    if name == "OutboundPickingSkill":
        from skills.warehouse_logistics.outbound_picking import OutboundPickingSkill

        return OutboundPickingSkill
    if name == "StockTransferSkill":
        from skills.warehouse_logistics.stock_transfer import StockTransferSkill

        return StockTransferSkill
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

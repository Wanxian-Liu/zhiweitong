"""快消板块 Skills (Phase 1).

Lazy exports avoid eager imports when parent packages are loaded (e.g. via
``find_spec`` during sandbox coverage setup).
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "B2COnlineOperationSkill",
    "DeliveryCoordinationSkill",
    "OrderProcessingSkill",
    "QuickConsumptionSupervisorSkill",
]


def __getattr__(name: str) -> Any:
    if name == "B2COnlineOperationSkill":
        from skills.quick_consumption.b2c_online_operation import B2COnlineOperationSkill

        return B2COnlineOperationSkill
    if name == "DeliveryCoordinationSkill":
        from skills.quick_consumption.delivery_coordination import DeliveryCoordinationSkill

        return DeliveryCoordinationSkill
    if name == "OrderProcessingSkill":
        from skills.quick_consumption.order_processing import OrderProcessingSkill

        return OrderProcessingSkill
    if name == "QuickConsumptionSupervisorSkill":
        from skills.quick_consumption.supervisor import QuickConsumptionSupervisorSkill

        return QuickConsumptionSupervisorSkill
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""快消板块 Skills (Phase 1)."""

from skills.quick_consumption.b2c_online_operation import B2COnlineOperationSkill
from skills.quick_consumption.delivery_coordination import DeliveryCoordinationSkill
from skills.quick_consumption.order_processing import OrderProcessingSkill
from skills.quick_consumption.supervisor import QuickConsumptionSupervisorSkill

__all__ = [
    "B2COnlineOperationSkill",
    "DeliveryCoordinationSkill",
    "OrderProcessingSkill",
    "QuickConsumptionSupervisorSkill",
]

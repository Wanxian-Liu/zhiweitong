"""Tests for quick consumption skills (Phase 1.3)."""

from __future__ import annotations

import asyncio
import tempfile
from typing import Any

from core.event_bus import EventBus
from core.orchestrator import command_topic, result_topic
from core.state_manager import StateManager
from skills.quick_consumption import (
    B2COnlineOperationSkill,
    DeliveryCoordinationSkill,
    OrderProcessingSkill,
    QuickConsumptionSupervisorSkill,
)
from skills.quick_consumption.b2c_online_operation import ORG_PATH as B2C_ORG_PATH
from skills.quick_consumption.delivery_coordination import ORG_PATH as DELIVERY_ORG_PATH
from skills.quick_consumption.order_processing import ORG_PATH as ORDER_ORG_PATH


def test_quick_consumption_meta_paths() -> None:
    assert QuickConsumptionSupervisorSkill.META.org_path == "/智维通/城市乳业/快消板块"
    assert B2COnlineOperationSkill.META.org_path == "/智维通/城市乳业/快消板块/B2C线上运营"
    assert OrderProcessingSkill.META.org_path == "/智维通/城市乳业/快消板块/订单处理"
    assert DeliveryCoordinationSkill.META.org_path == "/智维通/城市乳业/快消板块/配送协调"


def test_supervisor_fanout_and_aggregation() -> None:
    async def _run() -> None:
        bus = EventBus()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_url = f"sqlite+aiosqlite:///{f.name}"
        sm = StateManager(database_url=db_url)
        await sm.init_schema()

        supervisor = QuickConsumptionSupervisorSkill(bus, sm, step_timeout=3.0)
        b2c = B2COnlineOperationSkill(bus, sm)
        order = OrderProcessingSkill(bus, sm)
        delivery = DeliveryCoordinationSkill(bus, sm)

        async def b2c_worker(_: str, event: dict[str, Any]) -> None:
            await b2c.execute(event)

        async def order_worker(_: str, event: dict[str, Any]) -> None:
            out = await order.execute(event)
            # Ensure downstream receives order_no for deterministic delivery scheduling.
            event["payload"]["order_no"] = out["order_no"]

        async def delivery_worker(_: str, event: dict[str, Any]) -> None:
            await delivery.execute(event)

        await bus.subscribe(command_topic(B2C_ORG_PATH), b2c_worker)
        await bus.subscribe(command_topic(ORDER_ORG_PATH), order_worker)
        await bus.subscribe(command_topic(DELIVERY_ORG_PATH), delivery_worker)

        reports: list[dict[str, Any]] = []

        async def on_supervisor_result(_: str, event: dict[str, Any]) -> None:
            reports.append(event)

        await bus.subscribe(result_topic(supervisor.meta.org_path), on_supervisor_result)

        out = await supervisor.execute(
            {
                "correlation_id": "goal-1",
                "org_path": supervisor.meta.org_path,
                "skill_id": supervisor.meta.skill_id,
                "payload": {
                    "quantity": 3,
                    "channel": "community_group_buy",
                    "anomaly_signals": [],
                    "order_no": "ORD-001",
                    "address": "虹桥路 100 号",
                },
            },
        )

        await bus.aclose()
        await sm.aclose()

        assert out["ok"] is True
        assert out["summary"]["order_no"] == "ORD-001"
        assert out["summary"]["order_volume"] == 3
        assert out["summary"]["delivery_status"] == "scheduled"
        assert reports and reports[0]["payload"]["summary"]["order_no"] == "ORD-001"

    asyncio.run(_run())

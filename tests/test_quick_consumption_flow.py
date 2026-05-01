"""End-to-end integration flow for quick consumption domain (Phase 1.4)."""

from __future__ import annotations

import asyncio
import tempfile
from typing import Any
from unittest.mock import AsyncMock

import pytest

from config.settings import Settings
from core.event_bus import EventBus
from core.orchestrator import Orchestrator, PlanStep, command_topic
from core.org_tree import OrgTree
from core.skill_registry import SkillRegistry
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


class _DummyKnowledgeStore:
    async def store(
        self,
        tags: list[str],
        content: str,
        metadata: dict[str, Any],
        *,
        org_path: str | None = None,
    ) -> str:
        _ = (tags, content, metadata, org_path)
        return "doc-e2e"


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    SkillRegistry._reset_singleton_for_tests()
    yield
    SkillRegistry._reset_singleton_for_tests()


def test_quick_consumption_goal_flow_e2e() -> None:
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

        # Spy wrappers allow us to assert calls happen via EventBus workers only.
        supervisor.execute = AsyncMock(wraps=supervisor.execute)  # type: ignore[method-assign]
        b2c.execute = AsyncMock(wraps=b2c.execute)  # type: ignore[method-assign]
        order.execute = AsyncMock(wraps=order.execute)  # type: ignore[method-assign]
        delivery.execute = AsyncMock(wraps=delivery.execute)  # type: ignore[method-assign]

        async def supervisor_worker(_: str, event: dict[str, Any]) -> None:
            # Orchestrator payload is {"action","params",...}; supervisor domain input is params.
            payload = dict(event.get("payload", {}))
            transformed = dict(event)
            transformed["payload"] = dict(payload.get("params", {}))
            # EventBus dispatches callbacks serially; run supervisor concurrently to avoid deadlock.
            asyncio.create_task(supervisor.execute(transformed))

        async def b2c_worker(_: str, event: dict[str, Any]) -> None:
            await b2c.execute(event)

        async def order_worker(_: str, event: dict[str, Any]) -> None:
            await order.execute(event)

        async def delivery_worker(_: str, event: dict[str, Any]) -> None:
            await delivery.execute(event)

        await bus.subscribe(command_topic(supervisor.meta.org_path), supervisor_worker)
        await bus.subscribe(command_topic(B2C_ORG_PATH), b2c_worker)
        await bus.subscribe(command_topic(ORDER_ORG_PATH), order_worker)
        await bus.subscribe(command_topic(DELIVERY_ORG_PATH), delivery_worker)

        registry = SkillRegistry()
        registry.register(supervisor)
        registry.register(b2c)
        registry.register(order)
        registry.register(delivery)

        tree = OrgTree()
        tree.load_many(
            {
                "/智维通/城市乳业": {},
                supervisor.meta.org_path: {},
                B2C_ORG_PATH: {},
                ORDER_ORG_PATH: {},
                DELIVERY_ORG_PATH: {},
            },
        )

        async def plan_provider(_: str) -> list[PlanStep]:
            return [
                PlanStep(
                    skill_path=supervisor.meta.org_path,
                    action="handle_group_order",
                    params={
                        "quantity": 3,
                        "order_no": "ORD-E2E-001",
                        "channel": "community_group_buy",
                        "address": "人民路 8 号",
                        "anomaly_signals": [],
                    },
                ),
            ]

        orch = Orchestrator(
            bus,
            sm,
            registry,
            _DummyKnowledgeStore(),
            tree,
            settings=Settings(
                database_url=db_url,
                redis_url="",
                llm_api_key="",
                llm_base_url="https://example.invalid",
            ),
            plan_provider=plan_provider,
            step_timeout=5.0,
        )
        try:
            report = await orch.process_goal("处理今天社区团购订单：客户下单 3 箱牛奶，需配送")
        finally:
            await bus.aclose()
            await sm.aclose()

        assert report.ok is True
        assert len(report.steps) == 1
        assert report.steps[0].ok is True
        assert report.aggregated["summaries"]
        merged_summary = report.aggregated["summaries"][0]["summary"]
        assert merged_summary["order_no"] == "ORD-E2E-001"
        assert merged_summary["delivery_status"] == "scheduled"

        # No hidden direct calls: each child is invoked exactly once by its own worker.
        assert supervisor.execute.await_count == 1
        assert b2c.execute.await_count == 1
        assert order.execute.await_count == 1
        assert delivery.execute.await_count == 1

    asyncio.run(_run())

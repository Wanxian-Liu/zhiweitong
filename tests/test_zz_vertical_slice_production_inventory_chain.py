"""垂直切片 E2E：排产 → 物料需求 → 入库验收 → 库存管理 → 出库拣货（无 LLM，总线 + Gateway + Orchestrator）。

文件前缀 ``test_zz_``：在默认 pytest 收集顺序下排在 ``test_phase2_department_skills`` **之后**，
避免本测试预先 ``import skills.*`` 导致同进程内 ``run_sandbox`` 对相同模块的覆盖率统计偏低。
"""

from __future__ import annotations

import asyncio
import tempfile
from typing import Any

import pytest

from config.settings import Settings
from core.event_bus import EventBus
from core.org_tree import OrgTree
from core.orchestrator import Orchestrator, PlanStep
from core.skill_command_gateway import SkillCommandGateway
from core.skill_registry import SkillRegistry
from core.state_manager import StateManager
from shared.vertical_slices import (
    PRODUCTION_INVENTORY_CHAIN,
    PRODUCTION_INVENTORY_DEFAULT_PARAMS,
    production_inventory_org_paths,
)


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
        return "doc-vs"


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    SkillRegistry._reset_singleton_for_tests()
    yield
    SkillRegistry._reset_singleton_for_tests()


def test_production_to_inventory_vertical_slice_e2e() -> None:
    async def _run() -> None:
        from skills.production_center.material_requirement import MaterialRequirementSkill
        from skills.production_center.production_scheduling import ProductionSchedulingSkill
        from skills.warehouse_logistics.inbound_receiving import InboundReceivingSkill
        from skills.warehouse_logistics.inventory_management import InventoryManagementSkill
        from skills.warehouse_logistics.outbound_picking import OutboundPickingSkill

        bus = EventBus()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_url = f"sqlite+aiosqlite:///{f.name}"
        sm = StateManager(database_url=db_url)
        await sm.init_schema()

        reg = SkillRegistry()
        reg.register(ProductionSchedulingSkill())
        reg.register(MaterialRequirementSkill())
        reg.register(InboundReceivingSkill())
        reg.register(InventoryManagementSkill())
        reg.register(OutboundPickingSkill())

        gw = SkillCommandGateway(bus, reg, sm)
        await gw.start()

        tree = OrgTree()
        org_paths = production_inventory_org_paths()
        tree.load_many(
            {
                "/智维通/城市乳业": {},
                "/智维通/城市乳业/生产中心": {},
                "/智维通/城市乳业/仓储物流": {},
                **{p: {} for p in org_paths},
            },
        )
        async def plan_provider(_: str) -> list[PlanStep]:
            return [
                PlanStep(skill_path=s.org_path, action=s.planner_action, params=params)
                for s, params in zip(PRODUCTION_INVENTORY_CHAIN, PRODUCTION_INVENTORY_DEFAULT_PARAMS, strict=True)
            ]

        orch = Orchestrator(
            bus,
            sm,
            reg,
            _DummyKnowledgeStore(),
            tree,
            settings=Settings(
                database_url=db_url,
                redis_url="",
                llm_api_key="",
                llm_base_url="https://example.invalid",
            ),
            plan_provider=plan_provider,
            step_timeout=8.0,
        )
        try:
            report = await orch.process_goal("垂直切片：排产→物料→入库→库存→出库（固定计划）")
        finally:
            await gw.stop()
            await bus.aclose()
            await sm.aclose()

        assert report.ok is True
        assert len(report.steps) == 5
        assert all(s.ok for s in report.steps)

        for i, step_def in enumerate(PRODUCTION_INVENTORY_CHAIN):
            assert report.steps[i].skill_path == step_def.org_path
            assert report.steps[i].skill_id == step_def.skill_id
            assert report.steps[i].summary.get("rule_version") == step_def.rule_version

        assert report.steps[0].summary.get("planned_units") == 100
        assert report.steps[0].summary.get("line_id") == "LINE-VS"
        assert report.steps[1].summary.get("required_raw_qty") == 200
        assert report.steps[1].summary.get("mrp_feasible") is True
        assert report.steps[2].summary.get("receipt_complete") is True
        assert report.steps[3].summary.get("reorder_suggested") is False
        assert report.steps[4].summary.get("pick_complete") is True
        assert report.steps[4].summary.get("requested_qty") == 80
        assert report.steps[4].summary.get("picked_qty") == 80

        # L2：对账粒度 + 异常码（主链 happy path 无 Warning）
        assert report.steps[0].summary.get("l2_reconcile", {}).get("grain") == "production_plan_snapshot"
        assert report.steps[0].summary.get("exception_code") is None
        assert report.steps[1].summary.get("l2_reconcile", {}).get("grain") == "material_net_requirement"
        assert report.steps[1].summary.get("exception_code") is None
        assert report.steps[2].summary.get("l2_reconcile", {}).get("grain") == "warehouse_receipt_line"
        assert report.steps[2].summary.get("exception_code") is None
        assert report.steps[3].summary.get("l2_reconcile", {}).get("grain") == "sku_on_hand_snapshot"
        assert report.steps[3].summary.get("exception_code") is None
        assert report.steps[4].summary.get("l2_reconcile", {}).get("grain") == "warehouse_pick_line"
        assert report.steps[4].summary.get("exception_code") is None

    asyncio.run(_run())

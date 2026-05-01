"""财务垂直切片 E2E：应收对账 → 应付对账（无 LLM，总线 + Gateway + Orchestrator）。"""

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
    FINANCE_AR_AP_CHAIN,
    FINANCE_AR_AP_DEFAULT_PARAMS,
    finance_ar_ap_org_paths,
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
        return "doc-fin"


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    SkillRegistry._reset_singleton_for_tests()
    yield
    SkillRegistry._reset_singleton_for_tests()


def test_finance_ar_ap_vertical_slice_e2e() -> None:
    async def _run() -> None:
        from skills.finance_center.payable_reconciliation import PayableReconciliationSkill
        from skills.finance_center.receivable_reconciliation import ReceivableReconciliationSkill

        bus = EventBus()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_url = f"sqlite+aiosqlite:///{f.name}"
        sm = StateManager(database_url=db_url)
        await sm.init_schema()

        reg = SkillRegistry()
        reg.register(ReceivableReconciliationSkill())
        reg.register(PayableReconciliationSkill())

        gw = SkillCommandGateway(bus, reg, sm)
        await gw.start()

        tree = OrgTree()
        paths = finance_ar_ap_org_paths()
        tree.load_many(
            {
                "/智维通/城市乳业": {},
                "/智维通/城市乳业/财务中心": {},
                **{p: {} for p in paths},
            },
        )

        async def plan_provider(_: str) -> list[PlanStep]:
            return [
                PlanStep(skill_path=s.org_path, action=s.planner_action, params=params)
                for s, params in zip(FINANCE_AR_AP_CHAIN, FINANCE_AR_AP_DEFAULT_PARAMS, strict=True)
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
            report = await orch.process_goal("财务切片：应收→应付（固定计划）")
        finally:
            await gw.stop()
            await bus.aclose()
            await sm.aclose()

        assert report.ok is True
        assert len(report.steps) == 2
        assert all(s.ok for s in report.steps)

        for i, step_def in enumerate(FINANCE_AR_AP_CHAIN):
            assert report.steps[i].skill_path == step_def.org_path
            assert report.steps[i].skill_id == step_def.skill_id
            assert report.steps[i].summary.get("rule_version") == step_def.rule_version

        assert report.steps[0].summary.get("receivable_total") == 110.0
        assert report.steps[0].summary.get("discrepancy_count") == 0
        assert report.steps[1].summary.get("payable_total") == 230.0
        assert report.steps[1].summary.get("discrepancy_count") == 0

        assert report.steps[0].summary.get("l2_reconcile", {}).get("grain") == "ar_net_snapshot"
        assert report.steps[0].summary.get("exception_code") is None
        assert report.steps[1].summary.get("l2_reconcile", {}).get("grain") == "ap_net_snapshot"
        assert report.steps[1].summary.get("exception_code") is None

    asyncio.run(_run())

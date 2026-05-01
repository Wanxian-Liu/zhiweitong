"""生产补链垂直切片 E2E：质量检验 → 批次放行（无 LLM，总线 + Gateway + Orchestrator）。"""

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
    PRODUCTION_QUALITY_CHAIN,
    PRODUCTION_QUALITY_DEFAULT_PARAMS,
    production_quality_org_paths,
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
        return "doc-pq"


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    SkillRegistry._reset_singleton_for_tests()
    yield
    SkillRegistry._reset_singleton_for_tests()


def test_production_quality_vertical_slice_e2e() -> None:
    async def _run() -> None:
        from skills.production_center.batch_release import BatchReleaseSkill
        from skills.production_center.quality_inspection import QualityInspectionSkill

        bus = EventBus()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_url = f"sqlite+aiosqlite:///{f.name}"
        sm = StateManager(database_url=db_url)
        await sm.init_schema()

        reg = SkillRegistry()
        reg.register(QualityInspectionSkill())
        reg.register(BatchReleaseSkill())

        gw = SkillCommandGateway(bus, reg, sm)
        await gw.start()

        tree = OrgTree()
        paths = production_quality_org_paths()
        tree.load_many(
            {
                "/智维通/城市乳业": {},
                "/智维通/城市乳业/生产中心": {},
                **{p: {} for p in paths},
            },
        )

        async def plan_provider(_: str) -> list[PlanStep]:
            return [
                PlanStep(skill_path=s.org_path, action=s.planner_action, params=params)
                for s, params in zip(PRODUCTION_QUALITY_CHAIN, PRODUCTION_QUALITY_DEFAULT_PARAMS, strict=True)
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
            report = await orch.process_goal("生产切片：质检→批次放行（固定计划）")
        finally:
            await gw.stop()
            await bus.aclose()
            await sm.aclose()

        assert report.ok is True
        assert len(report.steps) == 2
        assert all(s.ok for s in report.steps)

        for i, step_def in enumerate(PRODUCTION_QUALITY_CHAIN):
            assert report.steps[i].skill_path == step_def.org_path
            assert report.steps[i].skill_id == step_def.skill_id
            assert report.steps[i].summary.get("rule_version") == step_def.rule_version

        assert report.steps[0].summary.get("qc_pass") is True
        assert report.steps[0].summary.get("defect_units") == 0
        assert report.steps[1].summary.get("release_committed") is True
        assert report.steps[1].summary.get("qc_cleared") is True

        assert report.steps[0].summary.get("l2_reconcile", {}).get("grain") == "qc_batch_snapshot"
        assert report.steps[0].summary.get("exception_code") is None
        assert report.steps[1].summary.get("l2_reconcile", {}).get("grain") == "batch_release_snapshot"
        assert report.steps[1].summary.get("exception_code") is None

    asyncio.run(_run())

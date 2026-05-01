"""可观测性：zt_* 日志 extra 与编排器落盘。"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import tempfile
from typing import Any

import pytest

from config.settings import Settings
from core.event_bus import EventBus
import core.observability as observability_mod
from core.observability import (
    ZT_BUS_CHANNEL,
    ZT_CORRELATION_ID,
    ZT_DURATION_MS,
    ZT_GOAL_RUN_ID,
    ZT_OUTCOME,
    ZT_SKILL_ID,
    ZT_STEP_INDEX,
    ZT_SUBSCRIPTION_ID,
    ZT_TOPIC,
    ZhiweitongJsonFormatter,
    zt_log_extra,
)
from core.orchestrator import GoalReport, Orchestrator, PlanStep
from core.org_tree import OrgTree
from core.skill_base import SkillBase, minimal_skill_meta
from core.skill_registry import SkillRegistry
from core.state_manager import StateManager
from shared.models import EventEnvelope


@pytest.fixture
def tmp_db_url() -> str:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        p = f.name
    return f"sqlite+aiosqlite:///{p}"


def test_zt_log_extra_omits_unset_keys() -> None:
    assert zt_log_extra(goal_run_id="g1") == {ZT_GOAL_RUN_ID: "g1"}
    assert zt_log_extra(step_index=2, skill_id="s") == {ZT_STEP_INDEX: 2, ZT_SKILL_ID: "s"}
    assert zt_log_extra() == {}
    assert zt_log_extra(outcome="goal_ok", duration_ms=12.4) == {
        ZT_OUTCOME: "goal_ok",
        ZT_DURATION_MS: 12,
    }
    assert zt_log_extra(
        bus_channel="ch:1",
        subscription_id="sub-x",
        topic="/t/command",
    ) == {ZT_BUS_CHANNEL: "ch:1", ZT_SUBSCRIPTION_ID: "sub-x", ZT_TOPIC: "/t/command"}


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    SkillRegistry._reset_singleton_for_tests()
    yield
    SkillRegistry._reset_singleton_for_tests()


class _Leaf(SkillBase):
    META = minimal_skill_meta(
        skill_id="leaf_obs",
        name="obs",
        org_path="/智维通/城市乳业/快消板块",
    )

    async def execute(self, event: dict) -> dict:
        return {"ok": True}


def test_orchestrator_logs_carry_zt_goal_run_and_step(tmp_db_url: str, caplog: pytest.LogCaptureFixture) -> None:
    holder: dict[str, GoalReport] = {}

    async def _run() -> None:
        bus = EventBus()
        sm = StateManager(database_url=tmp_db_url)
        await sm.init_schema()
        reg = SkillRegistry()
        reg.register(_Leaf())

        class DummyKS:
            async def store(
                self,
                tags: list[str],
                content: str,
                metadata: dict[str, Any],
                *,
                org_path: str | None = None,
            ) -> str:
                return "doc-1"

        tree = OrgTree()
        tree.load_many({"/智维通/城市乳业": {}, "/智维通/城市乳业/快消板块": {}})

        async def plan(_: str) -> list[PlanStep]:
            return [
                PlanStep(
                    skill_path="/智维通/城市乳业/快消板块",
                    action="ping",
                    params={},
                ),
            ]

        async def cmd_worker(topic: str, event: dict[str, Any]) -> None:
            if not str(topic).endswith("/command"):
                return
            base = str(topic)[: -len("/command")]
            out = EventEnvelope(
                correlation_id=event["correlation_id"],
                org_path=event["org_path"],
                skill_id=event["skill_id"],
                payload={"ok": True, "summary": {}},
            )
            await bus.publish(f"{base}/result", out.model_dump())

        await bus.subscribe("/智维通/城市乳业*", cmd_worker)

        orch = Orchestrator(
            bus,
            sm,
            reg,
            DummyKS(),
            tree,
            settings=Settings(
                database_url=tmp_db_url,
                redis_url="",
                llm_api_key="",
                llm_base_url="https://example.invalid",
            ),
            plan_provider=plan,
            step_timeout=5.0,
        )
        try:
            holder["report"] = await orch.process_goal("obs test")
        finally:
            await bus.aclose()
            await sm.aclose()

    with caplog.at_level(logging.INFO, logger="core.orchestrator"):
        asyncio.run(_run())

    rep = holder["report"]
    orch_recs = [r for r in caplog.records if r.name == "core.orchestrator"]
    assert any(getattr(r, ZT_GOAL_RUN_ID, None) == rep.plan_id for r in orch_recs)
    step_recs = [r for r in orch_recs if getattr(r, ZT_STEP_INDEX, None) is not None]
    assert len(step_recs) >= 2
    assert any(getattr(r, ZT_CORRELATION_ID, None) for r in step_recs)
    assert any(getattr(r, ZT_SKILL_ID, None) == "leaf_obs" for r in step_recs)
    finished = [r for r in orch_recs if getattr(r, ZT_OUTCOME, None) == "goal_ok"]
    assert len(finished) == 1
    assert getattr(finished[0], ZT_DURATION_MS, 0) >= 0
    step_done = [r for r in orch_recs if getattr(r, ZT_OUTCOME, None) == "step_ok"]
    assert len(step_done) >= 1
    assert all(getattr(r, ZT_DURATION_MS, None) is not None for r in step_done)


def test_zhiweitong_json_formatter_includes_zt_fields() -> None:
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(ZhiweitongJsonFormatter())
    log = logging.getLogger("zt_json_unit")
    log.handlers.clear()
    log.addHandler(h)
    log.setLevel(logging.INFO)
    log.propagate = False
    log.info("hello", extra=zt_log_extra(goal_run_id="g-run", step_index=3, component="test"))
    line = buf.getvalue().strip()
    d = json.loads(line)
    assert d["message"] == "hello"
    assert d["level"] == "INFO"
    assert d["logger"] == "zt_json_unit"
    assert d["zt_goal_run_id"] == "g-run"
    assert d["zt_step_index"] == 3
    assert d["zt_component"] == "test"


def test_configure_zhiweitong_logging_json_stderr(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("ZHIWEITONG_LOG_JSON", "1")
    observability_mod._logging_configure_done = False
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_zhiweitong_json", False):
            root.removeHandler(h)
    try:
        observability_mod.configure_zhiweitong_logging(force=True)
        logging.getLogger("zt_probe").info("evt", extra=zt_log_extra(goal_run_id="g2"))
        err = capsys.readouterr().err
        found: dict | None = None
        for ln in err.strip().splitlines():
            try:
                d = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if d.get("zt_goal_run_id") == "g2" and d.get("logger") == "zt_probe":
                found = d
                break
        assert found is not None
        assert found["message"] == "evt"
    finally:
        for h in list(root.handlers):
            if getattr(h, "_zhiweitong_json", False):
                root.removeHandler(h)
        observability_mod._logging_configure_done = False

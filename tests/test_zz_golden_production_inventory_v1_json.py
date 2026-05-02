"""L1 黄金用例：主链 ``production-inventory-v1`` 五步脱敏 JSON + 沙盒结果子集断言。

与 ``shared/vertical_slices.PRODUCTION_INVENTORY_DEFAULT_PARAMS`` 及
``tests/test_zz_vertical_slice_production_inventory_chain.py`` 同一演示数据。
``test_zz_``：收集顺序在 ``test_phase2_department_skills`` 之后。

沙盒用例使用 ``enforce_coverage=False``：同进程内若模块已被其它测试 import，
单文件覆盖率会失真（见 ``core/sandbox`` 文档）；各叶岗 **≥90%** 仍由
``tests/test_phase2_department_skills.py`` 承担。
"""

from __future__ import annotations

import asyncio
import copy
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from core.sandbox import run_sandbox

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "golden" / "production_inventory_v1"
_COVERAGE_MODULES: tuple[str, ...] = (
    "skills.production_center.production_scheduling",
    "skills.production_center.material_requirement",
    "skills.warehouse_logistics.inbound_receiving",
    "skills.warehouse_logistics.inventory_management",
    "skills.warehouse_logistics.outbound_picking",
)


def _envelope(skill_id: str, org_path: str, correlation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "correlation_id": correlation_id,
        "org_path": org_path,
        "skill_id": skill_id,
        "payload": payload,
    }


def _assert_subset(actual: Any, subset: dict[str, Any]) -> None:
    assert isinstance(actual, dict), f"expected dict, got {type(actual)}"
    for k, v in subset.items():
        assert k in actual, f"missing key {k!r} in {actual!r}"
        if isinstance(v, dict) and isinstance(actual[k], dict):
            _assert_subset(actual[k], v)
        else:
            assert actual[k] == v, f"{k!r}: {actual[k]!r} != {v!r}"


def _skill_factory(step_index: int):
    def factory():
        if step_index == 0:
            from skills.production_center.production_scheduling import ProductionSchedulingSkill

            return ProductionSchedulingSkill()
        if step_index == 1:
            from skills.production_center.material_requirement import MaterialRequirementSkill

            return MaterialRequirementSkill()
        if step_index == 2:
            from skills.warehouse_logistics.inbound_receiving import InboundReceivingSkill

            return InboundReceivingSkill()
        if step_index == 3:
            from skills.warehouse_logistics.inventory_management import InventoryManagementSkill

            return InventoryManagementSkill()
        from skills.warehouse_logistics.outbound_picking import OutboundPickingSkill

        return OutboundPickingSkill()

    return factory


def _expected_from_case(case: dict[str, Any]) -> dict[str, Any]:
    exp = copy.deepcopy(case["expected_subset"])
    if case["step_index"] == 0:
        cid = str(case["correlation_id"])
        exp["batch_id"] = f"BATCH-{uuid.uuid5(uuid.NAMESPACE_DNS, cid).hex[:10].upper()}"
    return exp


def test_golden_pi_v1_fixture_params_match_vertical_slice_defaults() -> None:
    from shared.vertical_slices import PRODUCTION_INVENTORY_DEFAULT_PARAMS

    paths = sorted(_FIXTURE_DIR.glob("step_*.json"))
    assert len(paths) == 5, "手册 L1：主链至少 5 条脱敏黄金用例"
    for i, p in enumerate(paths):
        case = json.loads(p.read_text(encoding="utf-8"))
        assert case["params"] == PRODUCTION_INVENTORY_DEFAULT_PARAMS[i], p.name


@pytest.mark.parametrize(
    "fixture_path",
    sorted(_FIXTURE_DIR.glob("step_*.json")),
    ids=lambda p: p.stem,
)
def test_golden_pi_v1_sandbox_matches_fixture(fixture_path: Path) -> None:
    case = json.loads(fixture_path.read_text(encoding="utf-8"))
    step = int(case["step_index"])
    assert 0 <= step < len(_COVERAGE_MODULES)

    async def _run() -> None:
        rep = await run_sandbox(
            [
                _envelope(
                    str(case["skill_id"]),
                    str(case["org_path"]),
                    str(case["correlation_id"]),
                    dict(case["params"]),
                ),
            ],
            skill_factory=_skill_factory(step),
            coverage_skill_module=_COVERAGE_MODULES[step],
            enforce_coverage=False,
        )
        assert rep.passed == 1 and rep.failed == 0
        assert rep.cases[0].result is not None
        actual = rep.cases[0].result
        expected = _expected_from_case(case)
        _assert_subset(actual, expected)

    asyncio.run(_run())


_BOUNDARY_DIR = _FIXTURE_DIR / "boundary"


@pytest.mark.parametrize(
    "fixture_path",
    sorted(_BOUNDARY_DIR.glob("*.json")),
    ids=lambda p: p.stem,
)
def test_golden_pi_v1_boundary_sandbox_matches_fixture(fixture_path: Path) -> None:
    """主链边界：欠料、短收、补货信号、拣货短少、需求负值钳制等（与 ``docs/ops-runbook.md`` L2 码一致）。"""
    case = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert case.get("kind") == "boundary"
    step = int(case["step_index"])
    assert 0 <= step < len(_COVERAGE_MODULES)

    async def _run() -> None:
        rep = await run_sandbox(
            [
                _envelope(
                    str(case["skill_id"]),
                    str(case["org_path"]),
                    str(case["correlation_id"]),
                    dict(case["params"]),
                ),
            ],
            skill_factory=_skill_factory(step),
            coverage_skill_module=_COVERAGE_MODULES[step],
            enforce_coverage=False,
        )
        assert rep.passed == 1 and rep.failed == 0
        assert rep.cases[0].result is not None
        actual = rep.cases[0].result
        expected = _expected_from_case(case)
        _assert_subset(actual, expected)
        # 边界类告警应带人工兜底文案（排产钳制仍为正常路径，不设 manual）
        summ = actual.get("summary") if isinstance(actual.get("summary"), dict) else {}
        ex = summ.get("exception_code")
        if ex in (
            "W_MRP_NET_SHORTAGE",
            "W_INBOUND_SHORTFALL",
            "W_OUTBOUND_SHORTFALL",
            "I_REORDER_SUGGESTED",
        ):
            assert summ.get("manual_handoff"), f"{ex} 应对应非空 manual_handoff"

    asyncio.run(_run())

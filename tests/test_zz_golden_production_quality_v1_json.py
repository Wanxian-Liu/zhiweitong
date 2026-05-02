"""L1 黄金用例：生产补链 ``production-quality-v1``（质量检验 → 批次放行）脱敏 JSON + 沙盒断言。

与 ``shared.vertical_slices.PRODUCTION_QUALITY_DEFAULT_PARAMS`` 及
``tests/test_zz_vertical_slice_production_quality_chain.py`` 一致。
``test_zz_``：收集顺序在 ``test_phase2_department_skills`` 之后。

沙盒 ``enforce_coverage=False`` 理由同 ``test_zz_golden_production_inventory_v1_json``。
"""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any

import pytest

from core.sandbox import run_sandbox

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "golden" / "production_quality_v1"
_COVERAGE_MODULES: tuple[str, ...] = (
    "skills.production_center.quality_inspection",
    "skills.production_center.batch_release",
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
            from skills.production_center.quality_inspection import QualityInspectionSkill

            return QualityInspectionSkill()
        from skills.production_center.batch_release import BatchReleaseSkill

        return BatchReleaseSkill()

    return factory


def _expected_from_case(case: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(case["expected_subset"])


def test_golden_pq_fixture_params_match_vertical_slice_defaults() -> None:
    from shared.vertical_slices import PRODUCTION_QUALITY_DEFAULT_PARAMS

    paths = sorted(_FIXTURE_DIR.glob("step_*.json"))
    assert len(paths) == 2
    for i, p in enumerate(paths):
        case = json.loads(p.read_text(encoding="utf-8"))
        assert case["params"] == PRODUCTION_QUALITY_DEFAULT_PARAMS[i], p.name


@pytest.mark.parametrize(
    "fixture_path",
    sorted(_FIXTURE_DIR.glob("step_*.json")),
    ids=lambda p: p.stem,
)
def test_golden_pq_sandbox_matches_fixture(fixture_path: Path) -> None:
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
        _assert_subset(rep.cases[0].result, _expected_from_case(case))

    asyncio.run(_run())


_BOUNDARY_DIR = _FIXTURE_DIR / "boundary"


@pytest.mark.parametrize(
    "fixture_path",
    sorted(_BOUNDARY_DIR.glob("*.json")),
    ids=lambda p: p.stem,
)
def test_golden_pq_boundary_sandbox_matches_fixture(fixture_path: Path) -> None:
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
        _assert_subset(actual, _expected_from_case(case))
        summ = actual.get("summary") if isinstance(actual.get("summary"), dict) else {}
        ex = summ.get("exception_code")
        if ex in ("W_QC_BATCH_REJECT", "W_RELEASE_BLOCKED"):
            assert summ.get("manual_handoff")

    asyncio.run(_run())

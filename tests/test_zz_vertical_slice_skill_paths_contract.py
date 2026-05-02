"""垂直切片：registry 中 skill_py 路径须在仓库内存在。"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared import vertical_slices as vs

_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "chain_name,chain",
    [
        ("production_inventory", vs.PRODUCTION_INVENTORY_CHAIN),
        ("finance_ar_ap", vs.FINANCE_AR_AP_CHAIN),
        ("finance_trial_report", vs.FINANCE_TRIAL_REPORT_CHAIN),
        ("production_quality", vs.PRODUCTION_QUALITY_CHAIN),
        ("wh_cycle_transfer", vs.WH_CYCLE_TRANSFER_CHAIN),
    ],
)
def test_vertical_slice_skill_py_files_exist(
    chain_name: str, chain: tuple[vs.VerticalSliceStep, ...]
) -> None:
    for step in chain:
        path = _REPO_ROOT / step.skill_py
        assert path.is_file(), (
            f"{chain_name}: skill_py 不存在或不是文件: {step.skill_py!r} "
            f"(planner_action={step.planner_action!r})"
        )

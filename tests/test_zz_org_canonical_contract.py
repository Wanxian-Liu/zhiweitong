"""``shared.org_canonical`` 与已注册 Skill 模块 ``ORG_PATH`` 一致（防组织树漂移）。

``test_zz_``：须在 Phase 2 沙盒等用例之后运行，避免提前 import Skill 模块导致
``run_sandbox`` 内 coverage 低估（见 ``core/sandbox.py`` 说明）。
"""

from __future__ import annotations

import importlib

import pytest

from core.org_tree import canonical_org_tree
from shared.org_canonical import CANONICAL_ORG_PATHS

# 与仓库内实现叶岗/主管一一对应；新增 Skill 时同步此表与 ``CANONICAL_ORG_PATHS``。
_SKILL_MODULES: tuple[str, ...] = (
    "skills.quick_consumption.supervisor",
    "skills.quick_consumption.b2c_online_operation",
    "skills.quick_consumption.order_processing",
    "skills.quick_consumption.delivery_coordination",
    "skills.finance_center.receivable_reconciliation",
    "skills.finance_center.payable_reconciliation",
    "skills.production_center.production_scheduling",
    "skills.production_center.material_requirement",
    "skills.warehouse_logistics.inbound_receiving",
    "skills.warehouse_logistics.inventory_management",
    "skills.warehouse_logistics.outbound_picking",
    "skills.general_office.audit_review",
)


def _org_path(module: str) -> str:
    m = importlib.import_module(module)
    return str(m.ORG_PATH)


def test_canonical_paths_match_skill_modules() -> None:
    from_skill = {_org_path(mod) for mod in _SKILL_MODULES}
    canonical = set(CANONICAL_ORG_PATHS)
    assert from_skill == canonical, (
        f"drift: only_in_skills={from_skill - canonical!r} "
        f"only_in_canonical={canonical - from_skill!r}"
    )


def test_canonical_org_tree_contains_all_paths() -> None:
    tree = canonical_org_tree()
    for p in CANONICAL_ORG_PATHS:
        assert tree.get_meta(p) == {}


def test_canonical_paths_are_unique() -> None:
    assert len(CANONICAL_ORG_PATHS) == len(set(CANONICAL_ORG_PATHS))


@pytest.mark.parametrize("mod", _SKILL_MODULES)
def test_each_listed_skill_module_exports_org_path(mod: str) -> None:
    assert _org_path(mod).startswith("/智维通/城市乳业/")

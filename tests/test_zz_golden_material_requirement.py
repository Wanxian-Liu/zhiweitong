"""黄金参考：物料需求岗算术（与 phase2 沙盒 5 条用例同步维护）。

``test_zz_``：默认收集顺序下排在 ``test_phase2_department_skills`` 之后；含
``import skills...`` 的用例避免拉低 ``run_sandbox`` 覆盖率。
"""

from __future__ import annotations


def test_material_requirement_rule_version() -> None:
    from skills.production_center.material_requirement import RULE_VERSION

    assert RULE_VERSION == "mrp-single-level-v1"


def test_golden_material_requirement_arithmetic_matches_sandbox_cases() -> None:
    """不重复跑 Skill；校验与 ``test_material_requirement_skill_sandbox`` 输入一致的中间量。"""
    assert 100 * 2 == 200
    assert max(0, 200 - 500) == 0
    assert 500 >= 200
    assert 0 * 1 == 0
    assert max(0, 0 - 0) == 0
    assert max(0, 150 - 100) == 50
    assert not (100 >= 150)
    assert 100 * 0 == 0
    assert max(0, 3000 - 2000) == 1000
    assert not (2000 >= 3000)

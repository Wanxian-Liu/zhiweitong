"""仓储补链垂直切片注册表与各 Skill 模块常量一致。"""

from __future__ import annotations

from shared.vertical_slices import WH_CYCLE_TRANSFER_CHAIN, WH_CYCLE_TRANSFER_DEFAULT_PARAMS


def test_wh_cycle_transfer_default_params_aligns_with_chain() -> None:
    assert len(WH_CYCLE_TRANSFER_DEFAULT_PARAMS) == len(WH_CYCLE_TRANSFER_CHAIN)


def test_wh_cycle_transfer_chain_matches_skill_modules() -> None:
    from skills.warehouse_logistics.cycle_count import ORG_PATH as cy_org, RULE_VERSION as cy_rv, SKILL_ID as cy_id
    from skills.warehouse_logistics.stock_transfer import ORG_PATH as tr_org, RULE_VERSION as tr_rv, SKILL_ID as tr_id

    expected = [
        (cy_org, cy_id, cy_rv),
        (tr_org, tr_id, tr_rv),
    ]
    for i, (step, (org, sid, rv)) in enumerate(zip(WH_CYCLE_TRANSFER_CHAIN, expected, strict=True)):
        assert step.step_index == i
        assert step.org_path == org
        assert step.skill_id == sid
        assert step.rule_version == rv

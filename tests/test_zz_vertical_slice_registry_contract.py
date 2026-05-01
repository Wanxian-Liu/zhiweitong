"""垂直切片注册表与各 Skill 模块常量一致（防 org_path / rule_version 漂移）。

``test_zz_``：排在 phase2 沙盒之后；在测试函数内 import skills。
"""

from __future__ import annotations

from shared.vertical_slices import (
    PRODUCTION_INVENTORY_CHAIN,
    PRODUCTION_INVENTORY_DEFAULT_PARAMS,
)


def test_production_inventory_default_params_aligns_with_chain() -> None:
    assert len(PRODUCTION_INVENTORY_DEFAULT_PARAMS) == len(PRODUCTION_INVENTORY_CHAIN)


def test_production_inventory_chain_matches_skill_modules() -> None:
    from skills.production_center.material_requirement import (
        ORG_PATH as mrp_org,
        RULE_VERSION as mrp_rv,
        SKILL_ID as mrp_id,
    )
    from skills.production_center.production_scheduling import (
        ORG_PATH as sched_org,
        RULE_VERSION as sched_rv,
        SKILL_ID as sched_id,
    )
    from skills.warehouse_logistics.inbound_receiving import (
        ORG_PATH as in_org,
        RULE_VERSION as in_rv,
        SKILL_ID as in_id,
    )
    from skills.warehouse_logistics.inventory_management import (
        ORG_PATH as inv_org,
        RULE_VERSION as inv_rv,
        SKILL_ID as inv_id,
    )
    from skills.warehouse_logistics.outbound_picking import (
        ORG_PATH as out_org,
        RULE_VERSION as out_rv,
        SKILL_ID as out_id,
    )

    expected = [
        (sched_org, sched_id, sched_rv),
        (mrp_org, mrp_id, mrp_rv),
        (in_org, in_id, in_rv),
        (inv_org, inv_id, inv_rv),
        (out_org, out_id, out_rv),
    ]
    for i, (step, (org, sid, rv)) in enumerate(zip(PRODUCTION_INVENTORY_CHAIN, expected, strict=True)):
        assert step.step_index == i
        assert step.org_path == org
        assert step.skill_id == sid
        assert step.rule_version == rv

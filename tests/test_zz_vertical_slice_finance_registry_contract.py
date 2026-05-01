"""财务垂直切片注册表与各 Skill 模块常量一致。"""

from __future__ import annotations

from shared.vertical_slices import FINANCE_AR_AP_CHAIN, FINANCE_AR_AP_DEFAULT_PARAMS


def test_finance_ar_ap_default_params_aligns_with_chain() -> None:
    assert len(FINANCE_AR_AP_DEFAULT_PARAMS) == len(FINANCE_AR_AP_CHAIN)


def test_finance_ar_ap_chain_matches_skill_modules() -> None:
    from skills.finance_center.payable_reconciliation import (
        ORG_PATH as ap_org,
        RULE_VERSION as ap_rv,
        SKILL_ID as ap_id,
    )
    from skills.finance_center.receivable_reconciliation import (
        ORG_PATH as ar_org,
        RULE_VERSION as ar_rv,
        SKILL_ID as ar_id,
    )

    expected = [
        (ar_org, ar_id, ar_rv),
        (ap_org, ap_id, ap_rv),
    ]
    for i, (step, (org, sid, rv)) in enumerate(zip(FINANCE_AR_AP_CHAIN, expected, strict=True)):
        assert step.step_index == i
        assert step.org_path == org
        assert step.skill_id == sid
        assert step.rule_version == rv

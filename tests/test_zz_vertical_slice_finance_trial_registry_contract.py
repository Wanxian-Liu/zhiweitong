"""财务试算→报表切片注册表与各 Skill 模块常量一致。"""

from __future__ import annotations

from shared.vertical_slices import FINANCE_TRIAL_REPORT_CHAIN, FINANCE_TRIAL_REPORT_DEFAULT_PARAMS


def test_finance_trial_report_default_params_aligns_with_chain() -> None:
    assert len(FINANCE_TRIAL_REPORT_DEFAULT_PARAMS) == len(FINANCE_TRIAL_REPORT_CHAIN)


def test_finance_trial_report_chain_matches_skill_modules() -> None:
    from skills.finance_center.report_snapshot import ORG_PATH as rs_org, RULE_VERSION as rs_rv, SKILL_ID as rs_id
    from skills.finance_center.trial_balance import ORG_PATH as tb_org, RULE_VERSION as tb_rv, SKILL_ID as tb_id

    expected = [
        (tb_org, tb_id, tb_rv),
        (rs_org, rs_id, rs_rv),
    ]
    for i, (step, (org, sid, rv)) in enumerate(zip(FINANCE_TRIAL_REPORT_CHAIN, expected, strict=True)):
        assert step.step_index == i
        assert step.org_path == org
        assert step.skill_id == sid
        assert step.rule_version == rv

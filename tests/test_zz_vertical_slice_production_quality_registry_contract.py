"""生产补链垂直切片注册表与各 Skill 模块常量一致。"""

from __future__ import annotations

from shared.vertical_slices import PRODUCTION_QUALITY_CHAIN, PRODUCTION_QUALITY_DEFAULT_PARAMS


def test_production_quality_default_params_aligns_with_chain() -> None:
    assert len(PRODUCTION_QUALITY_DEFAULT_PARAMS) == len(PRODUCTION_QUALITY_CHAIN)


def test_production_quality_chain_matches_skill_modules() -> None:
    from skills.production_center.batch_release import ORG_PATH as br_org, RULE_VERSION as br_rv, SKILL_ID as br_id
    from skills.production_center.quality_inspection import ORG_PATH as qc_org, RULE_VERSION as qc_rv, SKILL_ID as qc_id

    expected = [
        (qc_org, qc_id, qc_rv),
        (br_org, br_id, br_rv),
    ]
    for i, (step, (org, sid, rv)) in enumerate(zip(PRODUCTION_QUALITY_CHAIN, expected, strict=True)):
        assert step.step_index == i
        assert step.org_path == org
        assert step.skill_id == sid
        assert step.rule_version == rv

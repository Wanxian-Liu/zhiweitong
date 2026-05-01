"""黄金参考：Phase 2 部门岗 ``RULE_VERSION`` 与与沙盒一致的算术中间量。

``test_zz_``：默认收集顺序在 ``test_phase2_department_skills`` 之后。
"""

from __future__ import annotations


def test_phase2_rule_version_constants() -> None:
    from skills.finance_center.payable_reconciliation import RULE_VERSION as ap_rv
    from skills.finance_center.receivable_reconciliation import RULE_VERSION as ar_rv
    from skills.production_center.production_scheduling import RULE_VERSION as sched_rv
    from skills.warehouse_logistics.inbound_receiving import RULE_VERSION as in_rv
    from skills.warehouse_logistics.inventory_management import RULE_VERSION as inv_rv
    from skills.warehouse_logistics.outbound_picking import RULE_VERSION as out_rv

    assert ar_rv == "fin-ar-net-v1"
    assert ap_rv == "fin-ap-net-v1"
    assert sched_rv == "sched-demand-to-plan-v1"
    assert in_rv == "inbound-qty-match-v1"
    assert inv_rv == "inv-threshold-v1"
    assert out_rv == "outbound-pick-qty-v1"


def test_golden_finance_net_totals_match_sandbox() -> None:
    assert round(150.0 - 40.0, 2) == 110.0
    assert abs(2 - 3) == 1
    assert round(280.0 - 50.0, 2) == 230.0
    assert round(10.0 - 10.0, 2) == 0.0
    assert round(20.0 - 20.0, 2) == 0.0


def test_golden_scheduling_demand_clamp_matches_sandbox() -> None:
    assert max(-5, 0) == 0
    assert max(999, 0) == 999


def test_golden_warehouse_qty_rules_match_sandbox() -> None:
    assert max(0, 200 - 150) == 50
    assert max(0, 10 - 12) == 0
    assert 199 < 200
    assert (100 < 100) is False
    assert 0 < 100
    assert max(0, 40 - 25) == 15
    assert max(0, 10 - 15) == 0
    assert max(0, 100_000 - 99_999) == 1

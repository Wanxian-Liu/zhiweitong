"""Phase 2 department skills — sandbox coverage (deferred imports for tracing)."""

from __future__ import annotations

import asyncio


from core.sandbox import run_sandbox


def _envelope(skill_id: str, org_path: str, correlation_id: str, payload: dict) -> dict:
    return {
        "schema_version": "1",
        "correlation_id": correlation_id,
        "org_path": org_path,
        "skill_id": skill_id,
        "payload": payload,
    }


def test_receivable_reconciliation_skill_sandbox() -> None:
    async def _run() -> None:
        def factory():
            from skills.finance_center.receivable_reconciliation import ReceivableReconciliationSkill

            return ReceivableReconciliationSkill()

        rep = await run_sandbox(
            [
                _envelope(
                    "fin_receivable_reconciliation",
                    "/智维通/城市乳业/财务中心/应收对账",
                    "c1",
                    {"invoices": [100.0, 50.0], "payments": [40.0, 0.0]},
                ),
                _envelope(
                    "fin_receivable_reconciliation",
                    "/智维通/城市乳业/财务中心/应收对账",
                    "c1b",
                    {},
                ),
                _envelope(
                    "fin_receivable_reconciliation",
                    "/智维通/城市乳业/财务中心/应收对账",
                    "c1c",
                    {"invoices": [1.0, 2.0], "payments": [3.0, 4.0, 5.0]},
                ),
                _envelope(
                    "fin_receivable_reconciliation",
                    "/智维通/城市乳业/财务中心/应收对账",
                    "c1d",
                    {"invoices": [10.0], "payments": [10.0]},
                ),
                _envelope(
                    "fin_receivable_reconciliation",
                    "/智维通/城市乳业/财务中心/应收对账",
                    "c1e",
                    {"invoices": [5.0, 5.0], "payments": [3.0, 7.0]},
                ),
            ],
            skill_factory=factory,
            coverage_skill_module="skills.finance_center.receivable_reconciliation",
        )
        rv = "fin-ar-net-v1"
        assert rep.passed == 5 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["receivable_total"] == 110.0
        assert rep.cases[0].result["summary"]["exception_code"] is None
        assert rep.cases[1].result["rule_version"] == rv
        assert rep.cases[1].result["receivable_total"] == 0.0
        assert rep.cases[2].result["discrepancy_count"] == 1
        assert rep.cases[2].result["summary"]["exception_code"] == "W_FIN_AR_LINE_MISMATCH"
        assert rep.cases[3].result["receivable_total"] == 0.0
        assert rep.cases[3].result["discrepancy_count"] == 0
        assert rep.cases[4].result["receivable_total"] == 0.0
        assert rep.cases[4].result["discrepancy_count"] == 0

    asyncio.run(_run())


def test_payable_reconciliation_skill_sandbox() -> None:
    async def _run() -> None:
        def factory():
            from skills.finance_center.payable_reconciliation import PayableReconciliationSkill

            return PayableReconciliationSkill()

        rep = await run_sandbox(
            [
                _envelope(
                    "fin_payable_reconciliation",
                    "/智维通/城市乳业/财务中心/应付对账",
                    "p1",
                    {"bills": [200.0, 80.0], "payments": [50.0, 0.0]},
                ),
                _envelope(
                    "fin_payable_reconciliation",
                    "/智维通/城市乳业/财务中心/应付对账",
                    "p1b",
                    {},
                ),
                _envelope(
                    "fin_payable_reconciliation",
                    "/智维通/城市乳业/财务中心/应付对账",
                    "p1c",
                    {"bills": [10.0, 20.0], "payments": [1.0, 2.0, 3.0]},
                ),
                _envelope(
                    "fin_payable_reconciliation",
                    "/智维通/城市乳业/财务中心/应付对账",
                    "p1d",
                    {"bills": [100.0], "payments": [100.0]},
                ),
                _envelope(
                    "fin_payable_reconciliation",
                    "/智维通/城市乳业/财务中心/应付对账",
                    "p1e",
                    {"bills": [12.0, 8.0], "payments": [5.0, 15.0]},
                ),
            ],
            skill_factory=factory,
            coverage_skill_module="skills.finance_center.payable_reconciliation",
        )
        rv = "fin-ap-net-v1"
        assert rep.passed == 5 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["payable_total"] == 230.0
        assert rep.cases[0].result["summary"]["exception_code"] is None
        assert rep.cases[1].result["rule_version"] == rv
        assert rep.cases[1].result["payable_total"] == 0.0
        assert rep.cases[2].result["discrepancy_count"] == 1
        assert rep.cases[2].result["summary"]["exception_code"] == "W_FIN_AP_LINE_MISMATCH"
        assert rep.cases[3].result["payable_total"] == 0.0
        assert rep.cases[3].result["discrepancy_count"] == 0
        assert rep.cases[4].result["payable_total"] == 0.0
        assert rep.cases[4].result["discrepancy_count"] == 0

    asyncio.run(_run())


def test_production_scheduling_skill_sandbox() -> None:
    async def _run() -> None:
        def factory():
            from skills.production_center.production_scheduling import ProductionSchedulingSkill

            return ProductionSchedulingSkill()

        rep = await run_sandbox(
            [
                _envelope(
                    "prod_production_scheduling",
                    "/智维通/城市乳业/生产中心/排产",
                    "c2",
                    {"demand_units": 500, "line_id": "LINE-B2"},
                ),
                _envelope(
                    "prod_production_scheduling",
                    "/智维通/城市乳业/生产中心/排产",
                    "c2b",
                    {},
                ),
                _envelope(
                    "prod_production_scheduling",
                    "/智维通/城市乳业/生产中心/排产",
                    "c2c",
                    {"demand_units": -5, "line_id": "LINE-Z"},
                ),
                _envelope(
                    "prod_production_scheduling",
                    "/智维通/城市乳业/生产中心/排产",
                    "c2d",
                    {"demand_units": 1, "line_id": "LINE-X"},
                ),
                _envelope(
                    "prod_production_scheduling",
                    "/智维通/城市乳业/生产中心/排产",
                    "c2e",
                    {"demand_units": 999},
                ),
            ],
            skill_factory=factory,
            coverage_skill_module="skills.production_center.production_scheduling",
        )
        rv = "sched-demand-to-plan-v1"
        assert rep.passed == 5 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["planned_units"] == 500
        assert rep.cases[0].result["line_id"] == "LINE-B2"
        assert rep.cases[1].result["rule_version"] == rv
        assert rep.cases[1].result["planned_units"] == 0
        assert rep.cases[1].result["line_id"] == "LINE-A1"
        assert rep.cases[2].result["planned_units"] == 0
        assert rep.cases[2].result["line_id"] == "LINE-Z"
        assert rep.cases[3].result["planned_units"] == 1
        assert rep.cases[3].result["line_id"] == "LINE-X"
        assert rep.cases[4].result["planned_units"] == 999
        assert rep.cases[4].result["line_id"] == "LINE-A1"
        assert rep.cases[0].result["summary"]["l2_reconcile"]["grain"] == "production_plan_snapshot"
        assert rep.cases[0].result["summary"]["exception_code"] is None

    asyncio.run(_run())


def test_material_requirement_skill_sandbox() -> None:
    async def _run() -> None:
        def factory():
            from skills.production_center.material_requirement import MaterialRequirementSkill

            return MaterialRequirementSkill()

        rep = await run_sandbox(
            [
                _envelope(
                    "prod_material_requirement",
                    "/智维通/城市乳业/生产中心/物料需求",
                    "m1",
                    {
                        "fg_sku": "FG-MILK-1L",
                        "planned_fg_units": 100,
                        "raw_per_fg": 2,
                        "raw_stock": 500,
                    },
                ),
                _envelope(
                    "prod_material_requirement",
                    "/智维通/城市乳业/生产中心/物料需求",
                    "m1b",
                    {},
                ),
                _envelope(
                    "prod_material_requirement",
                    "/智维通/城市乳业/生产中心/物料需求",
                    "m1c",
                    {"planned_fg_units": 50, "raw_per_fg": 3, "raw_stock": 100},
                ),
                _envelope(
                    "prod_material_requirement",
                    "/智维通/城市乳业/生产中心/物料需求",
                    "m1d",
                    {"planned_fg_units": 100, "raw_per_fg": 0, "raw_stock": 0},
                ),
                _envelope(
                    "prod_material_requirement",
                    "/智维通/城市乳业/生产中心/物料需求",
                    "m1e",
                    {"planned_fg_units": 1000, "raw_per_fg": 3, "raw_stock": 2000},
                ),
            ],
            skill_factory=factory,
            coverage_skill_module="skills.production_center.material_requirement",
        )
        assert rep.passed == 5 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        rv = "mrp-single-level-v1"
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["required_raw_qty"] == 200
        assert rep.cases[0].result["shortage_qty"] == 0
        assert rep.cases[0].result["mrp_feasible"] is True
        assert rep.cases[1].result["rule_version"] == rv
        assert rep.cases[1].result["planned_fg_units"] == 0
        assert rep.cases[1].result["required_raw_qty"] == 0
        assert rep.cases[2].result["rule_version"] == rv
        assert rep.cases[2].result["required_raw_qty"] == 150
        assert rep.cases[2].result["shortage_qty"] == 50
        assert rep.cases[2].result["mrp_feasible"] is False
        assert rep.cases[2].result["summary"]["exception_code"] == "W_MRP_NET_SHORTAGE"
        assert rep.cases[2].result["summary"]["manual_handoff"]
        assert rep.cases[3].result["required_raw_qty"] == 0
        assert rep.cases[3].result["mrp_feasible"] is True
        assert rep.cases[3].result["summary"]["exception_code"] is None
        assert rep.cases[4].result["required_raw_qty"] == 3000
        assert rep.cases[4].result["shortage_qty"] == 1000
        assert rep.cases[4].result["mrp_feasible"] is False
        assert rep.cases[4].result["summary"]["exception_code"] == "W_MRP_NET_SHORTAGE"

    asyncio.run(_run())


def test_inventory_management_skill_sandbox() -> None:
    async def _run() -> None:
        def factory():
            from skills.warehouse_logistics.inventory_management import InventoryManagementSkill

            return InventoryManagementSkill()

        rep = await run_sandbox(
            [
                _envelope(
                    "wh_inventory_management",
                    "/智维通/城市乳业/仓储物流/库存管理",
                    "c3",
                    {"sku": "SKU-X", "quantity_on_hand": 30, "reorder_threshold": 100},
                ),
                _envelope(
                    "wh_inventory_management",
                    "/智维通/城市乳业/仓储物流/库存管理",
                    "c3b",
                    {"quantity_on_hand": 500, "reorder_threshold": 100},
                ),
                _envelope(
                    "wh_inventory_management",
                    "/智维通/城市乳业/仓储物流/库存管理",
                    "c3c",
                    {"sku": "SKU-EQ", "quantity_on_hand": 100, "reorder_threshold": 100},
                ),
                _envelope(
                    "wh_inventory_management",
                    "/智维通/城市乳业/仓储物流/库存管理",
                    "c3d",
                    {"sku": "SKU-EDGE", "quantity_on_hand": 199, "reorder_threshold": 200},
                ),
                _envelope(
                    "wh_inventory_management",
                    "/智维通/城市乳业/仓储物流/库存管理",
                    "c3e",
                    {},
                ),
            ],
            skill_factory=factory,
            coverage_skill_module="skills.warehouse_logistics.inventory_management",
        )
        rv = "inv-threshold-v1"
        assert rep.passed == 5 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["reorder_suggested"] is True
        assert rep.cases[0].result["summary"]["exception_code"] == "I_REORDER_SUGGESTED"
        assert rep.cases[1].result["rule_version"] == rv
        assert rep.cases[1].result["reorder_suggested"] is False
        assert rep.cases[1].result["summary"]["exception_code"] is None
        assert rep.cases[2].result["reorder_suggested"] is False
        assert rep.cases[2].result["summary"]["exception_code"] is None
        assert rep.cases[3].result["reorder_suggested"] is True
        assert rep.cases[3].result["summary"]["exception_code"] == "I_REORDER_SUGGESTED"
        assert rep.cases[4].result["sku"] == "SKU-MILK-1L"
        assert rep.cases[4].result["quantity_on_hand"] == 0
        assert rep.cases[4].result["reorder_suggested"] is True
        assert rep.cases[4].result["summary"]["exception_code"] == "I_REORDER_SUGGESTED"

    asyncio.run(_run())


def test_inbound_receiving_skill_sandbox() -> None:
    async def _run() -> None:
        def factory():
            from skills.warehouse_logistics.inbound_receiving import InboundReceivingSkill

            return InboundReceivingSkill()

        rep = await run_sandbox(
            [
                _envelope(
                    "wh_inbound_receiving",
                    "/智维通/城市乳业/仓储物流/入库验收",
                    "w1",
                    {"sku": "SKU-MILK", "ordered_qty": 100, "received_qty": 100},
                ),
                _envelope(
                    "wh_inbound_receiving",
                    "/智维通/城市乳业/仓储物流/入库验收",
                    "w1b",
                    {},
                ),
                _envelope(
                    "wh_inbound_receiving",
                    "/智维通/城市乳业/仓储物流/入库验收",
                    "w1c",
                    {"ordered_qty": 200, "received_qty": 150},
                ),
                _envelope(
                    "wh_inbound_receiving",
                    "/智维通/城市乳业/仓储物流/入库验收",
                    "w1d",
                    {"ordered_qty": 0, "received_qty": 0},
                ),
                _envelope(
                    "wh_inbound_receiving",
                    "/智维通/城市乳业/仓储物流/入库验收",
                    "w1e",
                    {"ordered_qty": 10, "received_qty": 12},
                ),
            ],
            skill_factory=factory,
            coverage_skill_module="skills.warehouse_logistics.inbound_receiving",
        )
        rv = "inbound-qty-match-v1"
        assert rep.passed == 5 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["shortfall"] == 0
        assert rep.cases[0].result["receipt_complete"] is True
        assert rep.cases[1].result["rule_version"] == rv
        assert rep.cases[1].result["ordered_qty"] == 0
        assert rep.cases[1].result["received_qty"] == 0
        assert rep.cases[2].result["shortfall"] == 50
        assert rep.cases[2].result["receipt_complete"] is False
        assert rep.cases[2].result["summary"]["exception_code"] == "W_INBOUND_SHORTFALL"
        assert rep.cases[3].result["receipt_complete"] is True
        assert rep.cases[3].result["summary"]["exception_code"] is None
        assert rep.cases[4].result["shortfall"] == 0
        assert rep.cases[4].result["receipt_complete"] is True
        assert rep.cases[4].result["summary"]["exception_code"] is None
        assert rep.cases[0].result["summary"]["exception_code"] is None

    asyncio.run(_run())


def test_outbound_picking_skill_sandbox() -> None:
    async def _run() -> None:
        def factory():
            from skills.warehouse_logistics.outbound_picking import OutboundPickingSkill

            return OutboundPickingSkill()

        rep = await run_sandbox(
            [
                _envelope(
                    "wh_outbound_picking",
                    "/智维通/城市乳业/仓储物流/出库拣货",
                    "o1",
                    {"sku": "SKU-YOG", "requested_qty": 60, "picked_qty": 60},
                ),
                _envelope(
                    "wh_outbound_picking",
                    "/智维通/城市乳业/仓储物流/出库拣货",
                    "o1b",
                    {},
                ),
                _envelope(
                    "wh_outbound_picking",
                    "/智维通/城市乳业/仓储物流/出库拣货",
                    "o1c",
                    {"requested_qty": 40, "picked_qty": 25},
                ),
                _envelope(
                    "wh_outbound_picking",
                    "/智维通/城市乳业/仓储物流/出库拣货",
                    "o1d",
                    {"requested_qty": 10, "picked_qty": 15},
                ),
                _envelope(
                    "wh_outbound_picking",
                    "/智维通/城市乳业/仓储物流/出库拣货",
                    "o1e",
                    {"requested_qty": 100_000, "picked_qty": 99_999},
                ),
            ],
            skill_factory=factory,
            coverage_skill_module="skills.warehouse_logistics.outbound_picking",
        )
        rv = "outbound-pick-qty-v1"
        assert rep.passed == 5 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["shortfall"] == 0
        assert rep.cases[0].result["pick_complete"] is True
        assert rep.cases[1].result["rule_version"] == rv
        assert rep.cases[1].result["requested_qty"] == 0
        assert rep.cases[1].result["picked_qty"] == 0
        assert rep.cases[2].result["shortfall"] == 15
        assert rep.cases[2].result["pick_complete"] is False
        assert rep.cases[3].result["shortfall"] == 0
        assert rep.cases[3].result["pick_complete"] is True
        assert rep.cases[4].result["shortfall"] == 1
        assert rep.cases[4].result["pick_complete"] is False
        assert rep.cases[0].result["summary"]["exception_code"] is None
        assert rep.cases[1].result["summary"]["exception_code"] is None
        assert rep.cases[2].result["summary"]["exception_code"] == "W_OUTBOUND_SHORTFALL"
        assert rep.cases[3].result["summary"]["exception_code"] is None
        assert rep.cases[4].result["summary"]["exception_code"] == "W_OUTBOUND_SHORTFALL"

    asyncio.run(_run())


def test_zz_phase2_org_path_exports() -> None:
    """Smoke last: avoid importing department modules before sandbox coverage tests."""
    from skills.finance_center.payable_reconciliation import ORG_PATH as p0
    from skills.finance_center.receivable_reconciliation import ORG_PATH as p1
    from skills.production_center.material_requirement import ORG_PATH as p2
    from skills.production_center.production_scheduling import ORG_PATH as p2b
    from skills.warehouse_logistics.inbound_receiving import ORG_PATH as p3
    from skills.warehouse_logistics.inventory_management import ORG_PATH as p4
    from skills.warehouse_logistics.outbound_picking import ORG_PATH as p5

    assert p0 == "/智维通/城市乳业/财务中心/应付对账"
    assert p1 == "/智维通/城市乳业/财务中心/应收对账"
    assert p2 == "/智维通/城市乳业/生产中心/物料需求"
    assert p2b == "/智维通/城市乳业/生产中心/排产"
    assert p3 == "/智维通/城市乳业/仓储物流/入库验收"
    assert p4 == "/智维通/城市乳业/仓储物流/库存管理"
    assert p5 == "/智维通/城市乳业/仓储物流/出库拣货"

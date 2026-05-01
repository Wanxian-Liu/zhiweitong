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
                    {"invoices": [100.0, 50.0], "payments": [40.0]},
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
            ],
            skill_factory=factory,
            coverage_skill_module="skills.finance_center.receivable_reconciliation",
        )
        assert rep.passed == 3 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["receivable_total"] == 110.0
        assert rep.cases[1].result["receivable_total"] == 0.0
        assert rep.cases[2].result["discrepancy_count"] == 1

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
            ],
            skill_factory=factory,
            coverage_skill_module="skills.production_center.production_scheduling",
        )
        assert rep.passed == 2 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["planned_units"] == 500
        assert rep.cases[0].result["line_id"] == "LINE-B2"
        assert rep.cases[1].result["planned_units"] == 0
        assert rep.cases[1].result["line_id"] == "LINE-A1"

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
            ],
            skill_factory=factory,
            coverage_skill_module="skills.warehouse_logistics.inventory_management",
        )
        assert rep.passed == 2 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["reorder_suggested"] is True
        assert rep.cases[1].result["reorder_suggested"] is False

    asyncio.run(_run())


def test_zz_phase2_org_path_exports() -> None:
    """Smoke last: avoid importing department modules before sandbox coverage tests."""
    from skills.finance_center.receivable_reconciliation import ORG_PATH as p1
    from skills.production_center.production_scheduling import ORG_PATH as p2
    from skills.warehouse_logistics.inventory_management import ORG_PATH as p3

    assert p1 == "/智维通/城市乳业/财务中心/应收对账"
    assert p2 == "/智维通/城市乳业/生产中心/排产"
    assert p3 == "/智维通/城市乳业/仓储物流/库存管理"

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
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"receivable_total": 200.0}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.finance_center.receivable_reconciliation import ReceivableReconciliationSkill

            return ReceivableReconciliationSkill()

        try:
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
                    _envelope(
                        "fin_receivable_reconciliation",
                        "/智维通/城市乳业/财务中心/应收对账",
                        "c1f",
                        {
                            "invoices": [10.0, 20.0],
                            "payments": [5.0, 5.0],
                            "external_receivable_total_url": "http://erp/ar",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "fin_receivable_reconciliation",
                        "/智维通/城市乳业/财务中心/应收对账",
                        "c1g",
                        {
                            "invoices": [100.0, 50.0],
                            "payments": [40.0, 0.0],
                            "external_receivable_total_url": "http://erp/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.finance_center.receivable_reconciliation",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "fin-ar-net-v1"
        assert rep.passed == 7 and rep.failed == 0
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
        assert rep.cases[5].result["receivable_total"] == 200.0
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["receivable_total"] == 110.0
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_payable_reconciliation_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"payable_total": 300.0}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.finance_center.payable_reconciliation import PayableReconciliationSkill

            return PayableReconciliationSkill()

        try:
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
                    _envelope(
                        "fin_payable_reconciliation",
                        "/智维通/城市乳业/财务中心/应付对账",
                        "p1f",
                        {
                            "bills": [50.0, 50.0],
                            "payments": [10.0, 10.0],
                            "external_payable_total_url": "http://erp/ap",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "fin_payable_reconciliation",
                        "/智维通/城市乳业/财务中心/应付对账",
                        "p1g",
                        {
                            "bills": [200.0, 80.0],
                            "payments": [50.0, 0.0],
                            "external_payable_total_url": "http://erp/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.finance_center.payable_reconciliation",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "fin-ap-net-v1"
        assert rep.passed == 7 and rep.failed == 0
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
        assert rep.cases[5].result["payable_total"] == 300.0
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["payable_total"] == 230.0
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_trial_balance_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            if "/debit" in url:
                return IntegrationGetResult(True, 200, {"debit_total": 1500.0}, 1, None)
            if "/credit" in url:
                return IntegrationGetResult(True, 200, {"credit_total": 1500.0}, 1, None)
            return IntegrationGetResult(True, 200, {"debit_total": 0.0}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.finance_center.trial_balance import TrialBalanceSkill

            return TrialBalanceSkill()

        try:
            rep = await run_sandbox(
                [
                    _envelope(
                        "fin_trial_balance",
                        "/智维通/城市乳业/财务中心/试算平衡",
                        "tb1",
                        {"debits": [1000.0, 500.0], "credits": [800.0, 700.0]},
                    ),
                    _envelope(
                        "fin_trial_balance",
                        "/智维通/城市乳业/财务中心/试算平衡",
                        "tb1b",
                        {},
                    ),
                    _envelope(
                        "fin_trial_balance",
                        "/智维通/城市乳业/财务中心/试算平衡",
                        "tb1c",
                        {"debits": [100.0], "credits": [50.0]},
                    ),
                    _envelope(
                        "fin_trial_balance",
                        "/智维通/城市乳业/财务中心/试算平衡",
                        "tb1d",
                        {"debits": [42.0], "credits": [42.0]},
                    ),
                    _envelope(
                        "fin_trial_balance",
                        "/智维通/城市乳业/财务中心/试算平衡",
                        "tb1e",
                        {"debits": [0.1, 0.2], "credits": [0.15, 0.15]},
                    ),
                    _envelope(
                        "fin_trial_balance",
                        "/智维通/城市乳业/财务中心/试算平衡",
                        "tb1f",
                        {
                            "debits": [100.0],
                            "credits": [50.0],
                            "external_debit_total_url": "http://gl/debit",
                            "external_credit_total_url": "http://gl/credit",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "fin_trial_balance",
                        "/智维通/城市乳业/财务中心/试算平衡",
                        "tb1g",
                        {
                            "debits": [1000.0, 500.0],
                            "credits": [800.0, 700.0],
                            "external_debit_total_url": "http://gl/down",
                            "external_credit_total_url": "http://gl/credit",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.finance_center.trial_balance",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "fin-trial-balance-v1"
        assert rep.passed == 7 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["tb_balanced"] is True
        assert rep.cases[0].result["summary"]["exception_code"] is None
        assert rep.cases[1].result["debit_total"] == 0.0
        assert rep.cases[1].result["tb_balanced"] is True
        assert rep.cases[2].result["tb_balanced"] is False
        assert rep.cases[2].result["summary"]["exception_code"] == "W_TRIAL_IMBALANCE"
        assert rep.cases[3].result["tb_balanced"] is True
        assert rep.cases[4].result["debit_total"] == 0.3
        assert rep.cases[4].result["credit_total"] == 0.3
        assert rep.cases[5].result["debit_total"] == 1500.0
        assert rep.cases[5].result["credit_total"] == 1500.0
        assert rep.cases[5].result["tb_balanced"] is True
        assert rep.cases[5].result["summary"]["l3_integration"]["debit_total"]["used_external"] is True
        assert rep.cases[5].result["summary"]["l3_integration"]["credit_total"]["used_external"] is True
        assert rep.cases[6].result["debit_total"] == 1500.0
        assert rep.cases[6].result["credit_total"] == 1500.0
        assert rep.cases[6].result["tb_balanced"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["debit_total"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["debit_total"]["used_external"] is False
        assert rep.cases[6].result["summary"]["l3_integration"]["credit_total"]["used_external"] is True

    asyncio.run(_run())


def test_report_snapshot_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"trial_cleared": 1}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.finance_center.report_snapshot import ReportSnapshotSkill

            return ReportSnapshotSkill()

        try:
            rep = await run_sandbox(
                [
                    _envelope(
                        "fin_report_snapshot",
                        "/智维通/城市乳业/财务中心/报表快照",
                        "rs1",
                        {"period_id": "P-Q1", "trial_cleared": True},
                    ),
                    _envelope(
                        "fin_report_snapshot",
                        "/智维通/城市乳业/财务中心/报表快照",
                        "rs1b",
                        {},
                    ),
                    _envelope(
                        "fin_report_snapshot",
                        "/智维通/城市乳业/财务中心/报表快照",
                        "rs1c",
                        {"period_id": "P-X", "trial_cleared": False},
                    ),
                    _envelope(
                        "fin_report_snapshot",
                        "/智维通/城市乳业/财务中心/报表快照",
                        "rs1d",
                        {"trial_cleared": True},
                    ),
                    _envelope(
                        "fin_report_snapshot",
                        "/智维通/城市乳业/财务中心/报表快照",
                        "rs1e",
                        {"trial_cleared": False},
                    ),
                    _envelope(
                        "fin_report_snapshot",
                        "/智维通/城市乳业/财务中心/报表快照",
                        "rs1f",
                        {
                            "period_id": "P-L3",
                            "trial_cleared": False,
                            "external_trial_cleared_url": "http://gl/gate",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "fin_report_snapshot",
                        "/智维通/城市乳业/财务中心/报表快照",
                        "rs1g",
                        {
                            "trial_cleared": True,
                            "external_trial_cleared_url": "http://gl/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.finance_center.report_snapshot",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "fin-report-gate-v1"
        assert rep.passed == 7 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["report_publishable"] is True
        assert rep.cases[0].result["summary"]["exception_code"] is None
        assert rep.cases[1].result["trial_cleared"] is False
        assert rep.cases[1].result["summary"]["exception_code"] == "W_FIN_REPORT_BLOCKED"
        assert rep.cases[2].result["report_publishable"] is False
        assert rep.cases[2].result["summary"]["exception_code"] == "W_FIN_REPORT_BLOCKED"
        assert rep.cases[3].result["report_publishable"] is True
        assert rep.cases[4].result["summary"]["exception_code"] == "W_FIN_REPORT_BLOCKED"
        assert rep.cases[5].result["trial_cleared"] is True
        assert rep.cases[5].result["report_publishable"] is True
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["trial_cleared"] is True
        assert rep.cases[6].result["report_publishable"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_production_scheduling_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"planned_units": 120}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.production_center.production_scheduling import ProductionSchedulingSkill

            return ProductionSchedulingSkill()

        try:
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
                    _envelope(
                        "prod_production_scheduling",
                        "/智维通/城市乳业/生产中心/排产",
                        "c2f",
                        {
                            "demand_units": 500,
                            "external_planned_units_url": "http://mes/ok",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "prod_production_scheduling",
                        "/智维通/城市乳业/生产中心/排产",
                        "c2g",
                        {
                            "demand_units": 100,
                            "external_planned_units_url": "http://mes/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.production_center.production_scheduling",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "sched-demand-to-plan-v1"
        assert rep.passed == 7 and rep.failed == 0
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
        assert rep.cases[5].result["planned_units"] == 120
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["planned_units"] == 100
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_material_requirement_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"raw_stock": 400}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.production_center.material_requirement import MaterialRequirementSkill

            return MaterialRequirementSkill()

        try:
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
                    _envelope(
                        "prod_material_requirement",
                        "/智维通/城市乳业/生产中心/物料需求",
                        "m1f",
                        {
                            "fg_sku": "FG-L3",
                            "planned_fg_units": 100,
                            "raw_per_fg": 2,
                            "raw_stock": 10,
                            "external_raw_stock_url": "http://wms/ok",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "prod_material_requirement",
                        "/智维通/城市乳业/生产中心/物料需求",
                        "m1g",
                        {
                            "planned_fg_units": 100,
                            "raw_per_fg": 2,
                            "raw_stock": 500,
                            "external_raw_stock_url": "http://wms/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.production_center.material_requirement",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries

        assert rep.passed == 7 and rep.failed == 0
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
        assert rep.cases[5].result["raw_stock"] == 400
        assert rep.cases[5].result["mrp_feasible"] is True
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["raw_stock"] == 500
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_quality_inspection_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"defect_units": 2}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.production_center.quality_inspection import QualityInspectionSkill

            return QualityInspectionSkill()

        try:
            rep = await run_sandbox(
                [
                    _envelope(
                        "prod_quality_inspection",
                        "/智维通/城市乳业/生产中心/质量检验",
                        "qc1",
                        {"batch_id": "B-QC", "units_inspected": 200, "defect_units": 0, "max_defect_units": 5},
                    ),
                    _envelope(
                        "prod_quality_inspection",
                        "/智维通/城市乳业/生产中心/质量检验",
                        "qc1b",
                        {},
                    ),
                    _envelope(
                        "prod_quality_inspection",
                        "/智维通/城市乳业/生产中心/质量检验",
                        "qc1c",
                        {"defect_units": 10, "max_defect_units": 5},
                    ),
                    _envelope(
                        "prod_quality_inspection",
                        "/智维通/城市乳业/生产中心/质量检验",
                        "qc1d",
                        {"defect_units": 5, "max_defect_units": 5},
                    ),
                    _envelope(
                        "prod_quality_inspection",
                        "/智维通/城市乳业/生产中心/质量检验",
                        "qc1e",
                        {"defect_units": 0, "max_defect_units": 0},
                    ),
                    _envelope(
                        "prod_quality_inspection",
                        "/智维通/城市乳业/生产中心/质量检验",
                        "qc1f",
                        {
                            "defect_units": 10,
                            "max_defect_units": 5,
                            "external_defect_units_url": "http://lims/ok",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "prod_quality_inspection",
                        "/智维通/城市乳业/生产中心/质量检验",
                        "qc1g",
                        {
                            "defect_units": 0,
                            "max_defect_units": 5,
                            "external_defect_units_url": "http://lims/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.production_center.quality_inspection",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "qc-defect-threshold-v1"
        assert rep.passed == 7 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["qc_pass"] is True
        assert rep.cases[0].result["summary"]["exception_code"] is None
        assert rep.cases[1].result["units_inspected"] == 0
        assert rep.cases[1].result["qc_pass"] is True
        assert rep.cases[2].result["qc_pass"] is False
        assert rep.cases[2].result["summary"]["exception_code"] == "W_QC_BATCH_REJECT"
        assert rep.cases[3].result["qc_pass"] is True
        assert rep.cases[3].result["summary"]["exception_code"] is None
        assert rep.cases[4].result["qc_pass"] is True
        assert rep.cases[5].result["defect_units"] == 2
        assert rep.cases[5].result["qc_pass"] is True
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["defect_units"] == 0
        assert rep.cases[6].result["qc_pass"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_batch_release_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"qc_cleared": 1}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.production_center.batch_release import BatchReleaseSkill

            return BatchReleaseSkill()

        try:
            rep = await run_sandbox(
                [
                    _envelope(
                        "prod_batch_release",
                        "/智维通/城市乳业/生产中心/批次放行",
                        "br1",
                        {"batch_id": "B-BR", "qc_cleared": True},
                    ),
                    _envelope(
                        "prod_batch_release",
                        "/智维通/城市乳业/生产中心/批次放行",
                        "br1b",
                        {},
                    ),
                    _envelope(
                        "prod_batch_release",
                        "/智维通/城市乳业/生产中心/批次放行",
                        "br1c",
                        {"batch_id": "B-X", "qc_cleared": False},
                    ),
                    _envelope(
                        "prod_batch_release",
                        "/智维通/城市乳业/生产中心/批次放行",
                        "br1d",
                        {"batch_id": "B-OK", "qc_cleared": True},
                    ),
                    _envelope(
                        "prod_batch_release",
                        "/智维通/城市乳业/生产中心/批次放行",
                        "br1e",
                        {"qc_cleared": False},
                    ),
                    _envelope(
                        "prod_batch_release",
                        "/智维通/城市乳业/生产中心/批次放行",
                        "br1f",
                        {
                            "batch_id": "B-L3",
                            "qc_cleared": False,
                            "external_qc_cleared_url": "http://mes/ok",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "prod_batch_release",
                        "/智维通/城市乳业/生产中心/批次放行",
                        "br1g",
                        {
                            "batch_id": "B-DG",
                            "qc_cleared": True,
                            "external_qc_cleared_url": "http://mes/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.production_center.batch_release",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "batch-release-gate-v1"
        assert rep.passed == 7 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["release_committed"] is True
        assert rep.cases[0].result["summary"]["exception_code"] is None
        assert rep.cases[1].result["qc_cleared"] is False
        assert rep.cases[1].result["release_committed"] is False
        assert rep.cases[1].result["summary"]["exception_code"] == "W_RELEASE_BLOCKED"
        assert rep.cases[2].result["release_committed"] is False
        assert rep.cases[2].result["summary"]["exception_code"] == "W_RELEASE_BLOCKED"
        assert rep.cases[3].result["release_committed"] is True
        assert rep.cases[3].result["summary"]["exception_code"] is None
        assert rep.cases[4].result["summary"]["exception_code"] == "W_RELEASE_BLOCKED"
        assert rep.cases[5].result["qc_cleared"] is True
        assert rep.cases[5].result["release_committed"] is True
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["qc_cleared"] is True
        assert rep.cases[6].result["release_committed"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_inventory_management_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"quantity_on_hand": 250}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.warehouse_logistics.inventory_management import InventoryManagementSkill

            return InventoryManagementSkill()

        try:
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
                    _envelope(
                        "wh_inventory_management",
                        "/智维通/城市乳业/仓储物流/库存管理",
                        "c3f",
                        {
                            "sku": "SKU-L3",
                            "quantity_on_hand": 30,
                            "reorder_threshold": 100,
                            "external_quantity_on_hand_url": "http://wms/ok",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "wh_inventory_management",
                        "/智维通/城市乳业/仓储物流/库存管理",
                        "c3g",
                        {
                            "quantity_on_hand": 30,
                            "reorder_threshold": 100,
                            "external_quantity_on_hand_url": "http://wms/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.warehouse_logistics.inventory_management",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "inv-threshold-v1"
        assert rep.passed == 7 and rep.failed == 0
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
        assert rep.cases[5].result["quantity_on_hand"] == 250
        assert rep.cases[5].result["reorder_suggested"] is False
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["quantity_on_hand"] == 30
        assert rep.cases[6].result["reorder_suggested"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_inbound_receiving_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"received_qty": 95}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.warehouse_logistics.inbound_receiving import InboundReceivingSkill

            return InboundReceivingSkill()

        try:
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
                    _envelope(
                        "wh_inbound_receiving",
                        "/智维通/城市乳业/仓储物流/入库验收",
                        "w1f",
                        {
                            "ordered_qty": 100,
                            "received_qty": 10,
                            "external_received_qty_url": "http://wms/ok",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "wh_inbound_receiving",
                        "/智维通/城市乳业/仓储物流/入库验收",
                        "w1g",
                        {
                            "ordered_qty": 100,
                            "received_qty": 100,
                            "external_received_qty_url": "http://wms/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.warehouse_logistics.inbound_receiving",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "inbound-qty-match-v1"
        assert rep.passed == 7 and rep.failed == 0
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
        assert rep.cases[5].result["received_qty"] == 95
        assert rep.cases[5].result["shortfall"] == 5
        assert rep.cases[5].result["receipt_complete"] is False
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["received_qty"] == 100
        assert rep.cases[6].result["receipt_complete"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_outbound_picking_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"picked_qty": 50}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.warehouse_logistics.outbound_picking import OutboundPickingSkill

            return OutboundPickingSkill()

        try:
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
                    _envelope(
                        "wh_outbound_picking",
                        "/智维通/城市乳业/仓储物流/出库拣货",
                        "o1f",
                        {
                            "requested_qty": 100,
                            "picked_qty": 10,
                            "external_picked_qty_url": "http://wms/ok",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "wh_outbound_picking",
                        "/智维通/城市乳业/仓储物流/出库拣货",
                        "o1g",
                        {
                            "requested_qty": 60,
                            "picked_qty": 60,
                            "external_picked_qty_url": "http://wms/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.warehouse_logistics.outbound_picking",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "outbound-pick-qty-v1"
        assert rep.passed == 7 and rep.failed == 0
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
        assert rep.cases[5].result["picked_qty"] == 50
        assert rep.cases[5].result["shortfall"] == 50
        assert rep.cases[5].result["pick_complete"] is False
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["picked_qty"] == 60
        assert rep.cases[6].result["pick_complete"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_cycle_count_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"counted_qty": 100}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.warehouse_logistics.cycle_count import CycleCountSkill

            return CycleCountSkill()

        try:
            rep = await run_sandbox(
                [
                    _envelope(
                        "wh_cycle_count",
                        "/智维通/城市乳业/仓储物流/库存盘点",
                        "cy1",
                        {"sku": "SKU-CY", "book_qty": 500, "counted_qty": 500},
                    ),
                    _envelope(
                        "wh_cycle_count",
                        "/智维通/城市乳业/仓储物流/库存盘点",
                        "cy1b",
                        {},
                    ),
                    _envelope(
                        "wh_cycle_count",
                        "/智维通/城市乳业/仓储物流/库存盘点",
                        "cy1c",
                        {"book_qty": 100, "counted_qty": 95},
                    ),
                    _envelope(
                        "wh_cycle_count",
                        "/智维通/城市乳业/仓储物流/库存盘点",
                        "cy1d",
                        {"book_qty": 10, "counted_qty": 12},
                    ),
                    _envelope(
                        "wh_cycle_count",
                        "/智维通/城市乳业/仓储物流/库存盘点",
                        "cy1e",
                        {"book_qty": 1, "counted_qty": 0},
                    ),
                    _envelope(
                        "wh_cycle_count",
                        "/智维通/城市乳业/仓储物流/库存盘点",
                        "cy1f",
                        {
                            "book_qty": 100,
                            "counted_qty": 10,
                            "external_counted_qty_url": "http://wms/ok",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "wh_cycle_count",
                        "/智维通/城市乳业/仓储物流/库存盘点",
                        "cy1g",
                        {
                            "book_qty": 100,
                            "counted_qty": 100,
                            "external_counted_qty_url": "http://wms/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.warehouse_logistics.cycle_count",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "cycle-count-variance-v1"
        assert rep.passed == 7 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["variance_qty"] == 0
        assert rep.cases[0].result["cycle_balanced"] is True
        assert rep.cases[0].result["summary"]["exception_code"] is None
        assert rep.cases[1].result["book_qty"] == 0
        assert rep.cases[1].result["cycle_balanced"] is True
        assert rep.cases[2].result["variance_qty"] == -5
        assert rep.cases[2].result["cycle_balanced"] is False
        assert rep.cases[2].result["summary"]["exception_code"] == "W_CYCLE_COUNT_VARIANCE"
        assert rep.cases[3].result["variance_qty"] == 2
        assert rep.cases[3].result["summary"]["exception_code"] == "W_CYCLE_COUNT_VARIANCE"
        assert rep.cases[4].result["variance_qty"] == -1
        assert rep.cases[4].result["summary"]["exception_code"] == "W_CYCLE_COUNT_VARIANCE"
        assert rep.cases[5].result["counted_qty"] == 100
        assert rep.cases[5].result["variance_qty"] == 0
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["counted_qty"] == 100
        assert rep.cases[6].result["cycle_balanced"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_stock_transfer_skill_sandbox() -> None:
    async def _run() -> None:
        from shared.integration_client import IntegrationGetResult, get_json_with_retries

        async def smart_fake(url: str, *, correlation_id: str, **kw: object) -> IntegrationGetResult:
            if "/down" in url:
                return IntegrationGetResult(False, 503, None, 3, "http_503")
            return IntegrationGetResult(True, 200, {"available_at_source": 500}, 1, None)

        def factory():
            import shared.integration_client as ic

            ic.get_json_with_retries = smart_fake
            from skills.warehouse_logistics.stock_transfer import StockTransferSkill

            return StockTransferSkill()

        try:
            rep = await run_sandbox(
                [
                    _envelope(
                        "wh_stock_transfer",
                        "/智维通/城市乳业/仓储物流/库内调拨",
                        "tr1",
                        {
                            "sku": "SKU-TR",
                            "from_location": "A-01",
                            "to_location": "B-02",
                            "quantity": 30,
                            "available_at_source": 500,
                        },
                    ),
                    _envelope(
                        "wh_stock_transfer",
                        "/智维通/城市乳业/仓储物流/库内调拨",
                        "tr1b",
                        {},
                    ),
                    _envelope(
                        "wh_stock_transfer",
                        "/智维通/城市乳业/仓储物流/库内调拨",
                        "tr1c",
                        {"quantity": 100, "available_at_source": 40},
                    ),
                    _envelope(
                        "wh_stock_transfer",
                        "/智维通/城市乳业/仓储物流/库内调拨",
                        "tr1d",
                        {"quantity": 50, "available_at_source": 50},
                    ),
                    _envelope(
                        "wh_stock_transfer",
                        "/智维通/城市乳业/仓储物流/库内调拨",
                        "tr1e",
                        {"quantity": 1000, "available_at_source": 999},
                    ),
                    _envelope(
                        "wh_stock_transfer",
                        "/智维通/城市乳业/仓储物流/库内调拨",
                        "tr1f",
                        {
                            "quantity": 30,
                            "available_at_source": 10,
                            "external_available_at_source_url": "http://wms/ok",
                            "external_request_headers": {"Authorization": "Bearer sandbox"},
                        },
                    ),
                    _envelope(
                        "wh_stock_transfer",
                        "/智维通/城市乳业/仓储物流/库内调拨",
                        "tr1g",
                        {
                            "quantity": 30,
                            "available_at_source": 500,
                            "external_available_at_source_url": "http://wms/down",
                        },
                    ),
                ],
                skill_factory=factory,
                coverage_skill_module="skills.warehouse_logistics.stock_transfer",
            )
        finally:
            import shared.integration_client as ic

            ic.get_json_with_retries = get_json_with_retries
        rv = "transfer-qty-availability-v1"
        assert rep.passed == 7 and rep.failed == 0
        assert rep.coverage_percent >= 90.0
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["rule_version"] == rv
        assert rep.cases[0].result["shortfall"] == 0
        assert rep.cases[0].result["transfer_complete"] is True
        assert rep.cases[0].result["summary"]["exception_code"] is None
        assert rep.cases[1].result["quantity"] == 0
        assert rep.cases[1].result["transfer_complete"] is True
        assert rep.cases[2].result["shortfall"] == 60
        assert rep.cases[2].result["transfer_complete"] is False
        assert rep.cases[2].result["summary"]["exception_code"] == "W_TRANSFER_SHORTFALL"
        assert rep.cases[3].result["shortfall"] == 0
        assert rep.cases[3].result["summary"]["exception_code"] is None
        assert rep.cases[4].result["shortfall"] == 1
        assert rep.cases[4].result["summary"]["exception_code"] == "W_TRANSFER_SHORTFALL"
        assert rep.cases[5].result["available_at_source"] == 500
        assert rep.cases[5].result["shortfall"] == 0
        assert rep.cases[5].result["summary"]["l3_integration"]["used_external"] is True
        assert rep.cases[6].result["available_at_source"] == 500
        assert rep.cases[6].result["transfer_complete"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["degraded"] is True
        assert rep.cases[6].result["summary"]["l3_integration"]["used_external"] is False

    asyncio.run(_run())


def test_zz_phase2_org_path_exports() -> None:
    """Smoke last: avoid importing department modules before sandbox coverage tests."""
    from skills.finance_center.payable_reconciliation import ORG_PATH as p0
    from skills.finance_center.receivable_reconciliation import ORG_PATH as p1
    from skills.finance_center.report_snapshot import ORG_PATH as p1rs
    from skills.finance_center.trial_balance import ORG_PATH as p1tb
    from skills.production_center.batch_release import ORG_PATH as p2rel
    from skills.production_center.material_requirement import ORG_PATH as p2
    from skills.production_center.production_scheduling import ORG_PATH as p2b
    from skills.production_center.quality_inspection import ORG_PATH as p2qc
    from skills.warehouse_logistics.cycle_count import ORG_PATH as p3a
    from skills.warehouse_logistics.inbound_receiving import ORG_PATH as p3
    from skills.warehouse_logistics.inventory_management import ORG_PATH as p4
    from skills.warehouse_logistics.outbound_picking import ORG_PATH as p5
    from skills.warehouse_logistics.stock_transfer import ORG_PATH as p5a

    assert p0 == "/智维通/城市乳业/财务中心/应付对账"
    assert p1 == "/智维通/城市乳业/财务中心/应收对账"
    assert p1tb == "/智维通/城市乳业/财务中心/试算平衡"
    assert p1rs == "/智维通/城市乳业/财务中心/报表快照"
    assert p2b == "/智维通/城市乳业/生产中心/排产"
    assert p2 == "/智维通/城市乳业/生产中心/物料需求"
    assert p2qc == "/智维通/城市乳业/生产中心/质量检验"
    assert p2rel == "/智维通/城市乳业/生产中心/批次放行"
    assert p3 == "/智维通/城市乳业/仓储物流/入库验收"
    assert p3a == "/智维通/城市乳业/仓储物流/库存盘点"
    assert p4 == "/智维通/城市乳业/仓储物流/库存管理"
    assert p5a == "/智维通/城市乳业/仓储物流/库内调拨"
    assert p5 == "/智维通/城市乳业/仓储物流/出库拣货"

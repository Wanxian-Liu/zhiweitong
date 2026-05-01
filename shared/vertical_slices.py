"""垂直切片 ↔ 叶岗注册表（org_path、skill_id、rule_version、编排动作）。

供集成测试、CLI 与文档引用；**rule_version 须与各 Skill 模块内常量一致**，
由 ``tests/test_zz_vertical_slice_registry_contract.py``、
``tests/test_zz_vertical_slice_finance_registry_contract.py``、
``tests/test_zz_vertical_slice_wh_registry_contract.py``、
``tests/test_zz_vertical_slice_production_quality_registry_contract.py``、
``tests/test_zz_vertical_slice_finance_trial_registry_contract.py`` 校验。

新增切片时：在此追加 ``VerticalSliceStep``，并同步 ``docs/vertical-slices.md``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

# --- 排产 → 物料需求 → 入库验收 → 库存管理 → 出库拣货（手册推荐主链；L1 + L2） ---

SLICE_PRODUCTION_INVENTORY_V1: Final = "production-inventory-v1"


@dataclass(frozen=True, slots=True)
class VerticalSliceStep:
    """切片中的一步：对应单一叶岗 Skill。"""

    step_index: int
    org_path: str
    skill_id: str
    rule_version: str
    planner_action: str
    skill_py: str
    """仓库内实现文件路径（便于检索，非 import 路径）。"""


PRODUCTION_INVENTORY_CHAIN: Final[tuple[VerticalSliceStep, ...]] = (
    VerticalSliceStep(
        0,
        "/智维通/城市乳业/生产中心/排产",
        "prod_production_scheduling",
        "sched-demand-to-plan-v1",
        "schedule",
        "skills/production_center/production_scheduling.py",
    ),
    VerticalSliceStep(
        1,
        "/智维通/城市乳业/生产中心/物料需求",
        "prod_material_requirement",
        "mrp-single-level-v1",
        "mrp",
        "skills/production_center/material_requirement.py",
    ),
    VerticalSliceStep(
        2,
        "/智维通/城市乳业/仓储物流/入库验收",
        "wh_inbound_receiving",
        "inbound-qty-match-v1",
        "receive",
        "skills/warehouse_logistics/inbound_receiving.py",
    ),
    VerticalSliceStep(
        3,
        "/智维通/城市乳业/仓储物流/库存管理",
        "wh_inventory_management",
        "inv-threshold-v1",
        "stock",
        "skills/warehouse_logistics/inventory_management.py",
    ),
    VerticalSliceStep(
        4,
        "/智维通/城市乳业/仓储物流/出库拣货",
        "wh_outbound_picking",
        "outbound-pick-qty-v1",
        "pick",
        "skills/warehouse_logistics/outbound_picking.py",
    ),
)

# 与 ``tests/test_zz_vertical_slice_production_inventory_chain`` 固定计划一致（脱敏演示参数）。
PRODUCTION_INVENTORY_DEFAULT_PARAMS: Final[tuple[dict[str, Any], ...]] = (
    {"demand_units": 100, "line_id": "LINE-VS"},
    {
        "fg_sku": "FG-VS",
        "planned_fg_units": 100,
        "raw_per_fg": 2,
        "raw_stock": 500,
    },
    {"sku": "RAW-VS", "ordered_qty": 200, "received_qty": 200},
    {
        "sku": "RAW-VS",
        "quantity_on_hand": 400,
        "reorder_threshold": 100,
    },
    {"sku": "RAW-VS", "requested_qty": 80, "picked_qty": 80},
)


def production_inventory_org_paths() -> frozenset[str]:
    return frozenset(s.org_path for s in PRODUCTION_INVENTORY_CHAIN)


def production_inventory_rule_version_by_org_path() -> dict[str, str]:
    return {s.org_path: s.rule_version for s in PRODUCTION_INVENTORY_CHAIN}


# --- 应收对账 → 应付对账（财务小闭环；L1 + L2） ---

SLICE_FINANCE_AR_AP_V1: Final = "finance-ar-ap-v1"

FINANCE_AR_AP_CHAIN: Final[tuple[VerticalSliceStep, ...]] = (
    VerticalSliceStep(
        0,
        "/智维通/城市乳业/财务中心/应收对账",
        "fin_receivable_reconciliation",
        "fin-ar-net-v1",
        "reconcile_ar",
        "skills/finance_center/receivable_reconciliation.py",
    ),
    VerticalSliceStep(
        1,
        "/智维通/城市乳业/财务中心/应付对账",
        "fin_payable_reconciliation",
        "fin-ap-net-v1",
        "reconcile_ap",
        "skills/finance_center/payable_reconciliation.py",
    ),
)

# 与 ``tests/test_zz_vertical_slice_finance_ar_ap_chain`` 固定计划一致（脱敏演示参数）。
# 行数须与 Skill 启发式一致（|invoices|==|payments|、|bills|==|payments|）；0 表示该发票/账单尚未核销的占位收款/付款。
FINANCE_AR_AP_DEFAULT_PARAMS: Final[tuple[dict[str, Any], ...]] = (
    {"invoices": [100.0, 50.0], "payments": [40.0, 0.0]},
    {"bills": [200.0, 80.0], "payments": [50.0, 0.0]},
)


def finance_ar_ap_org_paths() -> frozenset[str]:
    return frozenset(s.org_path for s in FINANCE_AR_AP_CHAIN)


def finance_ar_ap_rule_version_by_org_path() -> dict[str, str]:
    return {s.org_path: s.rule_version for s in FINANCE_AR_AP_CHAIN}


# --- 试算平衡 → 报表快照（财务总账/关账示意小闭环；L1 + L2） ---

SLICE_FINANCE_TRIAL_REPORT_V1: Final = "finance-trial-report-v1"

FINANCE_TRIAL_REPORT_CHAIN: Final[tuple[VerticalSliceStep, ...]] = (
    VerticalSliceStep(
        0,
        "/智维通/城市乳业/财务中心/试算平衡",
        "fin_trial_balance",
        "fin-trial-balance-v1",
        "trial_balance",
        "skills/finance_center/trial_balance.py",
    ),
    VerticalSliceStep(
        1,
        "/智维通/城市乳业/财务中心/报表快照",
        "fin_report_snapshot",
        "fin-report-gate-v1",
        "publish_report_snapshot",
        "skills/finance_center/report_snapshot.py",
    ),
)

FINANCE_TRIAL_REPORT_DEFAULT_PARAMS: Final[tuple[dict[str, Any], ...]] = (
    {"debits": [1000.0, 500.0], "credits": [800.0, 700.0]},
    {"period_id": "FY25-P04", "trial_cleared": True},
)


def finance_trial_report_org_paths() -> frozenset[str]:
    return frozenset(s.org_path for s in FINANCE_TRIAL_REPORT_CHAIN)


def finance_trial_report_rule_version_by_org_path() -> dict[str, str]:
    return {s.org_path: s.rule_version for s in FINANCE_TRIAL_REPORT_CHAIN}


# --- 质量检验 → 批次放行（生产补链小闭环；L1 + L2） ---

SLICE_PRODUCTION_QUALITY_V1: Final = "production-quality-v1"

PRODUCTION_QUALITY_CHAIN: Final[tuple[VerticalSliceStep, ...]] = (
    VerticalSliceStep(
        0,
        "/智维通/城市乳业/生产中心/质量检验",
        "prod_quality_inspection",
        "qc-defect-threshold-v1",
        "inspect_qc",
        "skills/production_center/quality_inspection.py",
    ),
    VerticalSliceStep(
        1,
        "/智维通/城市乳业/生产中心/批次放行",
        "prod_batch_release",
        "batch-release-gate-v1",
        "release_batch",
        "skills/production_center/batch_release.py",
    ),
)

PRODUCTION_QUALITY_DEFAULT_PARAMS: Final[tuple[dict[str, Any], ...]] = (
    {"batch_id": "PQ-VS", "units_inspected": 200, "defect_units": 0, "max_defect_units": 5},
    {"batch_id": "PQ-VS", "qc_cleared": True},
)


def production_quality_org_paths() -> frozenset[str]:
    return frozenset(s.org_path for s in PRODUCTION_QUALITY_CHAIN)


def production_quality_rule_version_by_org_path() -> dict[str, str]:
    return {s.org_path: s.rule_version for s in PRODUCTION_QUALITY_CHAIN}


# --- 库存盘点 → 库内调拨（仓储补链小闭环；L1 + L2） ---

SLICE_WAREHOUSE_CYCLE_TRANSFER_V1: Final = "warehouse-cycle-transfer-v1"

WH_CYCLE_TRANSFER_CHAIN: Final[tuple[VerticalSliceStep, ...]] = (
    VerticalSliceStep(
        0,
        "/智维通/城市乳业/仓储物流/库存盘点",
        "wh_cycle_count",
        "cycle-count-variance-v1",
        "cycle_count",
        "skills/warehouse_logistics/cycle_count.py",
    ),
    VerticalSliceStep(
        1,
        "/智维通/城市乳业/仓储物流/库内调拨",
        "wh_stock_transfer",
        "transfer-qty-availability-v1",
        "transfer_stock",
        "skills/warehouse_logistics/stock_transfer.py",
    ),
)

# 与 ``tests/test_zz_vertical_slice_wh_cycle_transfer_chain`` 固定计划一致。
WH_CYCLE_TRANSFER_DEFAULT_PARAMS: Final[tuple[dict[str, Any], ...]] = (
    {"sku": "WH-CT-VS", "book_qty": 500, "counted_qty": 500},
    {
        "sku": "WH-CT-VS",
        "from_location": "A-01",
        "to_location": "B-02",
        "quantity": 30,
        "available_at_source": 500,
    },
)


def wh_cycle_transfer_org_paths() -> frozenset[str]:
    return frozenset(s.org_path for s in WH_CYCLE_TRANSFER_CHAIN)


def wh_cycle_transfer_rule_version_by_org_path() -> dict[str, str]:
    return {s.org_path: s.rule_version for s in WH_CYCLE_TRANSFER_CHAIN}

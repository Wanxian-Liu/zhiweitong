# 垂直切片 ↔ 岗位映射

**目的**：把端到端业务链上的 **叶岗** 与 `org_path`、`skill_id`、`rule_version`、Orchestrator **计划动作** 固定为单一事实来源，避免测试与手册各写一套字符串。

**代码**：`shared/vertical_slices.py`

---

## 官方回归路径（主干）

**切片 ID**：`production-inventory-v1` —— 变更 core、总线契约或链上 Skill 时，**先跑通本条再合并**（比全量 `pytest` 更快，且覆盖端到端编排 + Gateway + State）。

**L3 外部集成（可选）**：链上 **排产 / 物料需求 / 入库验收 / 库存管理 / 出库拣货** 分别支持 **`external_planned_units_url`**、**`external_raw_stock_url`**、**`external_received_qty_url`**、**`external_quantity_on_hand_url`**、**`external_picked_qty_url`**；各岗另可选 **`external_request_headers`**（`str→str`，如 **`Authorization`**）。重试/幂等见 **`docs/vertical-slice-l3-integration.md`**；默认演示参数**不**带上述字段，故 **`make spine`** 行为不变。

**补链 `warehouse-cycle-transfer-v1`（可选 L3）**：**库存盘点 / 库内调拨** 分别支持 **`external_counted_qty_url`**、**`external_available_at_source_url`**，并同用 **`external_request_headers`**；默认 **`WH_CYCLE_TRANSFER_DEFAULT_PARAMS`** 不带上述字段，**`make spine`** 行为不变。

**补链 `production-quality-v1`（可选 L3）**：**质量检验 / 批次放行** 分别支持 **`external_defect_units_url`**、**`external_qc_cleared_url`**（放行门闩 JSON 中 **`qc_cleared`** 为 **0 / 正整数**），并同用 **`external_request_headers`**；默认 **`PRODUCTION_QUALITY_DEFAULT_PARAMS`** 不带上述字段，**`make spine`** 行为不变。

**切片 `finance-ar-ap-v1` / `finance-trial-report-v1`（可选 L3）**：**应收 / 应付** 分别支持 **`external_receivable_total_url`**、**`external_payable_total_url`**（JSON 金额 **`receivable_total`** / **`payable_total`**，2 位小数）；**试算平衡** 支持 **`external_debit_total_url`**、**`external_credit_total_url`**；**报表快照** 支持 **`external_trial_cleared_url`**（JSON **`trial_cleared`** 为 **0 / 正整数** 门闩）。均同用 **`external_request_headers`**；默认 **`FINANCE_AR_AP_DEFAULT_PARAMS`**、**`FINANCE_TRIAL_REPORT_DEFAULT_PARAMS`** 不带上述字段，**`make spine`** 行为不变。

在仓库根目录执行：

```bash
make spine
```

等价于：

```bash
poetry run pytest \
  tests/test_zz_vertical_slice_production_inventory_chain.py \
  tests/test_zz_vertical_slice_registry_contract.py \
  tests/test_zz_vertical_slice_finance_ar_ap_chain.py \
  tests/test_zz_vertical_slice_finance_registry_contract.py \
  tests/test_zz_vertical_slice_wh_cycle_transfer_chain.py \
  tests/test_zz_vertical_slice_wh_registry_contract.py \
  tests/test_zz_vertical_slice_production_quality_chain.py \
  tests/test_zz_vertical_slice_production_quality_registry_contract.py \
  tests/test_zz_vertical_slice_finance_trial_report_chain.py \
  tests/test_zz_vertical_slice_finance_trial_registry_contract.py \
  -q --tb=short
```

**期望现象**：

- 当前共 **15** 条用例全部通过（**5** 条链式 E2E + **10** 条注册表/参数契约；含供应链、财务双链、仓储补链、生产补链）。
- 链式集成用例 `test_production_to_inventory_vertical_slice_e2e` 成功时：`GoalReport.ok is True`、**5** 步全部 `ok`，且每步 `skill_path` / `skill_id` / `summary.rule_version` 与下表及 `shared/vertical_slices.py` 一致；摘要断言覆盖 `planned_units`、`required_raw_qty`、`receipt_complete`、`reorder_suggested`、`pick_complete` 等。

**不要求**：LLM、Redis、本机 `.env`（pytest 下 `ZHIWEITONG_SKIP_DOTENV=1`）。合并前仍建议本地或 CI 跑 **`make test`** 全量。

---

| 切片 ID | 链（业务顺序） | 集成测试 |
|--------|----------------|----------|
| `production-inventory-v1` | 排产 → 物料需求 → 入库验收 → 库存管理 → 出库拣货 | `tests/test_zz_vertical_slice_production_inventory_chain.py` |
| `finance-ar-ap-v1` | 应收对账 → 应付对账 | `tests/test_zz_vertical_slice_finance_ar_ap_chain.py` |
| `finance-trial-report-v1` | 试算平衡 → 报表快照 | `tests/test_zz_vertical_slice_finance_trial_report_chain.py` |
| `warehouse-cycle-transfer-v1` | 库存盘点 → 库内调拨 | `tests/test_zz_vertical_slice_wh_cycle_transfer_chain.py` |
| `production-quality-v1` | 质量检验 → 批次放行 | `tests/test_zz_vertical_slice_production_quality_chain.py` |

## `production-inventory-v1` 逐步

| step | org_path | skill_id | rule_version | planner_action | 实现文件 |
|-----:|----------|----------|--------------|----------------|----------|
| 0 | `/智维通/城市乳业/生产中心/排产` | `prod_production_scheduling` | `sched-demand-to-plan-v1` | `schedule` | `skills/production_center/production_scheduling.py` |
| 1 | `/智维通/城市乳业/生产中心/物料需求` | `prod_material_requirement` | `mrp-single-level-v1` | `mrp` | `skills/production_center/material_requirement.py` |
| 2 | `/智维通/城市乳业/仓储物流/入库验收` | `wh_inbound_receiving` | `inbound-qty-match-v1` | `receive` | `skills/warehouse_logistics/inbound_receiving.py` |
| 3 | `/智维通/城市乳业/仓储物流/库存管理` | `wh_inventory_management` | `inv-threshold-v1` | `stock` | `skills/warehouse_logistics/inventory_management.py` |
| 4 | `/智维通/城市乳业/仓储物流/出库拣货` | `wh_outbound_picking` | `outbound-pick-qty-v1` | `pick` | `skills/warehouse_logistics/outbound_picking.py` |

默认演示参数见 `PRODUCTION_INVENTORY_DEFAULT_PARAMS`（与上述集成测试内计划一致）。

## `finance-ar-ap-v1` 逐步

| step | org_path | skill_id | rule_version | planner_action | 实现文件 |
|-----:|----------|----------|--------------|----------------|----------|
| 0 | `/智维通/城市乳业/财务中心/应收对账` | `fin_receivable_reconciliation` | `fin-ar-net-v1` | `reconcile_ar` | `skills/finance_center/receivable_reconciliation.py` |
| 1 | `/智维通/城市乳业/财务中心/应付对账` | `fin_payable_reconciliation` | `fin-ap-net-v1` | `reconcile_ap` | `skills/finance_center/payable_reconciliation.py` |

默认演示参数见 `FINANCE_AR_AP_DEFAULT_PARAMS`（与 `tests/test_zz_vertical_slice_finance_ar_ap_chain.py` 内计划一致）：收/付款行与发票/应付单行数对齐，未核销行可用 `0` 占位以保持净额不变。

契约校验：`tests/test_zz_vertical_slice_finance_registry_contract.py`。

## `finance-trial-report-v1` 逐步

| step | org_path | skill_id | rule_version | planner_action | 实现文件 |
|-----:|----------|----------|--------------|----------------|----------|
| 0 | `/智维通/城市乳业/财务中心/试算平衡` | `fin_trial_balance` | `fin-trial-balance-v1` | `trial_balance` | `skills/finance_center/trial_balance.py` |
| 1 | `/智维通/城市乳业/财务中心/报表快照` | `fin_report_snapshot` | `fin-report-gate-v1` | `publish_report_snapshot` | `skills/finance_center/report_snapshot.py` |

默认演示参数见 `FINANCE_TRIAL_REPORT_DEFAULT_PARAMS`（与 `tests/test_zz_vertical_slice_finance_trial_report_chain.py` 内计划一致）。

契约校验：`tests/test_zz_vertical_slice_finance_trial_registry_contract.py`。

## `production-quality-v1` 逐步

| step | org_path | skill_id | rule_version | planner_action | 实现文件 |
|-----:|----------|----------|--------------|----------------|----------|
| 0 | `/智维通/城市乳业/生产中心/质量检验` | `prod_quality_inspection` | `qc-defect-threshold-v1` | `inspect_qc` | `skills/production_center/quality_inspection.py` |
| 1 | `/智维通/城市乳业/生产中心/批次放行` | `prod_batch_release` | `batch-release-gate-v1` | `release_batch` | `skills/production_center/batch_release.py` |

默认演示参数见 `PRODUCTION_QUALITY_DEFAULT_PARAMS`（与 `tests/test_zz_vertical_slice_production_quality_chain.py` 内计划一致）。

契约校验：`tests/test_zz_vertical_slice_production_quality_registry_contract.py`。

## `warehouse-cycle-transfer-v1` 逐步

| step | org_path | skill_id | rule_version | planner_action | 实现文件 |
|-----:|----------|----------|--------------|----------------|----------|
| 0 | `/智维通/城市乳业/仓储物流/库存盘点` | `wh_cycle_count` | `cycle-count-variance-v1` | `cycle_count` | `skills/warehouse_logistics/cycle_count.py` |
| 1 | `/智维通/城市乳业/仓储物流/库内调拨` | `wh_stock_transfer` | `transfer-qty-availability-v1` | `transfer_stock` | `skills/warehouse_logistics/stock_transfer.py` |

默认演示参数见 `WH_CYCLE_TRANSFER_DEFAULT_PARAMS`（与 `tests/test_zz_vertical_slice_wh_cycle_transfer_chain.py` 内计划一致）。

契约校验：`tests/test_zz_vertical_slice_wh_registry_contract.py`。

## L2（可对账）扩展

链上叶岗在 **`summary`** 中额外提供 **`l2_reconcile`**、**`exception_code`**、**`manual_handoff`**（手册技能成熟度 L2），`rule_version` 不变。仓储主链：**`W_OUTBOUND_SHORTFALL`** 等；**补链 `warehouse-cycle-transfer-v1`**：**`W_CYCLE_COUNT_VARIANCE`**、**`W_TRANSFER_SHORTFALL`**；**补链 `production-quality-v1`**：**`W_QC_BATCH_REJECT`**、**`W_RELEASE_BLOCKED`**；财务：**`W_FIN_AR_LINE_MISMATCH`** / **`W_FIN_AP_LINE_MISMATCH`**；**补链 `finance-trial-report-v1`**：**`W_TRIAL_IMBALANCE`**、**`W_FIN_REPORT_BLOCKED`**。字段含义与运维处置见 **`docs/ops-runbook.md`**「主垂直切片 L2」；构建辅助见 **`shared/slice_l2.py`**。

## 契约校验

`tests/test_zz_vertical_slice_registry_contract.py`（供应链）、`tests/test_zz_vertical_slice_finance_registry_contract.py`（应收应付）、`tests/test_zz_vertical_slice_finance_trial_registry_contract.py`（试算报表）、`tests/test_zz_vertical_slice_wh_registry_contract.py`（仓储补链）、`tests/test_zz_vertical_slice_production_quality_registry_contract.py`（生产补链）在运行时比对本表与各 Skill 模块导出的 `ORG_PATH` / `SKILL_ID` / `RULE_VERSION`，漂移即失败。

## 修订流程

1. 改 Skill 常量或编排步序时，**先改** `shared/vertical_slices.py`，再改集成测试与本文表格（或从模块生成表格）。
2. 总线 topic / 信封字段变更仍按 **`docs/event_topics.md`** 先行。

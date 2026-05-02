# 垂直切片 L3：外部系统集成（起步）

**范围**：在 **L2 可对账** 之上，为 **production-inventory-v1**、**warehouse-cycle-transfer-v1**、**production-quality-v1**、**finance-ar-ap-v1**、**finance-trial-report-v1** 等链增加「真实 WMS/ERP / LIMS / MES / 总账」对接的**可重复模式**（超时、重试、幂等键、失败回退），与 **`docs/handbook-gap-and-industrialization.md`** 中 L3 定义对齐。

## 共享客户端

- **模块**：`shared/integration_client.py`
- **方法**：`get_json_with_retries(url, correlation_id=..., max_attempts=3, extra_headers=..., ...)`；**`merge_json_int_override`**（非负整数）与 **`merge_json_float_override`**（有限浮点数，**四舍五入到 2 位小数**，与金额本地计算对齐）— 在 URL 非空时 GET JSON，将 **`field`** 覆盖 **`fallback`**，失败则回退并在返回的元数据中带 **`degraded` / `used_external`**。
- **语义**：GET JSON；请求头 **`Idempotency-Key`** = 与总线步级一致的 **`correlation_id`**；**`Accept: application/json`**；**`extra_headers`** 可追加 **`Authorization`** 等（**不会**覆盖幂等键与 Accept）；对 502/503/504 与网络错误重试；调用方可注入 **`httpx.AsyncClient`**（如 `MockTransport`）做契约测试。
- **鉴权与密钥**：Skill 默认**不**从环境变量读 Token（保持单测与沙盒无密钥）。生产环境由 **Gateway / 编排层** 在调用前组装 **`extra_headers`**，或对 **`httpx.AsyncClient`** 配置默认头；**勿**把长期密钥写进持久化 payload。
- **Payload（各 L3 岗通用）**：可选 **`external_request_headers`**：JSON 对象，键值均为字符串（如 **`Authorization`**），由 **`extra_headers_from_payload`** 解析后传入 **`merge_json_int_override` / `merge_json_float_override`**；与各岗自带的 **`external_*_url`** 同用。

## 链上示例

### 排产岗（`production-inventory-v1` 步 0）

- **文件**：`skills/production_center/production_scheduling.py`
- **可选 payload**：`external_planned_units_url` → 响应 JSON 字段 **`planned_units`**（在本地 `max(demand_units,0)` 之后覆盖，模拟 MES/APS 可排产量）

### 物料需求岗

- **文件**：`skills/production_center/material_requirement.py`
- **可选 payload**：`external_raw_stock_url`（非空则发起 GET；响应 JSON 须含整数 **`raw_stock`**）
- **回退**：HTTP 失败或 JSON 无效时，**仍使用 payload 内 `raw_stock`**，并在 **`summary.l3_integration`** 中标记 **`degraded`: true**

### 入库验收岗

- **文件**：`skills/warehouse_logistics/inbound_receiving.py`
- **可选 payload**：`external_received_qty_url` → 响应 JSON 字段 **`received_qty`**

### 库存管理岗

- **文件**：`skills/warehouse_logistics/inventory_management.py`
- **可选 payload**：`external_quantity_on_hand_url` → 响应 JSON 字段 **`quantity_on_hand`**

### 出库拣货岗

- **文件**：`skills/warehouse_logistics/outbound_picking.py`
- **可选 payload**：`external_picked_qty_url` → 响应 JSON 字段 **`picked_qty`**

### 库存盘点岗（补链 `warehouse-cycle-transfer-v1`）

- **文件**：`skills/warehouse_logistics/cycle_count.py`
- **可选 payload**：`external_counted_qty_url` → 响应 JSON 字段 **`counted_qty`**

### 库内调拨岗（补链 `warehouse-cycle-transfer-v1`）

- **文件**：`skills/warehouse_logistics/stock_transfer.py`
- **可选 payload**：`external_available_at_source_url` → 响应 JSON 字段 **`available_at_source`**

### 质量检验岗（补链 `production-quality-v1`）

- **文件**：`skills/production_center/quality_inspection.py`
- **可选 payload**：`external_defect_units_url` → 响应 JSON 字段 **`defect_units`**（整数，与 **`max_defect_units`** 比较）

### 批次放行岗（补链 `production-quality-v1`）

- **文件**：`skills/production_center/batch_release.py`
- **可选 payload**：`external_qc_cleared_url` → 响应 JSON 字段 **`qc_cleared`**（**非负整数**：**0** 表示未放行，**>0** 表示已放行/可放行）

### 应收对账岗（`finance-ar-ap-v1`）

- **文件**：`skills/finance_center/receivable_reconciliation.py`
- **可选 payload**：`external_receivable_total_url` → 响应 JSON 字段 **`receivable_total`**（**数字**，解析为 **2 位小数** 浮点，覆盖本地 ∑发票−∑收款）

### 应付对账岗（`finance-ar-ap-v1`）

- **文件**：`skills/finance_center/payable_reconciliation.py`
- **可选 payload**：`external_payable_total_url` → 响应 JSON 字段 **`payable_total`**（**数字**，**2 位小数**）

### 试算平衡岗（`finance-trial-report-v1`）

- **文件**：`skills/finance_center/trial_balance.py`
- **可选 payload**：`external_debit_total_url` → **`debit_total`**；`external_credit_total_url` → **`credit_total`**（各为一次 GET；可只配一侧）。合并后重算 **`tb_balanced`**。

### 报表快照岗（`finance-trial-report-v1`）

- **文件**：`skills/finance_center/report_snapshot.py`
- **可选 payload**：`external_trial_cleared_url` → 响应 JSON 字段 **`trial_cleared`**（**非负整数**：**0** 未通过，**>0** 视为试算通过/可发布门闩）

## 运维与安全

- 生产环境应对 WMS URL 使用 **HTTPS**、网络隔离与密钥；需 **Bearer / API Key** 时使用 **`extra_headers`** 或带默认头的 **`AsyncClient`**（见上文「鉴权与密钥」）。
- 与 **`docs/ops-runbook.md`**、**`docs/event_topics.md`「安全与访问边界」** 一致：Redis/总线侧仍按现有信任模型。

## 验证

- 单元契约：`tests/test_integration_client.py`（重试/幂等、`merge_json_int_override`、`merge_json_float_override`、`extra_headers` / `Authorization`）
- Skill 沙盒（`IntegrationGetResult` 假实现）：`tests/test_phase2_department_skills.py` 内各岗 sandbox 用例（patch **`get_json_with_retries`**）
- **主线五步 L3 + 真实 HTTP 栈**：`tests/test_zz_production_inventory_l3_mock_http.py` — **`httpx.MockTransport`** 注入 **`AsyncClient`**，调用真实 **`get_json_with_retries`**，覆盖 **`production-inventory-v1`** 五步 **`external_*_url`** 与一条 **`external_request_headers`**；纳入 **`make spine`**
- 主干回归未改默认参数：仓库根 **`make spine`**（黄金 JSON 仍不带 URL；L3 专测显式带 URL）

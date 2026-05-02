# 事件与信封契约速查（表格）

**权威来源**：逻辑 topic、Redis 载荷与安全边界以 **`docs/event_topics.md`** 为准；修订总线或信封字段时**先改** `event_topics.md`，再改代码。

## 逻辑 Topic 模式

| 类型 | Topic 模式 | 典型发布方 | 典型订阅方 |
|------|------------|------------|------------|
| 命令 | `{org_path}/command` | Orchestrator、EvolutionEngine 等 | `SkillCommandGateway` → 叶岗 Skill |
| 结果 | `{org_path}/result` | 叶岗 Skill | Orchestrator / 聚合岗（通配订阅） |
| 系统错误 | `/system/errors` | Orchestrator、Skill | 观测 / 进化引擎 |
| 进化审核 | `/system/evolution/review` | EvolutionEngine、Orchestrator | 人工 / 审计流 |
| 进化批准 | `/system/evolution/approved` | 审计岗 `gov_audit_review` | `EvolutionPromotion` |
| 进化否决 | `/system/evolution/rejected` | 审计岗 | 下游订阅（若有） |

**前缀**：`/智维通/城市乳业`；`org_path` 与 **`shared/org_canonical.py`** 及注册 Skill 一致。

## 信封字段（`EventEnvelope`）

实现见 **`shared/models.py`**。

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | `str` | 默认 `"1"` |
| `correlation_id` | `str` | 追踪 ID；编排器每步可生成独立 ID |
| `org_path` | `str` | 必须与组织树前缀一致 |
| `skill_id` | `str` | 叶岗或系统组件标识 |
| `payload` | `dict` | 业务载荷（`action`/`params`、`plan_id` 等由调用约定） |

## Redis 单条消息（多实例）

JSON 字符串：`{"t": "<topic>", "e": <event dict>}` — 见 **`core/redis_event_bus.py`** 与 **`event_topics.md`**「Redis 传输」。

## 主体推进步骤（按顺序打勾）

与 **`docs/handbook-gap-and-industrialization.md`**「推荐推进顺序」第 1 条一致；**不**替代 **`vertical-slices.md`** 与 **`event_topics.md`** 的权威细节。

1. **垂直切片与注册表**：改链上叶岗、`skill_id`、`rule_version` 或编排步序时，先改 **`shared/vertical_slices.py`**，再同步 **`docs/vertical-slices.md`** 与相关 **`tests/test_zz_vertical_slice_*.py`**；合并前根目录 **`make spine`**。
2. **总线 / 信封 / Redis 行为**：任何 topic、载荷或传输语义变更，**先改** **`docs/event_topics.md`**，再改 **`core/`**、**`shared/`**；本速查与权威不一致时，以 **`event_topics.md`** 为准并修正本文件。
3. **组织树与叶岗路径**：新增或调整 **`org_path`** 时同步 **`shared/org_canonical.py`** 与契约测试（见 **`CONTRIBUTING.md`**）。
4. **收束**：合入前 **`make verify`**（全量 pytest + **`core/*`** / **`skills/quick_consumption/*.py`** 覆盖率门禁）。

## 延伸阅读

- **部署与安全**：`event_topics.md`（部署模型、安全与访问边界）
- **运维与环境**：`docs/ops-runbook.md`
- **垂直切片与岗位映射**：`docs/vertical-slices.md`、`shared/vertical_slices.py`

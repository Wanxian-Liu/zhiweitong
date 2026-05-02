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

## 延伸阅读

- **部署与安全**：`event_topics.md`（部署模型、安全与访问边界）
- **运维与环境**：`docs/ops-runbook.md`
- **垂直切片与岗位映射**：`docs/vertical-slices.md`、`shared/vertical_slices.py`

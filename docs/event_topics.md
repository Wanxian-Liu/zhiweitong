# 事件 Topic 约定（zhiweitong）

**状态**：初稿 — 实现 `core/event_bus.py` 前可修订；修订须同步本文件与订阅方。

## 前缀

- 全局根：`/智维通/城市乳业`
- Topic 中 `org_path` 使用 **URL 编码或统一小写+下划线** 待定；当前建议 topic 字符串 **直接嵌入规范化 org_path**（与通配实现一致即可）。

## 模式（草案）

| 类型 | 模式 | 说明 |
|------|------|------|
| 命令 | `org_path{normalized}/command` | Orchestrator / 系统组件（如 EvolutionEngine）→ Skill；可由 `SkillCommandGateway` 订阅并派发到该 org_path 的唯一 Skill |
| 结果 | `org_path{normalized}/result` | Skill → 上游聚合 |
| 系统错误 | `/system/errors` | 全 Skill 异常上报（信封字段同 `EventEnvelope`；`payload` 建议含 `error`、`latency_ms`、可选 `source`） |
| 进化审核 | `/system/evolution/review` | `optimization_review`：EvolutionEngine 待人工审批的执行层补丁；`evolution_draft`：Orchestrator 手工触发 |
| 进化批准 | `/system/evolution/approved` | `gov_audit_review` 对补丁**明示批准**后发布；`payload.kind=audit_decision`，含 `target_skill_id`、`proposed_execution_patch`、`knowledge_doc_id` 等。**`EvolutionPromotion`** 订阅本 topic，幂等写入知识库快照 + State 标记（见 `core/evolution_promotion.py`） |
| 进化否决 | `/system/evolution/rejected` | 审计岗**明示否决**后发布；载荷结构同批准（`decision=rejected`） |

## 通配订阅

- 示例：订阅 `/智维通/城市乳业/*` 下所有 `result`，用于聚合岗（细则与 `event_bus` 实现同步）。
- **匹配规则**（见 `core/event_bus.topic_matches`）：精确相等；或模式以单个尾部 `*` 结尾时按前缀匹配；`"*"` 匹配任意 topic；其余 `*` 走 `fnmatch`。

## 垂直切片与叶岗映射

端到端链路上的 `org_path` / `skill_id` / `rule_version` / 计划动作见 **`docs/vertical-slices.md`** 与 **`shared/vertical_slices.py`**（与集成测试契约同步）。

## Redis 传输（多实例）

- **开关**：`ZHIWEITONG_EVENT_BUS_BACKEND=redis`，并设置非空的 `ZHIWEITONG_REDIS_URL`。
- **频道**：`ZHIWEITONG_REDIS_BUS_CHANNEL`（默认 `zhiweitong:events`）；所有进程须一致。
- **载荷**：单条 Pub/Sub 消息为 JSON 字符串 `{"t":"<topic>","e":{...}}`；订阅侧仍用与内存总线相同的 `topic_matches` 规则过滤。
- **实现**：`core/redis_event_bus.py`；构造入口 `core/event_bus_factory.py` 的 `create_event_bus`。

## JSON 信封（建议）

每条 `event: dict` 至少包含：

- `schema_version`
- `correlation_id`
- `org_path`
- `skill_id`
- `payload`

（具体字段在 `shared/models.py` 落地后同步本文。）

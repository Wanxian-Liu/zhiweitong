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

## 部署模型：内存总线 vs Redis（何时切换）

| 场景 | 推荐 `ZHIWEITONG_EVENT_BUS_BACKEND` | 说明 |
|------|--------------------------------------|------|
| 单进程、本地/CI、所有发布与订阅**同一进程** | `memory`（默认） | 无跨进程传输；最快、最少依赖 |
| **多副本 / 多进程**：编排器与 Gateway、或不同 Pod 上的组件需经总线互通 | `redis` | 必须使用 Redis Pub/Sub，否则 command/result 无法跨机器 |
| 仅水平扩**无状态 HTTP**、但总线仍在单进程内 | `memory` 可仍适用 | 一旦总线订阅方不在同一进程，即须 `redis` |

**契约（与实现对齐，变更须同步本文与订阅方）**

- 切换 `redis` 时，集群内 **`ZHIWEITONG_REDIS_BUS_CHANNEL` 与 `ZHIWEITONG_REDIS_URL` 指向的 Redis 逻辑库须一致**；否则会出现「部分节点收不到 command/result」。
- **语义**：Redis Pub/Sub 为**至多一次**投递的典型用法；跨网络分区时可能丢消息，业务上依赖 **`correlation_id`** 与 Orchestrator 超时/重试策略（见 **`docs/orchestrator-llm.md`**）。
- **与 State**：多写副本**不要**共享同一 SQLite 文件；远程 DB（如 Postgres）与 **`docs/ops-runbook.md`**「多实例与 State」一致。
- **与 Skill 集**：各进程加载的 Skill 注册表应**同源同版本**，否则同一 topic 可能路由到不同实现。

## Redis 传输（多实例）

- **开关**：`ZHIWEITONG_EVENT_BUS_BACKEND=redis`，并设置非空的 `ZHIWEITONG_REDIS_URL`。
- **频道**：`ZHIWEITONG_REDIS_BUS_CHANNEL`（默认 `zhiweitong:events`）；所有进程须一致。
- **载荷**：单条 Pub/Sub 消息为 JSON 字符串 `{"t":"<topic>","e":{...}}`；`t` 为逻辑 topic 字符串，`e` 为与内存总线相同的信封 `dict`；订阅侧仍用与内存总线相同的 `topic_matches` 规则过滤。
- **实现**：`core/redis_event_bus.py`；构造入口 `core/event_bus_factory.py` 的 `create_event_bus`。

## 安全与访问边界（P0：现状与运维依赖）

本节对应 **`docs/handbook-gap-and-industrialization.md`** 工业级清单 **P0 安全** 的契约层说明；**不在本文引入新的鉴权字段**（若将来在信封上增加 token/签名，须先修订本文再改实现）。

**总线鉴权（应用层）**

- 当前代码**不对** `publish` / 订阅回调做调用方身份校验：信任模型为「**同进程内**组件」或「**已接入同一 Redis 且网络可信**的节点」。
- **Redis 模式**下，产线应通过 **Redis ACL、口令轮换、`requirepass` / TLS（`rediss://`）**、以及 **网络隔离**（仅应用子网可达）降低未授权发布风险。
- **内存模式**下，总线不外露；进程边界即信任边界。

**敏感 topic（发布面收敛）**

| Topic 前缀或模式 | 风险说明 |
|------------------|----------|
| `/system/evolution/approved`、`/system/evolution/rejected`、`/system/evolution/review` | 可触发或门控**进化落库、知识库与 State 变更**；仅 Orchestrator、审计/治理岗、Evolution 相关组件应发布；订阅方应部署在受控进程。 |
| `/system/errors` | 汇聚异常与诊断信息；注意日志与下游存储中的**敏感 payload**。 |

**知识库与 State（数据层）**

- **Chroma / `KnowledgeStore`**：写入与检索须带合法 **`org_path`**（与组织树一致；未知路径拒绝等见 **`tests/test_knowledge_store.py`** 与 **`CLAUDE.md`**）。
- **State（SQLite/未来 Postgres）**：由 **`StateManager`** 与连接串访问；库文件或实例权限、备份与加密遵循 **`docs/ops-runbook.md`**（配置与密钥、灾备）。

## JSON 信封（与实现对齐）

实现为 **`shared/models.py`** 的 **`EventEnvelope`**（Pydantic）：`schema_version` 默认 **`"1"`**，其余字段 **`correlation_id`**、**`org_path`**、**`skill_id`**、**`payload`**（`dict`，默认空）与下表一致。内存总线与 Redis 传输均承载同一形状的字典（Redis 见上文「Redis 传输」）。

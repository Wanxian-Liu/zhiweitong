# 手册完成度 × 工业级优先级

本文档对照《OpenCLAW · Cursor 模块提示词手册（Phase 0–3）》与当前 **`zhiweitong`** 仓库实现，列出**剩余工作**与**工业级（产线就绪）**优先级，便于按阶段推进而无需先了解各类外围工具。

## 优先级图例

| 标记 | 含义 |
|------|------|
| **P0** | 工业级关键：影响可靠性、安全、可运维或可扩展底座；建议尽早做 |
| **P1** | 手册明确要求但尚未完成或仅部分完成 |
| **P2** | 体验、性能、文档或手册未写但产线常见的能力 |

---

## Phase 0：环境准备

| 小节 | 要求摘要 | 状态 | 优先级 |
|------|----------|------|--------|
| 0.1 | Poetry、依赖、目录、`config/settings`、`shared/models` & `errors` | 基本具备；`.env` 以本地为准 | P2：补 `.env.example` 与密钥管理说明 |
| 0.2 | 异步 EventBus、通配订阅、subscription_id | 已实现 | — |
| 0.3 | StateManager 异步 SQLite | 已实现 | P0：产线 DB 策略（连接池、迁移、备份） |
| 0.4 | OrgTree、路径前缀 | 已实现 | P1：与**完整组织树数据**（配置/DB）对齐 |
| 0.5 | Skill 六层元数据、SkillBase | 已实现 | — |
| 0.6 | 沙盒、覆盖率门禁 | 已实现 | P0：CI 中固定 `core/` 覆盖率阈值；Skill 避免预 import 导致假低覆盖 |
| 0.7 | Chroma 知识库 store/retrieve | 已实现（含 update/delete） | P0：持久化路径、备份、访问控制；P1：与手册「权限」规则验收用例 |

---

## Phase 1：核心岗位上线

| 小节 | 要求摘要 | 状态 | 优先级 |
|------|----------|------|--------|
| 1.1 | SkillRegistry 单例 | 已实现 | P0：多实例部署时的注册发现（未来 Redis/配置中心） |
| 1.2 | Orchestrator、LLM 计划、command/result、失败策略、**性能/token 日志**、`trigger_evolution` | LLM 计划与重试已有；**步骤失败发 `/system/errors`** 已接 | P1：token 消耗字段在结果路径上贯通；P0：LLM 失败降级与超时策略文档化 |
| 1.3 | 快消 4 岗 + 主管 | 已实现 | P2：主管与下属 topic 约定与监控对齐 |
| 1.4 | E2E `process_goal` | 已有 `test_quick_consumption_flow.py` | P1：对照手册断言「覆盖率≥90%」是否在 CI 强制执行 |

---

## Phase 2：全部门覆盖

手册要求：按模板为**财务、生产、仓储物流等全部部门**实现 Skill，**每岗沙盒覆盖率 ≥90%**。

| 领域 | 当前仓库 | 缺口 |
|------|----------|------|
| 快消板块 | 主管 + 4 叶岗 | 可持续补业务深度与集成测试 |
| 财务中心 | `receivable_reconciliation`（示例） | **其余财务岗位**（应付、总账、报表等，以组织树/业务定稿为准） |
| 生产中心 | `production_scheduling`（示例） | **其余生产岗位** |
| 仓储物流 | `inventory_management`（示例） | **其余仓储岗位** |
| 总经办 / 治理 | `audit_review`（审计审核岗） | 可与手册外「合规、法务、采购」等扩展 |

**优先级**：**P1（手册闭环）** — 按业务部门分批增加 Skill + 沙盒 + 注册清单；**P0（工业级）** — 每批上线前固定「测试、回滚、监控」检查项。

---

## Phase 3：复盘进化与 CLI

| 小节 | 要求摘要 | 状态 | 优先级 |
|------|----------|------|--------|
| 3.1 | Typer：`create-skill`、`batch-register`、`validate` | 已实现 + 测试；**`promote-preview`**、**`promote-apply`**（diff / `--write`+备份）；**CI**：`.github/workflows/ci.yml`（pytest + PR 内变更 Skill 的 `validate --skip-sandbox`）、PR 模板；**`poetry.lock`** 已纳入仓库 | P2：GitLab CI 若需要可另加 |
| 3.2 | EvolutionEngine、`/system/errors`、阈值、LLM 建议、沙盒、**审核岗**、知识库案例、**通过后更新元数据与版本** | 引擎 + 审计 + Gateway；`approved` → **`EvolutionPromotion`** 幂等写入知识库 + State；**真 LLM 优化**为占位；**execution 级源码落地**见 **`promote-apply`** | **P1**：**注册表覆盖**（模式 B）等；**P0**：多实例下 State 去重一致性（现依赖单库 SQLite） |

---

## 手册未写、工业级常见（建议纳入路线图）

以下不替代手册，但**工业级**通常需要，按 **P0 → P2** 排序：

1. **P0 可观测**：结构化日志、指标（步骤耗时、错误率、总线堆积）、追踪 ID（`correlation_id` 全链路透传已部分具备）。
2. **P0 配置与密钥**：环境分层（dev/stage/prod）、密钥不落盘、轮换策略。
3. **P0 部署模型**：单进程 vs 多副本；EventBus 从内存队列迁 **Redis Pub/Sub**（手册已预留）的时机与契约。
4. **P0 安全**：总线鉴权、敏感 topic、知识库与 State 的访问边界。
5. **P1 灾备**：SQLite/Chroma 备份恢复演练；State 与知识库一致性说明（起步见 **`docs/ops-runbook.md`**）。  
6. **P2 开发者体验**：`README` 一键启动、Makefile/poetry 脚本、API/事件契约的 OpenAPI 或表格维护。

---

## 建议执行顺序（专业但可执行）

1. **先封版「手册 Phase 0–3 功能清单」**：以本表 **P1** 为主，尤其是 **Phase 2 部门扩岗** 与 **进化「批准后落地」**。  
2. **并行抬升 P0 底座**：可观测、配置/密钥、部署与总线迁移策略 —— 与扩岗穿插，避免后期推倒重来。  
3. **每批 Skill 上线**：沙盒 + 集成测试 + `docs/event_topics.md` 更新；工业级检查项用简短 checklist 勾选。  
4. **手册外的工具（MCP 等）**：仅在具体任务需要时启用（查托管文档、连外部系统），不必预先全学。

---

## 修订

- 组织树与岗位全称以 **`文案汇辑.md` / 定稿组织数据** 为准时，应更新本表「Phase 2」部门列表并同步 `OrgTree` 配置来源。  
- 修改总线或信封字段时，**先改** `docs/event_topics.md`，再改实现。

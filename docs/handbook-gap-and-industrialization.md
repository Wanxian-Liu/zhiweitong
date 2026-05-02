# 手册完成度 × 工业级优先级

本文档对照《OpenCLAW · Cursor 模块提示词手册（Phase 0–3）》与当前 **`zhiweitong`** 仓库实现，列出**剩余工作**与**工业级（产线就绪）**优先级，便于按阶段推进而无需先了解各类外围工具。

## 封版与持续迭代（怎么算「开发完」）

- **手册 Phase 0–3**：下表中带 **「—」** 的优先级行视为**已与手册封版范围对齐**（以测试与 `make verify` 为证）。  
- **工业级 P0–P1**：可观测、配置与密钥、部署模型、安全、灾备等**起步文档**已落在 **`docs/ops-runbook.md`**、**`docs/event_topics.md`**（详见下表各条链接）。产线硬化（鉴权实现、真 Postgres、指标 exporter 等）仍可按路线图迭代。  
- **Phase 2 全部门岗位**：依赖业务定稿与组织树增量，**不以岗数封顶**；新增岗时同步 **`shared/org_canonical.py`**、沙盒与 **`make spine`** 相关切片（若有）。  
- **P2 开发者体验**：**`README`** 快速开始、**`make dev`**、事件契约 **`docs/event-contract-summary.md`**（权威仍为 **`event_topics.md`**）。

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
| 0.1 | Poetry、依赖、目录、`config/settings`、`shared/models` & `errors` | 基本具备；`.env` 以本地为准 | P2：密钥管理 SOP（仓库已提供 **`.env.example`**） |
| 0.2 | 异步 EventBus、通配订阅、subscription_id | 已实现 | — |
| 0.3 | StateManager 异步 SQLite | 已实现 | P2：正式 **Postgres** 选型后的连接池参数、迁移工具链（起步约束见 **`docs/ops-runbook.md`**） |
| 0.4 | OrgTree、路径前缀 | 已实现；已注册岗 **`org_path`** 单一来源 **`shared/org_canonical.py`**，与 Skill 模块 **`ORG_PATH`** 由 **`tests/test_zz_org_canonical_contract.py`** 锁定（`test_zz_` 须在 Phase 2 沙盒之后，避免提前 import 干扰沙盒 coverage）；运行时预载可用 **`core.org_tree.canonical_org_tree()`** | — |
| 0.5 | Skill 六层元数据、SkillBase | 已实现 | — |
| 0.6 | 沙盒、覆盖率门禁 | 已实现；**CI / `make verify`**：`core/*` **≥85%**，`skills/quick_consumption/*.py` **≥90%**；各 Skill 包 **`__init__.py` lazy**，避免预 import 拉低覆盖 | — |
| 0.7 | Chroma 知识库 store/retrieve | 已实现（含 update/delete）；持久化目录与备份见 **`docs/ops-runbook.md`**；配置 **`org_tree`** 时读写须合法 **`org_path`**（**`tests/test_knowledge_store.py`**：`unknown` 路径拒绝、retrieve 必带 `org_path`） | P2：大规模 IAM / 字段级 ACL |

---

## Phase 1：核心岗位上线

| 小节 | 要求摘要 | 状态 | 优先级 |
|------|----------|------|--------|
| 1.1 | SkillRegistry 单例 | 已实现 | P2：多实例部署时的注册发现（Redis / 配置中心） |
| 1.2 | Orchestrator、LLM 计划、command/result、失败策略、**性能/token 日志**、`trigger_evolution` | LLM 计划与重试已有；**步骤失败发 `/system/errors`** 已接；**token**：planner 为 `GoalReport.planner_tokens` + `aggregated["planner_tokens"]`（OpenAI `usage`）；步骤为 `StepRunRecord` 从 skill `payload.usage` 或扁平 token 字段贯通并写入 `save_state`；**超时/重试/观测**见 **`docs/orchestrator-llm.md`** | P2：LLM 运行时降级、多模型路由与按状态码重试（另立产品与里程碑） |
| 1.3 | 快消 4 岗 + 主管 | 已实现 | P2：主管与下属 topic 约定与监控对齐 |
| 1.4 | E2E `process_goal` | 已有 `test_quick_consumption_flow.py`；CI / **`make verify`** 对 **`skills/quick_consumption/*.py`** 行覆盖率 **≥90%**（与同次全量 `coverage run` 报告） | — |

---

## Phase 2：全部门覆盖

手册要求：按模板为**财务、生产、仓储物流等全部部门**实现 Skill，**每岗沙盒覆盖率 ≥90%**。

| 领域 | 当前仓库 | 缺口 |
|------|----------|------|
| 快消板块 | 主管 + 4 叶岗 | 可持续补业务深度与集成测试 |
| 财务中心 | `receivable_reconciliation`；`payable_reconciliation`；`trial_balance`；`report_snapshot`；**垂直切片 `finance-ar-ap-v1`**、**`finance-trial-report-v1`**（见 **`docs/vertical-slices.md`**） | **其余财务岗位**（以组织树/业务定稿为准） |
| 生产中心 | `production_scheduling`；`material_requirement`；**垂直切片 `production-quality-v1`**（质量检验→批次放行，见 **`docs/vertical-slices.md`**） | **其余生产岗位**（设备等，以定稿为准） |
| 仓储物流 | `inventory_management`；`inbound_receiving`；`outbound_picking`；**垂直切片 `warehouse-cycle-transfer-v1`**（库存盘点→库内调拨，见 **`docs/vertical-slices.md`**） | **其余仓储岗位**（全仓盘点策略、跨仓调拨等，以定稿为准） |
| 总经办 / 治理 | `audit_review`（审计审核岗） | 可与手册外「合规、法务、采购」等扩展 |

**优先级（持续迭代）**：按业务部门分批增加 Skill + 沙盒 + 注册清单；每批上线前「测试、回滚、监控」检查项见 **`docs/ops-runbook.md`** 与 CI。**本表「缺口」列**为产品 backlog，不阻塞 Phase 0–3 已列能力验收。

### 技能成熟度 L0–L3（从简版到可生产）

| 级别 | 含义 | 当前默认 |
|------|------|----------|
| **L0** | 岗位契约成立：`command`/`result`、State、沙盒覆盖率门禁通过；领域规则为**可替换**的示意实现 | Phase 2 新增岗默认 **L0** |
| **L1** | **可演示**：输出带 **规则/契约版本** 与关键中间量；**黄金用例**（脱敏 JSON）≥5 条落在 `tests/` | 垂直切片内优先抬升 |
| **L2** | **可对账**：与台账/报表 **同粒度** 可核对；异常码、人工兜底与 Runbook 段落齐备 | **`production-inventory-v1`**、**`production-quality-v1`**、**`finance-ar-ap-v1`**、**`finance-trial-report-v1`**、**`warehouse-cycle-transfer-v1`** 等切片链上叶岗已达 L2（`summary.l2_reconcile` 与 **`docs/ops-runbook.md`**）；其余岗继续按切片抬升 |
| **L3** | **可生产**：外部系统集成（超时/重试/幂等）、鉴权、监控与 SLO、回滚与灾备对齐 **`docs/ops-runbook.md`** | 按切片分批放行 |

**执行原则**：**垂直切片优先于横向扩岗** —— 选一条端到端业务链（当前主干：**排产 → 物料需求 → 入库验收 → 库存管理 → 出库拣货**），先把链上 Skill **从 L0 抬到 L1/L2**，再复制到其他部门；避免大量 L0 堆叠却无法对账。**主干回归命令**：仓库根 **`make spine`**（见 **`docs/vertical-slices.md`**「官方回归路径」）。**L3 起步**：**production-inventory-v1** 链上 **排产 / 物料需求 / 入库验收 / 库存管理 / 出库拣货** 已支持可选 **`external_planned_units_url`**、**`external_raw_stock_url`**、**`external_received_qty_url`**、**`external_quantity_on_hand_url`**、**`external_picked_qty_url`**；**warehouse-cycle-transfer-v1** 补链上 **库存盘点 / 库内调拨** 已支持 **`external_counted_qty_url`**、**`external_available_at_source_url`**（GET + 重试/幂等/回退）。**`shared/integration_client`** 的 **`get_json_with_retries` / `merge_json_int_override`** 支持 **`extra_headers`**；链上各 L3 岗可选 **`payload.external_request_headers`**（`str→str`，如 **`Authorization`**，**`extra_headers_from_payload`**），生产环境宜由 Gateway 注入、勿把长期密钥写入持久化 payload。**production-quality-v1** 补链上 **质量检验 / 批次放行** 已支持 **`external_defect_units_url`**、**`external_qc_cleared_url`**；**finance-ar-ap-v1** / **finance-trial-report-v1** 上 **应收 / 应付 / 试算 / 报表快照** 已支持 **`external_receivable_total_url`**、**`external_payable_total_url`**、**`external_debit_total_url`**、**`external_credit_total_url`**、**`external_trial_cleared_url`**（**`merge_json_float_override`** 见 **`shared/integration_client.py`**），见 **`docs/vertical-slice-l3-integration.md`**。

**推荐下一迭代提交顺序（可拆 PR）**：① **已实现**：`tests/test_zz_vertical_slice_production_inventory_chain.py`（`plan_provider` + `SkillCommandGateway` + `Orchestrator`，无 LLM）；Phase 2 岗位 Skill 通过 **`core.command_payload.effective_skill_payload`** 同时兼容 Orchestrator 的 `params` 包裹与沙盒扁平 `payload`。② **已实现（垂直切片 L1）**：链上 **排产 / 物料需求 / 入库 / 库存** 均带 **`rule_version`**；财务 **应收 / 应付**、仓储 **出库** 同步 L1；phase2 沙盒每岗 **5 条** + `tests/test_zz_golden_material_requirement.py` + `tests/test_zz_golden_phase2_rules.py`。③ **已实现**：**切片 ↔ 岗位** 单一来源 **`shared/vertical_slices.py`** + **`docs/vertical-slices.md`** + `tests/test_zz_vertical_slice_registry_contract.py`；CI 已加 **`core/*` 行覆盖率 ≥85%** 门禁。**Redis Pub/Sub 总线**（`RedisEventBus` + `create_event_bus`）已落地，见 **`docs/event_topics.md`**。**可观测最小集**：编排 / Gateway 关键路径日志带 **`zt_*` extra**；编排器写 **`zt_outcome`** / **`zt_duration_ms`**（目标级与每步）；**SkillCommandGateway** 写 **`execute_ok`** / **`execute_failed`** / **`resolve_ambiguous`** 及 **`zt_duration_ms`**；**`RedisEventBus`** 写 **`reader_started`** / **`publish_ok`**（DEBUG）/ **`payload_invalid`** / **`subscriber_failed`** / **`reader_stopped_error`**，并带 **`zt_bus_channel`** / **`zt_topic`** 等；内存 **`EventBus`** / **`EvolutionEngine`** / **`EvolutionPromotion`** 的 WARNING、EXCEPTION 路径已补 **`zt_*`**（见 **`docs/ops-runbook.md`**）。**`ZHIWEITONG_LOG_JSON`** 同文档。**覆盖率策略（当前）**：`core/*` + 快消 `skills/quick_consumption` 见 CI；Phase 2 各岗由沙盒单测门禁。**多实例 State** 见 **`docs/ops-runbook.md`**。

---

## Phase 3：复盘进化与 CLI

| 小节 | 要求摘要 | 状态 | 优先级 |
|------|----------|------|--------|
| 3.1 | Typer：`create-skill`、`batch-register`、`validate` | 已实现 + 测试；**`promote-preview`**、**`promote-apply`**（diff / `--write`+备份）；**CI**：`.github/workflows/ci.yml`（pytest + PR 内变更 Skill 的 `validate --skip-sandbox`）、PR 模板；**`poetry.lock`** 已纳入仓库 | P2：GitLab CI 若需要可另加 |
| 3.2 | EvolutionEngine、`/system/errors`、阈值、LLM 建议、沙盒、**审核岗**、知识库案例、**通过后更新元数据与版本** | 引擎 + 审计 + Gateway；`approved` → **`EvolutionPromotion`** 幂等写入知识库 + State；**真 LLM 优化**为占位；**execution 级源码落地**见 **`promote-apply`** | **模式 B（运行时注册表覆盖）**：暂缓，默认 **模式 A（GitOps）**，见 **`docs/evolution-promotion-professional-plan.md`**。**多实例 State**：单库 SQLite 约束与远程库指向见 **`docs/ops-runbook.md`** |

---

## 手册未写、工业级常见（建议纳入路线图）

以下不替代手册，但**工业级**通常需要，按 **P0 → P2** 排序：

1. **P0 可观测**：结构化日志、指标（步骤耗时、错误率、总线堆积）、追踪 ID（`correlation_id` 全链路透传已部分具备；**追踪拼接与日志衍生指标起步见 `docs/ops-runbook.md` §2「可观测 P0」**）。
2. **P0 配置与密钥**：环境分层（dev/stage/prod）、密钥不落盘、轮换策略（**起步见 `docs/ops-runbook.md` §2「配置与密钥 P0」**；**`.env.example`** 含 `ZHIWEITONG_ENV` 占位说明）。
3. **P0 部署模型**：单进程 vs 多副本；EventBus 从内存队列迁 **Redis Pub/Sub**（手册已预留）的时机与契约（**契约与切换条件见 `docs/event_topics.md`「部署模型」；运维核对清单见 `docs/ops-runbook.md` §2「部署模型 P0」**）。
4. **P0 安全**：总线鉴权、敏感 topic、知识库与 State 的访问边界（**契约见 `docs/event_topics.md`「安全与访问边界」；运维清单见 `docs/ops-runbook.md` §2「安全 P0」**）。
5. **P1 灾备**：SQLite/Chroma 备份恢复演练；State 与知识库一致性说明（起步与演练清单见 **`docs/ops-runbook.md` §5**）。
6. **P2 开发者体验**：`README` 快速开始、**`make dev`**（install + spine）、事件契约表格 **`docs/event-contract-summary.md`**（无 HTTP OpenAPI；对外契约以总线 topic/信封为准）。

---

## 推荐推进顺序（主体 → 流程 → 快消与运维）

若同时关心 **快消板块**（**`skills/quick_consumption/`**）与 **运维/产线硬化**（**`docs/ops-runbook.md`**、路线图中的可观测/密钥/部署/安全/灾备等），仍建议按下述 **时间顺序** 推进，避免多线并行返工：

1. **主体优先**：以 **`docs/vertical-slices.md`** 登记链与 **core / 总线** 为主干，用 **`make spine`**、**`make verify`** 客观收束；契约以 **`CLAUDE.md`**、**`docs/event_topics.md`** 为准（先改文档再改实现）。
2. **流程固化**：单轮节奏见 **`docs/ralph-loop.md`**；进化审阅与落盘见 Phase 3 及 **`promote-preview`** / **`promote-apply`** 等既有流程，不另起一套「私人脚本」替代验收。
3. **快消与运维后置、分里程碑完善**：快消岗业务加深与 **ops-runbook / 路线图 P0** 可在主体与流程跑顺后 **按里程碑迭代**，不必与垂直切片加深抢同一工期；细节仍回填本页表格与 **`docs/ops-runbook.md`**。

与下节「建议执行顺序」互补：**本节**强调 **何时做哪一类事**；**下节**强调 **表格内的技术优先级与扩岗策略**。

## 建议执行顺序（专业但可执行）

1. **Phase 0–3 功能清单**：本页 **Phase 0 / 1 / 3** 表格中 **优先级「—」** 项视为当前仓库已对齐手册的封版范围；**P2** 为增强项。  
2. **Phase 2**：在「横向扩岗」与「垂直切片加深」之间，**优先保证至少一条链达到 L1+**（主链见 **`docs/vertical-slices.md`**）。  
3. **每批 Skill 上线**：沙盒 + 切片级集成测试 + **`shared/org_canonical.py`** / **`docs/event_topics.md`**（若改总线）；按 **L0–L3** 勾选工业级项。  
4. **手册外的工具（MCP 等）**：仅在具体任务需要时启用，不必预先全学。

## 路线图（持续演进，非上表「未完成 P0/P1」）

下列来自手册外工业级清单与架构预留，**单独排期**，不占用上表「状态」列的闭环定义：

- 指标与总线堆积监控、追踪全链路强化（日志侧起步见 **`docs/ops-runbook.md` §2「可观测 P0」**）。  
- 环境分层（dev/stage/prod）与密钥轮换 SOP（起步见 **`docs/ops-runbook.md` §2「配置与密钥 P0」**）。  
- 多副本部署与 Redis 总线、State 方案（契约见 **`docs/event_topics.md`**「部署模型」；运维清单见 **`docs/ops-runbook.md` §2「部署模型 P0」**）。  
- 总线鉴权、敏感 topic、知识库与 State 的访问边界硬化（起步见 **`docs/event_topics.md`「安全与访问边界」**、**`docs/ops-runbook.md` §2「安全 P0」**）。  
- 灾备演练节奏与 RPO/RTO 目标文档化（起步见 **`docs/ops-runbook.md` §5.2**）。  
- OpenAPI / 事件契约的对外发布渠道（当前以 **`docs/event-contract-summary.md`** + **`event_topics.md`** 为发布面；若将来暴露 REST，再另增 OpenAPI）。

---

## 修订

- 组织树与岗位全称以 **`文案汇辑.md` / 定稿组织数据** 为准时，应更新本表「Phase 2」部门列表，并同步 **`shared/org_canonical.py`** 与 **`tests/test_zz_org_canonical_contract.py`** 内 **`_SKILL_MODULES`**。  
- 修改总线或信封字段时，**先改** `docs/event_topics.md`，再改实现。

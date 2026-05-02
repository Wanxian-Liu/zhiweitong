# 智维通 · 运维一页纸（本地数据与进化 CLI）

面向单机 / 小集群：**SQLite State**、**Chroma 知识库目录**、以及 **`promote-*` CLI** 的路径与备份约定。产线若迁 Postgres / 对象存储，应另写部署说明并替换本节默认值。

## 0. 组织树（`org_path`）

- 已注册 Skill 的 **`org_path`** 列表以仓库 **`shared/org_canonical.py`** 为准；与各 Skill 模块常量一致性由 **`tests/test_zz_org_canonical_contract.py`** 保证。  
- 进程内构建完整前缀树可使用 **`core.org_tree.canonical_org_tree()`**。定稿组织数据变更时同步 **`文案汇辑`** 与本文件及 **`docs/handbook-gap-and-industrialization.md`**。

### 主垂直切片 L2（`production-inventory-v1`）

- 链上叶岗（排产 → 物料需求 → 入库验收 → 库存管理 → **出库拣货**）在返回的 **`summary`** 中带 **`l2_reconcile`**：`grain`（对账粒度）、`keys`（与台账对齐的主键）、`basis_qty_field`（主数量字段名）、`ledger_hint`（与人工作业说明）。辅助模块 **`shared/slice_l2.py`**。  
- **`exception_code`**：`W_MRP_NET_SHORTAGE`（原料净需求大于现存量）、`W_INBOUND_SHORTFALL`（订购与实收短缺）、`W_OUTBOUND_SHORTFALL`（出库需求与实拣短缺）、`I_REORDER_SUGGESTED`（现存量低于阈值，信息类）；**生产补链**（质检→放行）：`W_QC_BATCH_REJECT`（缺陷超阈值）、`W_RELEASE_BLOCKED`（未质检放行）；**仓储补链**（盘点→调拨）：`W_CYCLE_COUNT_VARIANCE`（账存与实盘不一致）、`W_TRANSFER_SHORTFALL`（调拨量大于源库位可用量）；**财务岗**：`W_FIN_AR_LINE_MISMATCH`、`W_FIN_AP_LINE_MISMATCH`（应收/应付与收付款笔数不一致的示意规则）；**试算→报表**：`W_TRIAL_IMBALANCE`（借贷合计不一致）、`W_FIN_REPORT_BLOCKED`（试算未通过却请求报表快照）；正常为 `null`。  
- **`manual_handoff`**：非空时建议人工处理的短文案（补料、清点、补货审批等）。  
- 告警分级与工单对接未内置；可按日志 / `GoalReport` 步骤 `summary` 自行接入。

## 1. 默认路径（相对「进程当前工作目录」）

| 资源 | 默认位置 | 说明 |
|------|----------|------|
| State（SQLite） | `./var/zhiweitong.db` | 来自 `ZHIWEITONG_DATABASE_URL` 缺省值，见 `config/settings.py` |
| Chroma 持久化目录 | `./var/chroma` | `promote-preview` / `promote-apply` 在未指定 `--chroma-path` 且未设环境变量时使用 |
| Skill 源码根 | 仓库根 | CLI 通过 `ZHIWEITONG_PROJECT_ROOT` 覆盖（测试与多检出常用） |

**注意**：`sqlite+aiosqlite:///./var/zhiweitong.db` 中的 `./var/` 解析依赖**启动进程时的 cwd**。生产环境建议写**绝对路径**的 `ZHIWEITONG_DATABASE_URL`，或固定工作目录后再启动。

## 2. 环境变量（摘要）

本地可复制 **`.env.example`** → **`.env`**，按注释取消注释并填写。**`load_settings()`** 与 **`zhiweitong` CLI** 会从仓库根目录加载 `.env`（**不覆盖**已在进程里的变量）。运行 **pytest** 时默认 **`ZHIWEITONG_SKIP_DOTENV=1`**，以免本机 `.env` 打乱测试；仍可用 `export` / 编排平台注入变量。

| 变量 | 用途 | 缺省 |
|------|------|------|
| `ZHIWEITONG_DATABASE_URL` | 异步 SQLAlchemy 连接串（State 等） | `sqlite+aiosqlite:///./var/zhiweitong.db` |
| `ZHIWEITONG_CHROMA_PATH` | `promote-preview` / `promote-apply` 的 Chroma 目录 | `<repo>/var/chroma`（由 CLI 在设 `ZHIWEITONG_PROJECT_ROOT` 时相对该根解析） |
| `ZHIWEITONG_PROJECT_ROOT` | 仓库根（`skills/`、`cli/` 等） | `cli/main.py` 所在目录的上一级 |
| `ZHIWEITONG_REDIS_URL` | Redis（`EVENT_BUS_BACKEND=redis` 时必填；缓存等预留） | `redis://localhost:6379/0` |
| `ZHIWEITONG_EVENT_BUS_BACKEND` | 事件总线：`memory`（默认）或 `redis` | `memory` |
| `ZHIWEITONG_REDIS_BUS_CHANNEL` | Redis 总线 Pub/Sub 频道（多实例须一致） | `zhiweitong:events` |
| `ZHIWEITONG_LLM_API_KEY` / `ZHIWEITONG_LLM_BASE_URL` | Orchestrator LLM | 见 `config/settings.py` |
| `ZHIWEITONG_LOG_JSON` | 为根 logger 挂载 stderr JSON 行（字段含 `zt_*`） | 未设则关闭 |

密钥与端点：**勿提交 `.env`**；CI 不注入真实 LLM 密钥亦可跑通测试门禁。

### 配置与密钥 P0：环境分层、密钥与轮换（手册工业级清单）

本节对应 **`docs/handbook-gap-and-industrialization.md`** 工业级清单 **P0 配置与密钥** 的起步落地（不新增总线 topic、不改信封）。

**环境分层（dev / stage / prod）**

- 推荐**同一容器/制品**，在**各环境注入不同变量**：`ZHIWEITONG_DATABASE_URL`、`ZHIWEITONG_REDIS_URL`、`ZHIWEITONG_EVENT_BUS_BACKEND`、`ZHIWEITONG_LLM_*` 等；避免在镜像内 baked-in 密钥或库连接串。
- **本地**：仓库根 **`.env`**（由 **`.env.example`** 复制，已在 **`.gitignore`**）。**Staging / Prod**：由编排平台、systemd `EnvironmentFile`（权限 600）、K8s Secret、云 Secret Manager 等注入；**不要**依赖提交到 Git 的共享 `.env`。
- **可选标签**：可在进程环境中设 **`ZHIWEITONG_ENV`**=`development` | `staging` | `production`（或组织自有枚举），供外部采集/告警规则区分环境。**当前 `config/settings.load_settings()` 不读取该变量**（仅占位与文档对齐；若将来写入日志 `zt_*`，须单独立项并补测试）。

**密钥不落盘（最小纪律）**

- **`ZHIWEITONG_LLM_API_KEY`**、数据库与 Redis 密码等：只来自运行时环境或密钥服务；勿写入应用日志、工单正文、聊天或截图。
- 开发机 `.env` 视为**个人机密文件**，勿同步到网盘或共享仓库。

**轮换策略（起步 SOP）**

| 对象 | 建议动作 |
|------|----------|
| LLM API Key | 在提供商控制台**吊销旧 key → 创建新 key → 更新各环境密文 → 滚动重启**；观察错误率与 401 |
| 数据库 / Redis 凭据 | 按组织安全基线**定期轮换**；轮换后验证连接与 **`make verify` 类 CI**（测试可用占位连接，不依赖生产库） |
| 备份介质中的 `.db` / `var/` | 与 **§3、§5** 灾备一致：加密存储、访问审计，与在线库同样视为敏感数据 |

**CI 覆盖率门禁（摘要）**：全量 `pytest` 后同一份 coverage 数据上——**`core/*` 行覆盖 ≥85%**；Phase 1.4 快消 E2E 相关 **`skills/quick_consumption/*.py` ≥90%**（见 `.github/workflows/ci.yml`；本地 **`make verify`** 一致）。

**JSON 日志**：设 `ZHIWEITONG_LOG_JSON=1` 后，`load_settings()` 与 `zhiweitong` CLI 入口会调用 `core.observability.configure_zhiweitong_logging()`，向 stderr 输出单行 JSON（`ts`、`level`、`logger`、`message`、异常时的 `exception`、以及所有 `zt_*`）。嵌入进程可在启动早期自行调用同一函数。

**编排侧 LLM**：重试次数、HTTP 超时、步骤超时、空计划语义、`GoalReport` / token 字段与日志 grep 约定见 **`docs/orchestrator-llm.md`**。

### 日志字段（`zt_*`，可观测最小集）

Orchestrator、SkillCommandGateway 等在 ``logging`` 的 ``extra=`` 中写入以下属性（可在自定义 ``Formatter`` 中输出为 JSON 或键值对）：

| 属性 | 含义 |
|------|------|
| `zt_goal_run_id` | 单次 ``process_goal`` 的运行 ID（与 ``GoalReport.plan_id`` 相同） |
| `zt_step_index` | 计划步序号（从 0 起） |
| `zt_correlation_id` | 该步总线信封 ``correlation_id`` |
| `zt_skill_id` | 叶岗 ``skill_id`` |
| `zt_component` | 逻辑组件名（如 ``orchestrator``、``skill_command_gateway``） |
| `zt_outcome` | 稳定枚举：编排器 ``plan_aborted`` / ``goal_ok`` / ``goal_failed`` / ``step_ok`` / ``step_failed``；Gateway ``execute_ok`` / ``execute_failed`` / ``resolve_ambiguous``；内存 ``EventBus`` 与 Redis ``subscriber_failed``；Redis 另见 ``reader_started`` / ``publish_ok``（DEBUG）/ ``payload_invalid`` / ``reader_stopped_error``；进化 ``skill_not_in_registry``（WARNING）；落地 ``skip_missing_ids``（WARNING） |
| `zt_duration_ms` | 耗时毫秒（整数）：目标级为整次 ``process_goal``；步骤级为该步 command→result；Redis 为 publish 或 subscriber 回调 |
| `zt_bus_channel` | Redis Pub/Sub 频道名（与 ``ZHIWEITONG_REDIS_BUS_CHANNEL`` 等配置一致） |
| `zt_subscription_id` | Redis 总线本地订阅 id（``subscriber_failed`` 时便于定位回调） |
| `zt_topic` | 总线逻辑 topic（Redis publish / 分发失败时） |

辅助函数：`core.observability.zt_log_extra`；JSON 格式化类：`ZhiweitongJsonFormatter`。

### 可观测 P0：追踪拼接与从日志推导指标（手册工业级清单）

本节对应 **`docs/handbook-gap-and-industrialization.md`** 工业级清单 **P0 可观测** 的起步落地（不新增 topic、不改总线信封）。

**追踪 ID 怎么用**

- **`zt_goal_run_id`**：单次 **`process_goal`** 的根 ID，与 **`GoalReport.plan_id`**、编排器日志里的 `plan_id=` 一致。用它可把「规划 → 各步 command/result → 目标结束」串成一条业务追踪。
- **`zt_correlation_id`**：**每一步**总线信封上的 ID（编排器为每步生成新的 UUID），与 **`StepRunRecord.correlation_id`**、Gateway/Redis 侧分发一致。用于把**单步**延迟与总线事件对齐；**不是**跨步共用的同一个字符串。
- 拼接方式：先按 **`zt_goal_run_id`** 选同一次运行，再按 **`zt_step_index`**（0 起）排序；需要与总线明细对齐时，用该步的 **`zt_correlation_id`**。

**从 JSON 日志近似指标（无需额外 exporter 时）**

| 意图 | 建议 |
|------|------|
| 步骤耗时 | 取 `zt_component`=`orchestrator` 且带 **`zt_duration_ms`** 的步骤级记录（`zt_outcome` 为 `step_ok` / `step_failed`），或解析 `message` 中含 `orchestrator step` 的行 |
| 错误率 | 按 **`zt_outcome`** 聚合：`step_failed`、`goal_failed`、`execute_failed`、`plan_aborted` 与成功类 outcome 的比例（按环境定义分子分母） |
| 总线健康 | Redis Pub/Sub **没有**类似队列的「堆积深度」指标；请关注 **`subscriber_failed`**、**`payload_invalid`**、**`reader_stopped_error`** 及连接重试。更深监控可用 Redis **`CLIENT LIST`**、延迟探测或托管侧指标 |

全链路 **`correlation_id` 单一 ID 贯穿多步**：当前实现以 **`plan_id` / `zt_goal_run_id`** 作为根追踪、以**每步** `correlation_id` 作为总线关联；若产品要求「对外只暴露一个 trace id」，可在接入层将二者一并写入工单/Span 属性。

### 部署模型 P0：单进程与多副本（手册工业级清单）

本节对应 **`docs/handbook-gap-and-industrialization.md`** 工业级清单 **P0 部署模型** 的起步落地。逻辑 topic、Redis 载荷与切换条件以 **`docs/event_topics.md`** 为准（修订总线行为时**先改该文档**再改代码）。

**何时保持 `memory`**

- 开发与单进程集成测试；生产**仅单副本**且 Orchestrator、SkillCommandGateway、Evolution 等**共享同一进程**时，可用默认内存总线。

**何时必须切 `redis`**

- **多副本**或 command/result 路径跨**不同进程/主机**（例如 Orchestrator 在 Pod A、Gateway 在 Pod B）。此时须 **`ZHIWEITONG_EVENT_BUS_BACKEND=redis`**，且全集群 **`ZHIWEITONG_REDIS_BUS_CHANNEL`**（及可连通的 **`ZHIWEITONG_REDIS_URL`**）一致。

**上线前核对（多副本）**

1. **`event_topics.md`** 与当前代码中的 `topic_matches`、Redis 消息封装一致。  
2. **State**：多写实例勿共 SQLite 文件；使用同一远程 `ZHIWEITONG_DATABASE_URL` 或接受只读副本策略（见下节）。  
3. **Skill**：各实例部署同源、同注册清单（**`shared/org_canonical.py`** / 各包 `ORG_PATH`）。  
4. **Chroma**：多实例各自目录或共享只读挂载须单独设计；与 **`ZHIWEITONG_CHROMA_PATH`** 及 **`docs/ops-runbook.md` §5** 灾备一致。

### 安全 P0：总线、敏感 topic 与数据边界（手册工业级清单）

本节对应 **`docs/handbook-gap-and-industrialization.md`** 工业级清单 **P0 安全** 的起步落地。topic 分级与契约见 **`docs/event_topics.md`「安全与访问边界」**。

**总线**

- **`memory`**：无跨主机暴露；仍须保护运行进程的 OS 账户与调试接口。
- **`redis`**：**必须**限制 Redis 的网络可达性（安全组 / 防火墙）、强认证与 TLS；勿对公网开放无鉴权实例。频道名与 **`ZHIWEITONG_REDIS_BUS_CHANNEL`** 变更需全集群一致，避免误连「空集群」造成静默丢消息。

**敏感 topic 运维**

- **`/system/evolution/*`**：仅部署预期组件（编排器、审计岗、进化引擎、Promotion）；发布权限应纳入变更评审。
- **`/system/errors`**：下游归档或 SIEM 时注意 **payload 脱敏**（可能含业务字段）。

**知识库与 State**

- **`org_path`** 与注册 Skill 一致（**`shared/org_canonical.py`**）；知识库检索/写入的边界以代码与测试为准，产线仍应对 **DB、Chroma 目录、备份包**做访问控制与加密（见 **§2「配置与密钥 P0」**、**§3–§5**）。

### 多实例与 State（最小约束）

- **Redis 总线**：多副本时须 **`ZHIWEITONG_EVENT_BUS_BACKEND=redis`** 且 **`ZHIWEITONG_REDIS_BUS_CHANNEL`** 在全集群一致，否则 command/result 无法互通。
- **SQLite State**：默认库为**本地文件**，**不适合**多写副本共享同一 SQLite 文件（锁与损坏风险）。多实例请改为 **Postgres 等远程库**（连接串指向同一 `ZHIWEITONG_DATABASE_URL`），并自行处理迁移、连接池与备份。
- **SkillRegistry**：进程内单例；多实例下各进程加载的 Skill 集合应一致（同源部署或后续引入注册发现）。

## 3. 备份建议（频率仅为建议）

| 对象 | 建议 | 说明 |
|------|------|------|
| `var/zhiweitong.db` | 日备 + 变更前手工拷 | SQLite 单文件；备份前尽量**停写**或接受 WAL 一致性问题 |
| `var/chroma/` | 日备或与 DB 同批次 | 目录拷贝；与 DB **同一时间点**备份便于对账 |
| `*.promote-backup-*` | 随 `promote-apply --write` 自动生成 | 与 Git 提交/回滚配合使用 |

示例（在仓库根、服务已停或低峰）：

```bash
ts=$(date +%Y%m%d-%H%M%S)
tar -czf "backup-zhiweitong-${ts}.tar.gz" var/zhiweitong.db var/chroma 2>/dev/null || true
```

若 `var/` 下文件不存在，`tar` 仍可能打包空清单；按实际路径调整。

## 4. 恢复步骤（概要）

1. **停应用**（避免覆盖正在写入的 DB / Chroma）。
2. 将备份中的 `zhiweitong.db` 与 `chroma` 目录还原到与运行时一致的 **`var/`**（或与环境变量指向的路径一致）。
3. 确认 `ZHIWEITONG_DATABASE_URL`、`ZHIWEITONG_CHROMA_PATH` 与还原路径一致。
4. 启动后做一次** smoke**（例如对关键 Skill `validate`、或只读查询 State）。

**仅进化落盘回滚**：优先 `git checkout -- skills/...`；或使用 `promote-apply` 生成的 **`*.promote-backup-<unix_ts>`** 覆盖回 Skill 文件。

## 5. 灾备演练与 State / Chroma 一致性（手册 P1）

本节对应 **`docs/handbook-gap-and-industrialization.md`** 工业级清单中的 **P1 灾备**（起步落地）；不引入新总线 topic、不改信封。

### 5.1 一致性约定

- **State（SQLite）** 与 **Chroma 持久化目录** 可能同时引用「同一进化/知识」的不同侧面：State 存元数据与标记，Chroma 存向量与文档正文。恢复时**必须**使用**同一备份批次**中的 `zhiweitong.db` 与 `var/chroma/`（见 §3 示例 tarball），避免「库已回滚、向量仍新」或反向导致检索与 State 不一致。
- 若只恢复其一：可能出现 `knowledge_doc_id` 在 State 中存在但 Chroma 中无对应集合/文档（或相反）。处置需业务裁定：重跑 **`promote-preview`**、从 Git 恢复 Skill、或按运维流程清空一侧后重建（超出本文时单独评审）。

### 5.2 建议演练节奏与记录

| 动作 | 建议频率 | 记录要点 |
|------|----------|----------|
| 全量备份（DB + chroma） | 日备；**重大变更/发版前**必做 | 备份文件名时间戳、存放位置 |
| **恢复演练**（在副本目录或 Staging） | **每季度**或架构变更后 | 解压 → 对齐 `ZHIWEITONG_*` → smoke（如 `make verify` 在 CI、或最小进程启动 + 只读 retrieve） |
| RPO / RTO | 按组织目标单独立项 | **RPO**：可接受丢失的数据时段（通常 ≤ 上次备份时刻）；**RTO**：从停服到恢复可读 State+检索的耗时上界 |

演练不要求在生产高峰执行；以**可重复命令**（§3 的 `tar`、§4 的还原顺序）为准，结果记入变更单或内部 wiki 即可满足「文档化」起步。

## 6. `promote-preview` / `promote-apply`（运维侧）

- **审阅**：`poetry run zhiweitong promote-preview --doc-id <uuid> [--chroma-path DIR] [--skill-file PATH]`
- **预览改动**：`poetry run zhiweitong promote-apply --doc-id <uuid> ...`（stdout unified diff，stderr 提示加 `--write`）
- **写 Skill 源文件**：同上并加 **`--write`**（同目录先写备份文件）

Makefile：`make promote-preview DOC_ID=…`、`make promote-apply DOC_ID=… [WRITE=1]`（见仓库根 `Makefile`）。

**不要在 CI job 里对生产仓库执行 `--write`**；合入仍以 PR + 人工审查为准。

## 7. 与仓库 `.gitignore`

本地 `*.db`、`.venv/`、缓存目录等已忽略；**`var/chroma` 默认不忽略**（若需全员本地忽略可自行加规则）。勿将含业务数据的 `var/` 提交到公开仓库。

---

*修订时请同步 `docs/evolution-promotion-professional-plan.md`、`docs/orchestrator-llm.md` 与 `CLAUDE.md` 中的交叉引用。*

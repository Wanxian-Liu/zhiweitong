# 智维通 · 运维一页纸（本地数据与进化 CLI）

面向单机 / 小集群：**SQLite State**、**Chroma 知识库目录**、以及 **`promote-*` CLI** 的路径与备份约定。产线若迁 Postgres / 对象存储，应另写部署说明并替换本节默认值。

## 0. 组织树（`org_path`）

- 已注册 Skill 的 **`org_path`** 列表以仓库 **`shared/org_canonical.py`** 为准；与各 Skill 模块常量一致性由 **`tests/test_zz_org_canonical_contract.py`** 保证。  
- 进程内构建完整前缀树可使用 **`core.org_tree.canonical_org_tree()`**。定稿组织数据变更时同步 **`文案汇辑`** 与本文件及 **`docs/handbook-gap-and-industrialization.md`**。

### 主垂直切片 L2（`production-inventory-v1`）

- 链上叶岗（排产 → 物料需求 → 入库验收 → 库存管理 → **出库拣货**）在返回的 **`summary`** 中带 **`l2_reconcile`**：`grain`（对账粒度）、`keys`（与台账对齐的主键）、`basis_qty_field`（主数量字段名）、`ledger_hint`（与人工作业说明）。辅助模块 **`shared/slice_l2.py`**。  
- **`exception_code`**：`W_MRP_NET_SHORTAGE`（原料净需求大于现存量）、`W_INBOUND_SHORTFALL`（订购与实收短缺）、`W_OUTBOUND_SHORTFALL`（出库需求与实拣短缺）、`I_REORDER_SUGGESTED`（现存量低于阈值，信息类）；**财务岗**：`W_FIN_AR_LINE_MISMATCH`、`W_FIN_AP_LINE_MISMATCH`（应收/应付与收付款笔数不一致的示意规则）；正常为 `null`。  
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

## 5. `promote-preview` / `promote-apply`（运维侧）

- **审阅**：`poetry run zhiweitong promote-preview --doc-id <uuid> [--chroma-path DIR] [--skill-file PATH]`
- **预览改动**：`poetry run zhiweitong promote-apply --doc-id <uuid> ...`（stdout unified diff，stderr 提示加 `--write`）
- **写 Skill 源文件**：同上并加 **`--write`**（同目录先写备份文件）

Makefile：`make promote-preview DOC_ID=…`、`make promote-apply DOC_ID=… [WRITE=1]`（见仓库根 `Makefile`）。

**不要在 CI job 里对生产仓库执行 `--write`**；合入仍以 PR + 人工审查为准。

## 6. 与仓库 `.gitignore`

本地 `*.db`、`.venv/`、缓存目录等已忽略；**`var/chroma` 默认不忽略**（若需全员本地忽略可自行加规则）。勿将含业务数据的 `var/` 提交到公开仓库。

---

*修订时请同步 `docs/evolution-promotion-professional-plan.md`、`docs/orchestrator-llm.md` 与 `CLAUDE.md` 中的交叉引用。*

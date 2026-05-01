# 智维通 · 运维一页纸（本地数据与进化 CLI）

面向单机 / 小集群：**SQLite State**、**Chroma 知识库目录**、以及 **`promote-*` CLI** 的路径与备份约定。产线若迁 Postgres / 对象存储，应另写部署说明并替换本节默认值。

## 1. 默认路径（相对「进程当前工作目录」）

| 资源 | 默认位置 | 说明 |
|------|----------|------|
| State（SQLite） | `./var/zhiweitong.db` | 来自 `ZHIWEITONG_DATABASE_URL` 缺省值，见 `config/settings.py` |
| Chroma 持久化目录 | `./var/chroma` | `promote-preview` / `promote-apply` 在未指定 `--chroma-path` 且未设环境变量时使用 |
| Skill 源码根 | 仓库根 | CLI 通过 `ZHIWEITONG_PROJECT_ROOT` 覆盖（测试与多检出常用） |

**注意**：`sqlite+aiosqlite:///./var/zhiweitong.db` 中的 `./var/` 解析依赖**启动进程时的 cwd**。生产环境建议写**绝对路径**的 `ZHIWEITONG_DATABASE_URL`，或固定工作目录后再启动。

## 2. 环境变量（摘要）

本地可复制 **`.env.example`** → **`.env`**，按注释取消注释并填写；运行时仍依赖进程环境（若未使用 shell 自动 `export`，可用 `set -a; source .env; set +a` 或部署平台注入）。

| 变量 | 用途 | 缺省 |
|------|------|------|
| `ZHIWEITONG_DATABASE_URL` | 异步 SQLAlchemy 连接串（State 等） | `sqlite+aiosqlite:///./var/zhiweitong.db` |
| `ZHIWEITONG_CHROMA_PATH` | `promote-preview` / `promote-apply` 的 Chroma 目录 | `<repo>/var/chroma`（由 CLI 在设 `ZHIWEITONG_PROJECT_ROOT` 时相对该根解析） |
| `ZHIWEITONG_PROJECT_ROOT` | 仓库根（`skills/`、`cli/` 等） | `cli/main.py` 所在目录的上一级 |
| `ZHIWEITONG_REDIS_URL` | Redis（预留总线） | `redis://localhost:6379/0` |
| `ZHIWEITONG_LLM_API_KEY` / `ZHIWEITONG_LLM_BASE_URL` | Orchestrator LLM | 见 `config/settings.py` |

密钥与端点：**勿提交 `.env`**；CI 不注入真实 LLM 密钥亦可跑通测试门禁。

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

*修订时请同步 `docs/evolution-promotion-professional-plan.md` 与 `CLAUDE.md` 中的交叉引用。*

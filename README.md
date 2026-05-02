# 智维通（zhiweitong）

全新开发的数字员工平台代码仓：**仓库与 Python 包名统一为 `zhiweitong`**（智维通标准拼音）。

- **规范名**：OpenCLAW（见《智维通数字员工体系 · OpenCLAW 原生实现规范》）——指**契约与架构**，不是文件夹名。
- **旧原型（不继续维护本仓）**：`~/.openclaw/skills/zhihuitong` 等为历史路径，标识 `zhihuitong` 与拼音不一致，仅作迁移参考，见 `docs/LEGACY.md`。
- **主仓库约定**：日常开发与写文档请在 **本 Git 仓库的 clone**（示例路径 **`~/projects/zhiweitong`**）中进行；OpenClaw 技能目录**不是**主源码树。约定说明见 **`CLAUDE.md`**「主仓库（真源）」。
- **推进顺序**：优先 **主体**（垂直切片 + core）→ **流程**（`docs/ralph-loop.md`、promote）→ **快消与运维** 分里程碑；说明见 **`docs/handbook-gap-and-industrialization.md`**「**推荐推进顺序（主体 → 流程 → 快消与运维）**」。
- **参与贡献**：PR 前命令与总线约定见 **`CONTRIBUTING.md`**。

开发入口：`CLAUDE.md`、`docs/event_topics.md`；本地数据与备份见 **`docs/ops-runbook.md`**。  
环境变量骨架：**`.env.example`**（复制为 `.env` 后填写，勿提交 `.env`）。  
模块级 Cursor 提示词（Phase 0–3）仍可在记忆殿堂调阅：`~/.openclaw/memory-vault/data/projects/zhihuitong/OpenCLAW-Cursor模块提示词手册.md`（文中目录已改为本仓库名）。

## 快速开始（一键节奏）

1. **安装**：需 **Python 3.12+**、**Poetry**。在仓库根执行：  
   `poetry install --no-interaction`
2. **环境（可选）**：`cp .env.example .env`，按需填写 LLM/Redis 等；跑测试可不建 `.env`（pytest 会跳过加载 `.env`）。
3. **健康检查**：  
   - 日常开发：`make dev`（`poetry install` + **`make spine`** 主干垂直切片回归）  
   - 合并/CI 对齐：`make verify`（全量测试 + `core/*` 与快消 Skill 覆盖率门禁）

事件 topic 与信封的**表格速查**：**`docs/event-contract-summary.md`**（权威约定仍以 **`docs/event_topics.md`** 为准）。

## 主干回归（官方垂直切片）

改 **core / 总线 / 链上 Skill** 时，先在仓库根执行 **`make spine`**（无 LLM、无 Redis）：端到端 **排产 → 物料 → 入库 → 库存** + 与 `shared/vertical_slices.py` 的契约对齐。命令与期望说明见 **`docs/vertical-slices.md`**「官方回归路径」。合并前建议 **`make verify`**（全量测试 + `core/*` 覆盖率 ≥85%，对齐 CI）；节奏说明见 **`docs/ralph-loop.md`**。

## 故障排查（CI）

- GitHub **Required checks** 若配置了名称，需与 **`.github/workflows/ci.yml`** 里 **job `test`** 上报的检查一致，否则 merge 前可能一直黄或误判；详见 **`CONTRIBUTING.md`**。

## CLI（摘要）

- `poetry run zhiweitong --help`
- 进化审阅：`promote-preview`；**落盘**：`promote-apply`（默认仅 unified diff，确认后加 **`--write`**，会先写 `*.promote-backup-<时间戳>`）
- **Makefile**：`make promote-preview DOC_ID=…`、`make promote-apply DOC_ID=…`；写盘加 **`WRITE=1`**；可选 **`CHROMA=`**、**`SKILL=`**（见 `Makefile` 注释）

# 智维通（zhiweitong）

全新开发的数字员工平台代码仓：**仓库与 Python 包名统一为 `zhiweitong`**（智维通标准拼音）。

- **规范名**：OpenCLAW（见《智维通数字员工体系 · OpenCLAW 原生实现规范》）——指**契约与架构**，不是文件夹名。
- **旧原型（不继续维护本仓）**：`~/.openclaw/skills/zhihuitong` 等为历史路径，标识 `zhihuitong` 与拼音不一致，仅作迁移参考，见 `docs/LEGACY.md`。
- **主仓库约定**：日常开发与写文档请在 **本 Git 仓库的 clone**（示例路径 **`~/projects/zhiweitong`**）中进行；OpenClaw 技能目录**不是**主源码树。约定说明见 **`CLAUDE.md`**「主仓库（真源）」。
- **推进顺序**：优先 **主体**（垂直切片 + core）→ **流程**（`docs/ralph-loop.md`、promote）→ **快消与运维** 分里程碑；说明见 **`docs/handbook-gap-and-industrialization.md`**「**推荐推进顺序（主体 → 流程 → 快消与运维）**」。
- **参与贡献**：PR 前命令、分支保护与总线「先文档后代码」见 **`CONTRIBUTING.md`**。

开发入口：**`CLAUDE.md`**、**`docs/event_topics.md`**；topic/信封**速查表**（权威仍以 `event_topics` 为准）：**`docs/event-contract-summary.md`**。本地数据与备份见 **`docs/ops-runbook.md`**。  
环境变量骨架：**`.env.example`**（复制为 `.env` 后填写，勿提交 `.env`）。  
模块级 Cursor 提示词（Phase 0–3）仍可在记忆殿堂调阅：`~/.openclaw/memory-vault/data/projects/zhihuitong/OpenCLAW-Cursor模块提示词手册.md`（文中目录已改为本仓库名）。

## 快速开始（最短路径）

**前置**：**Python 3.12+**、**Poetry**、[Git](https://git-scm.com/)（已配置 `origin` 指向本仓库即可）。

```bash
git clone <你的 fork 或 Wanxian-Liu/zhiweitong 的 URL> zhiweitong
cd zhiweitong
poetry install --no-interaction
```

**可选环境**：`cp .env.example .env`；仅跑测试可不建 `.env`（pytest 会跳过加载 `.env`）。

| 命令 | 何时用 | 说明 |
|------|--------|------|
| **`make spine`** | 改 core / 总线 / 链上 Skill 后的**快速心跳** | 官方垂直切片 + 注册表契约；无 LLM、无 Redis；几秒级（用例数见 **`docs/vertical-slices.md`**） |
| **`make dev`** | 新 clone 或长期开发**日常起手** | `poetry install` + **`make spine`**（见根目录 **`Makefile`**） |
| **`make verify`** | **合并前 / 对齐 CI** | 全量 `pytest` + **`core/*` ≥85%** + **`skills/quick_consumption/*.py` ≥90%** |

**文档地图（按需打开）**

| 需求 | 文档 |
|------|------|
| 工程宪法、主仓库约定、与 Agent 协作 | **`CLAUDE.md`** |
| 事件 topic / Redis / 安全（完整约定） | **`docs/event_topics.md`** |
| topic 表格 + 变更顺序速查 | **`docs/event-contract-summary.md`** |
| 垂直切片与 `make spine` 列表 | **`docs/vertical-slices.md`** |
| PR 与 CI、改总线时的顺序 | **`CONTRIBUTING.md`** |
| 单轮节奏、Ralph 式验收 | **`docs/ralph-loop.md`** |

## 主干回归（官方垂直切片）

**`make spine`** 覆盖主链 **排产 → 物料 → 入库 → 库存 → 出库** 及财务/仓储/生产补链的契约测试；完整命令列表与用例数见 **`docs/vertical-slices.md`**「官方回归路径」。合并前节奏见 **`docs/ralph-loop.md`**。

## 故障排查（CI）

- GitHub **Required checks** 若配置了名称，需与 **`.github/workflows/ci.yml`** 里 **job `test`** 上报的检查一致，否则 merge 前可能一直黄或误判；详见 **`CONTRIBUTING.md`**。

## CLI（摘要）

- `poetry run zhiweitong --help`
- 进化审阅：`promote-preview`；**落盘**：`promote-apply`（默认仅 unified diff，确认后加 **`--write`**，会先写 `*.promote-backup-<时间戳>`）
- **Makefile**：`make promote-preview DOC_ID=…`、`make promote-apply DOC_ID=…`；写盘加 **`WRITE=1`**；可选 **`CHROMA=`**、**`SKILL=`**（见 `Makefile` 注释）

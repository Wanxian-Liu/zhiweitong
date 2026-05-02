# 智维通 · 工程宪法（CLAUDE.md）

本文件是 **本仓库** 开发的主提示词；与 OpenCLAW **规范**对齐，**产品 / 仓库标识** 一律为 **`zhiweitong`**。

## 命名

| 名称 | 含义 |
|------|------|
| **智维通** | 产品中文名 |
| **zhiweitong** | 仓库根目录、Poetry 包名、导入顶层包（标准拼音） |
| **OpenCLAW** | 架构/契约名称（文档用语），**不是**本仓库目录名 |
| **zhihuitong** | 仅指 **旧代码路径**（历史拼写），新代码禁止新增该标识 |

## 主仓库（真源）

- **仓库身份**：以本目录 **`git remote -v`** 所示的 **`origin`**（GitHub **`Wanxian-Liu/zhiweitong`**）为准；代码、`docs/`、**`make verify`**、PR 均针对该远程，**不**以 OpenClaw 安装目录下的副本为主。
- **本地工作副本**：在任意路径 **clone 一次** 作为日常修改目录（示例 **`~/projects/zhiweitong`**，与包名一致便于记忆）。**不要**在 **`~/.openclaw/skills/zhihuitong`** 等与技能挂载相关的路径当作主工程长期双改；需要时从该 clone **单向**同步到 OpenClaw。

## OpenCLAW 与仓库独立性

- **OpenCLAW** 在本仓库指 **架构契约**（无状态 Skill、仅 Event Bus、`org_path` 前缀、`supervisor=ai_ceo` 等），**不是**必须随附的第三方「大一统运行时」或封闭平台。
- **zhiweitong** 可 **独立构建、测试与部署**（Poetry、自有 CI、SQLite / Chroma、预留 Redis）；Cursor、MCP、外部 LLM 等 **按需接入**，不构成强依赖。
- 产品可独立演进与商业化；只要不破坏 **`CLAUDE.md`** 与 **`docs/event_topics.md`** 中的边界，即 **不偏离 OpenCLAW**，也 **不绑定** OpenClaw 某一具体发行版或工具链。

## 不可违背（OpenCLAW）

1. **Skill 无状态**；持久化只经 **State Manager**。  
2. **Skill 之间禁止直连**；只经 **Event Bus**（topic 见 `docs/event_topics.md`）。  
3. **`supervisor` 字面量恒为 `ai_ceo`**；部门主管 = 聚合 Skill，不是第二 Orchestrator。  
4. **org_path** 前缀：`/智维通/城市乳业/...`。  
5. **覆盖率**：阶段性门槛见 `pyproject.toml` 注释；默认先收紧 **`core/`**，再扩到各 Skill。

## 文档与提示词

- **事件约定**：`docs/event_topics.md`（修改总线前必须先改此文件）；**表格速查**：`docs/event-contract-summary.md`（含 **主体推进步骤** 拆单清单）。  
- **手册完成度与工业级优先级**：`docs/handbook-gap-and-industrialization.md`（含 **「推荐推进顺序（主体 → 流程 → 快消与运维）」**）。  
- **Ralph 式持续开发（单任务迭代 + 客观验收）**：`docs/ralph-loop.md`；提交前本地建议 **`make verify`**（与 CI 覆盖率门禁一致）。  
- **进化批准落地（工业级流程）**：`docs/evolution-promotion-professional-plan.md`。  
- **运维一页纸（Chroma / SQLite / 环境变量 / 备份）**：`docs/ops-runbook.md`。  
- **垂直切片 L3 外部集成（起步）**：`docs/vertical-slice-l3-integration.md`。  
- **Orchestrator · LLM 规划、重试、超时与日志**：`docs/orchestrator-llm.md`。  
- **环境变量骨架**：根目录 **`.env.example`**（复制为 `.env`；`load_settings()` 读环境变量，见 `config/settings.py`）。  
- **CI**：合并前请保持 `.github/workflows/ci.yml` 通过；变更 `skills/**/*.py` 时 PR 会逐项 `zhiweitong validate`。  
- **业务与阶段整理**：`~/.openclaw/memory-vault/data/projects/zhihuitong/文案汇辑.md`（定稿 v4）。  
- **按模块生成代码**：`~/.openclaw/memory-vault/data/projects/zhihuitong/OpenCLAW-Cursor模块提示词手册.md` — 复制其中 **0.1 → …** 到 Cursor，并 `@` 本仓库根目录。
- **贡献与 CI 约定**：根目录 **`CONTRIBUTING.md`**（clone、验证命令、总线文档优先、GitHub required check 名称）。

## 与 Agent 协作（仓库偏好）

- **默认**：任务边界清楚时，**连续执行**实现、测试与文档同步，**减少**「是否继续」类中途确认。  
- **须先停下或征得确认**：破坏性操作（删生产数据、大范围 `git reset --hard` 等）、**未在 `docs/event_topics.md` 落地的总线/信封变更**、新增依赖或扩大网络暴露面、以及**没有跑过 `make verify`（或等价 CI）却宣称已完成**。  
- **收束**：与 **`docs/ralph-loop.md`** 一致——合并前 **`make verify`**；日常可 **`make spine`** 做快速心跳。

## Cursor 开场（可复制）

```text
@CLAUDE.md @docs/event_topics.md
本仓库为 zhiweitong；严格按 OpenCLAW：无状态、仅 Event Bus、supervisor=ai_ceo、禁止 Skill 互调。实现手册第「X.Y」节。
```

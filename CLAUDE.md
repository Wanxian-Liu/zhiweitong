# 智维通 · 工程宪法（CLAUDE.md）

本文件是 **本仓库** 开发的主提示词；与 OpenCLAW **规范**对齐，**产品 / 仓库标识** 一律为 **`zhiweitong`**。

## 命名

| 名称 | 含义 |
|------|------|
| **智维通** | 产品中文名 |
| **zhiweitong** | 仓库根目录、Poetry 包名、导入顶层包（标准拼音） |
| **OpenCLAW** | 架构/契约名称（文档用语），**不是**本仓库目录名 |
| **zhihuitong** | 仅指 **旧代码路径**（历史拼写），新代码禁止新增该标识 |

## 不可违背（OpenCLAW）

1. **Skill 无状态**；持久化只经 **State Manager**。  
2. **Skill 之间禁止直连**；只经 **Event Bus**（topic 见 `docs/event_topics.md`）。  
3. **`supervisor` 字面量恒为 `ai_ceo`**；部门主管 = 聚合 Skill，不是第二 Orchestrator。  
4. **org_path** 前缀：`/智维通/城市乳业/...`。  
5. **覆盖率**：阶段性门槛见 `pyproject.toml` 注释；默认先收紧 **`core/`**，再扩到各 Skill。

## 文档与提示词

- **事件约定**：`docs/event_topics.md`（修改总线前必须先改此文件）。  
- **手册完成度与工业级优先级**：`docs/handbook-gap-and-industrialization.md`。  
- **进化批准落地（工业级流程）**：`docs/evolution-promotion-professional-plan.md`。  
- **运维一页纸（Chroma / SQLite / 环境变量 / 备份）**：`docs/ops-runbook.md`。  
- **环境变量骨架**：根目录 **`.env.example`**（复制为 `.env`；`load_settings()` 读环境变量，见 `config/settings.py`）。  
- **CI**：合并前请保持 `.github/workflows/ci.yml` 通过；变更 `skills/**/*.py` 时 PR 会逐项 `zhiweitong validate`。  
- **业务与阶段整理**：`~/.openclaw/memory-vault/data/projects/zhihuitong/文案汇辑.md`（定稿 v4）。  
- **按模块生成代码**：`~/.openclaw/memory-vault/data/projects/zhihuitong/OpenCLAW-Cursor模块提示词手册.md` — 复制其中 **0.1 → …** 到 Cursor，并 `@` 本仓库根目录。

## Cursor 开场（可复制）

```text
@CLAUDE.md @docs/event_topics.md
本仓库为 zhiweitong；严格按 OpenCLAW：无状态、仅 Event Bus、supervisor=ai_ceo、禁止 Skill 互调。实现手册第「X.Y」节。
```

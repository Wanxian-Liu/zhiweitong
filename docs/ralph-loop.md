# Ralph 式持续开发（zhiweitong）

**Ralph** 在本仓库不绑定外部 Sindri 脚本，而是采用同一套原则：**每一轮迭代只承认可客观验证的结果**（测试、覆盖率、契约文档），避免「以为做完」但未可证。

## 与 CLAUDE.md 的关系

- **宪法**：根目录 **`CLAUDE.md`**（无状态 Skill、仅 Event Bus、`supervisor=ai_ceo`、`org_path` 前缀、先改 `docs/event_topics.md` 再改总线等）——**每轮开发前扫一眼，做完对照检查**。
- **计划 backlog**：**`docs/handbook-gap-and-industrialization.md`** —— 含 **「第一步：城市乳业基础岗位（大纲内、有上限）」** 清单与完成判定；**Phase 0–3** 表格中优先级 **P2** 与 **Phase 2 横线扩岗** 为持续迭代；单轮任务可从 **P2**、**路线图** 或 **垂直切片加深** 中取**下一项**。封版范围内的 **「—」** 行不必再拆任务。
- **主体 → 流程 → 快消与运维**：时间维度上优先保证 **垂直切片 + core**（主体），再固化 **本文件单轮节奏 + promote 流程**；**快消板块**与 **运维硬化**（ops-runbook / 路线图 P0）宜 **分里程碑后置**，详见 **`docs/handbook-gap-and-industrialization.md`**「**推荐推进顺序（主体 → 流程 → 快消与运维）**」。

## 我困了 / 换会话时，能否「自动接着做」？

- **同一条 Cursor 对话**不会在你关机后继续跑；**新开对话**也没有上一轮的隐式记忆。
- **可持续做法**：
  1. 下一轮把下面 **「可复制开场」** 贴进 Agent，并 `@CLAUDE.md` `@docs/handbook-gap-and-industrialization.md` `@docs/ralph-loop.md`。
  2. 本地或 CI：用 **`make verify`**（或仅 **`make spine`** 做快速心跳）得到客观通过/失败。
  3. 若你本机有通用 **Ralph 循环脚本**（如多轮验证），可把 **`make verify`** 或 **`make spine`** 注册为其中一步的 `check_fn`，原则不变：**无命令输出 = 未通过**。

## 单轮迭代（推荐节奏）

1. **选题**：从 `handbook-gap-and-industrialization.md`（或 **路线图 / P2**）取**一个**明确项（例如：某一 Phase 2 切片加深、可观测增强）。
2. **改前**：若动总线 / 信封，**先改** **`docs/event_topics.md`**。
3. **实现**：尽量少扩散；遵守 OpenCLAW 边界（见 `CLAUDE.md`）。
4. **验证阶梯**：
   - 开发中：**`make spine`**（供应链 + **财务** + **仓储 / 生产补链**垂直切片 E2E 与注册表契约，见 **`docs/vertical-slices.md`**）。
   - 合并/提交前：**`make verify`**（全量 `pytest` + **`core/*` ≥85%** + **`skills/quick_consumption/*.py` ≥90%**，与 **`.github/workflows/ci.yml`** 一致）。
5. **收束**：若行为或运维语义变了，同步 **`docs/ops-runbook.md`** 等交叉文档（见 `CLAUDE.md` 文档列表）。

## 可复制开场（下一会话给 Agent）

```text
@CLAUDE.md @docs/handbook-gap-and-industrialization.md @docs/ralph-loop.md
仓库 zhiweitong。严格 OpenCLAW。优先主体（垂直切片 / core）；快消与运维分里程碑后置（见 handbook-gap「推荐推进顺序」）。
从 handbook-gap（P2 / 路线图 / Phase 2 切片）里选「下一项」单任务实现；动总线则先 event_topics.md。
验收：make spine（过程中可随时跑），结束前 make verify 必须通过。
```

## 命令对照

| 命令 | 用途 |
|------|------|
| `make dev` | `poetry install` + **`make spine`**（本地 bootstrap / 日常心跳） |
| `make spine` | 官方主干回归（快）：多切片 E2E + 注册表契约（见 vertical-slices） |
| `make test` | 全量 pytest |
| `make verify` | 全量 pytest + **`core/*` ≥85%** + **`skills/quick_consumption/*.py` ≥90%**（对齐 CI） |

---

*修订时请保持与 `CLAUDE.md`、`docs/vertical-slices.md`、CI 工作流一致。*

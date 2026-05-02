# 事件与信封契约速查（表格）

**用途**：给人类与 Agent **快速定位** topic 形状、信封字段与「改哪里」顺序；**不**替代 **`docs/event_topics.md`** 中的部署、安全、Redis 细节。

**权威层级**（冲突时以上为准）：

1. **`docs/event_topics.md`** — 逻辑 topic、Redis 载荷、部署模型、安全边界、与实现对齐的说明。  
2. **本文件** — 速查与推进清单；若与上条不一致，**改本文件**。  
3. **代码** — `core/event_bus.py`、`core/redis_event_bus.py`、`shared/models.py` 等；实现变更须回溯更新 **`event_topics.md`**。

---

## 逻辑 Topic 模式

| 类型 | Topic 模式 | 典型发布方 | 典型订阅方 |
|------|------------|------------|------------|
| 命令 | `{org_path}/command` | Orchestrator、EvolutionEngine 等 | `SkillCommandGateway` → 该 `org_path` 叶岗 Skill |
| 结果 | `{org_path}/result` | 叶岗 Skill | Orchestrator / 聚合岗（通配订阅 `…/result`） |
| 系统错误 | `/system/errors` | Orchestrator、Skill | 观测 / 进化引擎 |
| 进化审核 | `/system/evolution/review` | EvolutionEngine、Orchestrator | 人工 / 审计流 |
| 进化批准 | `/system/evolution/approved` | 审计岗 `gov_audit_review` | `EvolutionPromotion` |
| 进化否决 | `/system/evolution/rejected` | 审计岗 | 下游订阅（若有） |

**前缀**：`/智维通/城市乳业`；`org_path` 与 **`shared/org_canonical.py`**、各 Skill 模块 **`ORG_PATH`**、**`docs/vertical-slices.md`** 一致。

**通配与匹配**：见 **`event_topics.md`**「通配订阅」与 `core/event_bus.topic_matches`。

---

## 信封字段（`EventEnvelope`）

实现见 **`shared/models.py`**。

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | `str` | 默认 `"1"` |
| `correlation_id` | `str` | 追踪 ID；编排每步可独立生成；跨组件对齐见 **`docs/orchestrator-llm.md`** |
| `org_path` | `str` | 必须与组织树前缀一致 |
| `skill_id` | `str` | 叶岗或系统组件标识 |
| `payload` | `dict` | 业务载荷（`command`/`result` 内约定由 Gateway 与 Skill 对齐） |

---

## Redis 单条消息（多实例）

JSON 字符串：`{"t": "<topic>", "e": <event dict>}` — 见 **`core/redis_event_bus.py`**、**`event_topics.md`**「Redis 传输」。  
**何时用 `memory` vs `redis`**：见 **`event_topics.md`**「部署模型：内存总线 vs Redis」。

---

## 与垂直切片的关系

- **业务链上的 `org_path` / `skill_id` / `rule_version` / 计划动作**：单一事实来源 **`shared/vertical_slices.py`** + **`docs/vertical-slices.md`**；集成测试 **`tests/test_zz_vertical_slice_*.py`**。  
- **总线 topic 形状**：不因切片而变；切片只决定「哪些 `org_path` 上会发 `command`/`result`」。  
- **主干回归**：根目录 **`make spine`**（当前用例数见 **`vertical-slices.md`**「官方回归路径」）。

---

## 变更时的推荐顺序（打勾清单）

1. **只改链上业务规则、不改总线**  
   - 先 **`shared/vertical_slices.py`** → **`docs/vertical-slices.md`** → 相关 **`tests/test_zz_*.py`** → **`make spine`**。

2. **改 topic、信封、Redis 语义或安全边界**  
   - **先** **`docs/event_topics.md`** → 再 **`core/`** / **`shared/`** → 更新 **本速查**（若表格已变）→ **`make verify`**。

3. **新增或调整 `org_path`**  
   - **`shared/org_canonical.py`** + Skill **`ORG_PATH`** + **`tests/test_zz_org_canonical_contract.py`**（见 **`CONTRIBUTING.md`**）。

4. **合入前**  
   - **`make verify`**（全量 pytest + **`core/*`**、**`skills/quick_consumption/*.py`** 覆盖率门禁）。

与 **`docs/handbook-gap-and-industrialization.md`**「推荐推进顺序」第 1 条一致；**不**替代 **`vertical-slices.md`** 与 **`event_topics.md`** 的完整条文。

---

## 延伸阅读

| 主题 | 文档 |
|------|------|
| 部署、Redis、安全边界（完整条文） | **`docs/event_topics.md`** |
| 运维、密钥、备份、多实例 State | **`docs/ops-runbook.md`** |
| 垂直切片、岗位映射、`make spine` | **`docs/vertical-slices.md`**、**`shared/vertical_slices.py`** |
| Orchestrator 超时、重试、token | **`docs/orchestrator-llm.md`** |
| 单轮节奏与合并前验证 | **`docs/ralph-loop.md`** |
| 工程宪法与 Agent 协作偏好 | **`CLAUDE.md`** |

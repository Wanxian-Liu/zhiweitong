# Orchestrator · LLM 规划与超时（运维说明）

本文描述 **`core.orchestrator.Orchestrator`** 在 **`process_goal`** 中如何取计划、重试、超时，以及 **`GoalReport` / 日志**里可观测字段。与 **`.env.example`**、**`docs/ops-runbook.md`** 中的环境变量一致。

## 1. 两条规划路径

| 模式 | 条件 | 行为 |
|------|------|------|
| **注入 `plan_provider`** | 构造 `Orchestrator(..., plan_provider=async_fn)` | 不调用 HTTP；`plan_provider(goal_text)` 直接返回 `list[PlanStep]`；**无** LLM token 用量（`GoalReport.planner_tokens` 为 `None`）。用于测试或自定义规划器。 |
| **默认：OpenAI 兼容 API** | 未设置 `plan_provider`，且 **`ZHIWEITONG_LLM_API_KEY` 非空** | `POST {ZHIWEITONG_LLM_BASE_URL}/chat/completions`，解析 JSON 计划；响应体中的 **`usage`**（若存在）写入 **`GoalReport.planner_tokens`** 与 **`aggregated["planner_tokens"]`**。 |

若 **未** 提供 `plan_provider` 且 **API Key 为空**：不发起 HTTP 请求，立即返回失败的 **`GoalReport`**（`planner_error` 提示设置 `ZHIWEITONG_LLM_API_KEY` 或传入 `plan_provider`）。

## 2. HTTP 与重试

- **URL**：`{ZHIWEITONG_LLM_BASE_URL 去尾斜杠}/chat/completions`（默认 base 见 `config/settings.py`）。
- **单次请求超时**：Orchestrator **未**传入自定义 `http_client` 时，内部使用 **`httpx.AsyncClient(timeout=120.0)`**（秒）。传入自定义 client 时以该 client 的配置为准。
- **规划失败重试**：同一 goal 内，若单次调用在 **JSON 解析、校验、HTTP 错误、网络异常** 等任一环节抛异常，最多 **连续 3 次**（`attempt` 1～3）。**任一次成功即返回**，并带上**当次**成功的 **`usage`**（若有）；3 次均失败则 `steps` 为空，`planner_error` 为最后一次异常摘要。

**当前未实现**（需产品与实现另开需求）：降级到「空计划 / 固定模板 / 人工队列」、多模型主备切换、按 HTTP 状态码区分可重试错误。

## 3. 计划 JSON 与空计划

- LLM 须返回可被解析的 JSON，且符合 **`PlanPayload`**：`{"steps":[{"skill_path":"…","action":"…","params":{}}]}`（`skill_path` 为完整 org_path）。
- 若 **`steps` 为空数组** 且规划阶段无错误：`process_goal` **不会**报错，返回 **`ok=True`**、**`steps=[]`**。是否允许「空计划」由上游产品与 prompt 约束决定。

## 4. 步骤执行与超时

- 每个步骤：`EventBus` 发布 `command`，等待匹配 **`correlation_id` + `skill_id`** 的 **`result`**。
- **步骤超时**：`Orchestrator(..., step_timeout=60.0)`（默认 60s）；超时则该步 `ok=False`，`error="step_timeout"`，并视 Skill 元数据 **`abort_on_failure` / `strict`** 决定是否**中断后续步骤**。
- **Skill 返回 `ok: false`**：该步失败，同样可能触发 **`abort_on_failure`** 并发布 **`/system/errors`**（见 `shared.system_topics.SYSTEM_ERRORS`）。

## 5. Token 与结果路径

- **Planner**：OpenAI 风格响应中的 **`usage.prompt_tokens` / `completion_tokens` / `total_tokens`** → **`GoalReport.planner_tokens`** 与 **`aggregated["planner_tokens"]`**。
- **步骤**：Skill **`payload`** 中的 **`usage`** 对象，或顶层 **`prompt_tokens` / `completion_tokens`** → **`StepRunRecord`**，并写入 State 中对应 **`record`**（见 `process_goal` 内 `save_state`）。

便于对账时：同一 **`plan_id`** 串联 planner 与各步 **`correlation_id`**。

## 6. 日志（grep / 简单聚合）

编排器使用 **`logging`**，关键行包含固定子串与字段，便于 `grep`：

- 规划失败后提前返回：`orchestrator goal aborted`、`plan_id`、`error`。
- 开始执行步骤：`orchestrator goal`、`plan_id`、`step_count`、`planner_attempts`、`planner_tokens`。
- 发布命令：已有 `orchestrator published command`、`plan_id`、`correlation_id`。
- 步骤结束：`orchestrator step`、`plan_id`、`idx`、`skill_id`、`correlation_id`、`ok`、`duration_ms`、`err`。

生产环境若接入日志平台，可按 **`plan_id`**、**`correlation_id`** 做 trace 关联。

## 7. 修订

- 修改总线主题、信封字段或规划协议时：**先更新** **`docs/event_topics.md`** 与本文件，再改代码。

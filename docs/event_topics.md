# 事件 Topic 约定（zhiweitong）

**状态**：初稿 — 实现 `core/event_bus.py` 前可修订；修订须同步本文件与订阅方。

## 前缀

- 全局根：`/智维通/城市乳业`
- Topic 中 `org_path` 使用 **URL 编码或统一小写+下划线** 待定；当前建议 topic 字符串 **直接嵌入规范化 org_path**（与通配实现一致即可）。

## 模式（草案）

| 类型 | 模式 | 说明 |
|------|------|------|
| 命令 | `org_path{normalized}/command` | Orchestrator → Skill |
| 结果 | `org_path{normalized}/result` | Skill → 上游聚合 |
| 系统错误 | `/system/errors` | 全 Skill 异常上报 |
| 进化审核（占位） | `/system/evolution/review` | Phase 3 |

## 通配订阅

- 示例：订阅 `/智维通/城市乳业/*` 下所有 `result`，用于聚合岗（细则与 `event_bus` 实现同步）。

## JSON 信封（建议）

每条 `event: dict` 至少包含：

- `schema_version`
- `correlation_id`
- `org_path`
- `skill_id`
- `payload`

（具体字段在 `shared/models.py` 落地后同步本文。）

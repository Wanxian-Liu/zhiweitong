## 摘要

<!-- 简述本 PR 的目的（功能 / 修复 / 元数据修订） -->

## 关联

<!-- 工单、设计文档、或进化快照 -->

- 进化 / 元数据修订时**必填**：
  - `promotion` 知识库 **doc_id**：
  - 审计 **audit_correlation_id**（若适用）：
  - `zhiweitong promote-preview` 审阅稿（路径或粘贴要点）：
  - 若已本地落盘：说明是否跑过 **`zhiweitong promote-apply --doc-id …`（dry-run diff）**；**`--write`** 仅在本机执行并随本 PR 提交变更（勿在 CI 上写盘）：

## 检查项

- [ ] 已阅读 `CLAUDE.md` 与 `docs/event_topics.md`（若改总线 / topic，**先改文档再改代码**）
- [ ] 涉及 `skills/**/*.py`：本地已执行 `poetry run zhiweitong validate <文件>`（或与 CI 等价）
- [ ] 新增 / 调整 Skill：已补充或更新对应测试

## 工业级备注（可选）

- 是否影响 State / Chroma / 配置路径：
- 回滚方式（revert / 配置回滚）：

# 智维通（zhiweitong）

全新开发的数字员工平台代码仓：**仓库与 Python 包名统一为 `zhiweitong`**（智维通标准拼音）。

- **规范名**：OpenCLAW（见《智维通数字员工体系 · OpenCLAW 原生实现规范》）——指**契约与架构**，不是文件夹名。
- **旧原型（不继续维护本仓）**：`~/.openclaw/skills/zhihuitong` 等为历史路径，标识 `zhihuitong` 与拼音不一致，仅作迁移参考，见 `docs/LEGACY.md`。

开发入口：`CLAUDE.md`、`docs/event_topics.md`；本地数据与备份见 **`docs/ops-runbook.md`**。  
模块级 Cursor 提示词（Phase 0–3）仍可在记忆殿堂调阅：`~/.openclaw/memory-vault/data/projects/zhihuitong/OpenCLAW-Cursor模块提示词手册.md`（文中目录已改为本仓库名）。

## CLI（摘要）

- `poetry run zhiweitong --help`
- 进化审阅：`promote-preview`；**落盘**：`promote-apply`（默认仅 unified diff，确认后加 **`--write`**，会先写 `*.promote-backup-<时间戳>`）
- **Makefile**：`make promote-preview DOC_ID=…`、`make promote-apply DOC_ID=…`；写盘加 **`WRITE=1`**；可选 **`CHROMA=`**、**`SKILL=`**（见 `Makefile` 注释）

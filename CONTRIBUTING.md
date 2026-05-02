# 贡献指南（zhiweitong）

工程宪法见根目录 **`CLAUDE.md`**；契约与总线见 **`docs/event_topics.md`**（**修改总线或信封字段必须先改此文件，再改实现**）。

## 环境与命令

1. **Python 3.12+**、**Poetry**。在仓库根：  
   `poetry install --no-interaction`
2. **可选**：`cp .env.example .env`；跑测试可不建 `.env`（pytest 会跳过加载 `.env`）。
3. **验证**  
   - 日常：`make dev`（安装依赖 + **`make spine`**，见 **`docs/vertical-slices.md`**）  
   - 合并前 / 对齐 CI：**`make verify`**（全量 `pytest` + **`core/*` ≥85%** + **`skills/quick_consumption/*.py` ≥90%**）

## Pull request 与 Skill 校验

- CI 定义见 **[`.github/workflows/ci.yml`](.github/workflows/ci.yml)**：pytest、覆盖率门禁；**PR** 若改动 **`skills/**/*.py`**（不含 `__init__.py`），会对每个变更文件执行 **`poetry run zhiweitong validate <path> --skip-sandbox`**。
- 合并前请确保该 workflow **通过**。

## GitHub 分支保护与 required check

- 本仓库 workflow 中 **job id 为 `test`**（与 workflow 文件内 `jobs.test` 一致）。  
- 若在 **Settings → Rules / Branch protection** 里配置了 **Required status checks**，名称须与 GitHub 上实际上报的检查一致；写错会导致 merge 前一直等待或误判未通过。

## 推进节奏

- 单轮迭代节奏见 **`docs/ralph-loop.md`**；主体 / 快消 / 运维的时间顺序见 **`docs/handbook-gap-and-industrialization.md`**「**推荐推进顺序（主体 → 流程 → 快消与运维）**」。

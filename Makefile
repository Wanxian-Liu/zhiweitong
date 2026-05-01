# 本地对齐 CI：测试 +（可选）对当前分支相对 BASE 的 Skill 做 validate
# 进化：`promote-preview` / `promote-apply`（默认 diff；WRITE=1 写盘 + 备份）
.PHONY: test install validate-skills-diff promote-preview promote-apply

PYTHON ?= python3
POETRY ?= poetry

install:
	$(POETRY) install --no-interaction

test:
	$(POETRY) run pytest tests/ -q --tb=short

# 用法: make validate-skills-diff BASE=origin/main
# 未设置 BASE 时跳过（避免误跑全仓库）
validate-skills-diff:
	@test -n "$(BASE)" || (echo "Usage: make validate-skills-diff BASE=origin/main  (or commit SHA)"; exit 1)
	@files=$$(git diff --name-only "$(BASE)...HEAD" | grep -E '^skills/.+\.py$$' | grep -v '/__init__\.py$$' || true); \
	if [ -z "$$files" ]; then echo "No changed skill files."; exit 0; fi; \
	for f in $$files; do \
	  test -f "$$f" || continue; \
	  echo "==> validate $$f"; \
	  $(POETRY) run zhiweitong validate "$$f" --skip-sandbox; \
	done

# 用法: make promote-preview DOC_ID=<uuid> [CHROMA=var/chroma] [SKILL=skills/pkg/skill.py] [FULL_META=1] [OUT=preview.md]
# 未传 CHROMA 时用 CLI 默认（$ZHIWEITONG_CHROMA_PATH 或 <repo>/var/chroma）
promote-preview:
	@test -n "$(DOC_ID)" || (echo "Usage: make promote-preview DOC_ID=<uuid> [CHROMA=path] [SKILL=path] [FULL_META=1] [OUT=path]"; exit 1)
	@$(POETRY) run zhiweitong promote-preview --doc-id "$(DOC_ID)" \
		$$([ -n "$(CHROMA)" ] && echo --chroma-path "$(CHROMA)") \
		$$([ -n "$(SKILL)" ] && echo --skill-file "$(SKILL)") \
		$$([ "$(FULL_META)" = 1 ] && echo --full-meta) \
		$$([ -n "$(OUT)" ] && echo --output "$(OUT)")

# 用法: make promote-apply DOC_ID=<uuid> [CHROMA=...] [SKILL=...]  → 仅 unified diff（stderr 有提示）
#       make promote-apply DOC_ID=<uuid> WRITE=1 [CHROMA=...] [SKILL=...]  → 写盘并生成 *.promote-backup-<ts>
promote-apply:
	@test -n "$(DOC_ID)" || (echo "Usage: make promote-apply DOC_ID=<uuid> [CHROMA=path] [SKILL=path] [WRITE=1]"; exit 1)
	@$(POETRY) run zhiweitong promote-apply --doc-id "$(DOC_ID)" \
		$$([ -n "$(CHROMA)" ] && echo --chroma-path "$(CHROMA)") \
		$$([ -n "$(SKILL)" ] && echo --skill-file "$(SKILL)") \
		$$([ "$(WRITE)" = 1 ] && echo --write)

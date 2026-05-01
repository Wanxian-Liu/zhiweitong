# 本地对齐 CI：测试 +（可选）对当前分支相对 BASE 的 Skill 做 validate
.PHONY: test install validate-skills-diff

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

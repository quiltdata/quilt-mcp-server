# Quilt MCP Server - Phase-based Build System
# 
# This Makefile provides simple wrappers that delegate to phase-specific Makefiles.
# Each phase has its own Makefile and SPEC.md for focused, maintainable builds.

# Define phases
sinclude .env
PHASES := app dxt

# Endpoint configuration
APP_ENDPOINT ?= http://127.0.0.1:8000/mcp
FLAGS ?=

.PHONY: help check-env clean coverage $(PHASES) $(addprefix init-,$(PHASES)) $(addprefix test-,$(PHASES)) $(addprefix validate-,$(PHASES)) validate run-app run-app-tunnel run-app-tunnel-inspector tag-release tag-prerelease tag-dev tag check-clean-repo update-cursor-rules test-readme

# Default target
help:
	@echo "Quilt MCP Server - Phase-based Build System"
	@echo ""
	@echo "🏗️  Phase Commands (delegate to <phase>/Makefile):"
	@echo "  make app        - Phase 1: Local MCP server (app/)"
	@echo "  make dxt        - Phase 2: Claude Desktop Extension build (tools/dxt/)"
	@echo ""
	@echo "🚀 Server Commands:"
	@echo "  make run-app      - Run Phase 1 MCP server locally"
	@echo "  make run-app-tunnel - Expose local server via ngrok tunnel"
	@echo "  make run-app-tunnel-inspector - Expose MCP Inspector via ngrok tunnel"
	@echo ""
	@echo "🧹 Cleanup Commands:"
	@echo "  make clean      - Clean all phase artifacts"
	@echo ""
	@echo "🔍 Validation Commands:"
	@echo "  make validate       - Validate all phases sequentially"
	@echo "  make validate-app   - Validate Phase 1 only"
	@echo "  make validate-dxt - Validate Phase 2 only"
	@echo ""
	@echo "⚙️  Utilities:"
	@echo "  make check-env    - Validate .env configuration"
	@echo "  make coverage     - Run tests with coverage"
	@echo "  make test-readme  - Test README installation commands work"
	@echo "  make update-cursor-rules - Update Cursor IDE rules from CLAUDE.md"
	@echo ""
	@echo "🏷️  Release Management:"
	@echo "  make tag         - Create tag using version from manifest.json"
	@echo "  make tag-dev     - Create dev tag with auto-version (base-dev-timestamp)"
	@echo ""
	@echo "📖 Phase Documentation:"
	@echo "  Each phase has its own Makefile and SPEC.md:"
	@echo "  - app/Makefile + spec/1-app-spec.md"
	@echo "  - tools/dxt/Makefile + spec/5-dxt-spec.md"

# Phase Commands - delegate to phase-specific Makefiles
app:
	@$(MAKE) -C app run

dxt:
	@$(MAKE) -C tools/dxt build

test-ci: test-readme
	@$(MAKE) -C app test-ci

# Test Commands
test-app:
	@$(MAKE) -C app test

test-dxt:
	@$(MAKE) -C tools/dxt test

test-readme:
	@echo "Validating README bash code blocks..."
	@uv sync --group test
	@uv run python -m pytest tests/test_readme.py -v
	@echo "✅ README bash validation complete"

# Validation Commands - delegate to phase-specific Makefiles
validate:
	@echo "🔍 Running full validation pipeline (all phases)..."
	@$(MAKE) validate-app validate-dxt
	@echo "✅ All phases validated successfully!"

validate-app:
	@echo "🔍 Validating Phase 1 (App)..."
	@$(MAKE) -C app validate

validate-dxt:
	@echo "🔍 Validating Phase 2 (DXT)..."
	@$(MAKE) -C tools/dxt validate


# Server Commands
run-app:
	@$(MAKE) -C app run

run-app-tunnel:
	@echo "Starting app server and tunnel..."
	@$(MAKE) -C app run & app_pid=$$!; \
	sleep 3; \
	./shared/tunnel-endpoint.sh $(APP_ENDPOINT) $(FLAGS) || kill $$app_pid; \
	kill $$app_pid 2>/dev/null

inspect-app-tunnel:
	@$(MAKE) run-app-tunnel "FLAGS=--inspect"

test-endpoint-tunnel: # run app tunnel, then test-endpoint


# Utilities
check-env:
	@./shared/check-env.sh

clean:
	@echo "🧹 Cleaning all phase artifacts..."
	@$(MAKE) -C app clean
	@$(MAKE) -C tools/dxt clean 2>/dev/null || true

coverage:
	@$(MAKE) -C app coverage

# Release Management
REPO_URL = $(shell git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')

define check_git_clean
	@echo "🔍 Checking repository state..."
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "❌ Repository has uncommitted changes. Please commit or stash them first."; \
		git status --short; \
		exit 1; \
	fi
	@echo "✅ Repository is clean"
endef

define create_and_push_tag
	if git tag | grep -q "^v$(1)$$"; then \
		echo "❌ Tag v$(1) already exists"; \
		exit 1; \
	fi; \
	echo "🏷️  Creating $(2) tag v$(1)..."; \
	git pull origin $(3); \
	git tag -a "v$(1)" -m "$(2) v$(1)"; \
	git push origin "v$(1)"; \
	echo "✅ Tag v$(1) created and pushed"; \
	echo "🚀 GitHub Actions will now build and publish the DXT package"; \
	echo "📦 Release will be available at: https://github.com/$(REPO_URL)/releases/tag/v$(1)"
endef

check-clean-repo:
	$(call check_git_clean)

tag-dev: check-clean-repo
	@echo "🔍 Reading base version from pyproject.toml..."
	@BASE_VERSION=$$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"); \
	if [ -z "$$BASE_VERSION" ]; then \
		echo "❌ Could not read version from pyproject.toml"; \
		exit 1; \
	fi; \
	TIMESTAMP=$$(date +%Y%m%d%H%M%S); \
	DEV_VERSION="$$BASE_VERSION-dev-$$TIMESTAMP"; \
	echo "📋 Generated dev version: $$DEV_VERSION"; \
	@$(call create_and_push_tag,$$DEV_VERSION,Development build,$$(git rev-parse --abbrev-ref HEAD))

tag: check-clean-repo
	@echo "🔍 Reading version from tools/dxt/assets/manifest.json..."
	@if [ ! -f "tools/dxt/assets/manifest.json" ]; then \
		echo "❌ manifest.json not found at tools/dxt/assets/manifest.json"; \
		exit 1; \
	fi
	@MANIFEST_VERSION=$$(python3 -c "import json; print(json.load(open('tools/dxt/assets/manifest.json'))['version'])"); \
	if [ -z "$$MANIFEST_VERSION" ]; then \
		echo "❌ Could not read version from manifest.json"; \
		exit 1; \
	fi; \
	echo "📋 Found version: $$MANIFEST_VERSION"; \
	if echo "$$MANIFEST_VERSION" | grep -q "dev"; then \
		TAG_TYPE="Development build"; \
	elif echo "$$MANIFEST_VERSION" | grep -q -- "-"; then \
		TAG_TYPE="Prerelease"; \
	else \
		TAG_TYPE="Release"; \
	fi; \
	@$(call create_and_push_tag,$$MANIFEST_VERSION,$$TAG_TYPE,main)

# Cursor IDE Rules Update
update-cursor-rules:
	@echo "📝 Updating Cursor IDE rules..."
	@mkdir -p .cursor/rules
	@if [ -f CLAUDE.md ]; then \
		cp CLAUDE.md .cursor/rules/; \
		echo "✅ Cursor rules updated from CLAUDE.md"; \
	else \
		echo "⚠️  CLAUDE.md not found, skipping cursor rules update"; \
	fi
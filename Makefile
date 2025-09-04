# Quilt MCP Server - Phase-based Build System
# 
# This Makefile provides simple wrappers that delegate to phase-specific Makefiles.
# Each phase has its own Makefile and SPEC.md for focused, maintainable builds.

# Define phases
sinclude .env
PHASES := app build-dxt

# Endpoint configuration
APP_ENDPOINT ?= http://127.0.0.1:8000/mcp
FLAGS ?=

.PHONY: help check-env clean coverage $(PHASES) $(addprefix init-,$(PHASES)) test-ci test-app test-endpoint $(addprefix validate-,$(PHASES)) validate run-app run-app-tunnel run-app-tunnel-inspector tag-release tag-prerelease tag-dev tag check-clean-repo update-cursor-rules test-readme

# Default target
help:
	@echo "Quilt MCP Server - Phase-based Build System"
	@echo ""
	@echo "🏗️  Phase Commands (delegate to <phase>/Makefile):"
	@echo "  make app        - Phase 1: Local MCP server (app/)"
	@echo "  make build-dxt  - Phase 2: Claude Desktop Extension build (build-dxt/)"
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
	@echo "  make validate-build-dxt - Validate Phase 2 only"
	@echo ""
	@echo "⚙️  Utilities:"
	@echo "  make check-env    - Validate .env configuration"
	@echo "  make test-ci      - Run CI-safe tests"
	@echo "  make test-app     - Run all app tests locally"
	@echo "  make test-endpoint - Test MCP endpoint"
	@echo "  make coverage     - Run tests with coverage"
	@echo "  make test-readme  - Test README installation commands work"
	@echo "  make update-cursor-rules - Update Cursor IDE rules from CLAUDE.md"
	@echo ""
	@echo "🏷️  Release Management:"
	@echo "  make tag         - Create tag using version from manifest.json"
	@echo "  make tag-release VERSION=x.y.z  - Create release tag (triggers DXT build)"
	@echo "  make tag-prerelease VERSION=x.y.z-rc.1 - Create prerelease tag"
	@echo "  make tag-dev VERSION=x.y.z-dev  - Create development tag"
	@echo ""
	@echo "📖 Phase Documentation:"
	@echo "  Each phase has its own Makefile and SPEC.md:"
	@echo "  - app/Makefile + spec/1-app-spec.md"
	@echo "  - build-dxt/Makefile + spec/5-dxt-spec.md"

# Phase Commands - delegate to phase-specific Makefiles
app:
	@$(MAKE) -C app run

build-dxt:
	@$(MAKE) -C build-dxt build

test-ci:
	@$(MAKE) -C app test-ci

# Validation Commands - delegate to phase-specific Makefiles
validate:
	@echo "🔍 Running full validation pipeline (all phases)..."
	@$(MAKE) validate-app validate-build-dxt
	@echo "✅ All phases validated successfully!"

validate-app:
	@echo "🔍 Validating Phase 1 (App)..."
	@$(MAKE) -C app validate

validate-build-dxt:
	@echo "🔍 Validating Phase 2 (Build-DXT)..."
	@$(MAKE) -C build-dxt validate


# Test Commands - delegate to phase-specific Makefiles
test-app:
	@$(MAKE) -C app test

test-endpoint:
	@$(MAKE) -C app test-endpoint


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
	@$(MAKE) -C build-dxt clean 2>/dev/null || true

coverage:
	@$(MAKE) -C app coverage

test-readme:
	@echo "Validating README bash code blocks..."
	@uv sync --group test
	@uv run python -m pytest tests/test_readme.py -v
	@echo "✅ README bash validation complete"


# Release Management
check-clean-repo:
	@echo "🔍 Checking repository state..."
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "❌ Repository has uncommitted changes. Please commit or stash them first."; \
		git status --short; \
		exit 1; \
	fi
	@echo "✅ Repository is clean"

tag-release: check-clean-repo
	@if [ -z "$(VERSION)" ]; then \
		echo "❌ VERSION is required. Usage: make tag-release VERSION=1.0.0"; \
		exit 1; \
	fi
	@echo "🏷️  Creating release tag v$(VERSION)..."
	@if git tag | grep -q "^v$(VERSION)$$"; then \
		echo "❌ Tag v$(VERSION) already exists"; \
		exit 1; \
	fi
	@git pull origin main
	@git tag -a "v$(VERSION)" -m "Release v$(VERSION)"
	@git push origin "v$(VERSION)"
	@echo "✅ Release tag v$(VERSION) created and pushed"
	@echo "🚀 GitHub Actions will now build and publish the DXT package"
	@echo "📦 Release will be available at: https://github.com/$$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/releases/tag/v$(VERSION)"

tag-prerelease: check-clean-repo
	@if [ -z "$(VERSION)" ]; then \
		echo "❌ VERSION is required. Usage: make tag-prerelease VERSION=1.0.0-rc.1"; \
		exit 1; \
	fi
	@if ! echo "$(VERSION)" | grep -q -- "-"; then \
		echo "❌ Prerelease version must contain a hyphen (e.g., 1.0.0-rc.1, 1.0.0-beta.1)"; \
		exit 1; \
	fi
	@echo "🏷️  Creating prerelease tag v$(VERSION)..."
	@if git tag | grep -q "^v$(VERSION)$$"; then \
		echo "❌ Tag v$(VERSION) already exists"; \
		exit 1; \
	fi
	@git pull origin main
	@git tag -a "v$(VERSION)" -m "Prerelease v$(VERSION)"
	@git push origin "v$(VERSION)"
	@echo "✅ Prerelease tag v$(VERSION) created and pushed"
	@echo "🚀 GitHub Actions will now build and publish the DXT package as a prerelease"
	@echo "📦 Release will be available at: https://github.com/$$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/releases/tag/v$(VERSION)"

tag-dev: check-clean-repo
	@if [ -z "$(VERSION)" ]; then \
		echo "❌ VERSION is required. Usage: make tag-dev VERSION=1.0.0-dev"; \
		exit 1; \
	fi
	@if ! echo "$(VERSION)" | grep -q "dev"; then \
		echo "❌ Development version must contain 'dev' (e.g., 1.0.0-dev, 1.0.0-dev.1)"; \
		exit 1; \
	fi
	@echo "🏷️  Creating development tag v$(VERSION)..."
	@if git tag | grep -q "^v$(VERSION)$$"; then \
		echo "❌ Tag v$(VERSION) already exists"; \
		exit 1; \
	fi
	@git pull origin main
	@git tag -a "v$(VERSION)" -m "Development build v$(VERSION)"
	@git push origin "v$(VERSION)"
	@echo "✅ Development tag v$(VERSION) created and pushed"
	@echo "🚀 GitHub Actions will now build and publish the DXT package as a prerelease"
	@echo "📦 Release will be available at: https://github.com/$$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/releases/tag/v$(VERSION)"

tag: check-clean-repo
	@echo "🔍 Reading version from build-dxt/assets/manifest.json..."
	@if [ ! -f "build-dxt/assets/manifest.json" ]; then \
		echo "❌ manifest.json not found at build-dxt/assets/manifest.json"; \
		exit 1; \
	fi
	@MANIFEST_VERSION=$$(python3 -c "import json; print(json.load(open('build-dxt/assets/manifest.json'))['version'])"); \
	if [ -z "$$MANIFEST_VERSION" ]; then \
		echo "❌ Could not read version from manifest.json"; \
		exit 1; \
	fi; \
	echo "📋 Found version: $$MANIFEST_VERSION"; \
	if git tag | grep -q "^v$$MANIFEST_VERSION$$"; then \
		echo "❌ Tag v$$MANIFEST_VERSION already exists"; \
		exit 1; \
	fi; \
	if echo "$$MANIFEST_VERSION" | grep -q "dev"; then \
		echo "🏷️  Creating development tag v$$MANIFEST_VERSION..."; \
		TAG_TYPE="Development build"; \
	elif echo "$$MANIFEST_VERSION" | grep -q -- "-"; then \
		echo "🏷️  Creating prerelease tag v$$MANIFEST_VERSION..."; \
		TAG_TYPE="Prerelease"; \
	else \
		echo "🏷️  Creating release tag v$$MANIFEST_VERSION..."; \
		TAG_TYPE="Release"; \
	fi; \
	git pull origin main; \
	git tag -a "v$$MANIFEST_VERSION" -m "$$TAG_TYPE v$$MANIFEST_VERSION"; \
	git push origin "v$$MANIFEST_VERSION"; \
	echo "✅ Tag v$$MANIFEST_VERSION created and pushed"; \
	echo "🚀 GitHub Actions will now build and publish the DXT package"; \
	echo "📦 Release will be available at: https://github.com/$$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/releases/tag/v$$MANIFEST_VERSION"

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
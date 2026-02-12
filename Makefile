# Quilt MCP Server - Consolidated Build System
#
# This Makefile consolidates all build workflows into organized includes.
# Development targets are in make.dev, production targets are in make.deploy.

# Include development and production workflows
include make.dev
include make.deploy

# Load environment variables from .env if it exists
sinclude .env

.PHONY: help clean release-local build-all update-cursor-rules config-claude

# Default target - show organized help
help:
	@echo "Quilt MCP Server - Consolidated Build System"
	@echo ""
	@echo "🚀 Development Workflow (make.dev):"
	@echo "  make run              - Start local MCP server"
	@echo "  make test             - Run unit tests only (default, fast)"
	@echo "  make test-all         - Run ALL tests (unit, func, e2e, scripts, mcpb)"
	@echo "  make test-unit        - Run unit tests only (fast, mocked)"
	@echo "  make test-catalog     - Verify quiltx config matches .env"
	@echo "  make test-func        - Run func tests (mocked)"
	@echo "  make test-func-platform - Run platform-only func tests"
	@echo "  make test-e2e         - Run e2e tests"
	@echo "  make test-e2e-platform - Run platform-only e2e tests"
	@echo "  make test-scripts     - Run script validation tests"
	@echo "  make test-mcp         - Run MCP server tests (auto-regen via Make deps)"
	@echo "  make run-docker-remote - Start Docker + Inspector + ngrok (DEFAULT for remote access)"
	@echo "  make run-docker-remote WITH_NGROK=0 - Start Docker + Inspector only (local testing)"
	@echo "  make test-docker-remote - Start Docker (no Inspector), run mcp-test.py on http://localhost:8000/mcp, then stop"
	@echo "  make stop-docker-remote - Stop Docker container, Inspector, and ngrok"
	@echo "  make test-multiuser    - Run multiuser platform tests (JWT/Platform)"
	@echo "  make test-ci          - Run CI-optimized tests (excludes slow/platform)"
	@echo "  make lint             - Code formatting and type checking"
	@echo "  make coverage         - Generate combined coverage analysis CSV + validate thresholds"
	@echo "  make coverage-results - Validate coverage thresholds and generate YAML report"
	@echo "  make coverage-html    - Generate HTML coverage report for local viewing"
	@echo "  make run-inspector    - Launch MCP Inspector for testing"
	@echo ""
	@echo "📦 Production Workflow (make.deploy):"
	@echo "  make deploy-build     - Prepare production build environment"
	@echo "  make mcpb             - Create MCPB package (new format)"
	@echo "  make mcpb-validate    - Validate MCPB package"
	@echo "  make python-dist      - Build wheel + sdist into dist/ using uv (no publish)"
	@echo "  make python-publish   - Publish dist/ artifacts via uv (requires credentials)"
	@echo "  make release-zip      - Create release bundle with documentation"
	@echo "  make release          - Create and push release tag"
	@echo "  make release-dev      - Create and push development tag"
	@echo "  make release-local    - Full local workflow (test → deploy-build → mcpb → validate → zip)"
	@echo "  make build-all        - Pre-flight all release artifacts (test-all → build → docker)"
	@echo ""
	@echo "🐳 Docker Operations (make.deploy):"
	@echo "  make docker-build     - Build Docker image (cached, only if source changed)"
	@echo "  make docker-rebuild   - Force rebuild Docker image (bypass cache)"
	@echo "  make docker-push      - Build and push Docker image to ECR (requires VERSION)"
	@echo "  make docker-push-dev  - Build and push development Docker image"
	@echo "  make docker-validate  - Validate CI-pushed images (public read, no auth needed)"
	@echo ""
	@echo "🔢 Version Management:"
	@echo "  make bump-patch       - Bump patch version (1.2.3 → 1.2.4), update uv.lock, and commit"
	@echo "  make bump-minor       - Bump minor version (1.2.3 → 1.3.0), update uv.lock, and commit"
	@echo "  make bump-major       - Bump major version (1.2.3 → 2.0.0), update uv.lock, and commit"
	@echo ""
	@echo "🧹 Coordination & Utilities:"
	@echo "  make clean               - Clean all artifacts (dev + deploy)"
	@echo "  make update-cursor-rules - Update Cursor IDE rules from CLAUDE.md"
	@echo "  make config-claude       - Configure Claude CLI to use local MCP server"
	@echo ""
	@echo "📖 For detailed target information, see:"
	@echo "  - make.dev: Development workflow targets"
	@echo "  - make.deploy: Production/packaging targets"
	@echo ""
	@echo "🔍 Dry-run mode (add DRY_RUN=1 to see what would happen):"
	@echo "  DRY_RUN=1 make release     - Show what release tag would be created"
	@echo "  DRY_RUN=1 make release-dev - Show what dev tag would be created"

# Coordination targets
clean: dev-clean deploy-clean
	@echo "✅ All artifacts cleaned"

build-all: deploy-build python-dist docker-build release-zip
	@echo "✅ All release artifacts validated:"
	@echo "  - Python distribution built"
	@echo "  - Docker image built"
	@echo "  - Release ZIP created"

release-local: clean test lint deploy-build mcpb-validate release-zip
	@echo "✅ Full local release workflow completed"


# Release targets (delegated to make.deploy for semantic clarity)
release: release-tag

release-dev: release-dev-tag

update-cursor-rules:
	@echo "📝 Updating Cursor IDE rules..."
	@mkdir -p .cursor/rules
	@if [ -f CLAUDE.md ]; then \
		cp CLAUDE.md .cursor/rules/; \
		echo "✅ Cursor rules updated from CLAUDE.md"; \
	else \
		echo "⚠️  CLAUDE.md not found, skipping cursor rules update"; \
	fi

config-claude:
	@claude mcp add quilt-mcp --env FASTMCP_TRANSPORT=stdio -- make run
	@claude mcp list

# Version Management Targets (bump + update uv.lock + commit)
bump-patch:
	@scripts/release.sh bump patch

bump-minor:
	@scripts/release.sh bump minor

bump-major:
	@scripts/release.sh bump major

# Quilt MCP Server - Consolidated Build System
#
# This Makefile consolidates all build workflows into organized includes.
# Development targets are in make.dev, production targets are in make.deploy.

# Include development and production workflows
include make.dev
include make.deploy

# Load environment variables from .env if it exists
sinclude .env

.PHONY: help clean release-local update-cursor-rules config-claude

# Default target - show organized help
help:
	@echo "Quilt MCP Server - Consolidated Build System"
	@echo ""
	@echo "🚀 Development Workflow (make.dev):"
	@echo "  make run              - Start local MCP server"
	@echo "  make test             - Run all tests"
	@echo "  make test-unit        - Run unit tests only (fast)"
	@echo "  make test-integration - Run integration tests (with AWS)"
	@echo "  make test-ci          - Run CI-optimized tests"
	@echo "  make lint             - Code formatting and type checking"
	@echo "  make coverage         - Run tests with coverage report"
	@echo "  make coverage-html    - Generate HTML coverage report for local viewing"
	@echo "  make run-inspector    - Launch MCP Inspector for testing"
	@echo "  make config-claude    - Configure Claude CLI to use local MCP server"
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
	@echo ""
	@echo "🐳 Docker Operations (make.deploy):"
	@echo "  make docker-build     - Build Docker image locally"
	@echo "  make docker-push      - Build and push Docker image to ECR (requires VERSION)"
	@echo "  make docker-push-dev  - Build and push development Docker image"
	@echo ""
	@echo "🔢 Version Management:"
	@echo "  make bump-patch       - Bump patch version (1.2.3 → 1.2.4)"
	@echo "  make bump-minor       - Bump minor version (1.2.3 → 1.3.0)"
	@echo "  make bump-major       - Bump major version (1.2.3 → 2.0.0)"
	@echo "  make release-patch    - Bump patch version, commit, and create release"
	@echo "  make release-minor    - Bump minor version, commit, and create release"
	@echo "  make release-major    - Bump major version, commit, and create release"
	@echo ""
	@echo "🧹 Coordination & Utilities:"
	@echo "  make clean            - Clean all artifacts (dev + deploy)"
	@echo "  make release-local    - Full local workflow (test → deploy-build → mcpb → validate → zip)"
	@echo "  make update-cursor-rules - Update Cursor IDE rules from CLAUDE.md"
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

# Version Management Targets
bump-patch:
	@scripts/release.sh bump patch

bump-minor:
	@scripts/release.sh bump minor

bump-major:
	@scripts/release.sh bump major

# Combined Release Targets (bump + commit + tag)
release-patch: bump-patch
	@echo "🔍 Committing patch version bump..."
	@git add pyproject.toml
	@VERSION=$$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"); \
	git commit -m "bump: patch version to $$VERSION"; \
	echo "✅ Committed version bump to $$VERSION"
	@echo "🏷️  Creating release tag..."
	@scripts/release.sh release

release-minor: bump-minor
	@echo "🔍 Committing minor version bump..."
	@git add pyproject.toml
	@VERSION=$$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"); \
	git commit -m "bump: minor version to $$VERSION"; \
	echo "✅ Committed version bump to $$VERSION"
	@echo "🏷️  Creating release tag..."
	@scripts/release.sh release

release-major: bump-major
	@echo "🔍 Committing major version bump..."
	@git add pyproject.toml
	@VERSION=$$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"); \
	git commit -m "bump: major version to $$VERSION"; \
	echo "✅ Committed version bump to $$VERSION"
	@echo "🏷️  Creating release tag..."
	@scripts/release.sh release
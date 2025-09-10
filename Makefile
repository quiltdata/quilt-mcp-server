# Quilt MCP Server - Consolidated Build System
# 
# This Makefile consolidates all build workflows into organized includes.
# Development targets are in make.dev, production targets are in make.deploy.

# Include development and production workflows
include make.dev
include make.deploy

# Load environment variables from .env if it exists
sinclude .env

.PHONY: help clean release-local test-readme update-cursor-rules config-claude

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
	@echo "  make run-inspector    - Launch MCP Inspector for testing"
	@echo "  make config-claude    - Configure Claude CLI to use local MCP server"
	@echo ""
	@echo "📦 Production Workflow (make.deploy):"
	@echo "  make build            - Prepare production build environment"
	@echo "  make dxt              - Create DXT package"
	@echo "  make dxt-validate     - Validate DXT package"
	@echo "  make release-zip      - Create release bundle with documentation"
	@echo "  make release          - Create and push release tag"
	@echo "  make release-dev      - Create and push development tag"
	@echo ""
	@echo "🧹 Coordination & Utilities:"
	@echo "  make clean            - Clean all artifacts (dev + deploy)"
	@echo "  make release-local    - Full local workflow (test → build → dxt → validate → zip)"
	@echo "  make test-readme      - Test README installation commands"
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

release-local: test lint build dxt-validate release-zip
	@echo "✅ Full local release workflow completed"

# Release targets (delegated to make.deploy but renamed for semantic clarity)
release:
	@$(MAKE) -f make.deploy release

release-dev:
	@$(MAKE) -f make.deploy release-dev

# Utilities
test-readme:
	@echo "Validating README bash code blocks..."
	@uv sync --group test
	@uv run python -m pytest tests/test_readme.py -v
	@echo "✅ README bash validation complete"

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
	@echo "🤖 Configuring Claude CLI to use local MCP server..."
	@claude mcp add quilt-mcp --env FASTMCP_TRANSPORT=stdio -- make run
	@echo "✅ Claude CLI configured with 'quilt-mcp' server"
	@echo "💡 Verify with: claude mcp list"

# Error messages for removed targets
package:
	@echo "❌ Target 'package' has been removed for clarity"
	@echo "💡 Use 'make dxt' to create DXT packages"
	@exit 1

dxt-package:
	@echo "❌ Target 'dxt-package' has been removed (redundant)"
	@echo "💡 Use 'make dxt' to create DXT packages"
	@exit 1

validate-package:
	@echo "❌ Target 'validate-package' has been renamed for clarity"
	@echo "💡 Use 'make dxt-validate' to validate DXT packages"
	@exit 1

release-package:
	@echo "❌ Target 'release-package' has been renamed for clarity"
	@echo "💡 Use 'make release-zip' to create release bundles"
	@exit 1

tag:
	@echo "❌ Target 'tag' has been renamed for clarity"
	@echo "💡 Use 'make release' to create and push release tags"
	@exit 1

tag-dev:
	@echo "❌ Target 'tag-dev' has been renamed for clarity"
	@echo "💡 Use 'make release-dev' to create and push development tags"
	@exit 1
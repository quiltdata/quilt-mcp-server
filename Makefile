# Quilt MCP Server - Consolidated Build System
# 
# This Makefile consolidates all build workflows into organized includes.
# Development targets are in make.dev, production targets are in make.deploy.

# Include development and production workflows
include make.dev
include make.deploy

# Load environment variables from .env if it exists
sinclude .env

.PHONY: help clean release test-readme update-cursor-rules

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
	@echo ""
	@echo "📦 Production Workflow (make.deploy):"
	@echo "  make build            - Prepare production build environment"
	@echo "  make package          - Create Python package"
	@echo "  make dxt-package      - Create DXT package"
	@echo "  make validate-package - Validate DXT package"
	@echo "  make release-package  - Create release bundle with documentation"
	@echo ""
	@echo "🧹 Coordination & Utilities:"
	@echo "  make clean            - Clean all artifacts (dev + deploy)"
	@echo "  make release          - Full release workflow (test → build → package)"
	@echo "  make test-readme      - Test README installation commands"
	@echo "  make update-cursor-rules - Update Cursor IDE rules from CLAUDE.md"
	@echo ""
	@echo "📖 For detailed target information, see:"
	@echo "  - make.dev: Development workflow targets"
	@echo "  - make.deploy: Production/packaging targets"

# Coordination targets
clean: dev-clean deploy-clean
	@echo "✅ All artifacts cleaned"

release: test lint build validate-package release-package
	@echo "✅ Full release workflow completed"

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
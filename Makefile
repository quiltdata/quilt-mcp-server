# Quilt MCP Server - Phase-based Build System
# 
# This Makefile provides simple wrappers that delegate to phase-specific Makefiles.
# Each phase has its own Makefile and SPEC.md for focused, maintainable builds.

# Define phases
sinclude .env
export
PHASES := app build catalog deploy

# Endpoint configuration
APP_ENDPOINT ?= http://127.0.0.1:8000/mcp
BUILD_ENDPOINT ?= http://127.0.0.1:8001/mcp
CATALOG_ENDPOINT ?= http://127.0.0.1:8002/mcp
FLAGS ?=

.PHONY: help check-env clean coverage destroy status $(PHASES) $(addprefix init-,$(PHASES)) $(addprefix test-,$(PHASES)) $(addprefix validate-,$(PHASES)) validate run-app run-app-tunnel run-app-tunnel-inspector tag-release tag-prerelease tag-dev tag check-clean-repo publish-test check-publish-env

# Default target
help:
	@echo "Quilt MCP Server - Phase-based Build System"
	@echo ""
	@echo "🏗️  Phase Commands (delegate to <phase>/Makefile):"
	@echo "  make app        - Phase 1: Local MCP server (app/)"
	@echo "  make build      - Phase 2: Docker container (build-docker/)"
	@echo "  make catalog    - Phase 3: ECR registry push (catalog-push/)"  
	@echo "  make deploy     - Phase 4: ECS deployment (deploy-aws/)"
	@echo ""
	@echo "🚀 Server Commands:"
	@echo "  make run-app      - Run Phase 1 MCP server locally"
	@echo "  make run-app-tunnel - Expose local server via ngrok tunnel"
	@echo "  make run-app-tunnel-inspector - Expose MCP Inspector via ngrok tunnel"
	@echo ""
	@echo "📦 Publishing Commands:"
	@echo "  make publish-test      - Publish package to TestPyPI"
	@echo "  make check-publish-env - Validate publishing environment"
	@echo ""
	@echo "🧹 Cleanup Commands:"
	@echo "  make clean      - Clean all phase artifacts"
	@echo "  make destroy    - Clean up AWS resources"
	@echo ""
	@echo "🔍 Validation Commands:"
	@echo "  make validate       - Validate all phases sequentially"
	@echo "  make validate-app   - Validate Phase 1 only"
	@echo "  make validate-build - Validate Phase 2 only"
	@echo "  make validate-catalog - Validate Phase 3 only"
	@echo "  make validate-deploy - Validate Phase 4 only"
	@echo ""
	@echo "⚙️  Utilities:"
	@echo "  make check-env    - Validate .env configuration"
	@echo "  make coverage     - Run tests with coverage report"
	@echo "  make tag-release  - Tag release version"
	@echo "  make tag-prerelease - Tag prerelease version"
	@echo "  make tag-dev      - Tag development version"
	@echo ""
	@echo "For detailed phase help: make <phase>"

# Check environment configuration
check-env:
	@echo "Checking environment configuration..."
	@shared/check-env.sh

# Clean all phase artifacts
clean:
	@echo "Cleaning all phase artifacts..."
	@for phase in $(PHASES); do \
		if [ -f $$phase*/Makefile ]; then \
			echo "Cleaning $$phase..."; \
			$(MAKE) -C $$phase* clean 2>/dev/null || true; \
		fi; \
	done
	@echo "Clean complete."

# Run coverage testing
coverage:
	@$(MAKE) -C app coverage

# Destroy AWS resources
destroy:
	@echo "🔥 Destroying AWS resources..."
	@$(MAKE) -C deploy-aws destroy

# Show status across all phases
status:
	@echo "=== Quilt MCP Server Status ==="
	@for phase in $(PHASES); do \
		if [ -f $$phase*/Makefile ]; then \
			echo; \
			echo "📋 $$phase status:"; \
			$(MAKE) -C $$phase* status 2>/dev/null || echo "  No status available for $$phase"; \
		fi; \
	done

# Phase delegate targets
app:
	@$(MAKE) -C app

build:
	@$(MAKE) -C build-docker

catalog:
	@$(MAKE) -C catalog-push

deploy:
	@$(MAKE) -C deploy-aws

# Initialize phases
init-app:
	@$(MAKE) -C app init

init-build:
	@$(MAKE) -C build-docker init

init-catalog:
	@$(MAKE) -C catalog-push init

init-deploy:
	@$(MAKE) -C deploy-aws init

# Test phases individually
test-app:
	@$(MAKE) -C app test

test-build:
	@$(MAKE) -C build-docker test

test-catalog:
	@$(MAKE) -C catalog-push test

test-deploy:
	@$(MAKE) -C deploy-aws test


# Publishing Commands
publish-test: check-publish-env
	@echo "📦 Publishing package to TestPyPI..."
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "❌ UV not found. Please install UV first."; \
		echo "   pip install uv"; \
		exit 1; \
	fi
	@echo "🔨 Building package with UV..."
	@uv build
	@echo "🚀 Publishing to TestPyPI..."
	@UV_PUBLISH_URL=https://test.pypi.org/legacy/ UV_PUBLISH_TOKEN="$$TESTPYPI_TOKEN" uv publish
	@echo "✅ Package published to TestPyPI successfully!"

check-publish-env:
	@echo "🔍 Validating publishing environment..."
	@if [ -z "$$TESTPYPI_TOKEN" ]; then \
		echo "❌ Missing required environment variables:"; \
		echo "   - TESTPYPI_TOKEN"; \
		echo ""; \
		echo "TestPyPI credentials not configured"; \
		echo "Please add TESTPYPI_TOKEN to .env file"; \
		exit 1; \
	fi
	@echo "✅ TestPyPI configuration valid"
	@echo "✅ UV publishing environment ready"


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
	@$(MAKE) run-app-tunnel "FLAGS=--test-endpoint"

# Cloud-Enabled Tunneled Endpoints (tunnel + test)
run-build:
	@echo "Starting build server and tunnel..."
	@$(MAKE) -C build-docker run & build_pid=$$!; \
	sleep 5; \
	./shared/tunnel-endpoint.sh $(BUILD_ENDPOINT) $(FLAGS) || kill $$build_pid; \
	kill $$build_pid 2>/dev/null

run-catalog:
	@echo "Starting catalog server and tunnel..."
	@$(MAKE) -C catalog-push run & catalog_pid=$$!; \
	sleep 5; \
	./shared/tunnel-endpoint.sh $(CATALOG_ENDPOINT) $(FLAGS) || kill $$catalog_pid; \
	kill $$catalog_pid 2>/dev/null

run-all-tunnel:
	@echo "🚀 Starting all phase servers with tunnels..."
	@echo "This will take a moment to initialize all services..."
	@$(MAKE) run-app-tunnel & app_tunnel_pid=$$!; \
	sleep 2; \
	$(MAKE) run-build-tunnel & build_tunnel_pid=$$!; \
	sleep 2; \
	$(MAKE) run-catalog-tunnel & catalog_tunnel_pid=$$!; \
	sleep 5; \
	echo "All services running. Press Ctrl+C to stop all..."; \
	trap 'kill $$app_tunnel_pid $$build_tunnel_pid $$catalog_tunnel_pid 2>/dev/null' INT; \
	wait

# Validation phase targets
validate-app:
	@$(MAKE) -C app validate

validate-build:
	@$(MAKE) -C build-docker validate

validate-catalog:
	@$(MAKE) -C catalog-push validate

validate-deploy:
	@$(MAKE) -C deploy-aws validate

# Sequential validation across all phases
validate: validate-app validate-build validate-catalog validate-deploy
	@echo "✅ All phases validated successfully!"

# Release Management
check-clean-repo:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "❌ Repository has uncommitted changes:"; \
		git status --short; \
		echo "Please commit or stash changes before tagging."; \
		exit 1; \
	fi
	@echo "✅ Repository is clean"

tag-release: check-clean-repo
	@echo "🏷️  Tagging release version..."
	@./shared/tag-version.sh release

tag-prerelease: check-clean-repo
	@echo "🏷️  Tagging prerelease version..."
	@./shared/tag-version.sh prerelease

tag-dev: 
	@echo "🏷️  Tagging development version..."
	@./shared/tag-version.sh dev

tag:
	@echo "🏷️  Available tagging options:"
	@echo "  make tag-release    - Tag stable release (vX.Y.Z)"
	@echo "  make tag-prerelease - Tag prerelease (vX.Y.Z-rcN)"
	@echo "  make tag-dev        - Tag development (vX.Y.Z-devN)"
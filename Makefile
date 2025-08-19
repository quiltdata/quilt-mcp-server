# Quilt MCP Server - Phase-based Build System
# 
# This Makefile provides simple wrappers that delegate to phase-specific Makefiles.
# Each phase has its own Makefile and SPEC.md for focused, maintainable builds.

# Define phases
sinclude .env
PHASES := app build catalog deploy

# Endpoint configuration
APP_ENDPOINT ?= http://127.0.0.1:8000/mcp
BUILD_ENDPOINT ?= http://127.0.0.1:8001/mcp
CATALOG_ENDPOINT ?= http://127.0.0.1:8002/mcp
FLAGS ?=

.PHONY: help check-env clean coverage destroy status $(PHASES) $(addprefix init-,$(PHASES)) $(addprefix test-,$(PHASES)) $(addprefix validate-,$(PHASES)) validate run-app run-app-tunnel run-app-tunnel-inspector

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
	@echo "  make status       - Show deployment status"
	@echo "  make coverage     - Run tests with coverage"
	@echo ""
	@echo "📖 Phase Documentation:"
	@echo "  Each phase has its own Makefile and SPEC.md:"
	@echo "  - app/Makefile + app/SPEC.md"
	@echo "  - build-docker/Makefile + build-docker/SPEC.md"
	@echo "  - catalog-push/Makefile + catalog-push/SPEC.md"
	@echo "  - deploy-aws/Makefile + deploy-aws/SPEC.md"

# Phase Commands - delegate to phase-specific Makefiles
app:
	@$(MAKE) -C app run

build:
	@$(MAKE) -C build-docker build

catalog:
	@$(MAKE) -C catalog-push push

deploy:
	@$(MAKE) -C deploy-aws deploy

test-ci:
	@$(MAKE) -C app test-ci

# Validation Commands - delegate to phase-specific Makefiles
validate:
	@echo "🔍 Running full validation pipeline (all phases)..."
	@$(MAKE) validate-app validate-build validate-catalog validate-deploy
	@echo "✅ All phases validated successfully!"

validate-app:
	@echo "🔍 Validating Phase 1 (App)..."
	@$(MAKE) -C app validate

validate-build:
	@echo "🔍 Validating Phase 2 (Build-Docker)..."
	@$(MAKE) -C build-docker validate

validate-catalog:
	@echo "🔍 Validating Phase 3 (Catalog-Push)..."
	@$(MAKE) -C catalog-push validate

validate-deploy:
	@echo "🔍 Validating Phase 4 (Deploy-AWS)..."
	@$(MAKE) -C deploy-aws validate


# Test Commands - delegate to phase-specific Makefiles
test-app:
	@$(MAKE) -C app test

test-build:
	@$(MAKE) -C build-docker test

test-catalog:
	@$(MAKE) -C catalog-push test

test-deploy:
	@$(MAKE) -C deploy-aws test


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
	@$(MAKE) -C build-docker clean

coverage:
	@$(MAKE) -C app coverage

destroy:
	@$(MAKE) -C deploy-aws destroy

status:
	@$(MAKE) -C deploy-aws status
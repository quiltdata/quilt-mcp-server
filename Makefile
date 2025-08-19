# Quilt MCP Server - Phase-based Build System
# 
# This Makefile provides simple wrappers that delegate to phase-specific Makefiles.
# Each phase has its own Makefile and SPEC.md for focused, maintainable builds.

# Define phases
PHASES := app build catalog deploy

.PHONY: help check-env clean coverage destroy status $(PHASES) $(addprefix init-,$(PHASES)) $(addprefix test-,$(PHASES)) $(addprefix validate-,$(PHASES)) validate $(addprefix verify-,$(PHASES)) $(addprefix zero-,$(PHASES)) $(addprefix config-,$(PHASES)) run-app remote-export

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
	@echo "  make remote-export - Expose local server via ngrok tunnel"
	@echo ""
	@echo "🧹 Cleanup Commands:"
	@echo "  make clean      - Clean all phase artifacts"
	@echo "  make destroy    - Clean up AWS resources"
	@echo "  make zero-app     - Stop Phase 1 processes"
	@echo "  make zero-build   - Stop Phase 2 containers"
	@echo "  make zero-catalog - Stop Phase 3 containers"
	@echo "  make zero-deploy  - Disable Phase 4 endpoint"
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

remote-export:
	@echo "🌐 Starting ngrok tunnel for local MCP server..."
	@echo "   Local server: http://127.0.0.1:8000/mcp"
	@echo "   Public URL: https://uniformly-alive-halibut.ngrok-free.app/mcp"
	@echo "   Press Ctrl+C to stop both server and tunnel"
	@echo ""
	@trap 'echo "Stopping tunnel and server..."; kill $$app_pid 2>/dev/null; exit 0' INT; \
	$(MAKE) -C app run & app_pid=$$!; \
	sleep 3; \
	ngrok http 8000 --domain=uniformly-alive-halibut.ngrok-free.app; \
	kill $$app_pid 2>/dev/null

# Utilities
check-env:
	@echo "🔍 Checking environment configuration..."
	@if [ ! -f ".env" ]; then \
		echo "⚠️  No .env file found. Copy env.example to .env and configure."; \
		exit 1; \
	fi
	@echo "✅ .env file exists"
	@bash -c 'set -a && source .env && set +a && \
		echo "📋 Environment Summary:" && \
		echo "  AWS Account: $${CDK_DEFAULT_ACCOUNT:-$${AWS_ACCOUNT_ID:-Not set}}" && \
		echo "  AWS Region: $${CDK_DEFAULT_REGION:-$${AWS_DEFAULT_REGION:-Not set}}" && \
		echo "  ECR Registry: $${ECR_REGISTRY:-Will be auto-derived}" && \
		echo "  Quilt Bucket: $${QUILT_DEFAULT_BUCKET:-Not set}" && \
		echo "  Catalog Domain: $${QUILT_CATALOG_DOMAIN:-Not set}" && \
		echo "" && \
		echo "🔍 Validating required environment variables..." && \
		if [ -z "$${CDK_DEFAULT_ACCOUNT}" ] && [ -z "$${AWS_ACCOUNT_ID}" ]; then \
			echo "❌ Missing CDK_DEFAULT_ACCOUNT or AWS_ACCOUNT_ID"; \
			exit 1; \
		fi && \
		if [ -z "$${CDK_DEFAULT_REGION}" ] && [ -z "$${AWS_DEFAULT_REGION}" ]; then \
			echo "❌ Missing CDK_DEFAULT_REGION or AWS_DEFAULT_REGION"; \
			exit 1; \
		fi && \
		if [ -z "$${QUILT_DEFAULT_BUCKET}" ]; then \
			echo "❌ Missing QUILT_DEFAULT_BUCKET"; \
			exit 1; \
		fi && \
		if [ -z "$${QUILT_CATALOG_DOMAIN}" ]; then \
			echo "❌ Missing QUILT_CATALOG_DOMAIN"; \
			exit 1; \
		fi'
	@echo "✅ Environment validation complete"

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
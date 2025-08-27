# Quilt MCP Server - Phase 3 (Catalog-Push) Makefile
# ECR registry operations

.PHONY: help push pull test login validate clean config init verify zero

# Default target
help:
	@echo "Quilt MCP Server - Phase 3 (Catalog-Push)"
	@echo ""
	@echo "Commands:"
	@echo "  make push       - Push local image to ECR registry"
	@echo "  make pull       - Pull image from ECR registry"
	@echo "  make test       - Test pulling and running ECR image"
	@echo "  make login      - Login to ECR registry"
	@echo "  make validate   - Full SPEC-compliant validation"
	@echo "  make config     - Generate .config file with ECR info"
	@echo "  make init       - Check preconditions"
	@echo "  make verify     - Verify MCP endpoint"
	@echo "  make zero       - Stop running containers"

# Phase commands
push:
	@./catalog-push.sh push

pull:
	@./catalog-push.sh pull

test:
	@./catalog-push.sh test

login:
	@./catalog-push.sh login

validate:
	@./catalog-push.sh validate

config:
	@./catalog-push.sh config

# SPEC validation targets
init:
	@echo "Checking Phase 3 (Catalog) preconditions..."
	@command -v aws >/dev/null || (echo "Error: AWS CLI not found. Please install AWS CLI first." && exit 1)
	@aws sts get-caller-identity >/dev/null || (echo "Error: AWS credentials not configured" && exit 1)
	@command -v docker >/dev/null || (echo "Error: Docker not found. Please install Docker first." && exit 1)
	@command -v uv >/dev/null || (echo "Error: uv not found. Please install uv first." && exit 1)
	@echo "✅ Phase 3 preconditions met"

verify:
	@echo "Verifying Phase 3 MCP endpoint..."
	@../shared/test-endpoint.sh -p catalog -t

zero:
	@echo "Stopping Phase 3 (Catalog) containers..."
	@docker ps -q --filter "publish=8002" | xargs -r docker stop 2>/dev/null || true
	@echo "✅ Phase 3 containers stopped"
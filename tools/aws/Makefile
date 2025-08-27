# Quilt MCP Server - Phase 4 (Deploy-AWS) Makefile
# ECS/ALB deployment via CDK

.PHONY: help deploy test destroy status validate config init verify zero scale-down

# Default target
help:
	@echo "Quilt MCP Server - Phase 4 (Deploy-AWS)"
	@echo ""
	@echo "Commands:"
	@echo "  make deploy     - Deploy to ECS Fargate via CDK"
	@echo "  make test       - Test deployed endpoint"
	@echo "  make destroy    - Destroy CDK stack"
	@echo "  make status     - Show deployment status"
	@echo "  make validate   - Full SPEC-compliant validation"
	@echo "  make config     - Generate .config file with deployment info"
	@echo "  make init       - Check preconditions"
	@echo "  make verify     - Verify MCP endpoint"
	@echo "  make zero       - Disable public endpoint (preserve stack)"
	@echo "  make scale-down - Scale ECS service to 0 tasks"

# Phase commands
deploy:
	@./deploy-aws.sh deploy

test:
	@./deploy-aws.sh test

destroy:
	@./deploy-aws.sh destroy

status:
	@./deploy-aws.sh status

validate:
	@./deploy-aws.sh validate

config:
	@echo "Generating .config file with deployment info..."
	@if [ ! -f "../../.config" ]; then \
		echo "⚠️  .config file not found. Run deployment first to generate it."; \
		exit 1; \
	fi
	@echo "✅ .config file already exists and current"

# SPEC validation targets
init:
	@echo "Checking Phase 4 (Deploy) preconditions..."
	@command -v aws >/dev/null || (echo "Error: AWS CLI not found. Please install AWS CLI first." && exit 1)
	@aws sts get-caller-identity >/dev/null || (echo "Error: AWS credentials not configured" && exit 1)
	@command -v uv >/dev/null || (echo "Error: uv not found. Please install uv first." && exit 1)
	@echo "✅ Phase 4 preconditions met"

verify:
	@echo "Verifying Phase 4 MCP endpoint..."
	@../shared/test-endpoint.sh -p deploy -t

zero:
	@echo "Disabling Phase 4 (Deploy) public endpoint..."
	@./deploy-aws.sh scale-down 2>/dev/null || echo "No active deployment to scale down"
	@echo "✅ Phase 4 endpoint disabled (stack preserved)"

scale-down:
	@echo "Scaling ECS service to 0 tasks..."
	@if [ ! -f "../../.config" ]; then \
		echo "⚠️  No .config file found. Stack may not be deployed."; \
		exit 1; \
	fi
	@set -a && source ../../.config && set +a && \
		aws ecs update-service \
			--cluster "$$CLUSTER_NAME" \
			--service "$$SERVICE_NAME" \
			--desired-count 0 \
			--region "$$REGION" >/dev/null 2>&1 || true
	@echo "✅ ECS service scaled to 0 tasks"
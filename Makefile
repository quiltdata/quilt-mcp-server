# Quilt MCP Server - Phase-based Build System
# 
# This Makefile provides simple wrappers around the phase scripts.
# All validation logic lives in the individual phase scripts.

.PHONY: help app build catalog deploy full validate clean test status destroy

# Default target
help:
	@echo "Quilt MCP Server - Phase-based Build System"
	@echo ""
	@echo "Phase Commands:"
	@echo "  make app        - Phase 1: Run local MCP server"
	@echo "  make build      - Phase 2: Build Docker container"
	@echo "  make catalog    - Phase 3: Push to ECR registry"  
	@echo "  make deploy     - Phase 4: Deploy to ECS Fargate"
	@echo "  make full       - Complete pipeline (all phases)"
	@echo ""
	@echo "Validation Commands:"
	@echo "  make validate     - Validate all phases (app + build + catalog* + deploy*)"
	@echo "  make validate-app - Validate Phase 1 (App) only"
	@echo "  make validate-build - Validate Phase 2 (Build-Docker) only"
	@echo "  make validate-https - Validate HTTPS synthesis capability"
	@echo "  make test         - Quick test of current deployment"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean      - Clean artifacts"
	@echo "  make status     - Show deployment status"
	@echo "  make destroy    - Clean up AWS resources"
	@echo ""
	@echo "Environment Variables:"
	@echo "  ECR_REGISTRY    - ECR registry URL (required for catalog/deploy)"
	@echo "  ECR_REPOSITORY  - ECR repository name (default: quilt-mcp)"
	@echo "  ACM_CERT_ARN    - ACM certificate ARN (optional, enables HTTPS)"
	@echo ""
	@echo "* catalog and deploy phases require ECR_REGISTRY to be set"

# Phase Commands (delegate to phase scripts)
app:
	@./src/app/app.sh run

build:
	@./src/build-docker/build-docker.sh build

catalog:
	@./src/catalog-push/catalog-push.sh push

deploy:
	@./src/deploy-aws/deploy-aws.sh deploy

full:
	@./src/shared/pipeline.sh full

# Validation Commands (delegate to validation scripts)
validate:
	@./src/shared/validate.sh all

validate-app:
	@./src/shared/validate.sh app

validate-build:
	@./src/shared/validate.sh build

validate-https:
	@echo "🔍 Testing HTTPS synthesis capability..."
	@uv sync --group deploy > /dev/null 2>&1
	@cd src/deploy-aws && uv run cdk synth --app "python app.py" --output /tmp/cdk-out-http > /dev/null && echo "✅ HTTP synthesis working"
	@cd src/deploy-aws && ACM_CERT_ARN="arn:aws:acm:us-east-1:123456789012:certificate/test-cert" uv run cdk synth --app "python app.py" --output /tmp/cdk-out-https > /dev/null && echo "✅ HTTPS synthesis working"
	@echo "✅ HTTPS capability validated"

test:
	@./src/deploy-aws/deploy-aws.sh test

# Utilities (delegate to appropriate scripts)
clean:
	@./src/app/app.sh clean
	@./src/build-docker/build-docker.sh clean

status:
	@./src/deploy-aws/deploy-aws.sh status

destroy:
	@./src/deploy-aws/deploy-aws.sh destroy

# Legacy compatibility (redirect to new system)
pytest: 
	@./src/app/app.sh test

coverage:
	@./src/app/app.sh validate

stdio-run: app
remote-run: app
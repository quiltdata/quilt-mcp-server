# Quilt MCP Server - Phase 2 (Build-Docker) Makefile
# Docker containerization

.PHONY: help build test run validate clean config init verify zero

# Default target
help:
	@echo "Quilt MCP Server - Phase 2 (Build-Docker)"
	@echo ""
	@echo "Commands:"
	@echo "  make build      - Build Docker image with git SHA tag"
	@echo "  make test       - Test Docker container health"
	@echo "  make run        - Run Docker container locally on port 8000"
	@echo "  make validate   - Full SPEC-compliant validation"
	@echo "  make clean      - Clean Docker images"
	@echo "  make config     - Generate .config file with container info"
	@echo "  make init       - Check preconditions"
	@echo "  make verify     - Verify MCP endpoint"
	@echo "  make zero       - Stop running containers"

# Phase commands
build:
	@./build-docker.sh build

test:
	@./build-docker.sh test

run:
	@./build-docker.sh run

validate:
	@./build-docker.sh validate

clean:
	@./build-docker.sh clean

config:
	@./build-docker.sh config

# SPEC validation targets
init:
	@echo "Checking Phase 2 (Build) preconditions..."
	@command -v docker >/dev/null || (echo "Error: Docker not found. Please install Docker first." && exit 1)
	@command -v uv >/dev/null || (echo "Error: uv not found. Please install uv first." && exit 1)
	@echo "✅ Phase 2 preconditions met"

verify:
	@echo "Verifying Phase 2 MCP endpoint..."
	@../shared/test-endpoint.sh -p build -t

zero:
	@echo "Stopping Phase 2 (Build) containers..."
	@docker ps -q --filter "ancestor=quilt-mcp" | xargs -r docker stop 2>/dev/null || true
	@echo "✅ Phase 2 containers stopped"
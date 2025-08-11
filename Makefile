SHELL := /bin/bash
UV ?= uv
PY ?= python
INSPECTOR ?= npx -y @modelcontextprotocol/inspector@latest
TOKEN_CMD := ./scripts/get_token.sh
PROJECT_ROOT := $(shell pwd)

API_ENDPOINT := $(shell [ -f .config ] && . ./.config >/dev/null 2>&1; echo $$API_ENDPOINT)

.DEFAULT_GOAL := help

# Phony targets grouped by category: utility, build, stdio, remote
.PHONY: help setup env clean logs token pytest build test deploy stdio-run stdio-config stdio-inspector remote-run remote-test remote-inspector deps-test deps-lint deps-all
help:
	@echo "Quilt MCP Server - Makefile"
	@echo ""
	@echo "Utility Tasks:" 
	@echo "  setup              Install base dependencies (uv sync)"
	@echo "  deps-test          Install test dependency group"
	@echo "  deps-lint          Install lint dependency group"
	@echo "  deps-all           Install all dependency groups (test, lint, deploy)"
	@echo "  env                Create .env from env.example if missing"
	@echo "  clean              Clean build/test artifacts"
	@echo "  logs               Tail lambda logs (last 10m)"
	@echo "  token              Print OAuth token (using get_token.sh)"
	@echo "  pytest             Run pytest suite"
	@echo ""
	@echo "Build Tasks:" 
	@echo "  build              Build lambda artifact (scripts/build.sh build)"
	@echo "  test               Test deployed stack (scripts/build.sh test)"
	@echo "  deploy             Build + deploy via CDK (scripts/build.sh deploy)"
	@echo ""
	@echo "Stdio Tasks:" 
	@echo "  stdio-run          Run local stdio MCP server (quilt.main)"
	@echo "  stdio-config       Print Claude Desktop config snippet"
	@echo "  stdio-inspector    Launch MCP Inspector for stdio server"
	@echo ""
	@echo "Remote Tasks:" 
	@echo "  remote-run         Run local HTTP MCP server (remote.py)"
	@echo "  remote-test        curl tools/list against local HTTP server"
	@echo "  remote-inspector   Launch MCP Inspector for deployed endpoint"
	@echo ""

# Setup / env
default: help
setup:
	$(UV) sync

deps-test:
	$(UV) sync --group test

deps-lint:
	$(UV) sync --group lint

deps-all:
	$(UV) sync --all-extras --group test --group lint --group deploy || \
		($(UV) sync && $(UV) sync --group test && $(UV) sync --group lint && $(UV) sync --group deploy)

env:
	@[ -f .env ] && echo ".env already exists" || (cp env.example .env && echo "Created .env")

# Build / deploy wrappers
build:
	./scripts/build.sh build

test:
	./scripts/build.sh test

deploy:
	./scripts/build.sh deploy

clean:
	./scripts/build.sh clean || true
	rm -rf .pytest_cache .coverage dist build *.egg-info

# Logs & token
logs:
	./scripts/check_logs.sh -s 10m

token:
	@$(TOKEN_CMD)

# Local HTTP server
remote-run:
	$(UV) sync
	$(UV) run $(PY) -m quilt.remote

remote-test:
	@curl -s -X POST http://localhost:8000/mcp/ \
	  -H "Content-Type: application/json" \
	  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .

remote-inspector:
	@if [ -z "$(API_ENDPOINT)" ]; then echo "API_ENDPOINT not set in .config"; exit 1; fi; \
	TOKEN="$$($(TOKEN_CMD))"; \
	if [ -z "$$TOKEN" ]; then echo "Failed to get token"; exit 1; fi; \
	$(INSPECTOR) --server-url "$(API_ENDPOINT)/mcp"

# Stdio config & inspection
stdio-config:
	@echo '{'
	@echo '  "mcpServers": {'
	@echo '    "quilt": {'
	@echo '      "command": "uv",'
	@echo '      "args": ["run", "-m", "quilt.main"]'
	@echo '    }'
	@echo '  }'
	@echo '}'

stdio-inspector:
	$(UV) sync
	$(INSPECTOR) --server-command "$(UV)" --server-args "run -m quilt.main"

stdio-run:
	$(UV) sync
	$(UV) run $(PY) -m quilt.main

# Tests
pytest: deps-test
	$(UV) run python -m pytest -q

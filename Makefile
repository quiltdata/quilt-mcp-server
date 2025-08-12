SHELL := /bin/bash
UV ?= uv
ENV_FILE ?= .env
UVRUN ?= uv run --env-file $(ENV_FILE)
PY ?= python
INSPECTOR ?= npx -y @modelcontextprotocol/inspector@latest
TOKEN_CMD := ./scripts/get_token.sh
PROJECT_ROOT := $(shell pwd)

API_ENDPOINT := $(shell [ -f .config ] && . ./.config >/dev/null 2>&1; echo $$API_ENDPOINT)

.DEFAULT_GOAL := help

# Phony targets grouped by category: utility, build, stdio, remote
.PHONY: help setup env clean logs token pytest coverage build test deploy all stdio-run stdio-config stdio-inspector remote-run remote-hotload remote-test remote-inspector remote-kill deps-test deps-lint deps-all

# Test event generation pattern
tests/events/%.json: tests/generate_lambda_events.py
	@mkdir -p tests/events
	$(UVRUN) python tests/generate_lambda_events.py --event-type $* -o $@
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
	@echo "  coverage           Run pytest with coverage report"
	@echo ""
	@echo "Build Tasks:" 
	@echo "  build              Build lambda artifact (scripts/build.sh build)"
	@echo "  test               Test deployed stack (scripts/build.sh test)"
	@echo "  deploy             Build + deploy via CDK (scripts/build.sh deploy)"
	@echo "  all                Run pytest then deploy (test + deploy)"
	@echo ""
	@echo "Stdio Tasks:" 
	@echo "  stdio-run          Run local stdio MCP server (quilt.main)"
	@echo "  stdio-config       Print Claude Desktop config snippet"
	@echo "  stdio-inspector    Launch MCP Inspector for stdio server"
	@echo ""
	@echo "Remote Tasks:" 
	@echo "  remote-run         Run local HTTP MCP server (Python direct)"
	@echo "  remote-hotload     Run local HTTP MCP server with FastMCP hot reload"
	@echo "  remote-test        Test local FastMCP server with session management"
	@echo "  remote-test-full   Full test of local server with detailed output"
	@echo "  remote-kill        Stop local HTTP MCP server"
	@echo "  remote-inspector   Launch MCP Inspector for deployed endpoint"
	@echo ""
	@echo "Test Events:"
	@echo "  Generate Lambda test events in tests/events/ using:"
	@echo "    make tests/events/tools-list.json"
	@echo "    make tests/events/resources-list.json" 
	@echo "    make tests/events/health-check.json"
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

all: pytest deploy
	@echo "✅ All tasks completed: pytest + deploy"

clean:
	./scripts/build.sh clean || true
	rm -rf .pytest_cache .coverage dist build *.egg-info

# Logs & token
logs:
	./scripts/check_logs.sh -s 10m

token:
	@$(TOKEN_CMD)

# Local HTTP server
remote-run: setup
	$(UVRUN) python entry_points/dev_server.py

remote-hotload: setup
	$(UVRUN) fastmcp dev entry_points/dev_server.py:mcp --with-editable .

remote-test:
	@echo "Testing FastMCP streamable HTTP transport with session management..."
	@SESSION_ID=$$(curl -s -i -X POST http://localhost:8000/mcp \
	  -H "Content-Type: application/json" \
	  -H "Accept: application/json, text/event-stream" \
	  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}' \
	  | grep -i "mcp-session-id:" | head -1 | sed 's/.*mcp-session-id: *\([^ \r]*\).*/\1/' | tr -d '\r'); \
	if [ -n "$$SESSION_ID" ]; then \
	  echo "Got session ID: $$SESSION_ID"; \
	  curl -s -X POST http://localhost:8000/mcp \
	    -H "Content-Type: application/json" \
	    -H "Accept: application/json, text/event-stream" \
	    -H "Mcp-Session-Id: $$SESSION_ID" \
	    -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null; \
	  curl -s -X POST http://localhost:8000/mcp \
	    -H "Content-Type: application/json" \
	    -H "Accept: application/json, text/event-stream" \
	    -H "Mcp-Session-Id: $$SESSION_ID" \
	    -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | grep "^data: " | sed 's/^data: //' | jq .; \
	else \
	  echo "No session ID returned, testing without session management..."; \
	  curl -s -X POST http://localhost:8000/mcp \
	    -H "Content-Type: application/json" \
	    -H "Accept: application/json, text/event-stream" \
	    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | grep "^data: " | sed 's/^data: //' | jq .; \
	fi

remote-test-full:
	./scripts/test-endpoint.sh -l -v

remote-kill:
	@pkill -f "python -m quilt.remote" || echo "No remote server running"

remote-inspector:
	$(INSPECTOR) --server-url "http://127.0.0.1:8000/mcp"

lambda-inspector:
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
	@echo '      "args": ["run", "entry_points/stdio_server.py"]'
	@echo '    }'
	@echo '  }'
	@echo '}'

stdio-inspector: setup
	$(INSPECTOR) --server-command "$(UV)" --server-args "run entry_points/stdio_server.py"

stdio-run: setup
	$(UVRUN) $(PY) entry_points/stdio_server.py

# Tests
pytest: deps-test
	$(UVRUN) python -m pytest

coverage: deps-test
	$(UVRUN) python -m pytest --cov=quilt --cov-report=term-missing

lint: deps-lint
	@echo "Linting not configured yet - skipping"

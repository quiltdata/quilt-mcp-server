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
.PHONY: help setup env clean logs token pytest coverage build test deploy all stdio-run stdio-config stdio-inspector remote-run remote-hotload remote-export remote-test remote-inspector remote-kill deps-lint deps-all lint ruff ruff-fix black black-check mypy yaml-lint format lint-ci

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
	@echo "  lint               Auto-fix Python (ruff+black), then type & YAML lint"
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
	@echo "  remote-export      Expose local MCP server via ngrok tunnel"
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

remote-export: setup
	@echo "🚀 Starting MCP server and exposing via ngrok..."
	@echo "Make sure ngrok is installed: brew install ngrok (or download from ngrok.com)"
	@echo ""
	@echo "Starting MCP server on port 8000..."
	@$(UVRUN) python entry_points/dev_server.py & \
	SERVER_PID=$$!; \
	echo "Server started with PID: $$SERVER_PID"; \
	sleep 3; \
	echo "Starting ngrok tunnel..."; \
	ngrok http 8000 --log=stdout & \
	NGROK_PID=$$!; \
	echo "Ngrok started with PID: $$NGROK_PID"; \
	echo ""; \
	echo "🌐 Your MCP server will be available at the ngrok URL shown above"; \
	echo "📋 MCP endpoint will be: https://your-ngrok-url.ngrok.io/mcp"; \
	echo ""; \
	echo "Press Ctrl+C to stop both server and ngrok"; \
	trap 'echo "Stopping server and ngrok..."; kill $$SERVER_PID $$NGROK_PID 2>/dev/null; exit' INT; \
	wait

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
pytest: setup
	$(UVRUN) python -m pytest

coverage: setup
	$(UVRUN) python -m pytest --cov=quilt --cov-report=term-missing

PY_SRC := src tests entry_points
YAML_FILES := $(shell find . -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null)

lint: deps-lint ruff-fix black mypy yaml-lint ## Auto-fix formatting & style, then type & YAML lint
	@echo "✅ Lint (auto-fix) completed"

lint-ci: lint ## Alias for lint (CI friendly)

format: deps-lint ## Auto-format code with Ruff (imports, fixes) and Black
	@echo "🔧 Ruff (autofix)"
	$(UVRUN) ruff check --fix $(PY_SRC)
	@echo "🖤 Black formatting"
	$(UVRUN) black $(PY_SRC)
	@echo "✅ Formatting complete"

ruff: deps-lint ## Run Ruff (no fix)
	$(UVRUN) ruff check $(PY_SRC)

ruff-check: ruff ## Backward compatibility target (non-fixing)

ruff-fix: deps-lint ## Run Ruff with fixes
	$(UVRUN) ruff check --fix $(PY_SRC)

black: deps-lint ## Run Black (format in place)
	$(UVRUN) black $(PY_SRC)

black-check: deps-lint ## Run Black in check mode
	$(UVRUN) black --check --diff $(PY_SRC)

mypy: deps-lint ## Run mypy static type checking
	$(UVRUN) mypy src

yaml-lint: deps-lint ## Lint YAML files with yamllint (skip if none)
	@if [ -z "$(YAML_FILES)" ]; then echo "(No YAML files to lint)"; else $(UVRUN) yamllint $(YAML_FILES); fi

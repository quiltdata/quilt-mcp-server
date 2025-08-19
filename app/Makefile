# Quilt MCP Server - Phase 1 (App) Makefile
# Local MCP server build and run

.PHONY: help clean config coverage lint run test test-unit test-endpoint validate init verify zero 

# Default target
help:
	@echo "Quilt MCP Server - Phase 1 (App)"
	@echo ""
	@echo "Commands:"
	@echo "  make run          - Start local MCP server on http://127.0.0.1:8000/mcp/"
	@echo "  make test         - Run unit and integration tests"
	@echo "  make test-unit    - Run unit tests only (skip integration tests)"
	@echo "  make test-endpoint - Start server and test MCP endpoint"
	@echo "  make coverage     - Run tests with coverage (≥85% required)"
	@echo "  make lint         - Run code linting (auto-fixes formatting, reports remaining issues)"
	@echo "  make validate     - Full SPEC-compliant validation"
	@echo "  make clean        - Clean Python cache"
	@echo "  make config       - Generate .config file with test results"
	@echo "  make init         - Check preconditions"
	@echo "  make verify       - Verify MCP endpoint"
	@echo "  make zero         - Stop running processes"

clean:
	@./app.sh clean

config:
	@./app.sh config

coverage:
	@./app.sh coverage

lint:
	@echo "Running code linting and auto-fixing..."
	@uv sync --group lint
	@echo "Running black (formatter) - auto-fixing..."
	@uv run black quilt_mcp/ tests/
	@echo "Running ruff (linter) - auto-fixing..."
	@uv run ruff check --fix quilt_mcp/ tests/
	@echo "Running mypy (type checker)..."
	@uv run mypy quilt_mcp/
	@echo "✅ All linting completed"

run:
	@./app.sh run

test:
	@./app.sh test

test-ci:
	@echo "Running IAM tests only (skipping search tests)..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest tests/ -v -m "not search"

test-unit:
	@echo "Running unit tests only (skipping integration tests)..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest tests/ -v -m "not aws"

test-endpoint:
	@echo "Starting MCP server and testing endpoint..."
	@uv run python main.py & \
	SERVER_PID=$$!; \
	sleep 3; \
	../shared/test-endpoint.sh -t "http://127.0.0.1:8000/mcp/" || TEST_RESULT=$$?; \
	kill $$SERVER_PID 2>/dev/null || true; \
	exit $${TEST_RESULT:-0}

validate:
	@./app.sh validate

init:
	@echo "Checking Phase 1 (App) preconditions..."
	@command -v uv >/dev/null || (echo "Error: uv not found. Please install uv first." && exit 1)
	@echo "✅ Phase 1 preconditions met"

verify:
	@echo "Starting server for endpoint verification (using sse transport)..."
	@FASTMCP_TRANSPORT=sse ./app.sh run &
	@echo $$! > .app-server.pid
	@sleep 5  # Wait for server to start
	@echo "Testing MCP endpoint..."
	@../shared/test-endpoint.sh -p app -t || (kill `cat .app-server.pid` 2>/dev/null; rm -f .app-server.pid; exit 1)
	@echo "Stopping server..."
	@kill `cat .app-server.pid` 2>/dev/null || true
	@rm -f .app-server.pid

zero:
	@echo "Stopping Phase 1 (App) processes..."
	@pkill -f "python.*main.py" 2>/dev/null || true
	@echo "✅ Phase 1 processes stopped"

# Quilt MCP Server - Phase 1 (App) Makefile
# Local MCP server build and run

# Load environment variables from .env if it exists
sinclude ../.env
export

ENDPOINT ?= http://127.0.0.1:8000/mcp/

.PHONY: help clean config coverage lint run test test-unit test-endpoint validate init verify zero run-inspector 

# Default target
help:
	@echo "Quilt MCP Server - Phase 1 (App)"
	@echo ""
	@echo "Commands:"
	@echo "  make run          - Start local MCP server on $(ENDPOINT)"
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
	@echo "  make run-inspector - Launch MCP Inspector for visual testing"

clean:
	@echo "Cleaning Python cache..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean completed"

config:
	@./app.sh config

coverage:
	@echo "Running tests with coverage (≥85% required)..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest tests/ --cov=quilt_mcp --cov-report=term-missing --cov-fail-under=85 -v

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
	@echo "Starting local MCP server..."
	@uv sync
	@./app.sh config  # Generate .config before starting
	@echo "Server starting on $(ENDPOINT)"
	@export PYTHONPATH="$(PWD)" && uv run python main.py

run-inspector:
	@echo "Launching MCP Inspector for visual testing..."
	@command -v npx >/dev/null || (echo "Error: npx not found. Please install Node.js first." && exit 1)
	@uv sync
	@echo "Starting MCP Inspector with server at $(ENDPOINT)"
	@echo "Inspector UI will be available at http://127.0.0.1:6274"
	@export PYTHONPATH="$(PWD)" && npx @modelcontextprotocol/inspector uv run python main.py

test:
	@echo "Running local tests..."
	@uv sync --group test
	@if [ -d "tests" ] && [ "$$(find tests -name "*.py" | wc -l)" -gt 0 ]; then \
		export PYTHONPATH="$(PWD)" && uv run python -m pytest tests/ -v; \
	else \
		echo "No tests found, running import test..."; \
		export PYTHONPATH="$(PWD)" && uv run python -c "from quilt_mcp.server import main; from quilt_mcp.tools import auth, buckets, packages, package_ops; print('✅ All imports successful')"; \
	fi

test-ci:
	@echo "Running IAM tests only (skipping search tests)..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest tests/ -v -m "not search"

test-unit:
	@echo "Running unit tests only (skipping integration tests)..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest tests/ -v -m "not aws"

test-endpoint:
	@echo "Testing MCP endpoint at $(ENDPOINT)..."
	@../shared/test-endpoint.sh -t "$(ENDPOINT)"

validate:
	@./app.sh validate

init:
	@echo "Checking Phase 1 (App) preconditions..."
	@command -v uv >/dev/null || (echo "Error: uv not found. Please install uv first." && exit 1)
	@echo "✅ Phase 1 preconditions met"

verify:
	@echo "Verifying MCP endpoint by starting server and running tests..."
	@$(MAKE) run & \
	SERVER_PID=$$!; \
	sleep 3; \
	$(MAKE) test-endpoint || TEST_RESULT=$$?; \
	kill $$SERVER_PID 2>/dev/null || true; \
	exit $${TEST_RESULT:-0}

zero:
	@echo "Stopping Phase 1 (App) processes..."
	@pkill -f "python.*main.py" 2>/dev/null || true
	@echo "✅ Phase 1 processes stopped"

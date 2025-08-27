# Quilt MCP Server - Phase 1 (App) Makefile
# Local MCP server build and run

# Load environment variables from .env if it exists
sinclude ../.env
export

ENDPOINT ?= http://127.0.0.1:8001/mcp/

.PHONY: help clean config coverage lint run test test-unit test-endpoint validate init verify zero run-inspector test-tools update-cursor-rules 

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
	@echo "  make init         - Check preconditions and update Cursor rules"
	@echo "  make verify       - Verify MCP endpoint"
	@echo "  make zero         - Stop running processes"
	@echo "  make run-inspector - Launch MCP Inspector for visual testing"
	@echo "  make update-cursor-rules - Update Cursor IDE rules from CLAUDE.md"

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
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest ../tests/ --cov=quilt_mcp --cov-report=term-missing --cov-fail-under=85 -v

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
	@if [ -d "../tests" ] && [ "$$(find ../tests -name "*.py" | wc -l)" -gt 0 ]; then \
		export PYTHONPATH="$(PWD)" && uv run python -m pytest ../tests/ -v; \
	else \
		echo "No tests found, running import test..."; \
		export PYTHONPATH="$(PWD)" && uv run python -c "from quilt_mcp.server import main; from quilt_mcp.tools import auth, buckets, packages, package_ops; print('✅ All imports successful')"; \
	fi

test-ci:
	@echo "Running CI tests with timeouts (skipping search tests)..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && QUILT_DISABLE_QUILT3_SESSION=1 uv run python -m pytest ../tests/ -v -m "not search" --timeout=15 --disable-warnings

test-ci-with-aws:
	@echo "Running CI tests with real AWS credentials..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && QUILT_DISABLE_QUILT3_SESSION=1 uv run python -m pytest ../tests/ -v -m "not slow" --timeout=30 --disable-warnings

test-ci-with-aws-no-search:
	@echo "Running CI tests with real AWS credentials (excluding search)..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && QUILT_DISABLE_QUILT3_SESSION=1 uv run python -m pytest ../tests/ -v -m "not search and not slow" --timeout=30 --disable-warnings

test-unit-ci:
	@echo "Running unit tests only (no AWS calls)..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest ../tests/ -v -m "not aws and not search" --timeout=10 --disable-warnings

test-integration:
	@echo "Running integration tests with real AWS..."
	@uv sync --group test
	@mkdir -p test-results
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest ../tests/ -v -m "aws or search" --timeout=120 --disable-warnings \
		--junitxml=test-results/results.xml --cov=quilt_mcp --cov-report=xml:coverage.xml

test-aws:
	@echo "Running AWS-specific integration tests..."
	@uv sync --group test
	@mkdir -p test-results
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest ../tests/ -v -m "aws" --timeout=120 --disable-warnings \
		--junitxml=test-results/results.xml --cov=quilt_mcp --cov-report=xml:coverage.xml

test-search:
	@echo "Running search integration tests..."
	@uv sync --group test
	@mkdir -p test-results
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest ../tests/ -v -m "search" --timeout=120 --disable-warnings \
		--junitxml=test-results/results.xml --cov=quilt_mcp --cov-report=xml:coverage.xml

test-permissions:
	@echo "Running permission-specific tests..."
	@uv sync --group test
	@mkdir -p test-results
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest ../tests/test_permissions.py -v --timeout=60 --disable-warnings \
		--junitxml=test-results/results.xml --cov=quilt_mcp --cov-report=xml:coverage.xml

test-unit:
	@echo "Running unit tests only (skipping integration tests)..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest ../tests/ -v -m "not aws"

test-tools:
	@echo "Running tool-focused tests (metadata/buckets/packages)..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest ../tests/test_metadata_examples.py ../tests/test_bucket_tools.py ../tests/test_quilt_tools.py -v

test-endpoint:
	@echo "Testing MCP endpoint at $(ENDPOINT)..."
	@../shared/test-endpoint.sh -t "$(ENDPOINT)"

validate:
	@./app.sh validate

init:
	@echo "Checking Phase 1 (App) preconditions..."
	@command -v uv >/dev/null || (echo "Error: uv not found. Please install uv first." && exit 1)
	@$(MAKE) update-cursor-rules
	@echo "✅ Phase 1 preconditions met"

update-cursor-rules:
	@echo "📝 Updating Cursor IDE rules..."
	@mkdir -p ../.cursor/rules
	@if [ -f ../CLAUDE.md ]; then \
		cp ../CLAUDE.md ../.cursor/rules/; \
		echo "✅ Cursor rules updated from CLAUDE.md"; \
	else \
		echo "⚠️  CLAUDE.md not found, skipping cursor rules update"; \
	fi

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

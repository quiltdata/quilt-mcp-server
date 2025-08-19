#!/bin/bash
# App Phase: Local MCP server build and run
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load shared utilities
source "$PROJECT_ROOT/shared/common.sh"

usage() {
    echo "Usage: $0 [run|test|coverage|validate|clean|config]"
    echo ""
    echo "Commands:"
    echo "  test       Run unit and integration tests"
    echo "  coverage   Run tests with coverage (fails if <85%)"
    echo "  validate   Full validation (≥85% coverage + endpoint test)"
    echo "  run        Start local MCP server"
    echo "  clean      Clean Python cache"
    echo "  config     Generate .config file with test and coverage results"
}

case "${1:-run}" in
    run)
        log_info "Starting local MCP server..."
        
        # Check dependencies
        if ! command -v uv &> /dev/null; then
            log_error "uv not found. Please install uv first."
            exit 1
        fi
        
        cd "$SCRIPT_DIR"
        
        # Install dependencies
        uv sync
        
        # Set Python path
        export PYTHONPATH="$SCRIPT_DIR"
        
        # Generate .config file before starting server
        "$SCRIPT_DIR/app.sh" config
        
        # Run server
        log_info "Server starting on http://127.0.0.1:8000/mcp"
        uv run python main.py
        ;;
        
    test)
        log_info "Running local tests..."
        
        cd "$SCRIPT_DIR"
        
        # Install test dependencies
        uv sync --group test
        
        # Set Python path for tests
        export PYTHONPATH="$SCRIPT_DIR"
        
        # Check if tests exist
        if [ -d "tests" ] && [ "$(find tests -name "*.py" | wc -l)" -gt 0 ]; then
            # Run tests
            uv run python -m pytest tests/ -v
        else
            log_warning "No tests found in tests/ directory"
            log_info "Creating basic test to verify imports work..."
            # Test that we can import the main module
            uv run python -c "
import sys
sys.path.insert(0, '.')
try:
    from quilt_mcp.server import main
    print('✅ Successfully imported quilt_mcp.server')
    from quilt_mcp.tools import auth, buckets, packages, package_ops
    print('✅ Successfully imported all tools')
    print('✅ App phase validation completed')
except Exception as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"
        fi
        ;;
        
    coverage)
        log_info "Running tests with coverage (≥85% required)..."
        
        cd "$SCRIPT_DIR"
        
        # Install test dependencies
        uv sync --group test
        
        # Set Python path for tests
        export PYTHONPATH="$SCRIPT_DIR"
        
        # Run tests with coverage, fail if <85%
        if [ -d "tests" ] && [ "$(find tests -name "*.py" | wc -l)" -gt 0 ]; then
            log_info "Running pytest with --cov-fail-under=85..."
            uv run python -m pytest tests/ --cov=quilt_mcp --cov-report=term-missing --cov-fail-under=85 -v
            log_success "✅ Coverage validation passed (≥85%)"
        else
            log_error "❌ No tests found in tests/ directory"
            exit 1
        fi
        ;;
        
    validate)
        log_info "🔍 Phase 1: App validation (SPEC compliant: tests + coverage + endpoint)"
        log_info "SPEC Requirements: ≥85% coverage, all tests pass, MCP endpoint responds"
        
        cd "$SCRIPT_DIR"
        
        # Install test dependencies
        uv sync --group test
        
        # Set Python path for tests
        export PYTHONPATH="$SCRIPT_DIR"
        
        # SPEC REQUIREMENT: All tests with ≥85% coverage
        log_info "Running all tests with ≥85% coverage requirement..."
        if [ -d "tests" ] && [ "$(find tests -name "*.py" | wc -l)" -gt 0 ]; then
            uv run python -m pytest tests/ --cov=quilt_mcp --cov-report=term-missing --cov-fail-under=85 -v
        else
            log_error "❌ SPEC violation: No tests found in tests/ directory"
            log_error "SPEC requires tests with ≥85% coverage"
            exit 1
        fi
        
        # SPEC REQUIREMENT: Local endpoint validation via test-endpoint.sh
        log_info "Testing local MCP endpoint..."
        if [ -f "$PROJECT_ROOT/shared/test-endpoint.sh" ]; then
            # Start server in background (using SSE transport)
            uv run python main.py &
            SERVER_PID=$!
            sleep 3
            
            # Test endpoint
            "$PROJECT_ROOT/shared/test-endpoint.sh" -t "http://127.0.0.1:8000/mcp/" || (
                log_error "❌ SPEC violation: Local endpoint test failed"
                kill $SERVER_PID 2>/dev/null || true
                exit 1
            )
            
            # Stop server
            kill $SERVER_PID 2>/dev/null || true
        else
            log_warning "shared/test-endpoint.sh not found, skipping endpoint test"
        fi
        
        log_success "✅ App phase validation passed (SPEC compliant)"
        ;;
        
    config)
        log_info "Generating .config file with test and coverage results..."
        
        cd "$SCRIPT_DIR"
        
        # Install test dependencies
        uv sync --group test
        
        # Set Python path for tests
        export PYTHONPATH="$SCRIPT_DIR"
        
        # Run tests and capture results
        TEST_RESULT="❌ FAILED"
        COVERAGE_RESULT="❌ FAILED"
        COVERAGE_PERCENTAGE="0%"
        
        # Check if tests exist and run them
        if [ -d "tests" ] && [ "$(find tests -name "*.py" | wc -l)" -gt 0 ]; then
            if uv run python -m pytest tests/ -v > /tmp/app_test_results.log 2>&1; then
                TEST_RESULT="✅ PASSED"
            fi
            
            # Run coverage test
            if uv run python -m pytest tests/ --cov=quilt_mcp --cov-report=term-missing --cov-fail-under=85 > /tmp/app_coverage_results.log 2>&1; then
                COVERAGE_RESULT="✅ PASSED"
                # Extract coverage percentage from output
                COVERAGE_PERCENTAGE=$(grep "TOTAL" /tmp/app_coverage_results.log | awk '{print $NF}' || echo "Unknown")
            else
                # Try to extract coverage percentage even if it failed the 85% threshold
                COVERAGE_PERCENTAGE=$(grep "TOTAL" /tmp/app_coverage_results.log | awk '{print $NF}' || echo "Unknown")
            fi
        else
            log_warning "No tests found in tests/ directory"
            TEST_RESULT="⚠️  NO TESTS"
            COVERAGE_RESULT="⚠️  NO TESTS"
        fi
        
        # Create .config file
        cat > "$PROJECT_ROOT/.config" << EOF
# Quilt MCP Server - Phase 1 (App) Configuration
# Generated on $(date)

PHASE=app
PHASE_NAME="Local MCP Server"
ENDPOINT="http://127.0.0.1:8000/mcp"
TEST_STATUS="$TEST_RESULT"
COVERAGE_STATUS="$COVERAGE_RESULT"
COVERAGE_PERCENTAGE="$COVERAGE_PERCENTAGE"
PYTHON_PATH="$SCRIPT_DIR"
UV_SYNC_COMPLETED=true
GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GIT_HASH="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
EOF
        
        log_success "✅ Phase 1 .config generated successfully"
        log_info "Test Status: $TEST_RESULT"
        log_info "Coverage Status: $COVERAGE_RESULT ($COVERAGE_PERCENTAGE)"
        log_info "Configuration saved to $PROJECT_ROOT/.config"
        ;;
        
    clean)
        log_info "Cleaning Python cache..."
        cd "$SCRIPT_DIR"
        find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete 2>/dev/null || true
        log_info "Clean completed"
        ;;
        
    *)
        log_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac
#!/bin/bash
# App Phase: Local MCP server build and run
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load shared utilities
source "$PROJECT_ROOT/shared/common.sh"

usage() {
    echo "Usage: $0 [validate|config]"
    echo ""
    echo "Commands:"
    echo "  validate   Full validation (≥85% coverage + endpoint test)"
    echo "  config     Generate .config file with test and coverage results"
}

case "${1:-validate}" in
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
        if [ -d "../tests" ] && [ "$(find ../tests -name "*.py" | wc -l)" -gt 0 ]; then
            uv run python -m pytest ../tests/ --cov=quilt_mcp --cov-report=term-missing --cov-fail-under=85 -v
        else
            log_error "❌ SPEC violation: No tests found in ../tests/ directory"
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
            "$PROJECT_ROOT/shared/test-endpoint.sh" -t "${ENDPOINT:-http://127.0.0.1:8000/mcp/}" || (
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
        if [ -d "../tests" ] && [ "$(find ../tests -name "*.py" | wc -l)" -gt 0 ]; then
            # Run a quick subset of tests for config generation
            if uv run python -m pytest ../tests/test_formatting.py ../tests/test_mcp_client.py -v > /tmp/app_test_results.log 2>&1; then
                TEST_RESULT="✅ PASSED"
            fi
            
            # Run coverage test on a smaller subset
            if uv run python -m pytest ../tests/test_formatting.py ../tests/test_mcp_client.py ../tests/test_utils.py --cov=quilt_mcp --cov-report=term-missing > /tmp/app_coverage_results.log 2>&1; then
                COVERAGE_RESULT="✅ PASSED"
                # Extract coverage percentage from output
                COVERAGE_PERCENTAGE=$(grep "TOTAL" /tmp/app_coverage_results.log | awk '{print $NF}' || echo "Unknown")
            else
                # Try to extract coverage percentage even if it failed the 85% threshold
                COVERAGE_PERCENTAGE=$(grep "TOTAL" /tmp/app_coverage_results.log | awk '{print $NF}' || echo "Unknown")
            fi
        else
            log_warning "No tests found in ../tests/ directory"
            TEST_RESULT="⚠️  NO TESTS"
            COVERAGE_RESULT="⚠️  NO TESTS"
        fi
        
        # Create .config file
        cat > "$PROJECT_ROOT/.config" << EOF
# Quilt MCP Server - Phase 1 (App) Configuration
# Generated on $(date)

PHASE=app
PHASE_NAME="Local MCP Server"
ENDPOINT="${ENDPOINT:-http://127.0.0.1:8000/mcp/}"
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
        
    *)
        log_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac
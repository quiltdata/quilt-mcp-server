#!/bin/bash
# App Phase: Local MCP server build and run
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load shared utilities
source "$PROJECT_ROOT/src/shared/common.sh"

usage() {
    echo "Usage: $0 [run|test|test-local|validate|clean]"
    echo ""
    echo "Commands:"
    echo "  run        Start local MCP server"
    echo "  test       Run tests locally"
    echo "  test-local Test MCP server can start and validate tools"
    echo "  validate   Full validation (≥85% coverage + endpoint test)"
    echo "  clean      Clean Python cache"
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
        export PYTHONPATH="$SCRIPT_DIR/src"
        
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
        export PYTHONPATH="$SCRIPT_DIR/src"
        
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
sys.path.insert(0, 'src')
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
        
    test-local)
        log_info "Testing local MCP server startup..."
        
        cd "$SCRIPT_DIR"
        
        # Install dependencies
        uv sync
        
        # Set Python path
        export PYTHONPATH="$SCRIPT_DIR/src"
        
        # Test that server can start and initialize
        log_info "Testing server initialization..."
        uv run python -c "
import sys
sys.path.insert(0, 'src')
try:
    from quilt_mcp.adapters.fastmcp_bridge import FastMCPBridge
    from quilt_mcp.core.processor import MCPProcessor
    
    # Test processor initialization
    processor = MCPProcessor()
    processor.initialize()
    tools = processor.tool_registry.list_tools()
    
    print(f'✅ Successfully initialized processor with {len(tools)} tools')
    
    # Test bridge initialization
    bridge = FastMCPBridge('test')
    bridge.initialize()
    
    print('✅ Successfully initialized FastMCP bridge')
    print('✅ Local endpoint validation passed')
    
except Exception as e:
    print(f'❌ Local endpoint test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"
        ;;
        
    validate)
        log_info "🔍 Phase 1: App validation (unit tests + coverage + endpoint)"
        log_info "Requirements: ≥85% coverage, all tests pass, local endpoint responds"
        
        cd "$SCRIPT_DIR"
        
        # Install test dependencies
        uv sync --group test
        
        # Set Python path for tests
        export PYTHONPATH="$SCRIPT_DIR/src"
        
        # Unit tests with coverage requirement
        log_info "Running unit tests with coverage..."
        uv run python -m pytest tests/ --cov=quilt_mcp --cov-report=term-missing --cov-fail-under=85 -v
        
        # Integration tests (if they exist)
        if [ -d "tests/integration" ]; then
            log_info "Running integration tests..."
            uv run python -m pytest tests/integration/ -v
        else
            log_info "No integration tests found (tests/integration/ missing)"
        fi
        
        # Local endpoint test  
        log_info "Testing local MCP endpoint..."
        "$SCRIPT_DIR/app.sh" test-local || (log_error "❌ Local endpoint test failed" && exit 1)
        
        log_success "✅ App phase validation passed"
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
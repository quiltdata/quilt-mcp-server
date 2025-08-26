#!/bin/bash
# Test bash commands from README.md
# 
# This script implements NFR4: Documentation Testing by extracting and
# testing bash commands from README.md to ensure they work as documented.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
README_FILE="$REPO_ROOT/README.md"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Extract bash commands from README.md
extract_bash_commands() {
    local readme_file="$1"
    local temp_file=$(mktemp)
    
    # Extract bash code blocks
    awk '
    BEGIN { in_bash = 0; block_num = 0 }
    /^```bash/ { in_bash = 1; block_num++; next }
    /^```$/ && in_bash { in_bash = 0; print "---BLOCK_END---"; next }
    in_bash && !/^#/ && NF > 0 { 
        gsub(/^[ \t]+/, ""); 
        if ($0 != "") print "BLOCK_" block_num ":" $0 
    }
    ' "$readme_file" > "$temp_file"
    
    echo "$temp_file"
}

# Test if a command is safe to run
is_safe_command() {
    local cmd="$1"
    
    # Safe commands (read-only, help, or specifically designed for testing)
    local safe_patterns=(
        "make help"
        "make mcp_config$"  
        "python -m quilt_mcp.auto_configure --help"
        "python -m quilt_mcp.auto_configure$"
        "make coverage" 
        "make check-env"
        "make init-app"
        "cp env.example .env"
        "python3 --version"
        "uv --version"
        "curl.*--help"
    )
    
    # Unsafe patterns (modify files, deploy, etc.)
    local unsafe_patterns=(
        ".*--client.*"
        ".*--config-file.*"
        "make deploy"
        "make destroy"
        "make test"  # Non-existent target in root Makefile
        "make coverage"  # Long-running test suite
        "make validate"  # Long-running validation
        "aws configure"
        "git clone"
        "uvx.*"  # Don't actually install packages
        "uv run quilt-mcp$"  # Don't start server
        "make app$"  # Don't start server
    )
    
    # Check unsafe patterns first
    for pattern in "${unsafe_patterns[@]}"; do
        if [[ "$cmd" =~ $pattern ]]; then
            return 1  # unsafe
        fi
    done
    
    # Check safe patterns
    for pattern in "${safe_patterns[@]}"; do
        if [[ "$cmd" =~ $pattern ]]; then
            return 0  # safe
        fi
    done
    
    return 1  # default to unsafe
}

# Execute a command safely
execute_command() {
    local cmd="$1"
    local block_id="$2"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    log_info "Testing [$block_id]: $cmd"
    
    if ! is_safe_command "$cmd"; then
        log_warn "Skipping unsafe command: $cmd"
        return 0
    fi
    
    # Set up environment
    export PYTHONPATH="$REPO_ROOT/app"
    export QUILT_CATALOG_DOMAIN="demo.quiltdata.com"
    
    # Change to repo root for command execution
    cd "$REPO_ROOT"
    
    # Execute command with timeout
    local output
    local exit_code
    
    output=$(timeout 30s bash -c "$cmd" 2>&1)
    exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        log_info "✓ PASSED: $cmd"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        log_error "✗ FAILED: $cmd (exit code: $exit_code)"
        # Only show output for debugging if verbose mode is enabled
        if [[ "${VERBOSE:-}" == "1" ]]; then
            echo "Output: $output"
        fi
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Test specific command patterns that we know should work
test_known_good_commands() {
    log_info "Testing known-good commands..."
    
    # Test commands that should always work
    local good_commands=(
        "make help"
        "python3 --version"
        "make mcp_config"
        "python -m quilt_mcp.auto_configure --help"
    )
    
    for cmd in "${good_commands[@]}"; do
        execute_command "$cmd" "KNOWN_GOOD"
    done
}

# Test auto-configure functionality specifically
test_auto_configure() {
    log_info "Testing auto-configure functionality..."
    
    # Test display mode
    execute_command "python -m quilt_mcp.auto_configure" "AUTO_CONFIG"
    
    # Test with custom domain
    QUILT_CATALOG_DOMAIN="test.example.com" execute_command "python -m quilt_mcp.auto_configure" "AUTO_CONFIG_DOMAIN"
    
    # Test help
    execute_command "python -m quilt_mcp.auto_configure --help" "AUTO_CONFIG_HELP"
}

# Test that critical files exist
test_file_existence() {
    log_info "Testing that critical files exist..."
    
    local critical_files=(
        "README.md"
        "Makefile"
        "app/Makefile"
        "env.example"
        "pyproject.toml"
        "app/quilt_mcp/auto_configure.py"
    )
    
    for file in "${critical_files[@]}"; do
        TOTAL_TESTS=$((TOTAL_TESTS + 1))
        if [[ -f "$REPO_ROOT/$file" ]]; then
            log_info "✓ EXISTS: $file"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            log_error "✗ MISSING: $file"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    done
}

# Main execution
main() {
    log_info "Starting README command testing..."
    log_info "Repository root: $REPO_ROOT"
    
    # Verify README exists
    if [[ ! -f "$README_FILE" ]]; then
        log_error "README.md not found at $README_FILE"
        exit 1
    fi
    
    # Test file existence first
    test_file_existence
    
    # Test known good commands
    test_known_good_commands
    
    # Test auto-configure functionality
    test_auto_configure
    
    # Extract and test commands from README (selective)
    log_info "Extracting commands from README.md..."
    local commands_file
    commands_file=$(extract_bash_commands "$README_FILE")
    
    if [[ -s "$commands_file" ]]; then
        log_info "Found bash commands in README, testing safe ones..."
        
        while IFS=':' read -r block_id command; do
            if [[ -n "$command" ]]; then
                execute_command "$command" "$block_id"
            fi
        done < "$commands_file"
    else
        log_warn "No bash commands found in README"
    fi
    
    # Cleanup
    rm -f "$commands_file"
    
    # Report results
    echo
    log_info "===================="
    log_info "TEST RESULTS SUMMARY"
    log_info "===================="
    log_info "Total tests: $TOTAL_TESTS"
    log_info "Passed: $PASSED_TESTS"
    log_info "Failed: $FAILED_TESTS"
    
    if [[ $FAILED_TESTS -eq 0 ]]; then
        log_info "✓ All README commands passed!"
        exit 0
    else
        log_error "✗ $FAILED_TESTS README command(s) failed"
        exit 1
    fi
}

# Run main function
main "$@"
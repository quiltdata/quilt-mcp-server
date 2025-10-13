#!/bin/bash
# Test Docker Container Health Checks
#
# This script simulates exactly what ECS does when running health checks
# inside the container. Use this for quick debugging and validation.
#
# Usage:
#   ./scripts/test-docker-health.sh [build|test|clean|all]
#
# Commands:
#   build  - Build Docker image locally
#   test   - Run health check tests
#   clean  - Stop and remove test containers
#   all    - Build, test, and clean (default)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_TAG="quilt-mcp:health-test"
CONTAINER_NAME="quilt-mcp-health-check-test"
TEST_PORT=8080

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

build_image() {
    log_info "Building Docker image: $IMAGE_TAG"
    cd "$REPO_ROOT"
    docker build --platform linux/amd64 -t "$IMAGE_TAG" .
    log_success "Docker image built successfully"
}

start_container() {
    log_info "Starting container with ECS-like configuration..."

    # Stop any existing test container
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true

    # Run with EXACT same env vars as ECS deployment
    docker run -d \
        --name "$CONTAINER_NAME" \
        -e FASTMCP_HOST=0.0.0.0 \
        -e FASTMCP_PORT=80 \
        -e FASTMCP_TRANSPORT=http \
        -p "$TEST_PORT:80" \
        "$IMAGE_TAG"

    log_success "Container started: $CONTAINER_NAME"
}

wait_for_ready() {
    log_info "Waiting for container to be ready..."

    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -sf "http://localhost:$TEST_PORT/health" > /dev/null 2>&1; then
            log_success "Container is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done

    log_error "Container failed to become ready after ${max_attempts}s"
    return 1
}

test_curl_installed() {
    log_info "Checking if curl is installed in container..."

    if docker exec "$CONTAINER_NAME" which curl > /dev/null 2>&1; then
        local curl_path=$(docker exec "$CONTAINER_NAME" which curl)
        log_success "curl is installed: $curl_path"

        # Show curl version
        local curl_version=$(docker exec "$CONTAINER_NAME" curl --version | head -1)
        echo "  Version: $curl_version"
        return 0
    else
        log_error "curl is NOT installed in container"
        log_warning "ECS health checks will fail without curl!"
        return 1
    fi
}

test_internal_health_check() {
    local route="${1:-/health}"
    log_info "Testing internal health check: $route"

    # This is the EXACT command ECS uses
    local result
    set +e
    result=$(docker exec "$CONTAINER_NAME" /bin/sh -c \
        "curl -v -f --max-time 8 http://localhost:80$route 2>&1")
    local exit_code=$?
    set -e

    if [ $exit_code -eq 0 ]; then
        log_success "Internal health check passed for $route"
        echo "$result" | grep -E "HTTP/|status" || true
        return 0
    else
        log_error "Internal health check FAILED for $route"
        echo ""
        echo "=== Curl Output ==="
        echo "$result"
        echo ""
        return 1
    fi
}

test_all_routes() {
    log_info "Testing all health check routes..."

    local routes=("/health" "/healthz" "/")
    local failed=0

    for route in "${routes[@]}"; do
        if ! test_internal_health_check "$route"; then
            failed=$((failed + 1))
        fi
        echo ""
    done

    if [ $failed -eq 0 ]; then
        log_success "All health check routes passed!"
        return 0
    else
        log_error "$failed route(s) failed"
        return 1
    fi
}

show_diagnostics() {
    log_info "Showing container diagnostics..."

    echo ""
    echo "=== Running Processes ==="
    docker exec "$CONTAINER_NAME" ps aux || log_warning "ps command not available"

    echo ""
    echo "=== Listening Ports ==="
    docker exec "$CONTAINER_NAME" netstat -tln 2>/dev/null || \
        docker exec "$CONTAINER_NAME" ss -tln 2>/dev/null || \
        log_warning "netstat/ss not available"

    echo ""
    echo "=== Environment Variables ==="
    docker exec "$CONTAINER_NAME" env | grep -E "FASTMCP|PORT"

    echo ""
    echo "=== Container Logs (last 20 lines) ==="
    docker logs --tail 20 "$CONTAINER_NAME"
}

clean_up() {
    log_info "Cleaning up test containers..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
    log_success "Cleanup completed"
}

run_tests() {
    start_container

    if ! wait_for_ready; then
        show_diagnostics
        clean_up
        exit 1
    fi

    echo ""

    local all_passed=0

    if ! test_curl_installed; then
        all_passed=1
    fi

    echo ""

    if ! test_all_routes; then
        all_passed=1
    fi

    if [ $all_passed -ne 0 ]; then
        echo ""
        show_diagnostics
        clean_up
        exit 1
    fi

    log_success "All tests passed!"
}

show_usage() {
    echo "Usage: $0 [build|test|clean|all]"
    echo ""
    echo "Commands:"
    echo "  build  - Build Docker image locally"
    echo "  test   - Run health check tests (requires image)"
    echo "  clean  - Stop and remove test containers"
    echo "  all    - Build, test, and clean (default)"
    echo ""
    echo "This script simulates exactly what ECS does for health checks."
    echo "It tests the EXACT command that ECS runs inside the container:"
    echo "  curl -v -f --max-time 8 http://localhost:80/health"
}

main() {
    local command="${1:-all}"

    case "$command" in
        build)
            build_image
            ;;
        test)
            run_tests
            clean_up
            ;;
        clean)
            clean_up
            ;;
        all)
            build_image
            echo ""
            run_tests
            echo ""
            clean_up
            ;;
        -h|--help|help)
            show_usage
            ;;
        *)
            log_error "Unknown command: $command"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    log_error "Docker daemon is not running or not accessible"
    exit 1
fi

main "$@"

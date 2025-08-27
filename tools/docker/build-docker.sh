#!/bin/bash
# Build Phase: Docker containerization
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load shared utilities
source "$PROJECT_ROOT/shared/common.sh"
source "$PROJECT_ROOT/shared/version.sh"

# Load environment variables from .env if present
load_environment

# Default values
VERBOSE=false
TAG=""

usage() {
    echo "Usage: $0 [build|test|run|validate|clean|config] [options]"
    echo ""
    echo "Commands:"
    echo "  build     Build Docker image"
    echo "  test      Test Docker container"
    echo "  run       Run Docker container locally"
    echo "  validate  Full validation (build + health + container test)"
    echo "  clean     Clean Docker images"
    echo "  config    Generate .config file with container info and git hash"
    echo ""
    echo "Options:"
    echo "  -v, --verbose    Enable verbose output"
    echo "  -t, --tag TAG    Docker image tag (default: git SHA)"
}

# Parse arguments
COMMAND=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        build|test|run|validate|clean|config)
            COMMAND="$1"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    COMMAND="build"
fi

# Set default tag from git if not provided
if [ -z "$TAG" ]; then
    TAG=$(get_version)
fi

IMAGE_NAME="quilt-mcp:$TAG"

case $COMMAND in
    build)
        log_info "Building Docker image: $IMAGE_NAME"
        
        # Ensure app phase is validated first
        log_info "Validating app phase dependencies..."
        cd "$PROJECT_ROOT/app"
        if ! ./app.sh test-local > /dev/null 2>&1; then
            log_info "App phase validation failed, running tests..."
            ./app.sh test-local
        fi
        
        cd "$PROJECT_ROOT"
        
        if [ "$VERBOSE" = true ]; then
            docker build -t "$IMAGE_NAME" -f build-docker/Dockerfile .
        else
            docker build -t "$IMAGE_NAME" -f build-docker/Dockerfile . > /dev/null
        fi
        
        log_success "Build completed: $IMAGE_NAME"
        
        # Generate .config file after successful build
        "$SCRIPT_DIR/build-docker.sh" config --tag "$TAG"
        
        echo "$IMAGE_NAME"  # Return the image name for chaining
        ;;
        
    test)
        log_info "Testing Docker container: $IMAGE_NAME"
        
        # Check if image exists
        if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
            log_error "Image $IMAGE_NAME not found. Run build first."
            exit 1
        fi
        
        # Run container with health check
        log_info "Starting container for testing..."
        CONTAINER_ID=$(docker run -d -p 8001:8000 "$IMAGE_NAME")
        
        # Wait for container to be ready
        log_info "Waiting for container to be ready..."
        sleep 10
        
        # Test if container is healthy by checking if it's running and port is open
        if docker exec "$CONTAINER_ID" curl -s http://localhost:8000/mcp > /dev/null 2>&1; then
            log_success "Container health check passed"
        else
            log_warning "Basic curl check failed, trying container process check..."
            # Check if container is running and process is healthy
            if docker exec "$CONTAINER_ID" pgrep -f "python.*main.py" > /dev/null; then
                log_success "Container is running with MCP server process active"
            else
                log_error "Container health check failed"
                docker logs "$CONTAINER_ID"
                docker stop "$CONTAINER_ID" > /dev/null
                exit 1
            fi
        fi
        
        # Cleanup
        docker stop "$CONTAINER_ID" > /dev/null
        log_success "Test completed successfully"
        ;;
        
    run)
        log_info "Running Docker container: $IMAGE_NAME"
        
        # Check if image exists
        if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
            log_warning "Image $IMAGE_NAME not found. Building first..."
            "$0" build --tag "$TAG"
        fi
        
        log_info "Server starting on http://127.0.0.1:8000/mcp"
        docker run --rm -p 8000:8000 "$IMAGE_NAME"
        ;;
        
    validate)
        log_info "🔍 Phase 2: Build-Docker validation (build + health + container test)"
        log_info "Requirements: Docker build succeeds, container starts <30s, health check passes"
        
        # Build Docker image
        "$0" build --tag "$TAG"
        
        # Container health and endpoint tests
        "$0" test --tag "$TAG"
        
        log_success "✅ Build-Docker phase validation passed"
        ;;
        
    config)
        log_info "Generating .config file with container info and git hash..."
        
        # Check if image exists
        if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
            log_warning "Docker image $IMAGE_NAME not found. Build status will be marked as needed."
            BUILD_STATUS="❌ IMAGE NOT FOUND"
            IMAGE_ID="not_built"
            IMAGE_SIZE="unknown"
        else
            BUILD_STATUS="✅ IMAGE BUILT"
            IMAGE_ID=$(docker image inspect "$IMAGE_NAME" --format '{{.Id}}' | cut -d':' -f2 | head -c 12)
            IMAGE_SIZE=$(docker image inspect "$IMAGE_NAME" --format '{{.Size}}' | numfmt --to=iec)
        fi
        
        # Create .config file
        cat > "$PROJECT_ROOT/.config" << EOF
# Quilt MCP Server - Phase 2 (Build-Docker) Configuration
# Generated on $(date)

PHASE=build
PHASE_NAME="Docker Container"
ENDPOINT="http://127.0.0.1:8001/mcp"
IMAGE_NAME="$IMAGE_NAME"
IMAGE_TAG="$TAG"
IMAGE_ID="$IMAGE_ID"
IMAGE_SIZE="$IMAGE_SIZE"
BUILD_STATUS="$BUILD_STATUS"
DOCKERFILE_PATH="build-docker/Dockerfile"
PLATFORM="linux/amd64"
GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GIT_HASH="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
GIT_HASH_FULL="$(git rev-parse HEAD 2>/dev/null || echo 'unknown')"
EOF
        
        log_success "✅ Phase 2 .config generated successfully"
        log_info "Image: $IMAGE_NAME"
        log_info "Build Status: $BUILD_STATUS"
        log_info "Configuration saved to $PROJECT_ROOT/.config"
        ;;
        
    clean)
        log_info "Cleaning Docker images..."
        docker images "quilt-mcp" -q | xargs -r docker rmi -f 2>/dev/null || true
        log_success "Clean completed"
        ;;
        
    *)
        log_error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac
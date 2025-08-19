#!/bin/bash
# Catalog Phase: ECR push operations
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
FORCE=false
DRY_RUN=false

usage() {
    echo "Usage: $0 [push|pull|test|login|validate|config] [options] [LOCAL_IMAGE]"
    echo ""
    echo "Commands:"
    echo "  push      Push local image to ECR"
    echo "  pull      Pull image from ECR"
    echo "  test      Test pulling and running ECR image"
    echo "  login     Login to ECR registry"
    echo "  validate  Full validation (login + push + pull test)"
    echo "  config    Generate .config file with ECR info"
    echo ""
    echo "Arguments:"
    echo "  LOCAL_IMAGE  Local Docker image (e.g., quilt-mcp:abc123)"
    echo ""
    echo "Options:"
    echo "  -v, --verbose    Enable verbose output"
    echo "  -f, --force      Force push even if image exists"
    echo "  --dry-run        Simulate operations without executing"
    echo ""
    echo "Environment Variables:"
    echo "  ECR_REGISTRY     ECR registry URL (required)"
    echo "  ECR_REPOSITORY   ECR repository name (default: quilt-mcp)"
}

# Parse arguments
COMMAND=""
LOCAL_IMAGE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        push|pull|test|login|validate|config)
            COMMAND="$1"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            if [ -z "$LOCAL_IMAGE" ]; then
                LOCAL_IMAGE="$1"
            else
                log_error "Unknown option: $1"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    COMMAND="push"
fi

# Setup ECR registry (construct if needed)
if ! setup_ecr_registry; then
    exit 1
fi

case $COMMAND in
    login)
        log_info "Logging in to ECR registry: $ECR_REGISTRY"
        
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY-RUN] Would login to ECR registry"
            log_success "ECR login successful (simulated)"
            exit 0
        fi
        
        # Extract region from registry URL
        REGION=$(echo "$ECR_REGISTRY" | cut -d'.' -f4)
        
        aws ecr get-login-password --region "$REGION" | \
            docker login --username AWS --password-stdin "$ECR_REGISTRY"
        
        log_success "ECR login successful"
        ;;
        
    push)
        if [ -z "$LOCAL_IMAGE" ]; then
            # Default to latest built image
            VERSION=$(get_version)
            LOCAL_IMAGE="quilt-mcp:$VERSION"
        fi
        
        log_info "Pushing $LOCAL_IMAGE to ECR..."
        
        # Check if local image exists, build if not
        if ! docker image inspect "$LOCAL_IMAGE" > /dev/null 2>&1; then
            log_warning "Local image $LOCAL_IMAGE not found"
            log_info "Building required Docker image..."
            # Extract tag from desired local image (e.g., quilt-mcp:<tag>)
            TAG_TO_BUILD=$(echo "$LOCAL_IMAGE" | cut -d':' -f2)
            "$PROJECT_ROOT/build-docker/build-docker.sh" build --tag "$TAG_TO_BUILD"
        fi
        
        # Extract tag from local image
        TAG=$(echo "$LOCAL_IMAGE" | cut -d':' -f2)
        ECR_URI="$ECR_REGISTRY/$ECR_REPOSITORY:$TAG"
        
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY-RUN] Would tag image: $LOCAL_IMAGE -> $ECR_URI"
            log_info "[DRY-RUN] Would push to ECR: $ECR_URI"
            log_success "Push completed (simulated): $ECR_URI"
            echo "$ECR_URI"  # Return the ECR URI for chaining
            exit 0
        fi
        
        # Login to ECR
        "$0" login
        
        # Tag for ECR
        log_info "Tagging image for ECR: $ECR_URI"
        docker tag "$LOCAL_IMAGE" "$ECR_URI"
        
        # Push to ECR (create repository if it doesn't exist)
        log_info "Pushing to ECR: $ECR_URI"
        if [ "$VERBOSE" = true ]; then
            if ! docker push "$ECR_URI" 2>/dev/null; then
                # Repository might not exist, try to create it
                log_info "Repository doesn't exist, creating ECR repository: $ECR_REPOSITORY"
                REGION=$(echo "$ECR_REGISTRY" | cut -d'.' -f4)
                aws ecr create-repository --repository-name "$ECR_REPOSITORY" --region "$REGION" > /dev/null || true
                # Try push again
                docker push "$ECR_URI"
            fi
        else
            if ! docker push "$ECR_URI" > /dev/null 2>&1; then
                # Repository might not exist, try to create it
                log_info "Repository doesn't exist, creating ECR repository: $ECR_REPOSITORY"
                REGION=$(echo "$ECR_REGISTRY" | cut -d'.' -f4)
                aws ecr create-repository --repository-name "$ECR_REPOSITORY" --region "$REGION" > /dev/null || true
                # Try push again
                docker push "$ECR_URI" > /dev/null
            fi
        fi
        
        log_success "Push completed: $ECR_URI"
        
        # Generate .config file after successful push
        "$SCRIPT_DIR/catalog-push.sh" config "$LOCAL_IMAGE"
        
        echo "$ECR_URI"  # Return the ECR URI for chaining
        ;;
        
    pull)
        if [ -z "$LOCAL_IMAGE" ]; then
            # Default to current version
            VERSION=$(get_version)
            TAG="$VERSION"
        else
            TAG=$(echo "$LOCAL_IMAGE" | cut -d':' -f2)
        fi
        
        ECR_URI="$ECR_REGISTRY/$ECR_REPOSITORY:$TAG"
        
        log_info "Pulling from ECR: $ECR_URI"
        
        # Login to ECR
        "$0" login
        
        # Pull from ECR
        if [ "$VERBOSE" = true ]; then
            docker pull "$ECR_URI"
        else
            docker pull "$ECR_URI" > /dev/null
        fi
        
        log_success "Pull completed: $ECR_URI"
        echo "$ECR_URI"  # Return the ECR URI
        ;;
        
    test)
        if [ -z "$LOCAL_IMAGE" ]; then
            VERSION=$(get_version)
            TAG="$VERSION"
        else
            TAG=$(echo "$LOCAL_IMAGE" | cut -d':' -f2)
        fi
        
        ECR_URI="$ECR_REGISTRY/$ECR_REPOSITORY:$TAG"
        
        log_info "Testing ECR image: $ECR_URI"
        
        # Pull the image first
        "$0" pull "$TAG"
        
        # Run container with health check
        log_info "Starting container for testing..."
        CONTAINER_ID=$(docker run -d -p 8002:8000 "$ECR_URI")
        
        # Wait for container to be ready
        log_info "Waiting for container to be ready..."
        sleep 10
        
        # Test if container is healthy by checking if it's running and port is open
        if docker exec "$CONTAINER_ID" curl -s http://localhost:8000/mcp > /dev/null 2>&1; then
            log_success "ECR image test passed"
        else
            log_warning "Basic curl check failed, trying container process check..."
            # Check if container is running and process is healthy
            if docker exec "$CONTAINER_ID" pgrep -f "python.*main.py" > /dev/null; then
                log_success "ECR image test passed (container running with MCP server process active)"
            else
                log_error "ECR image test failed"
                docker logs "$CONTAINER_ID"
                docker stop "$CONTAINER_ID" > /dev/null
                exit 1
            fi
        fi
        
        # Cleanup
        docker stop "$CONTAINER_ID" > /dev/null
        log_success "Test completed successfully"
        ;;
        
    validate)
        log_info "🔍 Phase 3: Catalog-Push validation (login + push + pull test)"
        log_info "Requirements: ECR login succeeds, image pushes, pull/run test passes"
        
        if [ -z "$LOCAL_IMAGE" ]; then
            VERSION=$(get_version)
            LOCAL_IMAGE="quilt-mcp:$VERSION"
        fi
        
        # ECR login test (real test - scripts auto-construct ECR_REGISTRY)
        "$0" login
        
        # Push image to ECR (real test - scripts auto-construct ECR_REGISTRY)
        "$0" push "$LOCAL_IMAGE"
        
        # ECR pull test (real test)
        "$0" test "$LOCAL_IMAGE"
        
        log_success "✅ Catalog-Push phase validation passed"
        ;;
        
    config)
        log_info "Generating .config file with ECR info..."
        
        if [ -z "$LOCAL_IMAGE" ]; then
            # Default to current version
            VERSION=$(get_version)
            LOCAL_IMAGE="quilt-mcp:$VERSION"
        fi
        
        # Extract tag from local image
        TAG=$(echo "$LOCAL_IMAGE" | cut -d':' -f2)
        ECR_URI="$ECR_REGISTRY/$ECR_REPOSITORY:$TAG"
        
        # Check if ECR image exists
        ECR_STATUS="❌ NOT PUSHED"
        ECR_IMAGE_DIGEST="unknown"
        ECR_IMAGE_SIZE="unknown"
        LAST_PUSHED="unknown"
        
        # Try to get image info from ECR
        REGION=$(echo "$ECR_REGISTRY" | cut -d'.' -f4)
        if aws ecr describe-images --repository-name "$ECR_REPOSITORY" --image-ids imageTag="$TAG" --region "$REGION" > /tmp/ecr_image_info.json 2>/dev/null; then
            ECR_STATUS="✅ PUSHED"
            ECR_IMAGE_DIGEST=$(jq -r '.imageDetails[0].imageDigest' /tmp/ecr_image_info.json 2>/dev/null || echo "unknown")
            ECR_IMAGE_SIZE=$(jq -r '.imageDetails[0].imageSizeInBytes' /tmp/ecr_image_info.json 2>/dev/null | numfmt --to=iec 2>/dev/null || echo "unknown")
            LAST_PUSHED=$(jq -r '.imageDetails[0].imagePushedAt' /tmp/ecr_image_info.json 2>/dev/null || echo "unknown")
        fi
        
        # Check if local image exists
        LOCAL_STATUS="❌ NOT BUILT"
        if docker image inspect "$LOCAL_IMAGE" > /dev/null 2>&1; then
            LOCAL_STATUS="✅ BUILT"
        fi
        
        # Create .config file
        cat > "$PROJECT_ROOT/.config" << EOF
# Quilt MCP Server - Phase 3 (Catalog-Push) Configuration
# Generated on $(date)

PHASE=catalog
PHASE_NAME="ECR Registry"
ENDPOINT="http://127.0.0.1:8002/mcp"
LOCAL_IMAGE="$LOCAL_IMAGE"
LOCAL_STATUS="$LOCAL_STATUS"
ECR_REGISTRY="$ECR_REGISTRY"
ECR_REPOSITORY="$ECR_REPOSITORY"
ECR_URI="$ECR_URI"
ECR_STATUS="$ECR_STATUS"
ECR_IMAGE_DIGEST="$ECR_IMAGE_DIGEST"
ECR_IMAGE_SIZE="$ECR_IMAGE_SIZE"
LAST_PUSHED="$LAST_PUSHED"
REGION="$REGION"
GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GIT_HASH="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
EOF
        
        log_success "✅ Phase 3 .config generated successfully"
        log_info "ECR URI: $ECR_URI"
        log_info "ECR Status: $ECR_STATUS"
        log_info "Local Status: $LOCAL_STATUS"
        log_info "Configuration saved to $PROJECT_ROOT/.config"
        ;;
        
    *)
        log_error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac
#!/bin/bash
# Pipeline orchestration - runs all phases in sequence
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load shared utilities
source "$SCRIPT_DIR/common.sh"
source "$SCRIPT_DIR/version.sh"

# Default values
VERBOSE=false
SKIP_TESTS=false
PHASE=""

usage() {
    echo "Usage: $0 [full|app|build-docker|catalog-push|deploy-aws] [options]"
    echo ""
    echo "Phases:"
    echo "  full     Run complete pipeline (app test -> build-docker -> catalog-push -> deploy-aws)"
    echo "  app      Run app phase only (local MCP server)"
    echo "  build-docker    Run build-docker phase only (Docker)"
    echo "  catalog-push  Run catalog-push phase only (ECR)"
    echo "  deploy-aws   Run deploy-aws phase only (ECS/ALB)"
    echo ""
    echo "Options:"
    echo "  -v, --verbose     Enable verbose output"
    echo "  --skip-tests      Skip running tests"
    echo ""
    echo "Environment Variables:"
    echo "  ECR_REGISTRY      ECR registry URL (required for catalog-push/deploy-aws)"
    echo "  ECR_REPOSITORY    ECR repository name (default: quilt-mcp)"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        full|app|build-docker|catalog-push|deploy-aws)
            PHASE="$1"
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

if [ -z "$PHASE" ]; then
    PHASE="full"
fi

# Set verbose flags for sub-commands
VERBOSE_FLAG=""
if [ "$VERBOSE" = true ]; then
    VERBOSE_FLAG="-v"
fi

TEST_FLAG=""
if [ "$SKIP_TESTS" = true ]; then
    TEST_FLAG="--skip-tests"
fi

VERSION=$(get_version)
IMAGE_TAG="quilt-mcp:$VERSION"

case $PHASE in
    app)
        log_info "=== Running App Phase ==="
        "$PROJECT_ROOT/src/app/app.sh" test
        ;;
        
    build-docker)
        log_info "=== Running Build Phase ==="
        IMAGE=$("$PROJECT_ROOT/src/build-docker/build-docker.sh" build $VERBOSE_FLAG --tag "$VERSION")
        
        if [ "$SKIP_TESTS" != true ]; then
            "$PROJECT_ROOT/src/build-docker/build-docker.sh" test $VERBOSE_FLAG --tag "$VERSION"
        fi
        
        log_success "Build phase completed: $IMAGE"
        ;;
        
    catalog-push)
        log_info "=== Running Catalog Phase ==="
        
        if [ -z "$ECR_REGISTRY" ]; then
            log_error "ECR_REGISTRY environment variable required for catalog-push phase"
            log_info "Example: export ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com"
            exit 1
        fi
        
        # Ensure image is built
        if ! docker image inspect "$IMAGE_TAG" > /dev/null 2>&1; then
            log_info "Image not found locally, build-dockering first..."
            "$0" build-docker $VERBOSE_FLAG
        fi
        
        ECR_URI=$("$PROJECT_ROOT/src/catalog-push/catalog-push.sh" push $VERBOSE_FLAG "$IMAGE_TAG")
        
        if [ "$SKIP_TESTS" != true ]; then
            "$PROJECT_ROOT/src/catalog-push/catalog-push.sh" test $VERBOSE_FLAG "$VERSION"
        fi
        
        log_success "Catalog phase completed: $ECR_URI"
        ;;
        
    deploy-aws)
        log_info "=== Running Deploy Phase ==="
        
        if [ -z "$ECR_REGISTRY" ]; then
            log_error "ECR_REGISTRY environment variable required for deploy-aws phase"
            exit 1
        fi
        
        ECR_REPOSITORY=${ECR_REPOSITORY:-quilt-mcp}
    ECR_URI="$ECR_REGISTRY/$ECR_REPOSITORY:$VERSION"
        
    "$PROJECT_ROOT/src/deploy-aws/deploy-aws.sh" deploy $VERBOSE_FLAG $TEST_FLAG "$ECR_URI"
        
        if [ "$SKIP_TESTS" != true ]; then
            "$PROJECT_ROOT/src/deploy-aws/deploy-aws.sh" test $VERBOSE_FLAG
        fi
        
        log_success "Deploy phase completed"
        ;;
        
    full)
        log_info "=== Running Full Pipeline ==="
        log_info "Version: $VERSION"
        
        # Phase 1: App (test only)
        if [ "$SKIP_TESTS" != true ]; then
            "$0" app $VERBOSE_FLAG
        fi
        
        # Phase 2: Build
        "$0" build-docker $VERBOSE_FLAG $TEST_FLAG
        
        # Phase 3: Catalog
        "$0" catalog-push $VERBOSE_FLAG $TEST_FLAG
        
        # Phase 4: Deploy
        "$0" deploy-aws $VERBOSE_FLAG $TEST_FLAG
        
        log_success "=== Full Pipeline Completed ==="
        log_info "Version deploy-awsed: $VERSION"
        
        # Show final status
        if [ -f "$PROJECT_ROOT/.config" ]; then
            set -a && source "$PROJECT_ROOT/.config" && set +a
            log_info "MCP Endpoint: $MCP_ENDPOINT"
        fi
        ;;
        
    *)
        log_error "Unknown phase: $PHASE"
        usage
        exit 1
        ;;
esac
#!/bin/bash
# Shared validation orchestration script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load shared utilities
source "$SCRIPT_DIR/common.sh"
source "$SCRIPT_DIR/version.sh"

# Load environment variables from .env if present
load_environment

# Default values
VERBOSE=false
PHASE=""

usage() {
    echo "Usage: $0 [all|app|build|catalog|deploy] [options]"
    echo ""
    echo "Validation Phases:"
    echo "  all      Run all phase validations in sequence"
    echo "  app      Validate Phase 1 (App) only"
    echo "  build    Validate Phase 2 (Build-Docker) only"  
    echo "  catalog  Validate Phase 3 (Catalog-Push) only"
    echo "  deploy   Validate Phase 4 (Deploy-AWS) only"
    echo ""
    echo "Options:"
    echo "  -v, --verbose    Enable verbose output"
    echo ""
    echo "Environment Variables:"
    echo "  ECR_REGISTRY     ECR registry URL (required for catalog/deploy phases)"
    echo "  ECR_REPOSITORY   ECR repository name (default: quilt-mcp)"
    echo "  ACM_CERT_ARN     ACM certificate ARN (optional, tests HTTPS in deploy)"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        all|app|build|catalog|deploy)
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
    PHASE="all"
fi

# Set verbose flags for sub-commands
VERBOSE_FLAG=""
if [ "$VERBOSE" = true ]; then
    VERBOSE_FLAG="-v"
fi

log_info "🔍 Starting validation for phase: $PHASE"

case $PHASE in
    app)
        log_info "=== Validating Phase 1: App ==="
        "$PROJECT_ROOT/src/app/app.sh" validate
        ;;
        
    build)
        log_info "=== Validating Phase 2: Build-Docker ==="
        VERSION=$(get_version)
        "$PROJECT_ROOT/src/build-docker/build-docker.sh" validate --tag "$VERSION"
        ;;
        
    catalog)
        log_info "=== Validating Phase 3: Catalog-Push ==="
        
        # Check ECR_REGISTRY
        if ! setup_ecr_registry; then
            log_error "ECR_REGISTRY required for catalog validation"
            log_info "Example: export ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com"
            exit 1
        fi
        
        VERSION=$(get_version)
        LOCAL_IMAGE="quilt-mcp:$VERSION"
        
        # Ensure image is built first
        if ! docker image inspect "$LOCAL_IMAGE" > /dev/null 2>&1; then
            log_info "Image not found locally, building first..."
            "$PROJECT_ROOT/src/build-docker/build-docker.sh" build --tag "$VERSION"
        fi
        
        "$PROJECT_ROOT/src/catalog-push/catalog-push.sh" validate "$LOCAL_IMAGE"
        ;;
        
    deploy)
        log_info "=== Validating Phase 4: Deploy-AWS ==="
        
        # Check ECR_REGISTRY
        if ! setup_ecr_registry; then
            log_error "ECR_REGISTRY required for deploy validation"
            exit 1
        fi
        
        VERSION=$(get_version)
        ECR_REPOSITORY=${ECR_REPOSITORY:-quilt-mcp}
        ECR_URI="$ECR_REGISTRY/$ECR_REPOSITORY:$VERSION"
        
        "$PROJECT_ROOT/src/deploy-aws/deploy-aws.sh" validate "$ECR_URI"
        ;;
        
    all)
        log_info "=== Running Full Validation Pipeline ==="
        VERSION=$(get_version)
        log_info "Version: $VERSION"
        
        # Phase 1: App
        log_info ""
        log_info "🔄 Phase 1: App validation"
        "$0" app $VERBOSE_FLAG
        
        # Phase 2: Build
        log_info ""
        log_info "🔄 Phase 2: Build-Docker validation"
        "$0" build $VERBOSE_FLAG
        
        # Phase 3: Catalog (only if ECR_REGISTRY is available)
        log_info ""
        log_info "🔄 Phase 3: Catalog-Push validation"
        if setup_ecr_registry 2>/dev/null; then
            "$0" catalog $VERBOSE_FLAG
        else
            log_warning "Skipping Catalog-Push validation (ECR_REGISTRY not configured)"
            log_info "To enable: export ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com"
        fi
        
        # Phase 4: Deploy (only if ECR_REGISTRY is available)
        log_info ""
        log_info "🔄 Phase 4: Deploy-AWS validation"
        if setup_ecr_registry 2>/dev/null; then
            "$0" deploy $VERBOSE_FLAG
        else
            log_warning "Skipping Deploy-AWS validation (ECR_REGISTRY not configured)"
        fi
        
        log_info ""
        log_success "=== ✅ Full Validation Pipeline Completed ==="
        log_info "Version validated: $VERSION"
        ;;
        
    *)
        log_error "Unknown phase: $PHASE"
        usage
        exit 1
        ;;
esac

log_success "✅ Validation completed for phase: $PHASE"
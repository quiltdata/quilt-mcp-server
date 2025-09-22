#!/bin/bash
# Docker build and deployment script for Quilt MCP Server
# Extracts Docker operations from GitHub Actions workflows for reusability

set -euo pipefail

# Script configuration
SCRIPT_NAME="$(basename "$0")"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Default values
DEFAULT_IMAGE_NAME="quilt-mcp-server"
DEFAULT_REGION="us-east-1"

# Help function
show_help() {
    cat << EOF
Usage: $SCRIPT_NAME [COMMAND] [OPTIONS]

Docker build and deployment operations for Quilt MCP Server.

COMMANDS:
    build           Build Docker image locally
    push            Build and push Docker image to ECR
    help            Show this help message

OPTIONS:
    --version VERSION       Version tag for the image (required for push)
    --registry REGISTRY     ECR registry URL (optional, auto-detected if not provided)
    --image-name NAME       Docker image name (default: $DEFAULT_IMAGE_NAME)
    --region REGION         AWS region (default: $DEFAULT_REGION)
    --dry-run              Show what would be done without executing
    --no-latest            Don't tag as 'latest' (only for push command)

ENVIRONMENT VARIABLES:
    ECR_REGISTRY           ECR registry URL (overrides --registry)
    AWS_ACCOUNT_ID         AWS account ID (used to construct registry if ECR_REGISTRY not set)
    AWS_DEFAULT_REGION     AWS region (overrides --region)
    VERSION               Version tag (overrides --version)

EXAMPLES:
    # Build locally for testing
    $SCRIPT_NAME build

    # Build and push to ECR with version
    $SCRIPT_NAME push --version 1.2.3

    # Dry run to see what would happen
    $SCRIPT_NAME push --version 1.2.3 --dry-run

EOF
}

# Error handling
error() {
    echo "ERROR: $*" >&2
    exit 1
}

# Info logging
info() {
    echo "INFO: $*" >&2
}

# Debug logging
debug() {
    if [[ "${DEBUG:-}" == "1" ]]; then
        echo "DEBUG: $*" >&2
    fi
}

# Validate Docker is available
check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        error "Docker is not installed or not in PATH"
    fi

    if ! docker info >/dev/null 2>&1; then
        error "Docker daemon is not running or not accessible"
    fi
}

# Validate required tools for push operations
check_push_tools() {
    if ! command -v uv >/dev/null 2>&1; then
        error "uv is required for image tag generation (install: curl -LsSf https://astral.sh/uv/install.sh | sh)"
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        error "python3 is required for image tag generation"
    fi

    if [[ ! -f "$PROJECT_ROOT/scripts/docker_image.py" ]]; then
        error "docker_image.py script not found at $PROJECT_ROOT/scripts/docker_image.py"
    fi
}

# Determine ECR registry URL
get_registry() {
    local registry="${ECR_REGISTRY:-${1:-}}"
    local aws_account_id="${AWS_ACCOUNT_ID:-}"
    local aws_region="${AWS_DEFAULT_REGION:-${2:-$DEFAULT_REGION}}"

    if [[ -n "$registry" ]]; then
        echo "$registry"
        return 0
    fi

    if [[ -z "$aws_account_id" ]]; then
        error "ECR registry not configured. Set ECR_REGISTRY or AWS_ACCOUNT_ID environment variable"
    fi

    echo "${aws_account_id}.dkr.ecr.${aws_region}.amazonaws.com"
}

# Generate Docker image tags using docker_image.py
generate_image_tags() {
    local registry="$1"
    local version="$2"
    local image_name="${3:-$DEFAULT_IMAGE_NAME}"

    debug "Generating tags for registry=$registry, version=$version, image=$image_name"

    cd "$PROJECT_ROOT"
    uv run python scripts/docker_image.py --registry "$registry" --version "$version" --image "$image_name"
}

# Build Docker image
docker_build() {
    local image_tag="$1"

    info "Building Docker image: $image_tag"

    if [[ "${DRY_RUN:-}" == "1" ]]; then
        info "DRY RUN: Would execute: docker build --file Dockerfile --tag '$image_tag' ."
        return 0
    fi

    cd "$PROJECT_ROOT"
    docker build --file Dockerfile --tag "$image_tag" .

    info "Successfully built: $image_tag"
}

# Tag Docker image with additional tags
docker_tag() {
    local source_tag="$1"
    local target_tag="$2"

    info "Tagging image: $source_tag -> $target_tag"

    if [[ "${DRY_RUN:-}" == "1" ]]; then
        info "DRY RUN: Would execute: docker tag '$source_tag' '$target_tag'"
        return 0
    fi

    docker tag "$source_tag" "$target_tag"
}

# Push Docker image to registry
docker_push() {
    local image_tag="$1"

    info "Pushing image: $image_tag"

    if [[ "${DRY_RUN:-}" == "1" ]]; then
        info "DRY RUN: Would execute: docker push '$image_tag'"
        return 0
    fi

    docker push "$image_tag"

    info "Successfully pushed: $image_tag"
}

# Build command implementation
cmd_build() {
    local image_name="${IMAGE_NAME:-$DEFAULT_IMAGE_NAME}"
    local version="${VERSION:-dev}"
    local registry="${REGISTRY:-localhost:5000}"

    check_docker

    # For local builds, use simple tagging
    local image_tag="${registry}/${image_name}:${version}"

    info "Building Docker image locally"
    docker_build "$image_tag"

    info "Local build completed: $image_tag"
}

# Push command implementation
cmd_push() {
    local version="${VERSION:-}"
    local registry="${REGISTRY:-}"
    local image_name="${IMAGE_NAME:-$DEFAULT_IMAGE_NAME}"
    local region="${REGION:-$DEFAULT_REGION}"
    local no_latest="${NO_LATEST:-}"

    if [[ -z "$version" ]]; then
        error "Version is required for push command. Use --version or set VERSION environment variable"
    fi

    check_docker
    check_push_tools

    # Determine registry
    registry=$(get_registry "$registry" "$region")
    info "Using registry: $registry"

    # Generate all image tags
    info "Generating image tags for version: $version"
    local image_tags
    image_tags=$(generate_image_tags "$registry" "$version" "$image_name")

    if [[ -z "$image_tags" ]]; then
        error "Failed to generate image tags"
    fi

    # Convert to array for processing
    local tags_array=()
    while IFS= read -r line; do
        [[ -n "$line" ]] && tags_array+=("$line")
    done <<< "$image_tags"

    if [[ ${#tags_array[@]} -eq 0 ]]; then
        error "No image tags generated"
    fi

    # Filter out latest tag if --no-latest specified
    if [[ "$no_latest" == "1" ]]; then
        local filtered_tags=()
        for tag in "${tags_array[@]}"; do
            if [[ ! "$tag" =~ :latest$ ]]; then
                filtered_tags+=("$tag")
            fi
        done
        tags_array=("${filtered_tags[@]}")
    fi

    info "Generated ${#tags_array[@]} image tags:"
    for tag in "${tags_array[@]}"; do
        info "  - $tag"
    done

    # Build with first tag
    local primary_tag="${tags_array[0]}"
    docker_build "$primary_tag"

    # Tag with additional tags
    for tag in "${tags_array[@]:1}"; do
        docker_tag "$primary_tag" "$tag"
    done

    # Push all tags
    for tag in "${tags_array[@]}"; do
        docker_push "$tag"
    done

    info "Docker push completed successfully"
    info "Pushed ${#tags_array[@]} tags to registry: $registry"
}

# Parse command line arguments
parse_args() {
    COMMAND=""
    VERSION=""
    REGISTRY=""
    IMAGE_NAME=""
    REGION=""
    DRY_RUN=""
    NO_LATEST=""

    while [[ $# -gt 0 ]]; do
        case $1 in
            build|push|help)
                COMMAND="$1"
                shift
                ;;
            --version)
                VERSION="$2"
                shift 2
                ;;
            --registry)
                REGISTRY="$2"
                shift 2
                ;;
            --image-name)
                IMAGE_NAME="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN="1"
                shift
                ;;
            --no-latest)
                NO_LATEST="1"
                shift
                ;;
            -h|--help)
                COMMAND="help"
                shift
                ;;
            *)
                error "Unknown option: $1. Use --help for usage information."
                ;;
        esac
    done

    # Apply environment variable defaults
    VERSION="${VERSION:-${VERSION_ENV:-}}"
    REGISTRY="${REGISTRY:-${ECR_REGISTRY:-}}"
    IMAGE_NAME="${IMAGE_NAME:-$DEFAULT_IMAGE_NAME}"
    REGION="${REGION:-${AWS_DEFAULT_REGION:-$DEFAULT_REGION}}"

    # Validate command
    if [[ -z "$COMMAND" ]]; then
        error "Command is required. Use --help for usage information."
    fi
}

# Main function
main() {
    parse_args "$@"

    case "$COMMAND" in
        build)
            cmd_build
            ;;
        push)
            cmd_push
            ;;
        help)
            show_help
            ;;
        *)
            error "Unknown command: $COMMAND"
            ;;
    esac
}

# Only run main if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
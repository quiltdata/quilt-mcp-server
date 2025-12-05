#!/bin/bash
# Development environment validation script
# Checks .env configuration and AWS setup for development
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load shared utilities
source "$SCRIPT_DIR/common.sh"

log_info "🔍 Checking development environment configuration..."

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    log_error "⚠️  No .env file found. Copy env.example to .env and configure."
    exit 1
fi

log_success "✅ .env file exists"

# Load environment variables
set -a
source "$PROJECT_ROOT/.env"
set +a

# Display environment summary
log_info "📋 Development Environment Summary:"
echo "  AWS Account: ${CDK_DEFAULT_ACCOUNT:-${AWS_ACCOUNT_ID:-Not set}}"
echo "  AWS Region: ${CDK_DEFAULT_REGION:-${AWS_DEFAULT_REGION:-Not set}}"
echo "  ECR Registry: ${ECR_REGISTRY:-Will be auto-derived}"
echo "  Quilt Test Bucket: ${QUILT_TEST_BUCKET:-Not set}"
echo "  Catalog Domain: ${QUILT_CATALOG_DOMAIN:-Not set}"
echo "  ngrok Domain: ${NGROK_DOMAIN:-Auto-assigned (optional)}"
echo ""

# Validate required environment variables
log_info "🔍 Validating required development environment variables..."

if [ -z "${CDK_DEFAULT_ACCOUNT}" ] && [ -z "${AWS_ACCOUNT_ID}" ]; then
    log_error "❌ Missing CDK_DEFAULT_ACCOUNT or AWS_ACCOUNT_ID"
    exit 1
fi

if [ -z "${CDK_DEFAULT_REGION}" ] && [ -z "${AWS_DEFAULT_REGION}" ]; then
    log_error "❌ Missing CDK_DEFAULT_REGION or AWS_DEFAULT_REGION"
    exit 1
fi

if [ -z "${QUILT_TEST_BUCKET}" ]; then
    log_error "❌ Missing QUILT_TEST_BUCKET"
    exit 1
fi

if [ -z "${QUILT_CATALOG_DOMAIN}" ]; then
    log_error "❌ Missing QUILT_CATALOG_DOMAIN"
    exit 1
fi

log_success "✅ Development environment validation complete"
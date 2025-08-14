#!/bin/bash
# View logs for the Quilt MCP Server deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default values
FOLLOW=false
SINCE="10m"
LOG_TYPE="app"

usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "View logs for Quilt MCP Server deployment"
    echo ""
    echo "Options:"
    echo "  -f, --follow         Follow logs in real-time"
    echo "  -s, --since TIME     Show logs since TIME (default: 10m)"
    echo "  -t, --type TYPE      Log type: app|alb|vpc|all (default: app)"
    echo "  -h, --help           Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                   # View recent app logs"
    echo "  $0 -f                # Follow app logs"
    echo "  $0 -t all -s 1h      # View all logs from last hour"
    echo "  $0 -t alb -f         # Follow ALB logs"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -s|--since)
            SINCE="$2"
            shift 2
            ;;
        -t|--type)
            LOG_TYPE="$2"
            shift 2
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

# Check dependencies
check_dependencies aws

# Load configuration
load_config

# Build AWS logs command
AWS_LOGS_CMD="aws logs tail --region $REGION --since $SINCE"
if [ "$FOLLOW" = true ]; then
    AWS_LOGS_CMD="$AWS_LOGS_CMD --follow"
fi

# Show logs based on type
case $LOG_TYPE in
    app)
        log_info "📋 Application Logs (ECS Container)"
        log_info "Log Group: $APP_LOG_GROUP"
        $AWS_LOGS_CMD "$APP_LOG_GROUP"
        ;;
    alb)
        log_info "🌐 Load Balancer Logs"
        log_info "Log Group: $ALB_LOG_GROUP"
        $AWS_LOGS_CMD "$ALB_LOG_GROUP"
        ;;
    vpc)
        log_info "🔗 VPC Flow Logs"
        log_info "Log Group: $VPC_LOG_GROUP"
        $AWS_LOGS_CMD "$VPC_LOG_GROUP"
        ;;
    all)
        log_info "📋 All Logs for $STACK_NAME"
        echo ""
        log_info "=== Application Logs ==="
        $AWS_LOGS_CMD "$APP_LOG_GROUP" | head -20
        echo ""
        log_info "=== Load Balancer Logs ==="
        $AWS_LOGS_CMD "$ALB_LOG_GROUP" | head -10
        echo ""
        log_info "=== VPC Flow Logs ==="
        $AWS_LOGS_CMD "$VPC_LOG_GROUP" | head -10
        ;;
    *)
        log_error "Invalid log type: $LOG_TYPE"
        log_error "Valid types: app, alb, vpc, all"
        exit 1
        ;;
esac
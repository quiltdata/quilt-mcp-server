#!/bin/bash
set -e

# Load common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default values
FOLLOW=false
VERBOSE=false
SINCE="5m"
LAMBDA_ONLY=false
API_ONLY=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -s|--since)
            SINCE="$2"
            shift 2
            ;;
        -l|--lambda-only)
            LAMBDA_ONLY=true
            shift
            ;;
        -a|--api-only)
            API_ONLY=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "View AWS logs for the deployed MCP server"
            echo ""
            echo "Options:"
            echo "  -f, --follow       Follow log output (like tail -f)"
            echo "  -v, --verbose      Show verbose output with configuration"
            echo "  -s, --since TIME   Show logs since TIME (default: 5m)"
            echo "  -l, --lambda-only  Show only Lambda function logs"
            echo "  -a, --api-only     Show only API Gateway access logs"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                 # View recent logs from both Lambda and API Gateway"
            echo "  $0 -f              # Follow logs in real-time"
            echo "  $0 -s 1h           # Show logs from last hour"
            echo "  $0 -l -f           # Follow only Lambda logs"
            echo "  $0 -a -v -s 10m    # API Gateway logs with verbose output from last 10 minutes"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Load environment variables
if [ -f ".env" ]; then
    if [ "$VERBOSE" = true ]; then
        log_info "Loading environment from .env"
    fi
    set -a && source .env && set +a
fi

# Load configuration
load_config

# Validate required variables
if [ -z "$LOG_GROUP_NAME" ] || [ -z "$REGION" ]; then
    log_error "❌ Required configuration missing. Run ./deploy.sh to regenerate .config"
    exit 1
fi

log_info "🔍 Checking logs for Quilt MCP Server"
log_info "Region: ${REGION}"
log_info "Since: ${SINCE}"

# Build log command options
LOG_OPTS="--region $REGION --since $SINCE"
if [ "$FOLLOW" = true ]; then
    LOG_OPTS="$LOG_OPTS --follow"
fi

# Function to show Lambda logs
show_lambda_logs() {
    log_success "📋 Lambda Function Logs (${LAMBDA_FUNCTION_NAME}):"
    log_info "Log Group: ${LOG_GROUP_NAME}"
    
    if [ "$VERBOSE" = true ]; then
        log_info "Command: aws logs tail ${LOG_GROUP_NAME} ${LOG_OPTS}"
    fi
    
    aws logs tail "$LOG_GROUP_NAME" $LOG_OPTS || {
        log_error "❌ Failed to retrieve Lambda logs"
        log_warning "💡 Check if the log group exists and you have permissions"
        return 1
    }
}

# Function to show API Gateway logs (if they exist)
show_api_logs() {
    if [ -n "$API_LOG_GROUP_NAME" ]; then
        log_success "🌐 API Gateway Logs:"
        log_info "Log Group: ${API_LOG_GROUP_NAME}"
        
        if [ "$VERBOSE" = true ]; then
            log_info "Command: aws logs tail ${API_LOG_GROUP_NAME} ${LOG_OPTS}"
        fi
        
        aws logs tail "$API_LOG_GROUP_NAME" $LOG_OPTS || {
            log_warning "⚠️  Could not retrieve logs from ${API_LOG_GROUP_NAME}"
            log_info "💡 API Gateway logs may not be enabled yet or log group may not exist"
        }
    else
        log_warning "⚠️  No API Gateway log group configured"
        log_info "💡 Deploy with the latest CDK configuration to enable API Gateway logging"
    fi
}

# Function to show recent deployment events
show_recent_events() {
    if [ "$VERBOSE" = true ]; then
        log_success "📊 Recent CloudFormation Events:"
        aws cloudformation describe-stack-events --stack-name "$STACK_NAME" --region "$REGION" --max-items 10 --query "StackEvents[?Timestamp > \`$(date -u -d "$SINCE ago" +%Y-%m-%dT%H:%M:%S.%3NZ)\`].[Timestamp,LogicalResourceId,ResourceStatusReason]" --output table 2>/dev/null || {
            log_warning "⚠️  Could not retrieve stack events"
        }
        echo ""
    fi
}

# Function to show configuration summary
show_config() {
    if [ "$VERBOSE" = true ]; then
        log_success "⚙️  Current Configuration:"
        log_info "  Stack Name: ${STACK_NAME}"
        log_info "  Region: ${REGION}"
        log_info "  API Endpoint: ${API_ENDPOINT}"
        log_info "  Lambda Function: ${LAMBDA_FUNCTION_NAME}"
        log_info "  Lambda Log Group: ${LOG_GROUP_NAME}"
        if [ -n "$API_LOG_GROUP_NAME" ]; then
            log_info "  API Gateway Log Group: ${API_LOG_GROUP_NAME}"
        else
            log_info "  API Gateway Log Group: Not configured"
        fi
        echo ""
    fi
}

# Main execution
show_config
show_recent_events

if [ "$API_ONLY" = true ]; then
    show_api_logs
elif [ "$LAMBDA_ONLY" = true ]; then
    show_lambda_logs
else
    # Show both by default
    show_lambda_logs
    echo ""
    show_api_logs
fi

echo ""
log_success "📝 Log viewing complete!"

if [ "$FOLLOW" = false ]; then
    log_info "💡 Use -f flag to follow logs in real-time"
    log_info "💡 Use -s 1h to see logs from the last hour"
fi
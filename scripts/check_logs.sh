#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
            echo "  -v, --verbose      Show verbose output"
            echo "  -s, --since TIME   Show logs since TIME (default: 5m)"
            echo "  -l, --lambda-only  Show only Lambda logs"
            echo "  -a, --api-only     Show only API Gateway logs"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                 # View recent logs"
            echo "  $0 -f              # Follow logs in real-time"
            echo "  $0 -s 1h           # Show logs from last hour"
            echo "  $0 -l -f           # Follow only Lambda logs"
            echo "  $0 -v -s 10m       # Verbose logs from last 10 minutes"
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
        echo -e "${BLUE}Loading environment from .env${NC}"
    fi
    set -a && source .env && set +a
fi

# Load configuration
if [ ! -f ".config" ]; then
    echo -e "${RED}❌ .config file not found. Run ./deploy.sh first${NC}"
    exit 1
fi

if [ "$VERBOSE" = true ]; then
    echo -e "${BLUE}Loading configuration from .config${NC}"
fi
set -a && source .config && set +a

# Validate required variables
if [ -z "$LOG_GROUP_NAME" ] || [ -z "$REGION" ]; then
    echo -e "${RED}❌ Required configuration missing. Run ./deploy.sh to regenerate .config${NC}"
    exit 1
fi

echo -e "${BLUE}🔍 Checking logs for Quilt MCP Server${NC}"
echo -e "${BLUE}Region: ${REGION}${NC}"
echo -e "${BLUE}Since: ${SINCE}${NC}"

# Build log command options
LOG_OPTS="--region $REGION --since $SINCE"
if [ "$FOLLOW" = true ]; then
    LOG_OPTS="$LOG_OPTS --follow"
fi

# Function to show Lambda logs
show_lambda_logs() {
    echo -e "${GREEN}📋 Lambda Function Logs (${LAMBDA_FUNCTION_NAME}):${NC}"
    echo -e "${BLUE}Log Group: ${LOG_GROUP_NAME}${NC}"
    
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Command: aws logs tail ${LOG_GROUP_NAME} ${LOG_OPTS}${NC}"
    fi
    
    aws logs tail "$LOG_GROUP_NAME" $LOG_OPTS || {
        echo -e "${RED}❌ Failed to retrieve Lambda logs${NC}"
        echo -e "${YELLOW}💡 Check if the log group exists and you have permissions${NC}"
        return 1
    }
}

# Function to show API Gateway logs (if they exist)
show_api_logs() {
    # Try to find API Gateway log groups
    API_LOG_GROUPS=$(aws logs describe-log-groups --region "$REGION" --log-group-name-prefix "/aws/apigateway" --query "logGroups[?contains(logGroupName, 'quilt') || contains(logGroupName, 'mcp')].logGroupName" --output text 2>/dev/null || echo "")
    
    if [ -n "$API_LOG_GROUPS" ]; then
        echo -e "${GREEN}🌐 API Gateway Logs:${NC}"
        for log_group in $API_LOG_GROUPS; do
            echo -e "${BLUE}Log Group: ${log_group}${NC}"
            if [ "$VERBOSE" = true ]; then
                echo -e "${BLUE}Command: aws logs tail ${log_group} ${LOG_OPTS}${NC}"
            fi
            aws logs tail "$log_group" $LOG_OPTS || {
                echo -e "${YELLOW}⚠️  Could not retrieve logs from ${log_group}${NC}"
            }
        done
    else
        echo -e "${YELLOW}⚠️  No API Gateway logs found${NC}"
        echo -e "${BLUE}💡 API Gateway logs may not be enabled or may not exist yet${NC}"
    fi
}

# Function to show recent deployment events
show_recent_events() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${GREEN}📊 Recent CloudFormation Events:${NC}"
        aws cloudformation describe-stack-events --stack-name "$STACK_NAME" --region "$REGION" --max-items 10 --query "StackEvents[?Timestamp > \`$(date -u -d "$SINCE ago" +%Y-%m-%dT%H:%M:%S.%3NZ)\`].[Timestamp,LogicalResourceId,ResourceStatusReason]" --output table 2>/dev/null || {
            echo -e "${YELLOW}⚠️  Could not retrieve stack events${NC}"
        }
        echo ""
    fi
}

# Function to show configuration summary
show_config() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${GREEN}⚙️  Current Configuration:${NC}"
        echo -e "${BLUE}  Stack Name: ${STACK_NAME}${NC}"
        echo -e "${BLUE}  Region: ${REGION}${NC}"
        echo -e "${BLUE}  API Endpoint: ${API_ENDPOINT}${NC}"
        echo -e "${BLUE}  Lambda Function: ${LAMBDA_FUNCTION_NAME}${NC}"
        echo -e "${BLUE}  Log Group: ${LOG_GROUP_NAME}${NC}"
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
echo -e "${GREEN}📝 Log viewing complete!${NC}"

if [ "$FOLLOW" = false ]; then
    echo -e "${BLUE}💡 Use -f flag to follow logs in real-time${NC}"
    echo -e "${BLUE}💡 Use -s 1h to see logs from the last hour${NC}"
fi
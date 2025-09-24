# MCP Server Infrastructure Documentation

## Overview

The Quilt MCP Server is deployed as a containerized service on AWS ECS Fargate within the existing `sales-prod` infrastructure stack. This document provides comprehensive documentation of the infrastructure components, networking, and deployment architecture.

## Infrastructure Components

### 1. ECS Fargate Service

**Service Details:**
- **Cluster**: `sales-prod`
- **Service Name**: `sales-prod-mcp-server-production`
- **Task Definition**: `quilt-mcp-server`
- **Launch Type**: Fargate
- **Platform Version**: LATEST
- **Desired Count**: 1 (configurable via Terraform)

**Resource Allocation:**
- **CPU**: 256 units (0.25 vCPU)
- **Memory**: 512 MiB
- **Network Mode**: `awsvpc`
- **Public IP Assignment**: Disabled (private subnets only)

### 2. ECR Repository

**Repository Configuration:**
- **Registry**: `850787717197.dkr.ecr.us-east-1.amazonaws.com`
- **Repository Name**: `quilt-mcp-server`
- **Region**: `us-east-1`
- **Image Tags**: Versioned releases (e.g., `improved-error-handling`, `jwt-auth-v1.0.0`)

**Docker Image Specifications:**
- **Base Image**: `ghcr.io/astral-sh/uv:python3.11-bookworm-slim`
- **Platform**: `linux/amd64` (ECS Fargate compatibility)
- **Port**: 8000 (HTTP)
- **Health Check**: `/healthz` endpoint

### 3. Application Load Balancer (ALB) Integration

**Listener Configuration:**
- **Host Header**: `demo.quiltdata.com`
- **Path Pattern**: `/mcp/*`
- **Protocol**: HTTPS (TLS termination at ALB)
- **Listener Priority**: Configurable (typically 100+)

**Target Group:**
- **Name**: `sales-prod-mcp-server-tg` (truncated to 32 chars)
- **Protocol**: HTTP
- **Port**: 8000
- **Target Type**: IP
- **Health Check Path**: `/healthz`
- **Health Check Protocol**: HTTP
- **Healthy Threshold**: 2
- **Unhealthy Threshold**: 3
- **Interval**: 30 seconds
- **Timeout**: 6 seconds
- **Deregistration Delay**: 30 seconds

### 4. Security Groups

**MCP Service Security Group:**
- **Name**: `sales-prod-mcp-server-*` (with unique suffix)
- **VPC**: Same as sales-prod stack
- **Inbound Rules**:
  - Port 8000 from ALB security groups
- **Outbound Rules**:
  - All traffic (0.0.0.0/0)

**ALB Security Group Integration:**
- Allows traffic from ALB security groups to MCP service
- Inherits existing ALB security group configurations

### 5. IAM Roles and Policies

**ECS Task Role:**
- **Role Name**: `ecsTaskRole`
- **ARN**: `arn:aws:iam::850787717197:role/ecsTaskRole`
- **Permissions**: Quilt-specific AWS resource access (S3, Athena, etc.)

**ECS Execution Role:**
- **Role Name**: `ecsTaskExecutionRole`
- **ARN**: `arn:aws:iam::850787717197:role/ecsTaskExecutionRole`
- **Permissions**: ECR image pull, CloudWatch logs write

### 6. Networking

**VPC Configuration:**
- **VPC ID**: Inherited from sales-prod stack
- **CIDR Block**: `10.0.0.0/16` (default)
- **Subnets**: Private subnets only (no public IP assignment)

**Subnet Placement:**
- **Subnet Type**: Private subnets
- **AZ Distribution**: Multi-AZ for high availability
- **Network ACLs**: Inherit existing sales-prod NACL rules

### 7. CloudWatch Logging

**Log Group:**
- **Name**: `/ecs/mcp-server-production`
- **Region**: `us-east-1`
- **Retention**: 30 days (configurable)
- **Stream Prefix**: `ecs`

**Log Configuration:**
- **Driver**: `awslogs`
- **Format**: Structured JSON logs
- **Log Level**: INFO (configurable via environment variables)

## Environment Configuration

### Container Environment Variables

```bash
# AWS Configuration
AWS_DEFAULT_REGION=us-east-1
AWS_REGION=us-east-1

# Quilt Configuration
QUILT_CATALOG_URL=https://demo.quiltdata.com
QUILT_REGISTRY_URL=https://demo.quiltdata.com

# MCP Server Configuration
MCP_SERVER_NAME=quilt-mcp-server
MCP_SERVER_VERSION=0.6.13-jwt-auth
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1

# FastMCP Transport Configuration
FASTMCP_TRANSPORT=streamable-http
FASTMCP_ADDR=0.0.0.0
FASTMCP_PORT=8000

# JWT Authentication
MCP_ENHANCED_JWT_SECRET=development-enhanced-jwt-secret
MCP_ENHANCED_JWT_KID=frontend-enhanced
```

### Health Check Configuration

**Container Health Check:**
```bash
command: ["CMD-SHELL", "python3 -c \"import urllib.request, urllib.error; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).read()\" || exit 1"]
interval: 30
timeout: 5
retries: 3
startPeriod: 60
```

## Deployment Architecture

### Terraform Module Structure

```
deploy/terraform/
├── mcp-server.tf              # Main module instantiation
├── variables.tf               # Input variables
└── modules/
    └── mcp_server/
        ├── main.tf            # Resource definitions
        ├── variables.tf       # Module variables
        └── outputs.tf         # Module outputs
```

### Key Terraform Resources

1. **ECS Task Definition**: Container specification with environment variables
2. **ECS Service**: Service configuration with load balancer integration
3. **Target Group**: ALB target group for health checks and routing
4. **Listener Rule**: ALB listener rule for path-based routing
5. **Security Group**: Network access control for the MCP service
6. **CloudWatch Log Group**: Centralized logging configuration
7. **IAM Role**: Task execution role with minimal required permissions

## Deployment Process

### 1. Docker Image Build and Push

```bash
# Build with platform compatibility
docker build --platform linux/amd64 --tag quilt-mcp-server:version .

# Authenticate with ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 850787717197.dkr.ecr.us-east-1.amazonaws.com

# Push to ECR
docker push 850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:version
```

### 2. Infrastructure Deployment

```bash
# Using Terraform
cd deploy/terraform
terraform init
terraform plan -var="container_image=850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:version"
terraform apply
```

### 3. Service Update

```bash
# Using ECS deployment script
python scripts/ecs_deploy.py deploy --version jwt-auth-v1.0.0
```

## Monitoring and Observability

### CloudWatch Metrics

**ECS Service Metrics:**
- CPU utilization
- Memory utilization
- Task count (desired vs running)

**ALB Target Group Metrics:**
- Target response time
- Target health status
- Request count and error rate

### Log Analysis

**Key Log Patterns:**
- Authentication events
- MCP tool invocations
- Error conditions
- Performance metrics

### Health Monitoring

**Health Check Endpoints:**
- **ALB Health Check**: `/healthz`
- **Container Health Check**: Internal HTTP check on port 8000
- **Application Health**: MCP server startup and readiness

## Security Considerations

### Network Security

1. **Private Subnet Deployment**: No direct internet access
2. **Security Group Isolation**: Restricted to ALB traffic only
3. **TLS Termination**: HTTPS at ALB level
4. **VPC Flow Logs**: Network traffic monitoring (if enabled)

### Authentication and Authorization

1. **JWT Token Validation**: Enhanced JWT with bucket and permission claims
2. **IAM Role Integration**: AWS service access via task role
3. **CORS Configuration**: Controlled cross-origin access
4. **Request Validation**: MCP protocol compliance

### Data Protection

1. **Encryption in Transit**: TLS 1.2+ for all communications
2. **Encryption at Rest**: EBS volumes encrypted (default)
3. **Log Protection**: CloudWatch logs encrypted
4. **Secret Management**: Environment variables for sensitive configuration

## Troubleshooting

### Common Issues

1. **Service Won't Start**: Check CloudWatch logs for container startup errors
2. **Health Check Failures**: Verify `/healthz` endpoint accessibility
3. **Authentication Errors**: Validate JWT token configuration
4. **Network Connectivity**: Check security group rules and subnet routing

### Debugging Commands

```bash
# Check service status
aws ecs describe-services --cluster sales-prod --services sales-prod-mcp-server-production

# View recent logs
aws logs tail /ecs/mcp-server-production --follow

# Test health endpoint
curl -f https://demo.quiltdata.com/mcp/healthz

# Validate deployment
python scripts/ecs_deploy.py validate
```

## Integration Points

### Frontend Integration

**Endpoint**: `https://demo.quiltdata.com/mcp/*`
**Authentication**: JWT tokens in Authorization header
**CORS**: Configured for Quilt frontend domains

### Claude Desktop Integration

**Note**: Claude Desktop requires stdio transport. Use FastMCP proxy:
```bash
fastmcp as-proxy --transport stdio --project /path/to/quilt-mcp-server
```

### Quilt Stack Integration

**Shared Resources:**
- VPC and subnets
- ALB and security groups
- IAM roles and policies
- CloudWatch log groups

## Future Considerations

### Scaling

1. **Horizontal Scaling**: Increase desired count for higher availability
2. **Vertical Scaling**: Adjust CPU/memory based on usage patterns
3. **Auto Scaling**: Consider ECS Service Auto Scaling for dynamic load

### High Availability

1. **Multi-AZ Deployment**: Ensure tasks distributed across availability zones
2. **Health Check Optimization**: Fine-tune health check parameters
3. **Rolling Updates**: Zero-downtime deployments via ECS

### Monitoring Enhancements

1. **Custom Metrics**: Application-specific CloudWatch metrics
2. **Alerting**: CloudWatch alarms for critical conditions
3. **Dashboards**: Custom CloudWatch dashboards for operational visibility

# ALB Networking Configuration for MCP Server

## Overview

This document provides detailed configuration information for the Application Load Balancer (ALB) integration with the Quilt MCP Server, including listener rules, target groups, security groups, and network access patterns.

## ALB Listener Configuration

### Listener Rule Details

**Rule Name**: `sales-prod-mcp-server-listener-rule`
**Priority**: Configurable (typically 100+ to avoid conflicts)
**Protocol**: HTTPS (TLS termination at ALB)

**Host Header Condition**:
```
Host: demo.quiltdata.com
```

**Path Pattern Condition**:
```
Path: /mcp/*
```

**Action**:
```
Type: forward
Target Group: sales-prod-mcp-server-tg
```

### SSL/TLS Configuration

**Certificate**: Managed by AWS Certificate Manager (ACM)
**Protocols**: TLS 1.2 and 1.3
**Cipher Suites**: AWS-managed security policy
**SNI**: Server Name Indication enabled

## Target Group Configuration

### Target Group Specifications

**Name**: `sales-prod-mcp-server-tg` (truncated to 32 characters)
**Protocol**: HTTP
**Port**: 8000
**Target Type**: IP
**VPC**: Same as sales-prod VPC
**Health Check Protocol**: HTTP
**Health Check Port**: 8000

### Health Check Configuration

**Health Check Path**: `/healthz`
**Health Check Interval**: 30 seconds
**Health Check Timeout**: 6 seconds
**Healthy Threshold**: 2 consecutive successful checks
**Unhealthy Threshold**: 3 consecutive failed checks
**Matcher**: HTTP 200-399 status codes

### Load Balancing Algorithm

**Algorithm**: Round Robin
**Sticky Sessions**: Disabled (stateless MCP protocol)
**Deregistration Delay**: 30 seconds
**Slow Start Duration**: 0 seconds (disabled)

### Target Group Attributes

```json
{
  "deregistration_delay.timeout_seconds": "30",
  "stickiness.enabled": "false",
  "target_health.state": "healthy",
  "target_health.reason": "Target.ResponseCodeMismatch",
  "target_health.description": "Health checks failed with these codes: [403]"
}
```

## Security Group Configuration

### ALB Security Group (Existing)

**Name**: `sales-prod-alb-sg`
**Description**: Security group for Application Load Balancer

**Inbound Rules**:
```
Type: HTTPS
Protocol: TCP
Port: 443
Source: 0.0.0.0/0 (Internet)
Description: Allow HTTPS traffic from internet
```

**Outbound Rules**:
```
Type: All Traffic
Protocol: All
Port: All
Destination: 0.0.0.0/0
Description: Allow all outbound traffic
```

### MCP Service Security Group (New)

**Name**: `sales-prod-mcp-server-sg`
**Description**: Security group for MCP server ECS tasks

**Inbound Rules**:
```
Type: Custom TCP
Protocol: TCP
Port: 8000
Source: sales-prod-alb-sg (Security Group ID)
Description: Allow HTTP traffic from ALB security group
```

**Outbound Rules**:
```
Type: All Traffic
Protocol: All
Port: All
Destination: 0.0.0.0/0
Description: Allow all outbound traffic for AWS service access
```

### Security Group Rules Matrix

| Direction | Type | Protocol | Port | Source/Destination | Description |
|-----------|------|----------|------|-------------------|-------------|
| Inbound | HTTPS | TCP | 443 | 0.0.0.0/0 | Internet to ALB |
| Inbound | HTTP | TCP | 8000 | ALB Security Group | ALB to MCP Service |
| Outbound | All | All | All | 0.0.0.0/0 | ALB to Internet |
| Outbound | All | All | All | 0.0.0.0/0 | MCP Service to AWS Services |

## Network ACL Configuration

### Subnet-Level Access Control

**Network ACLs**: Inherit existing sales-prod NACL rules

**Public Subnet NACL** (ALB placement):
```
Inbound Rules:
- Allow HTTP (80) from 0.0.0.0/0
- Allow HTTPS (443) from 0.0.0.0/0
- Allow ephemeral ports (1024-65535) from 0.0.0.0/0

Outbound Rules:
- Allow all traffic to 0.0.0.0/0
- Allow ephemeral ports (1024-65535) to 0.0.0.0/0
```

**Private Subnet NACL** (ECS task placement):
```
Inbound Rules:
- Allow HTTP (8000) from ALB subnet CIDR
- Allow ephemeral ports (1024-65535) from 0.0.0.0/0

Outbound Rules:
- Allow HTTP (80) to 0.0.0.0/0 (for package downloads)
- Allow HTTPS (443) to 0.0.0.0/0 (for AWS API calls)
- Allow all traffic to VPC CIDR (10.0.0.0/16)
```

## Route Table Configuration

### Public Subnet Route Table (ALB)

**Routes**:
```
10.0.0.0/16 → Local (VPC)
0.0.0.0/0 → Internet Gateway
```

### Private Subnet Route Table (ECS Tasks)

**Routes**:
```
10.0.0.0/16 → Local (VPC)
0.0.0.0/0 → NAT Gateway (for outbound internet access)
```

## ALB Access Logs

### Access Log Configuration

**Access Logs**: Disabled (can be enabled for debugging)
**S3 Bucket**: Not configured (optional for audit trails)
**Log Format**: Standard ALB access log format

**Example Access Log Entry** (if enabled):
```
https 2024-01-15T10:30:00.123456Z app/sales-prod-alb/1234567890123456 192.0.2.1:12345 10.0.1.100:8000 0.001 0.002 0.000 200 200 1234 456 "GET https://demo.quiltdata.com:443/mcp/tools HTTP/1.1" "Mozilla/5.0..." arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/sales-prod-mcp-server-tg/1234567890123456 "Root=1-12345678-1234567890123456789012345" "demo.quiltdata.com" "arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012" 1
```

## Connection Handling

### Keep-Alive Configuration

**ALB Idle Timeout**: 60 seconds (default)
**Connection Draining**: 30 seconds
**HTTP Keep-Alive**: Enabled
**TCP Keep-Alive**: Enabled

### Streaming Support

**SSE (Server-Sent Events)**: Supported
**WebSocket**: Not supported (HTTP only)
**Long Polling**: Supported
**Chunked Transfer Encoding**: Supported

## CORS Configuration

### CORS Headers (Application-Level)

The MCP server application handles CORS headers:

```
Access-Control-Allow-Origin: https://demo.quiltdata.com
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type, Accept
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 86400
```

### ALB-Level CORS

ALB does not modify CORS headers - handled by application.

## Health Check Monitoring

### ALB Health Check Metrics

**CloudWatch Metrics**:
- `TargetResponseTime`: Average response time for health checks
- `HTTPCode_Target_2XX_Count`: Successful health check responses
- `HTTPCode_Target_4XX_Count`: Client error responses
- `HTTPCode_Target_5XX_Count`: Server error responses
- `HealthyHostCount`: Number of healthy targets
- `UnHealthyHostCount`: Number of unhealthy targets

### Health Check Endpoint

**Endpoint**: `/healthz`
**Method**: GET
**Expected Response**: HTTP 200 with simple response body
**Response Time**: < 6 seconds (ALB timeout)

**Example Health Check Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "0.6.13-jwt-auth"
}
```

## Troubleshooting Network Issues

### Common ALB Issues

1. **Target Group Health Checks Failing**
   - Verify `/healthz` endpoint is accessible
   - Check security group rules allow ALB to reach port 8000
   - Ensure ECS tasks are running and healthy

2. **503 Service Unavailable**
   - Check if target group has healthy targets
   - Verify ECS service desired count vs running count
   - Review CloudWatch logs for application errors

3. **Connection Timeouts**
   - Verify ALB idle timeout settings
   - Check if MCP requests exceed timeout limits
   - Review application response times

### Network Debugging Commands

```bash
# Check target group health
aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:us-east-1:850787717197:targetgroup/sales-prod-mcp-server-tg/1234567890123456

# Check security group rules
aws ec2 describe-security-groups --group-ids sg-12345678

# Test health endpoint
curl -f https://demo.quiltdata.com/mcp/healthz

# Check ALB listener rules
aws elbv2 describe-rules --listener-arn arn:aws:elasticloadbalancing:us-east-1:850787717197:listener/app/sales-prod-alb/1234567890123456/1234567890123456
```

## Performance Considerations

### Connection Pooling

**ALB Connection Reuse**: Enabled
**Backend Connection Pooling**: Application-managed
**Connection Limits**: Based on Fargate task capacity

### Load Distribution

**Algorithm**: Round Robin (default)
**Session Affinity**: Disabled (stateless protocol)
**Cross-Zone Load Balancing**: Enabled

### Scaling Considerations

**Target Group Capacity**: Limited by ECS service scaling
**ALB Capacity**: Managed by AWS (no configuration needed)
**Connection Limits**: Monitor ALB and target group metrics

## Security Best Practices

### Network Security

1. **Private Subnet Deployment**: ECS tasks in private subnets only
2. **Security Group Isolation**: Minimal required access between components
3. **TLS Termination**: HTTPS at ALB, HTTP to backend
4. **No Direct Internet Access**: ECS tasks cannot be reached directly

### Access Control

1. **IAM Integration**: ECS tasks use IAM roles for AWS access
2. **JWT Authentication**: Application-level token validation
3. **CORS Restrictions**: Limited to Quilt frontend domains
4. **Health Check Security**: Internal health checks only

### Monitoring and Alerting

1. **CloudWatch Metrics**: Monitor ALB and target group health
2. **Security Group Changes**: CloudTrail logs security group modifications
3. **Access Logs**: Optional S3 access logs for audit trails
4. **Health Check Alerts**: CloudWatch alarms for unhealthy targets

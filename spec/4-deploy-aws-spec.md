# Phase 4: Deploy-AWS (ECS/ALB Deployment) Specification

## Overview

Phase 4 deploys the MCP server to AWS using ECS Fargate with Application Load Balancer, providing a production-ready public endpoint.

## Requirements

### Functional Requirements

- **ECS Fargate**: Serverless container deployment
- **Application Load Balancer**: Public HTTP/HTTPS endpoint
- **CloudFormation**: Infrastructure as Code via AWS CDK
- **Auto-scaling**: ECS service with desired task count
- **Logging**: CloudWatch log groups for ECS, ALB, and VPC

### Quality Requirements

- **CDK Synthesis**: Template generation succeeds for HTTP and HTTPS
- **Deployment Success**: CDK deployment completes without errors
- **Health Checks**: ECS tasks pass ALB health checks
- **Endpoint Validation**: Public MCP endpoint responds correctly
- **HTTPS Support**: Configurable SSL/TLS termination

### Technical Requirements

- **CDK Bootstrap**: AWS environment prepared for CDK
- **VPC**: Uses default VPC or specified VPC_ID
- **Security Groups**: Proper ingress/egress rules
- **IAM Roles**: Task and execution roles with minimal permissions
- **Image Source**: Uses ECR image from Phase 3

## Validation Process

The SPEC-compliant validation follows this 6-step process:

1. **Preconditions** (`make init`): Check AWS CLI, CDK, credentials
2. **Execution** (`make deploy`): Deploy to ECS via CDK
3. **Testing** (`make test`): Validate deployed endpoint health
4. **Verification** (`make verify`): Test MCP protocol compliance
5. **Zero** (`make zero`): Scale service to 0 (preserve stack)
6. **Config** (`make config`): Generate `.config` with deployment details

## Success Criteria

- ✅ CDK synthesis succeeds (HTTP and HTTPS modes)
- ✅ CDK deployment completes successfully
- ✅ ECS service running with healthy tasks
- ✅ ALB health checks pass
- ✅ Public endpoint responds to HTTP requests
- ✅ MCP protocol validation passes
- ✅ HTTPS configuration works when enabled
- ✅ `.config` file generated with all endpoints and resources

## Files and Structure

```text
deploy-aws/
├── Makefile           # Phase-specific build targets
├── SPEC.md           # This specification
├── deploy-aws.sh     # Core phase script
├── app.py            # CDK application definition
└── cdk.out/          # CDK synthesis outputs
```

## Infrastructure Components

- **ECS Cluster**: Fargate cluster for container hosting
- **ECS Service**: Service managing container tasks
- **Application Load Balancer**: Public-facing load balancer
- **Target Group**: ALB target group for health checks
- **Security Groups**: Network security rules
- **CloudWatch Log Groups**: Centralized logging
- **IAM Roles**: Task execution and application roles

## Environment Variables

- `CDK_DEFAULT_ACCOUNT`: AWS account ID (auto-detected)
- `CDK_DEFAULT_REGION`: AWS region (default: us-east-1)
- `IMAGE_URI`: ECR image URI (auto-constructed or specified)
- `VPC_ID`: Existing VPC ID (optional)
- `ACM_CERT_ARN`: SSL certificate ARN for HTTPS (optional)

## Endpoints

- **HTTP**: `http://<alb-dns>/mcp`
- **HTTPS**: `https://<alb-dns>/mcp` (when ACM_CERT_ARN provided)
- **Health Check**: `http://<alb-dns>/mcp` (ALB target group)

## AWS Resources Created

- CloudFormation Stack: `QuiltMcpFargateStack`
- ECS Cluster: `QuiltMcpCluster`
- ECS Service: `QuiltMcpService`
- Application Load Balancer: `QuiltMcpALB`
- Log Groups: `/ecs/quilt-mcp`, `/aws/elasticloadbalancing/...`

## Common Issues

- **CDK Bootstrap**: Required for first-time deployment
- **ECR Image**: Must exist before deployment
- **VPC Limits**: Default VPC must have sufficient subnets
- **IAM Permissions**: CDK requires broad AWS permissions
- **Health Check Timing**: Allow time for tasks to become healthy
- **HTTPS Setup**: Requires valid ACM certificate

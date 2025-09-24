# ECR Repository and Docker Deployment Process

## Overview

This document provides comprehensive information about the Amazon Elastic Container Registry (ECR) configuration, Docker image deployment process, and CI/CD pipeline integration for the Quilt MCP Server.

## ECR Repository Configuration

### Repository Details

**Registry URL**: `850787717197.dkr.ecr.us-east-1.amazonaws.com`
**Repository Name**: `quilt-mcp-server`
**Region**: `us-east-1`
**Account ID**: `850787717197`

### Repository Settings

**Image Scanning**: Enabled (vulnerability scanning on push)
**Encryption**: AES-256 encryption at rest
**Lifecycle Policy**: Automatic cleanup of untagged images older than 7 days
**Tag Immutability**: Disabled (allows image tag updates)

### Repository Permissions

**IAM Policy** (ECR Repository Access):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": "arn:aws:ecr:us-east-1:850787717197:repository/quilt-mcp-server"
    }
  ]
}
```

## Docker Image Configuration

### Base Image

**Base Image**: `ghcr.io/astral-sh/uv:python3.11-bookworm-slim`
**Architecture**: `linux/amd64` (required for ECS Fargate compatibility)
**Size**: ~200MB (optimized for production deployment)

### Dockerfile Configuration

```dockerfile
# Use official uv Python image as base
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for native Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libcurl4-openssl-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies using uv
RUN uv sync --frozen

# Set environment variables
ENV FASTMCP_TRANSPORT=http
ENV FASTMCP_HOST=0.0.0.0
ENV FASTMCP_PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python3 -c "import urllib.request, urllib.error; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).read()" || exit 1

# Run the application
CMD ["uv", "run", "quilt-mcp"]
```

### Image Tagging Strategy

**Version Tags**:
- `latest`: Most recent stable release
- `v1.0.0`: Semantic version tags
- `jwt-auth-v1.0.0`: Feature-specific versions
- `improved-error-handling`: Descriptive feature tags
- `auto-role-assumption`: Implementation-specific tags

**Development Tags**:
- `dev`: Development builds
- `pr-123`: Pull request builds
- `commit-abc123`: Commit-specific builds

## CI/CD Pipeline Integration

### GitHub Actions Workflow

**Workflow File**: `.github/workflows/release.yml`
**Triggers**: 
- Push to `main` branch
- Release tags (e.g., `v1.0.0`)
- Manual dispatch

### Build Process

1. **Code Checkout**: Clone repository with full history
2. **Dependency Installation**: Install build dependencies
3. **Docker Build**: Build image with platform compatibility
4. **ECR Authentication**: Login to ECR registry
5. **Image Push**: Push tagged image to ECR
6. **ECS Deployment**: Update ECS service (optional)

### Build Configuration

```yaml
name: Release and Deploy

on:
  push:
    branches: [main]
    tags: ['v*']
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-east-1
    
    - name: Login to Amazon ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v2
    
    - name: Build and push Docker image
      env:
        ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
        ECR_REPOSITORY: quilt-mcp-server
        IMAGE_TAG: ${{ github.sha }}
      run: |
        docker build --platform linux/amd64 -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
        docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
```

## Manual Deployment Process

### Prerequisites

**Required Tools**:
- Docker Desktop or Docker Engine
- AWS CLI v2
- Python 3.11+ (for deployment scripts)

**Environment Variables**:
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
export ECR_REGISTRY=850787717197.dkr.ecr.us-east-1.amazonaws.com
export VERSION=your_version_tag
```

### Step-by-Step Deployment

#### 1. Authenticate with ECR

```bash
# Get ECR login token
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  850787717197.dkr.ecr.us-east-1.amazonaws.com
```

#### 2. Build Docker Image

```bash
# Build with platform compatibility for ECS Fargate
docker build \
  --platform linux/amd64 \
  --tag quilt-mcp-server:$VERSION \
  --file Dockerfile \
  .

# Tag for ECR
docker tag quilt-mcp-server:$VERSION \
  850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:$VERSION
```

#### 3. Push to ECR

```bash
# Push image to ECR
docker push \
  850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:$VERSION
```

#### 4. Update ECS Service

```bash
# Using the deployment script
python scripts/ecs_deploy.py deploy --version $VERSION

# Or manually update task definition
aws ecs update-service \
  --cluster sales-prod \
  --service sales-prod-mcp-server-production \
  --task-definition quilt-mcp-server:$VERSION
```

### Automated Deployment Script

**Script**: `scripts/ecs_deploy.py`

**Features**:
- ECR authentication
- Docker image building with platform compatibility
- ECR image push
- ECS task definition update
- Service deployment
- Health validation
- Log retrieval

**Usage**:
```bash
# Deploy with automatic version detection
python scripts/ecs_deploy.py deploy

# Deploy with specific version
python scripts/ecs_deploy.py deploy --version jwt-auth-v1.0.0

# Validate existing deployment
python scripts/ecs_deploy.py validate

# Dry run (show what would be done)
python scripts/ecs_deploy.py deploy --dry-run
```

## Image Management

### Lifecycle Policies

**Automatic Cleanup**:
- Untagged images older than 7 days
- Images with tags matching `dev-*` older than 14 days
- Images with tags matching `pr-*` older than 3 days

**Lifecycle Policy JSON**:
```json
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Delete untagged images older than 7 days",
      "selection": {
        "tagStatus": "untagged",
        "countType": "sinceImagePushed",
        "countUnit": "days",
        "countNumber": 7
      },
      "action": {
        "type": "expire"
      }
    },
    {
      "rulePriority": 2,
      "description": "Delete dev images older than 14 days",
      "selection": {
        "tagStatus": "tagged",
        "tagPrefixList": ["dev-"],
        "countType": "sinceImagePushed",
        "countUnit": "days",
        "countNumber": 14
      },
      "action": {
        "type": "expire"
      }
    }
  ]
}
```

### Image Scanning

**Vulnerability Scanning**: Enabled on all pushed images
**Scan Results**: Available in ECR console and CloudWatch logs
**Severity Levels**: CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL

## Security Considerations

### Image Security

1. **Base Image Updates**: Regular updates of base image for security patches
2. **Dependency Scanning**: Automated scanning of Python dependencies
3. **Minimal Attack Surface**: Slim base image with only required packages
4. **Non-Root User**: Container runs as non-root user (uv image default)

### Registry Security

1. **Encryption**: All images encrypted at rest with AES-256
2. **Access Control**: IAM-based access control to ECR repository
3. **Network Security**: ECR accessible only from authorized networks
4. **Audit Logging**: CloudTrail logs all ECR API calls

### Runtime Security

1. **Read-Only Root Filesystem**: Container filesystem mounted as read-only
2. **Resource Limits**: CPU and memory limits enforced by ECS
3. **Network Policies**: Security groups restrict network access
4. **IAM Roles**: Least-privilege access to AWS services

## Monitoring and Observability

### ECR Metrics

**CloudWatch Metrics**:
- `RepositoryImageCount`: Number of images in repository
- `RepositoryImageSizeBytes`: Total size of repository images
- `RepositoryPullCount`: Number of image pulls

### Deployment Monitoring

**ECS Metrics**:
- `CPUUtilization`: Container CPU usage
- `MemoryUtilization`: Container memory usage
- `RunningTaskCount`: Number of running tasks

**ALB Metrics**:
- `TargetResponseTime`: Response time from targets
- `HTTPCode_Target_2XX_Count`: Successful responses
- `HealthyHostCount`: Number of healthy targets

### Log Aggregation

**CloudWatch Logs**:
- ECS task logs: `/ecs/mcp-server-production`
- ECR push/pull logs: CloudTrail events
- ALB access logs: Optional S3 logging

## Troubleshooting

### Common ECR Issues

1. **Authentication Failures**
   ```bash
   # Re-authenticate with ECR
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin \
     850787717197.dkr.ecr.us-east-1.amazonaws.com
   ```

2. **Image Push Failures**
   ```bash
   # Check repository exists
   aws ecr describe-repositories --repository-names quilt-mcp-server
   
   # Verify IAM permissions
   aws ecr get-authorization-token --region us-east-1
   ```

3. **Platform Compatibility Issues**
   ```bash
   # Ensure linux/amd64 platform
   docker build --platform linux/amd64 -t quilt-mcp-server .
   
   # Verify image architecture
   docker inspect quilt-mcp-server | grep Architecture
   ```

### Common Deployment Issues

1. **ECS Task Won't Start**
   - Check ECR image accessibility
   - Verify IAM role permissions
   - Review CloudWatch logs for startup errors

2. **Health Check Failures**
   - Verify `/healthz` endpoint is accessible
   - Check security group rules
   - Review application logs

3. **Image Pull Failures**
   - Verify ECR repository permissions
   - Check network connectivity from ECS tasks
   - Review ECS execution role permissions

### Debugging Commands

```bash
# Check ECR repository status
aws ecr describe-repositories --repository-names quilt-mcp-server

# List image tags
aws ecr list-images --repository-name quilt-mcp-server

# Check ECS service status
aws ecs describe-services \
  --cluster sales-prod \
  --services sales-prod-mcp-server-production

# View recent logs
aws logs tail /ecs/mcp-server-production --follow

# Test deployment script
python scripts/ecs_deploy.py validate
```

## Best Practices

### Image Management

1. **Semantic Versioning**: Use semantic version tags for releases
2. **Immutable Images**: Avoid updating existing tags in production
3. **Regular Cleanup**: Implement lifecycle policies for old images
4. **Security Scanning**: Enable vulnerability scanning on all images

### Deployment Process

1. **Automated Testing**: Run tests before building images
2. **Staged Deployment**: Test in development before production
3. **Rollback Strategy**: Maintain previous image versions for rollback
4. **Health Validation**: Verify deployment health before completion

### Security

1. **Least Privilege**: Use minimal IAM permissions for ECR access
2. **Network Isolation**: Deploy containers in private subnets
3. **Regular Updates**: Keep base images and dependencies updated
4. **Audit Logging**: Monitor ECR access and image changes

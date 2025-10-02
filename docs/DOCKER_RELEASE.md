# Docker Release Workflow

Complete guide for building, pushing, and deploying the Quilt MCP Server Docker container to AWS ECS Fargate.

## Quick Start

### Production Release
Build AMD64 image, push to ECR, and deploy to ECS in one command:
```bash
make docker-release
```

### Development Release
Build and deploy a timestamped development version:
```bash
make docker-release-dev
```

## Architecture

The Docker release workflow consists of four main steps:

1. **Build**: Create Docker image for AMD64 architecture (required for ECS Fargate)
2. **Push**: Upload image to Amazon ECR
3. **Update Task Definition**: Create new ECS task definition revision with updated image
4. **Deploy Service**: Update ECS service and wait for deployment to stabilize

## Available Make Targets

### Building Images

```bash
# Build locally (native architecture)
make docker-build

# Build for AMD64 (ECS compatible)
make docker-build-amd64

# Build and push to ECR (native architecture)
make docker-push

# Build and push AMD64 to ECR
make docker-push-amd64

# Build and push development version
make docker-push-dev
```

### ECS Deployment

```bash
# Deploy specific image to ECS (wait for completion)
make ecs-deploy IMAGE_URI=712023778557.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:1.2.3

# Deploy without waiting for service to stabilize
make ecs-deploy-no-wait IMAGE_URI=<image-uri>
```

### Complete Release Workflows

```bash
# Production: Build AMD64, push, deploy, and wait
make docker-release

# Development: Build, push, and deploy dev version
make docker-release-dev
```

## Configuration

Override default configuration via environment variables or make parameters:

```bash
# ECS Configuration
ECS_CLUSTER=my-cluster \
ECS_SERVICE=my-service \
ECS_TASK_FAMILY=my-task \
make docker-release

# AWS Region
AWS_REGION=us-west-2 make docker-release

# Docker Platform (default: linux/amd64 for ECS)
DOCKER_PLATFORM=linux/arm64 make docker-release
```

### Default Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ECS_CLUSTER` | `quilt-mcp-cluster` | ECS cluster name |
| `ECS_SERVICE` | `quilt-mcp-service` | ECS service name |
| `ECS_TASK_FAMILY` | `quilt-mcp-task` | Task definition family |
| `AWS_REGION` | `us-east-1` | AWS region |
| `DOCKER_PLATFORM` | `linux/amd64` | Target platform for builds |

## Step-by-Step Manual Workflow

If you need more control, you can run each step individually:

### 1. Build and Push Image

```bash
# Get current version
VERSION=$(python3 scripts/version.py get-version)

# Build and push AMD64 image
VERSION=$VERSION DOCKER_PLATFORM=linux/amd64 \
  uv run python scripts/docker.py push \
    --version $VERSION \
    --platform linux/amd64
```

### 2. Get Image URI

```bash
IMAGE_URI=$(VERSION=$VERSION uv run python scripts/docker.py info --version $VERSION)
echo "Image URI: $IMAGE_URI"
```

### 3. Deploy to ECS

```bash
uv run python scripts/ecs_deploy.py \
  --image $IMAGE_URI \
  --cluster quilt-mcp-cluster \
  --service quilt-mcp-service \
  --task-family quilt-mcp-task \
  --region us-east-1
```

## Scripts Reference

### `scripts/docker.py`

Docker image management script with platform support.

```bash
# Generate tags for a version
uv run python scripts/docker.py tags --version 1.2.3

# Build locally
uv run python scripts/docker.py build

# Build and push to ECR
uv run python scripts/docker.py push --version 1.2.3 --platform linux/amd64

# Get image URI for a version
uv run python scripts/docker.py info --version 1.2.3

# Dry run
uv run python scripts/docker.py push --version 1.2.3 --dry-run
```

### `scripts/ecs_deploy.py`

ECS task definition and service deployment script.

```bash
# Deploy to ECS
uv run python scripts/ecs_deploy.py \
  --image <image-uri> \
  --cluster quilt-mcp-cluster \
  --service quilt-mcp-service \
  --task-family quilt-mcp-task

# Deploy without waiting
uv run python scripts/ecs_deploy.py \
  --image <image-uri> \
  --no-wait

# Dry run
uv run python scripts/ecs_deploy.py \
  --image <image-uri> \
  --dry-run
```

## Troubleshooting

### Build fails with "exec format error"

**Problem**: Image built for wrong architecture (e.g., ARM64 when ECS expects AMD64).

**Solution**: Always use `--platform linux/amd64` for ECS deployments:
```bash
make docker-push-amd64
```

### ECR authentication fails

**Problem**: Docker not authenticated with ECR.

**Solution**: Targets automatically authenticate, but you can manually authenticate:
```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  712023778557.dkr.ecr.us-east-1.amazonaws.com
```

### ECS deployment times out

**Problem**: Service deployment takes longer than expected.

**Solution**: Increase timeout or deploy without waiting:
```bash
# Increase timeout to 15 minutes
uv run python scripts/ecs_deploy.py --image <uri> --timeout 900

# Or deploy without waiting
make ecs-deploy-no-wait IMAGE_URI=<uri>
```

### Service fails to stabilize

**Problem**: New tasks fail health checks or exit immediately.

**Solution**: Check ECS service logs:
```bash
# View service events
aws ecs describe-services \
  --cluster quilt-mcp-cluster \
  --services quilt-mcp-service \
  --query 'services[0].events' \
  --output table

# View CloudWatch logs
aws logs tail /ecs/quilt-mcp-task --follow
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to ECS

on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      
      - name: Deploy to ECS
        run: make docker-release
```

## Multi-Region Deployment

To deploy to multiple regions:

```bash
# Deploy to us-east-1
AWS_REGION=us-east-1 make docker-release

# Deploy to us-west-2
AWS_REGION=us-west-2 make docker-release

# Deploy to eu-west-1
AWS_REGION=eu-west-1 make docker-release
```

## Version Management

The workflow automatically uses the version from `pyproject.toml`:

```bash
# Get current version
python3 scripts/version.py get-version

# Bump version before releasing
make bump-patch    # 1.2.3 → 1.2.4
make bump-minor    # 1.2.3 → 1.3.0
make bump-major    # 1.2.3 → 2.0.0

# Then release
make docker-release
```

## Best Practices

1. **Always build for AMD64**: ECS Fargate requires AMD64 images
   ```bash
   make docker-push-amd64  # ✅ Correct
   make docker-push        # ❌ May be wrong architecture
   ```

2. **Use tagged versions for production**: Don't rely on `latest`
   ```bash
   make docker-release     # ✅ Uses version from pyproject.toml
   ```

3. **Test in development first**:
   ```bash
   make docker-release-dev  # Deploy dev version
   # Test thoroughly
   make docker-release      # Deploy production
   ```

4. **Monitor deployments**: Always wait for service to stabilize
   ```bash
   make docker-release      # ✅ Waits for completion
   make ecs-deploy-no-wait  # ❌ Fire and forget
   ```

5. **Use dry-run for verification**:
   ```bash
   uv run python scripts/ecs_deploy.py --image <uri> --dry-run
   ```

## Architecture Notes

### AMD64 Requirement

AWS ECS Fargate requires AMD64 (x86_64) images. If you're developing on Apple Silicon (M1/M2/M3):

```bash
# Your Mac runs ARM64, but ECS needs AMD64
# Docker will cross-compile automatically with --platform flag
DOCKER_PLATFORM=linux/amd64 make docker-release
```

The build may be slower due to emulation, but ensures compatibility.

### Multi-Stage Build

The Dockerfile uses multi-stage builds:
- **Builder stage**: Compiles native extensions (e.g., pybigwig)
- **Runtime stage**: Minimal image with only necessary dependencies

This reduces final image size and improves security.

## See Also

- [Docker Documentation](https://docs.docker.com/)
- [Amazon ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [ECR User Guide](https://docs.aws.amazon.com/ecr/)
- [Dockerfile Best Practices](https://docs.docker.com/develop/dev-best-practices/)


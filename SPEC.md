# Fast MCP Server - Phase Specifications

This document defines the contracts, requirements, and validation criteria for each phase of the deployment pipeline.

## Architecture Overview

The system uses a 4-phase pipeline where each phase is atomic, testable, and has clear input/output contracts:

```tree
src/
├── app/           # Phase 1: Local MCP server (Python)
├── build-docker/  # Phase 2: Docker containerization  
├── catalog-push/  # Phase 3: ECR registry operations
├── deploy-aws/    # Phase 4: ECS/ALB deployment
└── shared/        # Common utilities and pipeline orchestration
```

## Version Management Contract

All phases MUST use git SHA as the canonical version to prevent skew:

- **Version Source**: `git rev-parse --short HEAD`
- **Local Image**: `quilt-mcp:${GIT_SHA}`
- **ECR Image**: `${ECR_REGISTRY}/quilt-mcp:${GIT_SHA}`
- **Deployed Service**: Tagged with `${GIT_SHA}`

## Phase 1: App (Local MCP Server)

### Phase 1 Purpose

Develop and validate the core MCP server functionality locally.

### Phase 1 Input Contract

- Source code in `src/app/src/quilt_mcp/`
- Python dependencies in `pyproject.toml`
- Test configuration

### Phase 1 Output Contract

- Validated MCP server ready for containerization
- All tests passing with required coverage
- Local endpoint responding correctly

### Phase 1 Validation Requirements

#### Phase 1 Unit Tests

```bash
./src/app/app.sh test
```

- **Requirement**: All unit tests MUST pass
- **Coverage**: Minimum 85% code coverage
- **Location**: `src/app/tests/test_*.py`
- **Command**: `uv run python -m pytest tests/ --cov=quilt_mcp --cov-report=term-missing --cov-fail-under=85`

#### Phase 1 Integration Tests  

```bash
./src/app/app.sh test --integration
```

- **Requirement**: All integration tests MUST pass
- **Real Data**: Tests against actual Quilt buckets/packages
- **Authentication**: Validates OAuth and AWS credentials

#### Phase 1 Local Endpoint Validation

```bash
./test-endpoint.sh -l -t
```

- **Requirement**: Local server MUST respond to MCP calls
- **Port**: Server runs on `http://127.0.0.1:8000/mcp`
- **Methods**: `initialize`, `tools/list`, `tools/call` all functional
- **Response Format**: Valid JSON-RPC 2.0 responses

#### Phase 1 Import Validation

- All core modules import without error
- No circular dependencies
- All tools register correctly

### Phase 1 Success Criteria

- [ ] All unit tests pass with ≥85% coverage
- [ ] All integration tests pass  
- [ ] `test-endpoint.sh -l -t` passes
- [ ] Server starts and responds within 10 seconds
- [ ] All MCP tools return valid responses

### Phase 1 Script

- **Location**: `src/app/app.sh`
- **Commands**: `run`, `test`, `test --integration`, `test --coverage`, `clean`

## Phase 2: Build-Docker (Containerization)

### Phase 2 Purpose

Package the MCP server into a Docker container for cloud deployment.

### Phase 2 Input Contract

- Validated app phase (Phase 1 success)
- Git SHA version tag
- `Dockerfile` with proper Python/dependency setup

### Phase 2 Output Contract

- Docker image: `quilt-mcp:${GIT_SHA}`
- Container passes health checks
- Image ready for registry push

### Phase 2 Validation Requirements

#### Phase 2 Build Validation

```bash
./src/build-docker/build-docker.sh build
```

- **Requirement**: Docker build MUST complete without errors
- **Platform**: `linux/amd64` for ECS compatibility
- **Size**: Image should be optimized (< 1GB)
- **Layers**: Proper layer caching for fast rebuilds

#### Phase 2 Container Health Check

```bash
./src/build-docker/build-docker.sh test  
```

- **Requirement**: Container MUST pass health check
- **Startup**: Container starts within 30 seconds
- **Health Endpoint**: `/health` returns 200 OK
- **MCP Endpoint**: `/mcp` accepts requests
- **Port**: Exposes port 8000

#### Phase 2 Container Runtime Test

- Container runs without privileged access
- No hardcoded secrets or credentials
- Proper signal handling (SIGTERM)
- Logs to stdout/stderr

### Phase 2 Success Criteria

- [ ] Docker build completes successfully
- [ ] Container starts and responds within 30s
- [ ] Health check passes (`curl -f http://localhost:8001/health`)
- [ ] MCP endpoint responds (`curl -f http://localhost:8001/mcp`)
- [ ] Container stops gracefully on SIGTERM

### Phase 2 Script

- **Location**: `src/build-docker/build-docker.sh`  
- **Commands**: `build`, `test`, `run`, `clean`

## Phase 3: Catalog-Push (ECR Registry)

### Phase 3 Purpose

Push Docker images to ECR registry for cloud deployment.

### Phase 3 Input Contract

- Valid Docker image from Phase 2: `quilt-mcp:${GIT_SHA}`
- ECR registry URL: `$ECR_REGISTRY`
- AWS credentials with ECR push permissions

### Phase 3 Output Contract

- ECR image: `${ECR_REGISTRY}/quilt-mcp:${GIT_SHA}`
- Image available for ECS deployment
- Registry tagged with git SHA

### Phase 3 Validation Requirements

#### Phase 3 Registry Authentication

```bash
./src/catalog-push/catalog-push.sh login
```

- **Requirement**: ECR login MUST succeed
- **Credentials**: Uses AWS credentials/profile
- **Region**: Extracted from registry URL

#### Phase 3 Push Validation

```bash
./src/catalog-push/catalog-push.sh push quilt-mcp:${GIT_SHA}
```

- **Requirement**: Image push MUST succeed
- **Tagging**: Proper ECR URI format
- **Verification**: Image manifest uploaded

#### Phase 3 Pull Test

```bash
./src/catalog-push/catalog-push.sh test ${GIT_SHA}
```

- **Requirement**: Can pull and run ECR image
- **Integrity**: Pulled image identical to local
- **Runtime**: Container from ECR runs correctly

### Phase 3 Success Criteria

- [ ] ECR login successful
- [ ] Image push completes without errors
- [ ] ECR image pull and run test passes
- [ ] Image tagged with correct git SHA
- [ ] Registry metadata correct

### Phase 3 Script

- **Location**: `src/catalog-push/catalog-push.sh`
- **Commands**: `push`, `pull`, `test`, `login`

## Phase 4: Deploy-AWS (ECS/ALB Deployment)

### Phase 4 Purpose

Deploy containerized MCP server to AWS ECS with ALB load balancing.

### Phase 4 Input Contract

- ECR image: `${ECR_REGISTRY}/quilt-mcp:${GIT_SHA}`
- AWS credentials with ECS/ALB/CloudFormation permissions
- CDK app definition

### Phase 4 Output Contract  

- Live ECS service behind ALB
- Public HTTPS endpoint
- CloudWatch logging enabled
- Health monitoring active

### Phase 4 Validation Requirements

#### Phase 4 Infrastructure Deployment

```bash
./src/deploy-aws/deploy-aws.sh deploy ${ECR_URI}
```

- **Requirement**: CDK deployment MUST succeed
- **Resources**: ECS cluster, service, ALB, target groups
- **Configuration**: `.config` file generated with outputs

#### Phase 4 Service Health Check

```bash
./src/deploy-aws/deploy-aws.sh test
```

- **Requirement**: Deployed service MUST be healthy
- **ALB Health**: Target groups show healthy targets
- **ECS Health**: All tasks running and healthy
- **Endpoint**: Public ALB endpoint responds

#### Phase 4 MCP Endpoint Validation

- **URL**: From `.config` file `$MCP_ENDPOINT`
- **HTTPS**: SSL certificate valid
- **Methods**: All MCP methods functional
- **Performance**: Response time < 2 seconds

#### Phase 4 Monitoring Validation

- CloudWatch logs streaming
- ECS service metrics available
- ALB access logs (if configured)

### Phase 4 Success Criteria

- [ ] CDK deployment completes successfully
- [ ] ECS service reaches RUNNING state
- [ ] ALB health checks pass
- [ ] Public endpoint responds correctly
- [ ] All MCP tools functional via ALB
- [ ] CloudWatch logs streaming

### Phase 4 Script

- **Location**: `src/deploy-aws/deploy-aws.sh`
- **Commands**: `deploy`, `test`, `status`, `destroy`

## Pipeline Orchestration Contract

### Full Pipeline Execution

```bash
./src/shared/pipeline.sh full
```

**Requirements**:

1. Each phase MUST complete successfully before next starts
2. Version consistency maintained across all phases
3. Any phase failure stops the pipeline
4. Rollback capability for failed deployments

### Individual Phase Execution

```bash
./src/shared/pipeline.sh [app|build-docker|catalog-push|deploy-aws]
```

**Requirements**:

- Each phase can run independently
- Input requirements validated before execution
- Clear success/failure reporting

## Environment Requirements

### Required Environment Variables

```bash
# For catalog-push and deploy-aws phases
export ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com
export ECR_REPOSITORY=quilt-mcp  # Optional, defaults to quilt-mcp

# Optional AWS configuration
export CDK_DEFAULT_ACCOUNT=123456789012
export CDK_DEFAULT_REGION=us-east-1
export VPC_ID=vpc-12345678  # Use existing VPC
```

### AWS Permissions Required

- ECR: `GetAuthorizationToken`, `BatchGetImage`, `BatchCheckLayerAvailability`, `PutImage`
- ECS: `CreateCluster`, `CreateService`, `UpdateService`, `DescribeServices`
- CloudFormation: Full access for CDK operations
- IAM: Create roles for ECS tasks
- EC2: VPC and security group operations

## Makefile Integration

The Makefile provides convenient shortcuts while enforcing phase contracts:

```bash
# Individual phases with full validation
make app        # Runs app phase with coverage requirements
make build      # Runs build phase with container tests  
make catalog    # Runs catalog phase with push/pull validation
make deploy     # Runs deploy phase with endpoint validation

# Pipeline orchestration
make full       # Full pipeline with all validations

# Testing shortcuts
make test-app   # Phase 1 validation only
make test-build # Phase 2 validation only  
make test-deploy# Phase 4 validation only

# Utilities
make clean      # Clean all phase artifacts
make status     # Show deployment status
make destroy    # Clean up AWS resources
```

## Validation Matrix

| Phase | Unit Tests | Integration | Health Check | Endpoint Test | Coverage |
|-------|------------|-------------|--------------|---------------|----------|
| app   | ✅ Required | ✅ Required | N/A          | ✅ Local     | ≥85%     |
| build-docker | N/A | N/A | ✅ Container | ✅ Container | N/A |
| catalog-push | N/A | N/A | ✅ Registry | ✅ Pull/Run | N/A |
| deploy-aws | N/A | N/A | ✅ ECS/ALB | ✅ Public | N/A |

## Failure Handling

### Phase Failure Response

1. **Immediate Stop**: Pipeline halts on any phase failure
2. **Error Reporting**: Clear error messages with debugging info
3. **State Preservation**: No cleanup on failure for debugging
4. **Rollback Options**: Phase-specific rollback procedures

### Common Failure Scenarios

- **App**: Test failures, coverage below 85%, import errors
- **Build-Docker**: Docker build failure, health check timeout
- **Catalog-Push**: ECR authentication, network issues, image corruption
- **Deploy-AWS**: CDK deployment failure, ECS service startup issues

### Recovery Procedures

Each phase script includes troubleshooting guidance and recovery steps.

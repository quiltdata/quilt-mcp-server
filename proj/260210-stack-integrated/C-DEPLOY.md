# Fargate Deployment Reference

## Quick Start

**Image:** `730278974607.dkr.ecr.us-east-1.amazonaws.com/quiltdata/mcp:latest`
**Port:** 8000 (HTTP)
**Architecture:** Stateless, horizontally scalable, GraphQL-backed

For general Fargate deployment guidance, see [AWS ECS on Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html).

## Docker Images (CI-Built)

Docker images are automatically built and published on every push to `main` branch.

**CI Workflow:** [Production Docker Build](https://github.com/quiltdata/quilt-mcp-server/actions/workflows/prod.yml)

**ECR Repository:**

- **Registry:** `730278974607.dkr.ecr.us-east-1.amazonaws.com`
- **Image:** `quiltdata/mcp`
- **Access:** Public read (no authentication required for pull)

**Available tags:**

- `latest` - Most recent main branch build
- `{version}` - Specific version tags (e.g., `0.5.9`, `1.0.0`)

**Full URIs:**

```text
730278974607.dkr.ecr.us-east-1.amazonaws.com/quiltdata/mcp:latest
730278974607.dkr.ecr.us-east-1.amazonaws.com/quiltdata/mcp:{version}
```

**Where to look:**

1. Check recent workflow runs: [Production Docker Build Actions](https://github.com/quiltdata/quilt-mcp-server/actions/workflows/prod.yml)
2. View build outputs in the "Deployment Summary" job step
3. Images include version from `pyproject.toml` in the tag

## Required Environment Variables

```bash
# Deployment mode (required)
QUILT_MULTIUSER_MODE=true

# Catalog endpoints (required)
QUILT_CATALOG_URL=https://quilt.example.com
QUILT_REGISTRY_URL=https://quilt-registry.example.com

# JWT secret (choose one)
MCP_JWT_SECRET=your-shared-secret              # Testing only
MCP_JWT_SECRET_SSM_PARAMETER=/quilt-mcp/jwt    # Production (requires AWS_REGION)

# Transport (required for Fargate)
FASTMCP_TRANSPORT=http
FASTMCP_HOST=0.0.0.0
FASTMCP_PORT=8000
```

**Optional:**

```bash
MCP_JWT_ISSUER=https://quilt.example.com       # Validate issuer claim
MCP_JWT_AUDIENCE=quilt-mcp-api                 # Validate audience claim
QUILT_SERVICE_TIMEOUT=60                       # HTTP timeout (seconds)
MCP_SKIP_BANNER=true                           # Suppress startup banner
```

See [Environment Variables Reference](#environment-variables-reference) for complete list.

## Health Checks

Three endpoints (no authentication required):

```log
GET /         → 200 {"status": "ok", ...}
GET /health   → 200 {"status": "ok", ...}
GET /healthz  → 200 {"status": "ok", ...}
```

**Recommended health check:**

```bash
CMD-SHELL curl -f http://localhost:8000/health || exit 1
```

Interval: 30s | Timeout: 5s | Retries: 3 | Start period: 60s

## Authentication

### JWT Token Format

Catalog-issued HS256 tokens with required claims:

```json
{
  "id": 123,           // User ID (integer)
  "uuid": "user-uuid", // User UUID (string)
  "exp": 1738675200    // Expiration (unix timestamp)
}
```

### Request Format

```http
Authorization: Bearer <jwt-token>
```

Health check endpoints (`/`, `/health`, `/healthz`) do not require authentication.
All other endpoints (`/mcp/*`) require valid JWT.

## IAM Permissions

### Task Execution Role

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
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/ecs/quilt-mcp-server:*"
    }
  ]
}
```

### Task Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SSMParameterAccess",
      "Effect": "Allow",
      "Action": ["ssm:GetParameter"],
      "Resource": ["arn:aws:ssm:REGION:ACCOUNT:parameter/quilt-mcp/jwt"]
    }
  ]
}
```

**Note:** No S3 permissions required. All data operations proxy through catalog GraphQL API.

## Key Architectural Details

1. **Stateless:** No filesystem dependencies, fully horizontally scalable
2. **No direct S3 access:** All operations via catalog GraphQL API (port 443 outbound to `QUILT_REGISTRY_URL`)
3. **Single-tenant:** One deployment per catalog/registry pair
4. **JWT validation:** Server validates tokens, catalog enforces permissions

## Startup Log Patterns

**Success:**

```log
Quilt MCP Server starting in multiuser mode
Backend type: graphql
JWT required: True
```

**Configuration error:**

```log
Invalid configuration: Multiuser mode requires MCP_JWT_SECRET environment variable
```

**JWT validation failure:**

```log
JWT validation failed (token_expired) request_id=abc123
```

## Troubleshooting

| Symptom                     | Most Common Cause                                                                  |
| --------------------------- | ---------------------------------------------------------------------------------- |
| Container exits immediately | Missing `QUILT_CATALOG_URL`, `QUILT_REGISTRY_URL`, or JWT secret                  |
| Health checks fail          | `FASTMCP_HOST` not set to `0.0.0.0` or security group blocking port 8000          |
| 401/403 errors              | JWT secret mismatch or expired tokens                                             |
| Backend/GraphQL errors      | `QUILT_REGISTRY_URL` not accessible from Fargate (check security groups)          |

## Environment Variables Reference

### Required (Multiuser Mode)

| Variable | Description | Example |
|----------|-------------|---------|
| `QUILT_MULTIUSER_MODE` | Enable production mode | `true` |
| `QUILT_CATALOG_URL` | Catalog URL | `https://quilt.example.com` |
| `QUILT_REGISTRY_URL` | Registry URL (GraphQL endpoint derived from this) | `https://quilt-registry.example.com` |
| `MCP_JWT_SECRET` or `MCP_JWT_SECRET_SSM_PARAMETER` | JWT validation secret | `your-secret` or `/ssm/path` |
| `FASTMCP_TRANSPORT` | Transport protocol | `http` |
| `FASTMCP_HOST` | Bind address | `0.0.0.0` |
| `FASTMCP_PORT` | Service port | `8000` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `QUILT_GRAPHQL_ENDPOINT` | Auto-derived | Override GraphQL endpoint URL |
| `MCP_JWT_ISSUER` | None | Validate JWT issuer claim |
| `MCP_JWT_AUDIENCE` | None | Validate JWT audience claim |
| `QUILT_SERVICE_TIMEOUT` | `60` | HTTP request timeout (seconds) |
| `QUILT_BROWSING_SESSION_TTL` | `180` | Browsing session TTL (seconds) |
| `MCP_SKIP_BANNER` | `false` | Suppress startup banner |
| `QUILT_MCP_RESOURCES_ENABLED` | `true` | Enable MCP resource framework |
| `QUILT_MCP_RESOURCE_CACHE_TTL` | `300` | Resource cache TTL (seconds) |
| `MCP_TELEMETRY_ENABLED` | `true` | Enable telemetry collection |
| `MCP_TELEMETRY_LEVEL` | `standard` | Telemetry level: `minimal`, `standard`, `detailed` |
| `MCP_OPTIMIZATION_ENABLED` | `true` | Enable query optimization |

### Python Runtime (Pre-configured)

| Variable | Default | Description |
|----------|---------|-------------|
| `PYTHONUNBUFFERED` | `1` | Disable stdout/stderr buffering |
| `PYTHONDONTWRITEBYTECODE` | `1` | Prevent .pyc file creation |

## Minimal Task Definition

```json
{
  "family": "quilt-mcp-server",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/quilt-mcp-execution-role",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/quilt-mcp-task-role",
  "containerDefinitions": [{
    "name": "quilt-mcp-server",
    "image": "730278974607.dkr.ecr.us-east-1.amazonaws.com/quiltdata/mcp:latest",
    "essential": true,
    "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
    "environment": [
      {"name": "QUILT_MULTIUSER_MODE", "value": "true"},
      {"name": "QUILT_CATALOG_URL", "value": "https://quilt.example.com"},
      {"name": "QUILT_REGISTRY_URL", "value": "https://quilt-registry.example.com"},
      {"name": "MCP_JWT_SECRET_SSM_PARAMETER", "value": "/quilt-mcp/jwt"},
      {"name": "AWS_REGION", "value": "us-east-1"},
      {"name": "FASTMCP_TRANSPORT", "value": "http"},
      {"name": "FASTMCP_HOST", "value": "0.0.0.0"},
      {"name": "FASTMCP_PORT", "value": "8000"},
      {"name": "MCP_SKIP_BANNER", "value": "true"}
    ],
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
      "interval": 30,
      "timeout": 5,
      "retries": 3,
      "startPeriod": 60
    },
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/quilt-mcp-server",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }]
}
```

## Deployment Checklist

- [ ] JWT secret stored in SSM Parameter Store
- [ ] Task execution role created with ECR + CloudWatch Logs permissions
- [ ] Task role created with SSM GetParameter permission
- [ ] Security group allows inbound 8000 from ALB
- [ ] Security group allows outbound 443 to `QUILT_REGISTRY_URL`
- [ ] Target group created with health check path `/health`
- [ ] CloudWatch log group `/ecs/quilt-mcp-server` created
- [ ] Environment variables configured in task definition
- [ ] Health check tested via ALB
- [ ] JWT authentication tested with sample token
- [ ] Catalog connectivity verified from Fargate tasks

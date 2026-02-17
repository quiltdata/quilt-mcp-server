# Fargate Deployment Reference

> Version 1.0 | February 16, 2026
> **Status Note (2026-02-17):** This is a deployment runbook/reference. Checklist items below are environment-execution tasks and are intentionally left unchecked in code-only review updates.

## Quick Start

**Image:** `730278974607.dkr.ecr.us-east-1.amazonaws.com/quiltdata/mcp:latest`
**Port:** 8000 (HTTP)
**Architecture:** Stateless, horizontally scalable, GraphQL-backed
**Default Mode:** `remote` (container pre-configured for production deployment)

The Docker container is pre-configured with `QUILT_DEPLOYMENT=remote`, which automatically sets:

- Backend: GraphQL (platform)
- Transport: HTTP
- JWT: Required (pass-through to catalog for validation)
- Multiuser: Enabled

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

The Docker container is pre-configured with `QUILT_DEPLOYMENT=remote`, so minimal configuration is needed:

```bash
# Catalog endpoints (required)
QUILT_CATALOG_URL=https://quilt.example.com
QUILT_REGISTRY_URL=https://quilt-registry.example.com

# These are already set in the Docker container (no need to override):
# QUILT_DEPLOYMENT=remote           # Pre-configured in container
# FASTMCP_TRANSPORT=http            # Pre-configured in container
# FASTMCP_HOST=0.0.0.0              # Pre-configured in container
# FASTMCP_PORT=8000                 # Pre-configured in container
```

**Optional:**

```bash
QUILT_SERVICE_TIMEOUT=60            # HTTP timeout (seconds)
MCP_SKIP_BANNER=true                # Suppress startup banner
```

**Legacy (backward compatibility):**

```bash
QUILT_MULTIUSER_MODE=true           # Deprecated: Use QUILT_DEPLOYMENT=remote instead
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

### JWT Pass-Through Architecture

The MCP server uses a **pass-through authentication model**:

1. Client sends JWT in `Authorization: Bearer <token>` header
2. MCP server forwards JWT to catalog GraphQL backend
3. Catalog validates JWT and enforces permissions
4. MCP server exchanges JWT for temporary AWS credentials via `/api/auth/get_credentials`
5. MCP server uses temporary credentials for S3 operations

**Key Points:**

- MCP server does NOT validate JWT signatures locally
- MCP server does NOT store or generate JWT secrets
- All authentication/authorization happens at the catalog backend
- JWT validation errors are passed through from the catalog

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
      "Sid": "NoPermissionsRequired",
      "Effect": "Allow",
      "Action": ["none:*"],
      "Resource": "*"
    }
  ]
}
```

**Note:** No S3 or SSM permissions required. The MCP server:

- Uses JWT pass-through authentication (no local secrets)
- Exchanges JWT for temporary AWS credentials via catalog API
- All data operations proxy through catalog GraphQL API

## Key Architectural Details

1. **Stateless:** No filesystem dependencies, fully horizontally scalable
2. **No direct S3 access:** All operations via catalog GraphQL API (port 443 outbound to `QUILT_REGISTRY_URL`)
3. **Single-tenant:** One deployment per catalog/registry pair
4. **JWT pass-through:** MCP server forwards JWTs to catalog, which validates and enforces permissions
5. **Pre-configured:** Docker container defaults to `QUILT_DEPLOYMENT=remote` (GraphQL backend, HTTP transport)

## Startup Log Patterns

**Success:**

```log
Starting Quilt MCP Server
Deployment mode: remote (from: deployment-env)
Backend: platform (graphql)
Transport: http
JWT required: True
Registry: https://quilt-registry.example.com
```

**Configuration error:**

```log
Invalid configuration: Platform backend requires QUILT_CATALOG_URL environment variable
Invalid configuration: Platform backend requires QUILT_REGISTRY_URL environment variable
```

**JWT authentication failure:**

```log
JWT authentication required. Provide Authorization: Bearer header.
JWT token invalid or expired. Please re-authenticate.
```

## Troubleshooting

| Symptom                     | Most Common Cause                                                               |
| --------------------------- | ------------------------------------------------------------------------------- |
| Container exits immediately | Missing `QUILT_CATALOG_URL` or `QUILT_REGISTRY_URL`                             |
| Health checks fail          | Security group blocking port 8000 (container pre-configured with correct host)  |
| 401/403 errors              | Invalid/expired JWT or catalog rejecting token                                  |
| Backend/GraphQL errors      | `QUILT_REGISTRY_URL` not accessible from Fargate (check security groups)        |
| AWS credential errors       | JWT exchange failing - check catalog `/api/auth/get_credentials` endpoint       |

## Environment Variables Reference

### Required (Remote Deployment)

**Note:** Docker container is pre-configured with `QUILT_DEPLOYMENT=remote`. Only these variables are required:

| Variable                | Description                                       | Example                              |
| ----------------------- | ------------------------------------------------- | ------------------------------------ |
| `QUILT_CATALOG_URL`     | Catalog URL                                       | `https://quilt.example.com`          |
| `QUILT_REGISTRY_URL`    | Registry URL (GraphQL endpoint derived from this) | `https://quilt-registry.example.com` |

**Pre-configured in Docker (no need to set):**

| Variable            | Default Value | Description          |
| ------------------- | ------------- | -------------------- |
| `QUILT_DEPLOYMENT`  | `remote`      | Deployment mode      |
| `FASTMCP_TRANSPORT` | `http`        | Transport protocol   |
| `FASTMCP_HOST`      | `0.0.0.0`     | Bind address         |
| `FASTMCP_PORT`      | `8000`        | Service port         |

### Optional

| Variable                       | Default      | Description                                        |
| ------------------------------ | ------------ | -------------------------------------------------- |
| `QUILT_GRAPHQL_ENDPOINT`       | Auto-derived | Override GraphQL endpoint URL                      |
| `QUILT_SERVICE_TIMEOUT`        | `60`         | HTTP request timeout (seconds)                     |
| `QUILT_BROWSING_SESSION_TTL`   | `180`        | Browsing session TTL (seconds)                     |
| `MCP_SKIP_BANNER`              | `false`      | Suppress startup banner                            |
| `QUILT_MCP_RESOURCES_ENABLED`  | `true`       | Enable MCP resource framework                      |
| `QUILT_MCP_RESOURCE_CACHE_TTL` | `300`        | Resource cache TTL (seconds)                       |
| `MCP_TELEMETRY_ENABLED`        | `true`       | Enable telemetry collection                        |
| `MCP_TELEMETRY_LEVEL`          | `standard`   | Telemetry level: `minimal`, `standard`, `detailed` |
| `MCP_OPTIMIZATION_ENABLED`     | `true`       | Enable query optimization                          |

### Legacy (Backward Compatibility)

| Variable               | Replacement               | Description                      |
| ---------------------- | ------------------------- | -------------------------------- |
| `QUILT_MULTIUSER_MODE` | `QUILT_DEPLOYMENT=remote` | Old way to enable multiuser mode |

### Python Runtime (Pre-configured in Docker)

| Variable                  | Default | Description                     |
| ------------------------- | ------- | ------------------------------- |
| `PYTHONUNBUFFERED`        | `1`     | Disable stdout/stderr buffering |
| `PYTHONDONTWRITEBYTECODE` | `1`     | Prevent .pyc file creation      |

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
      {"name": "QUILT_CATALOG_URL", "value": "https://quilt.example.com"},
      {"name": "QUILT_REGISTRY_URL", "value": "https://quilt-registry.example.com"},
      {"name": "MCP_SKIP_BANNER", "value": "true"}
    ],
    "comment": "QUILT_DEPLOYMENT=remote is pre-configured in the Docker image",
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

- [ ] Task execution role created with ECR + CloudWatch Logs permissions
- [ ] Task role created (minimal permissions - no SSM needed)
- [ ] Security group allows inbound 8000 from ALB
- [ ] Security group allows outbound 443 to `QUILT_REGISTRY_URL`
- [ ] Target group created with health check path `/health`
- [ ] CloudWatch log group `/ecs/quilt-mcp-server` created
- [ ] Environment variables configured: `QUILT_CATALOG_URL`, `QUILT_REGISTRY_URL`
- [ ] Health check tested via ALB
- [ ] JWT authentication tested with sample token from catalog
- [ ] Catalog connectivity verified from Fargate tasks
- [ ] Verified JWT exchange for AWS credentials works (`/api/auth/get_credentials`)

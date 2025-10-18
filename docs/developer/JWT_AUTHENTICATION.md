# JWT Authentication Deployment Guide

This guide explains how to **deploy** and **configure** JWT-based authentication for the Quilt MCP server.

> **For architecture details**, see [JWT_ARCHITECTURE.md](../JWT_ARCHITECTURE.md)

## Quick Start

The MCP server enforces JWT-only authentication. No IAM fallback exists for tool operations.

## Prerequisites

- Frontend and backend must share the same JWT secret (55+ characters)
- Frontend must send `Authorization: Bearer <token>` header
- Tokens must include AWS credentials or role ARN

## Deployment Steps

### Step 1: Store JWT Secret in AWS SSM (Recommended)

```bash
aws ssm put-parameter \
  --name "/quilt/mcp-server/jwt-secret" \
  --value "your-55-char-secret-here" \
  --type "SecureString" \
  --region us-east-1 \
  --overwrite
```

### Step 2: Configure Environment Variables

**Option A: Direct Secret (Development)**

```bash
export MCP_ENHANCED_JWT_SECRET="your-55-char-secret-here"
export MCP_ENHANCED_JWT_KID="frontend-enhanced"
export QUILT_CATALOG_URL="https://demo.quiltdata.com"
```

**Option B: SSM Parameter (Production)**

```bash
export MCP_ENHANCED_JWT_SECRET_SSM_PARAMETER="/quilt/mcp-server/jwt-secret"
export AWS_REGION="us-east-1"
export MCP_ENHANCED_JWT_KID="frontend-enhanced"
export QUILT_CATALOG_URL="https://demo.quiltdata.com"
```

### Step 3: Deploy with Docker/ECS

**Docker Compose:**

```yaml
version: '3.8'
services:
  quilt-mcp:
    image: quilt-mcp-server:latest
    environment:
      - MCP_ENHANCED_JWT_SECRET=${JWT_SECRET}
      - MCP_ENHANCED_JWT_KID=frontend-enhanced
      - QUILT_CATALOG_URL=https://demo.quiltdata.com
      - FASTMCP_TRANSPORT=http
      - FASTMCP_HOST=0.0.0.0
      - FASTMCP_PORT=8000
    ports:
      - "8000:8000"
```

**ECS Task Definition:**

```json
{
  "containerDefinitions": [{
    "name": "quilt-mcp-server",
    "environment": [
      {
        "name": "MCP_ENHANCED_JWT_SECRET_SSM_PARAMETER",
        "value": "/quilt/mcp-server/jwt-secret"
      },
      {
        "name": "MCP_ENHANCED_JWT_KID",
        "value": "frontend-enhanced"
      },
      {
        "name": "QUILT_CATALOG_URL",
        "value": "https://demo.quiltdata.com"
      }
    ]
  }]
}
```

## Verification

### Step 4: Test Deployment

**Health Check:**
```bash
curl https://demo.quiltdata.com/mcp/healthz
# Expected: {"status": "ok"}
```

**JWT Diagnostics (via Qurator):**
```
Ask Qurator: "Check my JWT authentication status"
```

Expected response shows:
- `auth_scheme: "jwt"` ✅
- `buckets_count: 32` ✅
- `permissions_count: 24` ✅

### Step 5: Monitor CloudWatch Logs

```bash
aws logs tail /ecs/mcp-server-production --follow --region us-east-1
```

**Success Pattern:**
```
INFO: Session abc123: JWT authenticated for user testuser (buckets=32, permissions=24)
INFO: Using cached JWT auth for session abc123
INFO: ✅ Using JWT-based S3 client for bucket_objects_list
```

**Failure Pattern:**
```
ERROR: JWT validation failed: Signature verification failed
ERROR: JWT authorization failed: JWT authentication required
```

## Troubleshooting

### Issue: "Signature verification failed"

**Cause:** JWT secrets don't match between frontend and backend

**Fix:**
1. Get frontend secret:
   ```javascript
   // Browser console
   const tokenGen = window.__dynamicAuthManager?.tokenGenerator
   console.log('Secret:', tokenGen?.signingSecret)
   console.log('Length:', tokenGen?.signingSecret?.length)
   ```

2. Compare with backend:
   ```bash
   aws ecs describe-task-definition \
     --task-definition quilt-mcp-server \
     --query 'taskDefinition.containerDefinitions[0].environment[?name==`MCP_ENHANCED_JWT_SECRET`]'
   ```

3. Update task definition if they don't match

### Issue: Tools use IAM role instead of JWT

**Cause:** Authorization header not being sent or JWT validation failing

**Fix:**
1. Check browser console for outgoing requests
2. Verify `Authorization: Bearer` header is present
3. Run `jwt_diagnostics` tool via Qurator
4. Check CloudWatch logs for authentication errors

### Issue: No buckets/permissions in JWT

**Cause:** Frontend not including authorization data in token

**Fix:**
1. Verify frontend token includes `buckets` and `permissions` claims
2. Check role mappings in `AWSBucketDiscoveryService`
3. Ensure token generation includes user's AWS access

## Security Best Practices

1. **Strong Secrets**: Use 55+ character cryptographically secure secrets
2. **HTTPS Only**: Always use TLS for JWT transmission
3. **Short Expiration**: Tokens should expire in < 24 hours
4. **Secret Rotation**: Rotate JWT secrets periodically
5. **Monitoring**: Track authentication failures in CloudWatch

## References

- **Architecture Details**: [JWT_ARCHITECTURE.md](../JWT_ARCHITECTURE.md)
- **Bearer Auth Service**: `src/quilt_mcp/services/bearer_auth_service.py`
- **JWT Decoder**: `src/quilt_mcp/services/jwt_decoder.py`
- **Session Manager**: `src/quilt_mcp/services/session_auth.py`

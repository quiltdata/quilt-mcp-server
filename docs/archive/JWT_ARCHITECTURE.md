# JWT Authentication Architecture

## Overview

The Quilt MCP Server uses JWT-based authentication with enhanced tokens from the Quilt frontend.
This document explains the **current** architecture and how it works.

## Current Architecture (2025-09-25)

### Authentication Flow

```
┌──────────────┐    JWT Bearer    ┌──────────────────┐    AWS      ┌──────────────────┐
│   Quilt      │    Token        │   MCP Server     │   Creds     │   S3/Athena/     │
│   Frontend   ├─────────────────►│   + FastMCP      ├────────────►│   Quilt Registry │
└──────────────┘                  └──────────────────┘             └──────────────────┘
```

1. **Frontend**: User authenticates with Quilt via OAuth2
2. **JWT Generation**: Frontend generates enhanced JWT with user's AWS credentials/role
3. **Request**: Frontend sends JWT in `Authorization: Bearer <token>` header
4. **Validation**: MCP server validates JWT signature using shared secret
5. **Session Cache**: Server caches validated JWT by MCP session ID
6. **AWS Operations**: All tools use JWT-derived boto3 session (not IAM role)

### Key Principle: JWT-Only, No IAM Fallback

**Critical**: The server **enforces** JWT authentication. There is **NO** fallback to IAM roles for bucket/package operations.

- `/healthz` endpoint: Unauthenticated (for load balancers)
- MCP session initialization: Unauthenticated (protocol requirement)
- All tool operations: **Require** valid JWT, fail if missing

## JWT Token Structure

### Compressed Format (Sent by Frontend)

The frontend sends tokens with abbreviated field names to stay under 8KB:

```json
{
  "iss": "quilt-frontend",
  "aud": "quilt-mcp-server",
  "sub": "user-id",
  "iat": 1758740633,
  "exp": 1758827033,

  // Abbreviated claims (compressed)
  "s": "w",                        // scope
  "p": ["g", "p", "d", "l"],       // permissions
  "r": ["ReadWriteQuiltV2-sales"], // roles
  "b": {                           // buckets (grouped)
    "_type": "groups",
    "_data": {
      "quilt": ["sandbox-bucket", "sales-raw"],
      "cell": ["cellpainting-gallery"]
    }
  },
  "l": "write",                    // level

  // Expanded claims (for compatibility)
  "scope": "w",
  "permissions": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
  "roles": ["ReadWriteQuiltV2-sales"],
  "buckets": ["quilt-sandbox-bucket", "quilt-sales-raw", "cellpainting-gallery"],
  "level": "write",

  // AWS credentials (embedded)
  "aws_credentials": {
    "access_key_id": "ASIA...",
    "secret_access_key": "...",
    "session_token": "...",
    "region": "us-east-1"
  }
}
```

### Permission Abbreviations

| Abbr | Full Permission |
|------|-----------------|
| `g`  | `s3:GetObject` |
| `p`  | `s3:PutObject` |
| `d`  | `s3:DeleteObject` |
| `l`  | `s3:ListBucket` |
| `la` | `s3:ListAllMyBuckets` |
| `gv` | `s3:GetObjectVersion` |

### Bucket Compression Format

The `b` field uses grouped compression to minimize token size:

```json
{
  "_type": "groups",
  "_data": {
    "quilt": ["sandbox-bucket", "sales-raw"],
    "cell": ["cellpainting-gallery"]
  }
}
```

Decompresses to: `["quilt-sandbox-bucket", "quilt-sales-raw", "cellpainting-gallery"]`

## Implementation Details

### 1. JWT Validation (`BearerAuthService`)

Location: `src/quilt_mcp/services/bearer_auth_service.py`

**Process:**

1. Extract `Authorization: Bearer <token>` header
2. Decode JWT using `MCP_ENHANCED_JWT_SECRET`
3. Validate signature, issuer, audience, expiration
4. Decompress abbreviated claims
5. Extract AWS credentials from payload
6. Return `JwtAuthResult` with boto3 session

**Secret Management:**

- Primary: `MCP_ENHANCED_JWT_SECRET` environment variable
- Fallback: `MCP_ENHANCED_JWT_SECRET_SSM_PARAMETER` (AWS SSM)
- Caches SSM lookups per `(parameter, region)` tuple

### 2. JWT Decompression (`JwtDecoder`)

Location: `src/quilt_mcp/services/jwt_decoder.py`

**Strategy:**

1. **Prefer expanded fields**: Use `permissions`, `buckets`, `roles` when present
2. **Fall back to abbreviated**: Decompress `p`, `b`, `r` if expanded missing
3. **Validate results**: Ensure bucket count matches expectations (max 32)
4. **Fail if invalid**: Return error if validation fails

**Bucket Decompression:**

```python
# Handles three formats:
# 1. Groups: {"_type": "groups", "_data": {"prefix": ["bucket1"]}}
# 2. Patterns: {"_type": "patterns", "_data": {"prefix": ["pattern"]}}
# 3. Compressed: {"_type": "compressed", "_data": "base64..."}
```

### 3. Session Management (`SessionAuthManager`)

Location: `src/quilt_mcp/services/session_auth.py`

**Purpose:** Cache validated JWT auth by MCP session ID to avoid repeated validation.

**Lifecycle:**

1. **First Request**: Validate JWT, create boto3 session, cache by session ID
2. **Subsequent Requests**: Check cache, reuse boto3 session
3. **Expiration**: Sessions expire after 1 hour (from creation time)

**Storage:**

```python
{
  "session_id": {
    "jwt_result": JwtAuthResult,
    "boto3_session": boto3.Session,
    "created_at": datetime,
    "user_id": str
  }
}
```

### 4. Middleware (`QuiltAuthMiddleware`)

Location: `src/quilt_mcp/middleware/auth.py`

**Responsibilities:**

1. Extract `Authorization` and `mcp-session-id` headers
2. Set runtime context environment (web-jwt, web-bearer, etc.)
3. Validate JWT on first request per session
4. Allow unauthenticated requests for `/healthz` and MCP initialization
5. Return 401 for missing/invalid JWT on tool operations

### 5. Tool Authorization

Location: `src/quilt_mcp/services/bearer_auth_service.py`

**Per-Tool Permissions:**

```python
{
    "bucket_objects_list": ["s3:ListBucket", "s3:GetBucketLocation"],
    "bucket_object_fetch": ["s3:GetObject"],
    "package_create": ["s3:ListBucket", "s3:GetObject", "s3:PutObject"],
    # ... etc
}
```

**Authorization Checks:**

1. User has required permissions for the tool
2. User has access to the target bucket
3. JWT session is cached and valid
4. Return JWT-derived S3 client or error

## Environment Configuration

### Required Variables

```bash
# JWT Secret (choose one)
MCP_ENHANCED_JWT_SECRET=your-jwt-secret-here
# OR
MCP_ENHANCED_JWT_SECRET_SSM_PARAMETER=/quilt/mcp-server/jwt-secret
AWS_REGION=us-east-1

# JWT Key ID
MCP_ENHANCED_JWT_KID=frontend-enhanced

# Quilt Catalog
QUILT_CATALOG_URL=https://your-catalog.quiltdata.com
QUILT_DEFAULT_BUCKET=your-default-bucket
```

### Docker/ECS Deployment

```dockerfile
ENV FASTMCP_TRANSPORT=http
ENV FASTMCP_HOST=0.0.0.0
ENV FASTMCP_PORT=8000
ENV MCP_ENHANCED_JWT_SECRET=<secret>
ENV MCP_ENHANCED_JWT_KID=frontend-enhanced
ENV QUILT_CATALOG_URL=https://demo.quiltdata.com
```

## Diagnostic Tools

Three MCP tools are available for troubleshooting:

### 1. `jwt_diagnostics`

**Usage:** Ask Qurator: "Check my JWT authentication status"

**Returns:**

- Runtime environment
- Auth scheme (jwt, bearer, role, etc.)
- Session cache stats
- JWT claims (buckets, permissions, roles)
- Recommendations

### 2. `validate_jwt_token`

**Usage:** Ask Qurator: "Validate my JWT token"

**Returns:**

- Token validation result (pass/fail)
- Header and payload details
- Secret configuration comparison
- Specific fix recommendations

### 3. `session_diagnostics`

**Usage:** Ask Qurator: "Show session diagnostics"

**Returns:**

- Active sessions
- Session ages and idle times
- User information per session

## Security Considerations

### Production Requirements

1. **Strong JWT Secret**: Use cryptographically secure, 55+ character secret
2. **HTTPS Only**: Always use TLS for JWT transmission
3. **Short Token Expiration**: Frontend uses tokens < 24 hours
4. **Secret Rotation**: Periodically rotate JWT secret
5. **Audience Validation**: Ensure `aud` claim matches your server
6. **Monitoring**: Log authentication attempts and failures

### Secret Management

**Recommended:** Use AWS Systems Manager Parameter Store

```bash
# Store secret
aws ssm put-parameter \
  --name "/quilt/mcp-server/jwt-secret" \
  --value "your-55-char-secret-here" \
  --type "SecureString" \
  --region us-east-1

# Reference in ECS task definition
{
  "name": "MCP_ENHANCED_JWT_SECRET",
  "valueFrom": "arn:aws:ssm:us-east-1:123456789012:parameter/quilt/mcp-server/jwt-secret"
}
```

## Testing

### Unit Tests

```bash
# JWT decompression
uv run pytest tests/unit/test_jwt_decompression.py -v

# Session caching
uv run pytest tests/unit/test_session_auth.py -v

# Bearer auth service
uv run pytest tests/unit/test_auth_service.py -v
```

### Integration Tests

```bash
# With JWT token
QUILT_ACCESS_TOKEN=eyJhbG... uv run pytest tests/integration/
```

### Local Testing

```bash
# Test with curl
curl -H "Authorization: Bearer eyJhbG..." \
     http://localhost:8000/mcp/tools/bucket_objects_list
```

## Troubleshooting

### Issue: JWT Validation Fails

**Symptom:** "JWT token could not be verified"

**Diagnosis:**

```
Ask Qurator: "Validate my JWT token"
```

**Solution:**

1. Verify frontend and backend secrets match exactly (case-sensitive)
2. Check secret length (should be 55 chars, not 31)
3. Verify `kid` matches in both frontend and backend

### Issue: Tools Use IAM Role Instead of JWT

**Symptom:** CloudWatch logs show "Using IAM role" instead of JWT

**Diagnosis:**

```
Ask Qurator: "Check my JWT authentication status"
```

**Solution:**

1. Ensure `Authorization: Bearer` header is being sent
2. Check middleware is setting runtime context correctly
3. Verify bucket tools call JWT auth helpers (not legacy paths)

### Issue: Session Not Cached

**Symptom:** JWT validation happens on every request (slow)

**Diagnosis:**

```
Ask Qurator: "Show session diagnostics"
```

**Solution:**

1. Check `mcp-session-id` header is being sent
2. Verify session manager is initialized
3. Check for session expiration (1 hour default)

## CloudWatch Log Patterns

### Successful Flow

```
INFO: MCP request: method=POST path=/mcp session=abc123 has_auth=True
INFO: Session abc123: JWT authenticated for user testuser (buckets=32, permissions=24)
INFO: Cached auth for session abc123
INFO: Using cached JWT auth for session abc123
INFO: ✅ Using JWT-based S3 client for bucket_objects_list
```

### Failed Flow

```
ERROR: Session abc123 authentication failed: JWT token could not be verified
ERROR: JWT validation failed: Signature verification failed
WARNING: JWT authorization failed: JWT authentication required
```

## Migration Notes

### From OAuth2 to JWT

1. Deploy MCP server with JWT secret configured
2. Update frontend to generate enhanced JWTs
3. Test with both OAuth2 and JWT (parallel)
4. Monitor authentication success/failure rates
5. Gradually migrate users to JWT-based access
6. Deprecate OAuth2 once migration complete

## References

- **Bearer Auth Service**: `src/quilt_mcp/services/bearer_auth_service.py`
- **JWT Decoder**: `src/quilt_mcp/services/jwt_decoder.py`
- **Session Manager**: `src/quilt_mcp/services/session_auth.py`
- **Middleware**: `src/quilt_mcp/middleware/auth.py`
- **Runtime Context**: `src/quilt_mcp/runtime_context.py`

## Summary

The current JWT architecture:

✅ **JWT-only authentication** - No IAM fallback for tool operations
✅ **Session caching** - Validates once per session, reuses credentials
✅ **Compressed tokens** - Stays under 8KB size limit
✅ **Diagnostic tools** - Built-in troubleshooting via Qurator
✅ **Security-first** - Signature validation, expiration, audience checks
✅ **Production-ready** - Deployed and tested on demo.quiltdata.com

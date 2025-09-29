# JWT Authentication for Quilt MCP Server

This guide explains how to deploy and configure JWT-based authentication for the Quilt MCP server, following patterns from the quiltdata/quilt repository.

## Overview

The Quilt MCP server supports JWT-based authentication with enhanced tokens from the Quilt frontend. These tokens use compression to stay under the 8KB limit while providing comprehensive authorization information.

### Authentication Flow

```
┌──────────────┐         ┌──────────────────┐         ┌──────────────────┐
│   Quilt      │  JWT    │   MCP Server     │  AWS    │   S3/Athena/     │
│   Frontend   ├────────►│   + FastMCP      ├────────►│   Quilt Registry │
└──────────────┘         └──────────────────┘         └──────────────────┘
```

1. User authenticates with Quilt frontend (OAuth2)
2. Frontend generates compressed JWT with user's AWS credentials/role
3. Frontend sends JWT in `Authorization: Bearer <token>` header
4. MCP server validates and decompresses JWT
5. MCP server uses AWS credentials/role from JWT for operations

## JWT Token Structure

### Compressed Format

The frontend sends tokens with abbreviated field names to save space:

```json
{
  "iss": "quilt-frontend",
  "aud": "quilt-mcp-server",
  "sub": "user-id",
  "iat": 1758740633,
  "exp": 1758827033,
  "jti": "1a2b3c4d5e",
  "s": "w",                        // scope (abbreviated)
  "p": ["g", "p", "d", "l"],       // permissions (abbreviated)
  "r": ["ReadWriteQuiltV2-sales"], // roles
  "b": {                           // buckets (compressed)
    "_type": "groups",
    "_data": {
      "quilt": ["sandbox-bucket", "sales-raw"],
      "cell": ["cellpainting-gallery"]
    }
  },
  "l": "write",                    // level (abbreviated)
  
  // Expanded fields for compatibility
  "scope": "w",
  "permissions": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
  "roles": ["ReadWriteQuiltV2-sales"],
  "buckets": ["quilt-sandbox-bucket", "quilt-sales-raw", "cellpainting-gallery"],
  "level": "write",
  
  // Optional AWS credentials
  "aws_credentials": {
    "access_key_id": "ASIA...",
    "secret_access_key": "...",
    "session_token": "...",
    "region": "us-east-1"
  },
  
  // Or AWS role ARN for assumption
  "aws_role_arn": "arn:aws:iam::123456789012:role/QuiltUserRole"
}
```

### Bucket Compression Formats

The MCP server supports three bucket compression formats:

#### 1. Groups Format
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

#### 2. Patterns Format
```json
{
  "_type": "patterns",
  "_data": {
    "quilt": ["sandbox-bucket"],
    "other": ["data-drop-off-bucket"]
  }
}
```

#### 3. Compressed Format
```json
{
  "_type": "compressed",
  "_data": "eyJxdWlsdC1zYW5kYm94LWJ1Y2tldCI..." // base64 encoded JSON
}
```

### Permission Abbreviations

| Abbreviation | Full Permission |
|--------------|-----------------|
| `g` | `s3:GetObject` |
| `p` | `s3:PutObject` |
| `d` | `s3:DeleteObject` |
| `l` | `s3:ListBucket` |
| `la` | `s3:ListAllMyBuckets` |
| `gv` | `s3:GetObjectVersion` |
| `pa` | `s3:PutObjectAcl` |
| `amu` | `s3:AbortMultipartUpload` |

## Environment Configuration

### Required Environment Variables

```bash
# JWT Configuration
MCP_ENHANCED_JWT_SECRET=your-jwt-secret-here
MCP_ENHANCED_JWT_KID=frontend-enhanced

# Quilt Catalog Configuration
QUILT_CATALOG_URL=https://your-catalog.quiltdata.com
QUILT_DEFAULT_BUCKET=your-default-bucket

# AWS Configuration (for IAM role-based auth)
AWS_DEFAULT_REGION=us-east-1
```

### Docker Deployment

For Docker/ECS deployments, the MCP server can use:

1. **JWT with embedded AWS credentials** - Frontend includes temporary AWS credentials in JWT
2. **JWT with role ARN** - Frontend includes role ARN, server assumes it
3. **ECS task role** - Server uses IAM role attached to ECS task

Example docker-compose.yml:

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

## Implementation Details

### JWT Validation

The MCP server validates JWTs in the following order:

1. Check for `Authorization: Bearer <token>` header
2. Decode JWT using configured secret
3. Validate standard claims (iss, aud, exp)
4. Decompress abbreviated claims
5. Extract AWS credentials or role ARN
6. Create boto3 session for AWS operations

See `src/quilt_mcp/services/bearer_auth_service.py` for implementation.

### Decompression

The JWT decompression follows this strategy:

1. **Prefer expanded fields** - Use `permissions`, `buckets`, `roles`, `scope`, `level` when present
2. **Fall back to abbreviated** - Decompress `p`, `b`, `r`, `s`, `l` if expanded fields missing
3. **Validate results** - Ensure bucket count matches expected values
4. **Provide defaults** - Fall back to read-only access if validation fails

See `src/quilt_mcp/services/jwt_decoder.py` for implementation.

### Tool Authorization

Each MCP tool has required permissions defined in the bearer auth service:

```python
{
    "bucket_objects_list": ["s3:ListBucket", "s3:GetBucketLocation"],
    "bucket_object_fetch": ["s3:GetObject"],
    "package_create": ["s3:ListBucket", "s3:GetObject", "s3:PutObject"],
    ...
}
```

The server checks:
1. User has required permissions for the tool
2. User has access to the target bucket (if applicable)

## Testing

### Local Testing

1. Generate a test JWT using the frontend token generator
2. Set the JWT secret in environment variables
3. Send requests with `Authorization: Bearer <token>` header

```bash
# Test with curl
curl -H "Authorization: Bearer eyJhbG..." \
     http://localhost:8000/mcp/packages/browse?package_name=user/dataset
```

### Integration Testing

The repository includes integration tests for JWT authentication:

```bash
# Run JWT-specific tests
uv run pytest tests/integration/test_jwt_auth.py -v

# Run with bearer token
QUILT_ACCESS_TOKEN=eyJhbG... uv run pytest tests/integration/
```

## Security Considerations

### Production Deployment

1. **Use strong JWT secrets** - Generate cryptographically secure secrets
2. **Enable HTTPS** - Always use TLS for JWT transmission
3. **Set appropriate token expiration** - Frontend should use short-lived tokens (< 24 hours)
4. **Rotate secrets regularly** - Update JWT secret periodically
5. **Validate audience** - Ensure `aud` claim matches your server
6. **Monitor token usage** - Log authentication attempts and failures

### IAM Role-Based Auth

For ECS deployments, consider using IAM roles instead of embedded credentials:

1. Frontend includes role ARN in JWT
2. MCP server assumes role using ECS task role
3. Provides better audit trail (via CloudTrail)
4. Avoids embedding credentials in JWTs

## Troubleshooting

### Common Issues

#### JWT Validation Fails

```
ERROR: JWT token could not be verified
```

**Solution**: Check that `MCP_ENHANCED_JWT_SECRET` matches the frontend's secret.

#### Bucket Access Denied

```
ERROR: Access denied to bucket my-bucket
```

**Solution**: Verify the JWT includes the bucket in the `buckets` claim.

#### Permission Denied

```
ERROR: Missing required permission(s): s3:PutObject
```

**Solution**: Check the user's role includes write permissions.

### Debug Logging

Enable debug logging to see JWT decompression details:

```bash
export LOG_LEVEL=DEBUG
uv run quilt-mcp
```

This will log:
- JWT payload after decompression
- Permission and bucket validation
- AWS credential retrieval
- Tool authorization decisions

## References

- Quilt JWT Compression Format: `catalog/app/services/JWTCompressionFormat.md` in quiltdata/quilt
- MCP Server JWT Guide: `catalog/app/services/MCP_Server_JWT_Decompression_Guide.md` in quiltdata/quilt
- Bearer Auth Service: `src/quilt_mcp/services/bearer_auth_service.py`
- JWT Decoder: `src/quilt_mcp/services/jwt_decoder.py`
- Authentication Service: `src/quilt_mcp/services/auth_service.py`

## Migration from OAuth2

If migrating from OAuth2-only authentication:

1. Update frontend to generate enhanced JWTs
2. Deploy MCP server with JWT secret configured
3. Test with both OAuth2 and JWT (parallel deployment)
4. Gradually migrate users to JWT-based access
5. Monitor for authentication failures
6. Deprecate OAuth2 once migration complete

## Next Steps

- Review [AUTHENTICATION.md](./AUTHENTICATION.md) for overall auth architecture
- See [DEPLOYMENT.md](../DEPLOYMENT.md) for deployment options
- Check [TESTING.md](./TESTING.md) for testing procedures

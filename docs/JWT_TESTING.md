# JWT Testing with mcp-test.py

## Overview

The `mcp-test.py` script supports JWT authentication for testing stateless MCP deployments that require JWT tokens. This enables end-to-end testing of JWT-authenticated MCP servers.

## Quick Start

1. **Generate a test JWT token:**

   ```bash
   python scripts/tests/jwt_helper.py generate \
     --role-arn "arn:aws:iam::123456789012:role/TestRole" \
     --secret "test-secret-key" \
     --expiry 3600
   ```

2. **Run tests with JWT token:**

   ```bash
   # Using environment variable (recommended)
   export MCP_JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
   python scripts/mcp-test.py http://localhost:8000/mcp --tools-test --resources-test

   # Using command-line argument
   python scripts/mcp-test.py http://localhost:8000/mcp \
     --jwt-token "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     --tools-test --resources-test
   ```

## JWT Token Generation

### Using jwt_helper.py

The `scripts/tests/jwt_helper.py` utility generates HS256 JWT tokens for testing:

```bash
# Basic token generation
python scripts/tests/jwt_helper.py generate \
  --role-arn "arn:aws:iam::123456789012:role/TestRole" \
  --secret "your-jwt-secret"

# Token with custom expiry (2 hours)
python scripts/tests/jwt_helper.py generate \
  --role-arn "arn:aws:iam::123456789012:role/TestRole" \
  --secret "your-jwt-secret" \
  --expiry 7200

# Token with session tags
python scripts/tests/jwt_helper.py generate \
  --role-arn "arn:aws:iam::123456789012:role/TestRole" \
  --secret "your-jwt-secret" \
  --session-tags '{"Environment": "test", "Project": "mcp"}'
```

### Token Format and Claims

Generated JWT tokens include these claims:

**Standard Claims:**

- `iss` (issuer): "mcp-test" (configurable)
- `aud` (audience): "mcp-server" (configurable)  
- `iat` (issued at): Current timestamp
- `exp` (expires): Current timestamp + expiry seconds
- `sub` (subject): "test-user"

**MCP-Specific Claims:**

- `role_arn`: AWS IAM role ARN to assume
- `external_id`: Optional external ID for role assumption
- `session_tags`: Optional AWS session tags

### Manual Token Creation

For production testing, generate tokens using your auth system. Ensure tokens include:

1. **Required claims:** `role_arn` with valid AWS IAM role
2. **Proper signature:** HS256 algorithm with matching secret
3. **Valid expiry:** `exp` claim in the future
4. **Correct audience:** `aud` claim matching server expectation

## Testing Scenarios

### Local Development with JWT

1. **Start MCP server in JWT mode:**

   ```bash
   export MCP_REQUIRE_JWT=true
   export MCP_JWT_SECRET="your-secret-key"
   python -m quilt_mcp.main
   ```

2. **Generate test token:**

   ```bash
   JWT_TOKEN=$(python scripts/tests/jwt_helper.py generate \
     --role-arn "arn:aws:iam::123456789012:role/TestRole" \
     --secret "your-secret-key")
   ```

3. **Run tests:**

   ```bash
   export MCP_JWT_TOKEN="$JWT_TOKEN"
   python scripts/mcp-test.py http://localhost:8000/mcp --tools-test
   ```

### CI/CD with Programmatic Tokens

```bash
# In CI pipeline
JWT_TOKEN=$(python scripts/tests/jwt_helper.py generate \
  --role-arn "$TEST_ROLE_ARN" \
  --secret "$JWT_SECRET" \
  --expiry 1800)

export MCP_JWT_TOKEN="$JWT_TOKEN"
make test-stateless-mcp
```

### Manual Testing with Real Tokens

```bash
# Use token from your auth system
export MCP_JWT_TOKEN="<real-jwt-token-from-auth-system>"
python scripts/mcp-test.py https://your-mcp-server.com/mcp --tools-test
```

## Troubleshooting

### 401 Unauthorized Errors

**Error:** "Authentication failed: JWT token rejected"

**Possible causes:**

- Token signature doesn't match server's JWT_SECRET
- Token has expired (check `exp` claim)
- Token missing required claims (`role_arn`, etc.)

**Solutions:**

1. Verify JWT_SECRET matches between client and server
2. Generate new token with longer expiry
3. Check token claims with inspect command:

   ```bash
   python scripts/tests/jwt_helper.py inspect \
     --token "$JWT_TOKEN" --secret "$JWT_SECRET"
   ```

### 403 Forbidden Errors

**Error:** "Authorization failed: Insufficient permissions"

**Possible causes:**

- JWT `role_arn` lacks necessary AWS permissions
- Session tags don't provide required access
- Role assumption failed

**Solutions:**

1. Verify IAM role has required permissions
2. Check role trust policy allows assumption
3. Review session tags in JWT claims

### Token Expiration

**Error:** Token expired

**Solutions:**

1. Generate new token:

   ```bash
   JWT_TOKEN=$(python scripts/tests/jwt_helper.py generate \
     --role-arn "$ROLE_ARN" --secret "$SECRET" --expiry 3600)
   ```

2. Use longer expiry for long-running tests
3. Implement token refresh in test automation

### Signature Mismatches

**Error:** "JWT token rejected (invalid signature)"

**Solutions:**

1. Ensure JWT_SECRET matches exactly between client and server
2. Check for whitespace or encoding issues in secret
3. Verify HS256 algorithm is used

## Security Best Practices

### Token Storage

- ✅ **Use environment variables:** `MCP_JWT_TOKEN`
- ✅ **Secure secret management:** Store JWT_SECRET securely
- ❌ **Never commit tokens:** Don't put tokens in code/config files
- ❌ **Avoid command-line args:** Process lists may expose tokens

### Token Lifecycle

- ✅ **Short expiry:** Use 1-hour expiry for test tokens
- ✅ **Rotate regularly:** Generate new tokens frequently
- ✅ **Scope appropriately:** Use minimal required permissions
- ❌ **Don't reuse:** Generate fresh tokens for each test run

### Development vs Production

- ✅ **Test tokens:** Use jwt_helper.py for development/CI
- ✅ **Production tokens:** Use proper auth system for real deployments
- ✅ **Separate secrets:** Different JWT_SECRET for each environment
- ❌ **Don't mix:** Never use test tokens in production

## Integration with Make Targets

### test-stateless-mcp

The `test-stateless-mcp` make target automatically generates JWT tokens and runs comprehensive tests:

```bash
make test-stateless-mcp
```

This target:

1. Generates test JWT token using jwt_helper.py
2. Starts Docker container in JWT mode with stateless constraints
3. Runs mcp-test.py with JWT authentication
4. Tests both tools and resources
5. Cleans up container on completion

### Manual Docker Testing

```bash
# Start container with JWT enabled
docker run -d --name mcp-jwt-test \
  -e MCP_REQUIRE_JWT=true \
  -e MCP_JWT_SECRET="test-secret" \
  -p 8000:8000 \
  quilt-mcp:test

# Generate token and test
JWT_TOKEN=$(python scripts/tests/jwt_helper.py generate \
  --role-arn "arn:aws:iam::123456789012:role/TestRole" \
  --secret "test-secret")

python scripts/mcp-test.py http://localhost:8000/mcp \
  --jwt-token "$JWT_TOKEN" --tools-test

# Cleanup
docker stop mcp-jwt-test && docker rm mcp-jwt-test
```

## Command Reference

### mcp-test.py JWT Options

```bash
python scripts/mcp-test.py [endpoint] [options]

JWT Authentication:
  --jwt-token TOKEN    JWT token for authentication (HTTP only)
                      Alternative: set MCP_JWT_TOKEN env var
                      ⚠️  Prefer env var to avoid token exposure

Environment Variables:
  MCP_JWT_TOKEN       JWT token (preferred over --jwt-token)

Examples:
  # Environment variable (recommended)
  export MCP_JWT_TOKEN="eyJhbG..."
  python scripts/mcp-test.py http://localhost:8000/mcp --tools-test

  # Command line argument
  python scripts/mcp-test.py http://localhost:8000/mcp \
    --jwt-token "eyJhbG..." --tools-test
```

### jwt_helper.py Commands

```bash
# Generate token
python scripts/tests/jwt_helper.py generate \
  --role-arn ARN --secret SECRET [options]

# Inspect token
python scripts/tests/jwt_helper.py inspect \
  --token TOKEN --secret SECRET

Options for generate:
  --expiry SECONDS     Token expiry (default: 3600)
  --external-id ID     External ID for role assumption
  --session-tags JSON  Session tags as JSON string
  --issuer ISSUER      Token issuer (default: mcp-test)
  --audience AUDIENCE  Token audience (default: mcp-server)
```

## Examples

### Complete Testing Workflow

```bash
#!/bin/bash
# Complete JWT testing workflow

# 1. Set up environment
export JWT_SECRET="test-secret-for-development"
export ROLE_ARN="arn:aws:iam::123456789012:role/TestRole"

# 2. Start MCP server with JWT
export MCP_REQUIRE_JWT=true
export MCP_JWT_SECRET="$JWT_SECRET"
python -m quilt_mcp.main &
SERVER_PID=$!

# Wait for server startup
sleep 3

# 3. Generate JWT token
JWT_TOKEN=$(python scripts/tests/jwt_helper.py generate \
  --role-arn "$ROLE_ARN" \
  --secret "$JWT_SECRET" \
  --expiry 1800)

# 4. Run comprehensive tests
export MCP_JWT_TOKEN="$JWT_TOKEN"
python scripts/mcp-test.py http://localhost:8000/mcp \
  --tools-test --resources-test --verbose

# 5. Cleanup
kill $SERVER_PID
```

### Docker Integration Testing

```bash
#!/bin/bash
# Docker-based JWT integration testing

# Build test image
docker build -t quilt-mcp:jwt-test .

# Run with JWT constraints (same as test-stateless)
JWT_TOKEN=$(python scripts/tests/jwt_helper.py generate \
  --role-arn "arn:aws:iam::123456789012:role/TestRole" \
  --secret "test-secret-key" \
  --expiry 3600)

docker run --rm \
  --read-only \
  --security-opt=no-new-privileges:true \
  --cap-drop=ALL \
  --tmpfs=/tmp:size=100M,mode=1777 \
  --tmpfs=/run:size=10M,mode=755 \
  --memory=512m --memory-swap=512m \
  --cpu-quota=100000 --cpu-period=100000 \
  -e MCP_REQUIRE_JWT=true \
  -e MCP_JWT_SECRET="test-secret-key" \
  -e QUILT_DISABLE_CACHE=true \
  -e HOME=/tmp \
  -e QUILT_MCP_STATELESS_MODE=true \
  -p 8000:8000 \
  quilt-mcp:jwt-test &

# Test with JWT
sleep 3
python scripts/mcp-test.py http://localhost:8000/mcp \
  --jwt-token "$JWT_TOKEN" --tools-test --resources-test
```

## Related Documentation

- [MCP Protocol Testing](../spec/a11-client-testing/01-protocol-testing.md)
- [Stateless Architecture](../spec/a10-multitenant/01-stateless.md)
- [JWT Authentication Implementation](../spec/a10-multitenant/04-finish-jwt.md)

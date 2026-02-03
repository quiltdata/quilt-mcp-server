# JWT Testing with mcp-test.py

## Overview

The `mcp-test.py` script supports JWT authentication for testing stateless MCP deployments that require Platform-style JWT tokens.

Platform JWTs contain only:

- `id`
- `uuid`
- `exp`

## Quick Start

1. **Generate a test JWT token:**

   ```bash
   python tests/jwt_helpers.py generate \
     --secret "test-secret-key" \
     --id "user-123" \
     --uuid "uuid-123" \
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

### Using tests/jwt_helpers.py

```bash
# Basic token generation
python tests/jwt_helpers.py generate \
  --secret "your-jwt-secret" \
  --id "user-123" \
  --uuid "uuid-123"

# Token with custom expiry (2 hours)
python tests/jwt_helpers.py generate \
  --secret "your-jwt-secret" \
  --id "user-123" \
  --uuid "uuid-123" \
  --expiry 7200
```

### Token Format and Claims

Generated JWT tokens include these claims:

**Required Claims:**

- `id` (user identifier)
- `uuid` (user UUID)
- `exp` (expiration timestamp)

**Optional Standard Claims:**

- `iss` (issuer)
- `aud` (audience)

### Manual Token Creation

For production testing, generate tokens using your auth system. Ensure tokens include:

1. **Required claims:** `id`, `uuid`, `exp`
2. **Proper signature:** HS256 algorithm with matching secret
3. **Valid expiry:** `exp` claim in the future
4. **Correct audience/issuer:** if your server validates them

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
   JWT_TOKEN=$(python tests/jwt_helpers.py generate \
     --secret "your-secret-key" \
     --id "user-123" \
     --uuid "uuid-123")
   ```

3. **Run tests:**

   ```bash
   export MCP_JWT_TOKEN="$JWT_TOKEN"
   python scripts/mcp-test.py http://localhost:8000/mcp --tools-test
   ```

### CI/CD with Programmatic Tokens

```bash
# In CI pipeline
JWT_TOKEN=$(python tests/jwt_helpers.py generate \
  --secret "$JWT_SECRET" \
  --id "$TEST_USER_ID" \
  --uuid "$TEST_USER_UUID" \
  --expiry 1800)

export MCP_JWT_TOKEN="$JWT_TOKEN"
make test-stateless-mcp
```

## Troubleshooting

### 401 Unauthorized Errors

**Error:** "Authentication failed: JWT token rejected"

**Possible causes:**

- Token signature doesn't match server's JWT_SECRET
- Token has expired (check `exp` claim)
- Token missing required claims (`id`, `uuid`, `exp`)

**Solutions:**

1. Verify JWT_SECRET matches between client and server
2. Generate new token with longer expiry
3. Check token claims with inspect command:

   ```bash
   python tests/jwt_helpers.py inspect \
     --token "$JWT_TOKEN" --secret "$JWT_SECRET"
   ```

### 403 Forbidden Errors

**Error:** "Authorization failed: Insufficient permissions"

**Possible causes:**

- User does not have access to the requested resource
- Token is valid but not authorized for the platform tenant

**Solutions:**

1. Verify the user has access to the requested package/bucket
2. Confirm the token is issued for the correct platform tenant

### Token Expiration

**Error:** Token expired

**Solutions:**

1. Generate new token:

   ```bash
   JWT_TOKEN=$(python tests/jwt_helpers.py generate \
     --secret "$SECRET" --id "$USER_ID" --uuid "$USER_UUID" --expiry 3600)
   ```

2. Use longer expiry for long-running tests
3. Implement token refresh in test automation

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

- ✅ **Test tokens:** Use tests/jwt_helpers.py for development/CI
- ✅ **Production tokens:** Use proper auth system for real deployments
- ✅ **Separate secrets:** Different JWT_SECRET for each environment
- ❌ **Don't mix:** Never use test tokens in production

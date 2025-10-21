# JWT Authentication Merge Strategy

> **Goal**: Make both JWT (web) and IAM/quilt3 (desktop) authentication work in the same codebase.

## Current State

- **JWT Branch** (`doc/mcp-server-authentication`): JWT authentication works, IAM doesn't
- **Main Branch**: IAM/quilt3 authentication works, JWT doesn't
- **Both branches**: All tools already implemented and functional

## The Simple Solution

**Check for JWT at runtime. If present, use it. If absent, use IAM/quilt3.**

```python
def get_credentials():
    # Try JWT first
    jwt_result = get_runtime_jwt()
    if jwt_result:
        return jwt_result.credentials

    # Fall back to IAM/quilt3
    return get_iam_credentials()
```

That's it.

## Implementation Changes

### 1. Middleware - Stop Rejecting Missing JWTs

**Current** (JWT branch):

```python
if not auth_header:
    return JSONResponse(status_code=401, content={"error": "Missing JWT"})
```

**New**:

```python
if not auth_header:
    # No JWT - just don't set JWT context, let tools fall back to IAM
    return await call_next(request)
```

### 2. Auth Helpers - Add Fallback Logic

**Current** (JWT branch):

```python
def check_s3_authorization(tool_name, tool_args):
    jwt_result = _runtime_jwt_result()
    if not jwt_result:
        return {"authorized": False, "error": "JWT required"}
    # ... use JWT
```

**New**:

```python
def check_s3_authorization(tool_name, tool_args):
    # Try JWT first
    jwt_result = _runtime_jwt_result()
    if jwt_result:
        return _use_jwt_credentials(jwt_result)

    # Fall back to IAM/quilt3
    return _use_iam_credentials()
```

### 3. Optional - Strict Mode Environment Variable

Add `MCP_REQUIRE_JWT` environment variable for deployments that want to enforce JWT-only:

```python
REQUIRE_JWT = os.getenv("MCP_REQUIRE_JWT", "false").lower() == "true"

def check_s3_authorization(tool_name, tool_args):
    jwt_result = _runtime_jwt_result()
    if jwt_result:
        return _use_jwt_credentials(jwt_result)

    if REQUIRE_JWT:
        return {"authorized": False, "error": "JWT required but not provided"}

    return _use_iam_credentials()
```

## Files to Change

### Core Auth Logic (3 files)

1. **`src/quilt_mcp/utils.py`** - Middleware: Don't return 401 on missing JWT
2. **`src/quilt_mcp/tools/auth_helpers.py`** - Add IAM fallback to `check_s3_authorization` and `check_package_authorization`
3. **`src/quilt_mcp/services/auth_service.py`** - Add `_use_iam_credentials()` helper

### Tool Files (Already Working)

- All bucket tools already use `check_s3_authorization()`
- All package tools already use `check_package_authorization()`
- No changes needed to individual tools

## Testing

### Unit Tests

Add tests for both modes:

```python
def test_jwt_mode():
    """When JWT present, use JWT credentials."""
    # Set JWT in runtime context
    # Call tool
    # Verify JWT credentials used

def test_iam_fallback_mode():
    """When JWT absent, use IAM credentials."""
    # No JWT in runtime context
    # Call tool
    # Verify IAM credentials used
```

### Integration Tests

```python
def test_web_request_with_jwt():
    """Web requests with JWT header use JWT auth."""
    response = client.get("/tool", headers={"Authorization": "Bearer ..."})
    assert response.status_code == 200

def test_web_request_without_jwt():
    """Web requests without JWT header use IAM auth."""
    response = client.get("/tool")
    assert response.status_code == 200

def test_strict_mode():
    """Strict mode rejects missing JWT."""
    os.environ["MCP_REQUIRE_JWT"] = "true"
    response = client.get("/tool")
    assert response.status_code == 401
```

## Deployment Scenarios

### Development (Desktop)

```bash
# No JWT env vars set
# Uses IAM/quilt3 credentials
# Works like main branch
```

### Production (Web)

```bash
# JWT secret configured
MCP_ENHANCED_JWT_SECRET_SSM_PARAMETER=/quilt/mcp-server/jwt-secret

# Optional: Enforce JWT-only
MCP_REQUIRE_JWT=false  # Allow IAM fallback (default)
# OR
MCP_REQUIRE_JWT=true   # Require JWT, reject if missing
```

## Benefits

1. **Zero Breaking Changes**: Main branch behavior preserved when JWT absent
2. **Works Immediately**: JWT features available when JWT present
3. **Simple Logic**: One runtime check, two code paths
4. **Easy Testing**: Test both modes independently
5. **Flexible Deployment**: Configure strict/permissive mode per environment

## What This Is NOT

- ❌ Not adding new features
- ❌ Not changing tool signatures
- ❌ Not complex fallback chains
- ❌ Not optional authentication modes
- ❌ Not a phased migration plan

## What This IS

- ✅ Making both authentication methods work
- ✅ Runtime credential selection
- ✅ Backward compatible with main branch
- ✅ Forward compatible with JWT features
- ✅ Simple: check JWT, use it or don't

## Summary

The merge is straightforward:

1. Don't reject requests without JWT in middleware
2. Check for JWT in auth helpers
3. Use JWT if present, IAM if not
4. Done

Everything else already works. We're just connecting the two paths.

# Root Cause Found: Missing JWT Configuration

**Date:** 2026-02-05
**Status:** ✅ ROOT CAUSE IDENTIFIED
**Branch:** `a18-valid-jwts`

---

## Summary

**ROOT CAUSE:** Test container is missing required JWT environment variables (`MCP_JWT_ISSUER` and `MCP_JWT_AUDIENCE`), causing server initialization to fail.

**IMPACT:** Server crashes on startup when JWT middleware tries to initialize without proper configuration.

**FIX:** Add missing environment variables to `stateless_container` fixture.

---

## The Discovery Path

### 1. Tests Exist and Are Failing ✅

Found existing JWT tests in `tests/stateless/test_jwt_authentication.py`:
- `test_jwt_required_environment_variable` - PASSED ✅
- `test_request_without_jwt_fails_clearly` - FAILED ❌ (Connection reset)
- `test_request_with_malformed_jwt_fails_clearly` - FAILED ❌ (Connection reset)

### 2. JWT Middleware Exists and Looks Correct ✅

Found JWT middleware in `src/quilt_mcp/middleware/jwt_middleware.py`:
- Properly returns 401 for missing Authorization header (lines 47-53)
- Properly returns 401 for invalid Bearer format (lines 55-58)
- Properly returns 403 for invalid JWT (lines 68-74)

**Middleware code is CORRECT!**

### 3. JWT Decoder Requires Configuration ✅

Found JWT decoder in `src/quilt_mcp/services/jwt_decoder.py`:
- Requires `MCP_JWT_SECRET` (line 53)
- Requires `MCP_JWT_ISSUER` (line 149)
- Requires `MCP_JWT_AUDIENCE` (line 150)
- Raises `JwtConfigError` if any are missing

### 4. Test Container is Missing Configuration ❌

Found `stateless_container` fixture in `tests/conftest.py` (lines 556-565):

```python
environment={
    "QUILT_MULTIUSER_MODE": "true",    # ✅ Present
    "MCP_JWT_SECRET": "test-secret",   # ✅ Present
    "MCP_JWT_ISSUER": ???,             # ❌ MISSING!
    "MCP_JWT_AUDIENCE": ???,           # ❌ MISSING!
    "QUILT_DISABLE_CACHE": "true",
    "HOME": "/tmp",
    "LOG_LEVEL": "DEBUG",
    "FASTMCP_TRANSPORT": "http",
    "FASTMCP_HOST": "0.0.0.0",
    "FASTMCP_PORT": "8000",
}
```

---

## Why This Causes "Connection Reset"

### Failure Sequence

1. **Container starts** - Docker runs the image
2. **Python loads** - Application starts
3. **Server initialization begins** - `main.py` calls `run_server()`
4. **HTTP app creation** - `build_http_app()` called (line 694 in utils.py)
5. **Middleware initialization** - `JwtAuthMiddleware` instantiated (line 651 in utils.py)
6. **JWT decoder initialization** - `get_jwt_decoder()` called (line 34 in jwt_middleware.py)
7. **Configuration validation** - Checks for required env vars
8. **❌ CRASH** - Raises `JwtConfigError` because `MCP_JWT_ISSUER` missing

### Why "Connection Reset by Peer"

When the server crashes during initialization:
- Container is running (process started)
- Port is bound (listening)
- Client connects (TCP connection established)
- **Server crashes before HTTP response sent**
- TCP connection forcibly closed
- Client receives: `[Errno 54] Connection reset by peer`

This is a **crash**, not graceful error handling.

---

## The Fix

### Required Changes

**File:** `tests/conftest.py`
**Fixture:** `stateless_container` (starting at line 516)
**Change:** Add missing JWT environment variables

```python
environment={
    "QUILT_MULTIUSER_MODE": "true",
    "MCP_JWT_SECRET": "test-secret",
    "MCP_JWT_ISSUER": "test-issuer",      # ✅ ADD THIS
    "MCP_JWT_AUDIENCE": "test-audience",  # ✅ ADD THIS
    "QUILT_DISABLE_CACHE": "true",
    "HOME": "/tmp",
    "LOG_LEVEL": "DEBUG",
    "FASTMCP_TRANSPORT": "http",
    "FASTMCP_HOST": "0.0.0.0",
    "FASTMCP_PORT": "8000",
}
```

### Expected Result After Fix

```bash
$ make test-stateless

✅ test_jwt_required_environment_variable - PASSED
✅ test_request_without_jwt_fails_clearly - PASSED
✅ test_request_with_malformed_jwt_fails_clearly - PASSED
```

Tests should now PASS because:
1. Server initializes successfully
2. JWT middleware is active
3. Requests without JWT get 401 response
4. Requests with invalid JWT get 401 response

---

## Verification Steps

### Step 1: Apply the Fix

Add `MCP_JWT_ISSUER` and `MCP_JWT_AUDIENCE` to `stateless_container` fixture.

### Step 2: Run Tests

```bash
uv run pytest tests/stateless/test_jwt_authentication.py -v
```

### Step 3: Verify Results

**Expected:**
- All 3 tests PASS
- No "Connection reset by peer" errors
- Tests receive proper 401 HTTP responses

### Step 4: Expand Tests (Future)

Once basic tests pass, add:
- Test with valid JWT (should succeed)
- Test with expired JWT (should fail with 401)
- Test actual MCP tool calls (not just `tools/list`)

---

## Key Files

### Configuration Files
- [tests/conftest.py:516](../../tests/conftest.py#L516) - `stateless_container` fixture (needs fix)
- [src/quilt_mcp/services/jwt_decoder.py:53-60](../../src/quilt_mcp/services/jwt_decoder.py#L53-L60) - Required env vars

### Middleware Files
- [src/quilt_mcp/middleware/jwt_middleware.py](../../src/quilt_mcp/middleware/jwt_middleware.py) - JWT auth middleware (correct)
- [src/quilt_mcp/utils.py:569](../../src/quilt_mcp/utils.py#L569) - `build_http_app` adds middleware

### Test Files
- [tests/stateless/test_jwt_authentication.py](../../tests/stateless/test_jwt_authentication.py) - JWT auth tests

---

## Why This Was Hidden

### The Problem Was Disguised

1. **Container appears to start** - Docker shows container running
2. **Port appears open** - Port binding succeeds
3. **Error is cryptic** - "Connection reset" doesn't explain why
4. **No server logs captured** - Tests don't show server-side errors
5. **Multiple possible causes** - Could be networking, crashes, auth, etc.

### What Finally Revealed It

**Systematic investigation:**
1. Confirmed tests exist ✅
2. Found tests are failing ✅
3. Found middleware code ✅
4. Found JWT decoder requirements ✅
5. Found missing config in fixture ✅

**Key insight:** Don't assume the problem is where you think it is. Follow the code path systematically.

---

## Implications

### What This Tells Us

1. **JWT middleware IS implemented** - Code exists and looks correct
2. **JWT enforcement WILL work** - Once config is fixed
3. **Tests ARE valuable** - They found the problem (config missing)
4. **Integration tests matter** - Unit tests don't catch config issues

### What We Still Don't Know

1. **Does JWT enforcement actually work?** - Need to test with valid JWT
2. **Are all endpoints protected?** - Need to test multiple operations
3. **Is error handling complete?** - Need to test edge cases
4. **Performance impact?** - Need to measure JWT validation overhead

---

## Next Steps

### Immediate (This PR)

1. ✅ Identify root cause (DONE - documented in this file)
2. 🔜 Fix `stateless_container` fixture (add missing env vars)
3. 🔜 Run tests to verify fix works
4. 🔜 Update final summary document
5. 🔜 Commit changes

### Follow-up (Future PRs)

1. Add test with valid JWT (positive case)
2. Add test with expired JWT
3. Test actual MCP tool operations (not just `tools/list`)
4. Add container log capture for debugging
5. Document JWT configuration requirements

---

## Document Status

**Status:** ✅ Complete - Root cause identified and fix known
**Next Action:** Apply fix to `tests/conftest.py`
**Priority:** 🚨 HIGH - Simple fix, immediate impact

# Test Results: JWT Tests EXIST and are FAILING

**Date:** 2026-02-05
**Status:** 🚨 CRITICAL - Tests reveal server crashes on auth requests
**Branch:** `a18-valid-jwts`

---

## Executive Summary

**WE ALREADY HAVE JWT AUTHORIZATION TESTS** in `tests/stateless/test_jwt_authentication.py`.

**THE TESTS ARE FAILING** - Not because JWT auth isn't enforced, but because **the server CRASHES** when it receives requests without/with invalid JWT.

---

## Test Execution Results

```bash
$ make test-stateless
# Or: uv run pytest tests/stateless/test_jwt_authentication.py -v

✅ test_jwt_required_environment_variable - PASSED
   Container has QUILT_MULTIUSER_MODE=true ✓

❌ test_request_without_jwt_fails_clearly - FAILED
   Error: Connection reset by peer

❌ test_request_with_malformed_jwt_fails_clearly - FAILED
   Error: Connection reset by peer
```

---

## What the Tests Do

Located in: `tests/stateless/test_jwt_authentication.py`

### Test 1: Environment Variable Check ✅

```python
def test_jwt_required_environment_variable(stateless_container: Container):
    """Verify container has QUILT_MULTIUSER_MODE enabled."""
```

**Result:** PASSED - Container correctly configured with `QUILT_MULTIUSER_MODE=true`

### Test 2: Request Without JWT ❌

```python
def test_request_without_jwt_fails_clearly(container_url: str):
    """Verify requests without JWT are rejected with clear error message."""
    response = httpx.post(
        f"{container_url}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Content-Type": "application/json"},
        timeout=10.0,
    )
```

**Expected:** Server returns 401/403 with error message
**Actual:** `httpcore.ReadError: [Errno 54] Connection reset by peer`
**Result:** FAILED - Server crashes/resets connection

### Test 3: Request With Malformed JWT ❌

```python
def test_request_with_malformed_jwt_fails_clearly(container_url: str):
    """Verify requests with malformed JWT are rejected with clear error."""
    response = httpx.post(
        f"{container_url}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer not-a-valid-jwt-token",
        },
        timeout=10.0,
    )
```

**Expected:** Server returns 401/403 with error message
**Actual:** `httpcore.ReadError: [Errno 54] Connection reset by peer`
**Result:** FAILED - Server crashes/resets connection

---

## The Problem

**The server is not gracefully handling authentication failures.**

When the MCP server running in Platform/multiuser mode receives requests:
- WITHOUT Authorization header → Connection reset (crash)
- WITH invalid Authorization header → Connection reset (crash)

This is **WORSE** than not enforcing JWT auth. The server should:
1. Accept the HTTP request
2. Validate the JWT token
3. Return proper 401/403 error with message

Instead, it's:
1. Receive HTTP request
2. **CRASH or RESET CONNECTION**

---

## Why This Matters

### Security Implications

**Current state:** Server crashes on auth failure
- Availability issue: Repeated auth failures could DoS the service
- No graceful error handling: Can't debug authentication issues
- Potential information disclosure: Crashes may leak stack traces

**Desired state:** Server returns proper error codes
- 401 Unauthorized: No/invalid JWT token
- 403 Forbidden: Valid JWT but insufficient permissions
- Clear error messages: Help developers debug issues

### Testing Implications

**The tests are CORRECT** - They're exposing a real bug:
- Tests expect graceful error handling
- Server is not handling errors gracefully
- This is a legitimate failure that needs fixing

---

## Investigation Needed

### Question 1: Why is the connection being reset?

**Possible causes:**
1. Server crashes on missing JWT (unhandled exception)
2. Server rejects connection before HTTP request completes
3. FastMCP/transport layer issue with auth
4. Docker networking issue

**Next step:** Check container logs during test execution

### Question 2: Where is JWT validation happening?

**Need to find:**
- JWT validation middleware/decorator
- Request authentication logic
- Error handling for auth failures

**Files to check:**
- `src/quilt_mcp/main.py` - MCP server entry point
- `src/quilt_mcp/backends/quilt3_backend_session.py` - Auth logic
- FastMCP framework auth hooks

### Question 3: Is this a FastMCP transport issue?

**MCP over HTTP requires:**
- JSON-RPC 2.0 format
- Proper header handling
- Error response format

**Hypothesis:** FastMCP might not support Authorization header injection properly

---

## What the Tests Tell Us

### What We Know ✅

1. **Tests exist** - JWT auth tests are already written
2. **Tests run** - Infrastructure works (container starts, tests execute)
3. **Configuration is correct** - QUILT_MULTIUSER_MODE=true is set
4. **Server is running** - Container starts successfully
5. **Problem is reproducible** - Tests fail consistently

### What We DON'T Know ❌

1. **Why connection resets** - Need container logs
2. **Where auth code is** - Need to find JWT validation logic
3. **What error it's hitting** - Need stack traces
4. **How to fix it** - Need to understand the auth flow

---

## Next Steps

### Immediate Actions

1. **Capture container logs** during test execution
   - See what error the server is hitting
   - Check for stack traces or exceptions
   - Understand the failure mode

2. **Find JWT validation code**
   - Search for JWT validation in codebase
   - Understand where/how JWT should be checked
   - Identify missing error handling

3. **Fix the crash**
   - Add proper error handling for missing JWT
   - Return 401/403 instead of crashing
   - Make tests pass

### Test Expansion (After Fix)

Once the server handles auth errors gracefully:

1. **Add positive test** - Request WITH valid JWT succeeds
2. **Add tool operation tests** - Test actual MCP tools (not just tools/list)
3. **Add expired JWT test** - Verify expiration is checked
4. **Add permission tests** - If JWT has permission claims

---

## Updated Understanding

### Original Belief ❌

"We don't have tests to validate JWT auth enforcement"

### Actual Reality ✅

"We HAVE tests for JWT auth enforcement, but they're FAILING because the server crashes instead of returning proper error responses"

---

## File References

- Tests: [tests/stateless/test_jwt_authentication.py](../../tests/stateless/test_jwt_authentication.py)
- Conftest: [tests/stateless/conftest.py](../../tests/stateless/conftest.py)
- Shared fixtures: [tests/conftest.py](../../tests/conftest.py)

---

## Error Details

### Full Error Stack

```
httpcore.ReadError: [Errno 54] Connection reset by peer

The above exception was the direct cause of the following exception:

httpx.ReadError: [Errno 54] Connection reset by peer

During handling of the above exception, another exception occurred:

Failed: ❌ FAIL: Network error when testing JWT requirement
Error: [Errno 54] Connection reset by peer
Server should respond with auth error, not crash
```

### Container Lifecycle

```
---------------------------- Captured stdout setup -----------------------------
🚀 Started container: c5c73931cf2a
✅ Container running: c5c73931cf2a

--------------------------- Captured stdout teardown ---------------------------
🧹 Cleaning up container: c5c73931cf2a
✅ Container cleaned up
```

**Observation:** Container starts and runs, but crashes/resets when receiving requests

---

## Comparison to Expected Behavior

### Current Behavior (WRONG)

```
Client Request (no JWT) → Server → [CONNECTION RESET] → Client Error
```

### Expected Behavior (CORRECT)

```
Client Request (no JWT) → Server → Check JWT → Missing → Return 401 → Client receives error
```

---

## Document Status

**Status:** ✅ Complete - Tests found and results documented
**Next Action:** Investigate why server crashes (capture container logs)
**Priority:** 🚨 HIGH - Server crash on auth failure is a critical bug

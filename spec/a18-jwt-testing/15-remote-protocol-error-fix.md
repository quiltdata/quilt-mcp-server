# Stateless Test Fix: RemoteProtocolError Race Condition

**Date:** 2026-02-05
**Issue:** Random test failures with "Server disconnected without sending a response"
**Result:** All 11 stateless tests passing consistently ✅

## Problem Summary

Tests were failing **randomly** with:
```
httpx.RemoteProtocolError: Server disconnected without sending a response.
```

**Key characteristics:**
- Different tests failed on each run (non-deterministic)
- Always during fixture setup (health check)
- Tests passed individually but failed when run together
- First few tests passed, then 1-2 random tests failed

## Root Cause

The health check loop in container fixtures only caught **some** httpx exceptions:

```python
# BEFORE: Incomplete exception handling
except (httpx.ConnectError, httpx.ReadError):
    # Server not ready yet, continue waiting
    continue
```

**Missing:** `httpx.RemoteProtocolError`

### What is RemoteProtocolError?

This exception occurs when:
1. TCP connection succeeds (port is open)
2. HTTP request is sent
3. Server **closes the connection without sending a response**

This happens when the server is:
- Still initializing and not ready to handle requests
- Overloaded and dropping connections
- Crashing while handling the request

### Why It Was Intermittent

When running all 11 tests together:
1. Each test creates a fresh container (function-scoped)
2. 11 containers starting rapidly stresses Docker
3. Some containers take longer to initialize
4. Health check connects before server is ready
5. Server closes connection → `RemoteProtocolError`
6. Exception not caught → test fails

## Solution

Add `httpx.RemoteProtocolError` to caught exceptions in health check loops:

### Fix 1: [tests/conftest.py:600](../../tests/conftest.py#L600)

```python
# AFTER: Complete exception handling
except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError):
    # Server not ready yet, continue waiting
    continue
```

### Fix 2: [tests/stateless/test_persistent_state.py:78](../../tests/stateless/test_persistent_state.py#L78)

Same fix applied to the persistent state test fixture.

## Files Changed

1. **[tests/conftest.py](../../tests/conftest.py)** (line 600)
   - Added `httpx.RemoteProtocolError` to exception handler

2. **[tests/stateless/test_persistent_state.py](../../tests/stateless/test_persistent_state.py)** (line 78)
   - Added `httpx.RemoteProtocolError` to exception handler

## Test Results

**Before fix:**
```
Run 1: 9 passed, 2 errors (test_container_starts... and test_request_with_malformed...)
Run 2: 9 passed, 2 errors (test_request_without... and test_request_with_malformed...)
```

**After fix:**
```
Run 1: 11 passed ✅ (70.09s)
Run 2: 11 passed ✅ (74.68s)
```

## Why This Wasn't Caught Earlier

1. **Tests passed individually** - Running one test at a time doesn't stress Docker
2. **Session-scoped fixtures masked it** - When fixtures were session-scoped (one container for all tests), the issue didn't occur
3. **After reverting to function scope** - Each test gets a fresh container, exposing the race condition

## Related Issues

This fix complements the earlier session scope fix in [14-session-scope-fix.md](./14-session-scope-fix.md):
- That fix: Reverted to function scope for test isolation
- This fix: Handles the timing issues that function scope exposed

## Key Lessons

1. **Health checks need comprehensive exception handling**
   - Don't assume which exceptions will occur
   - Catch all transient connection errors
   - Let only permanent failures propagate

2. **Race conditions emerge under load**
   - Tests passing individually ≠ tests passing together
   - Container startup timing varies with system load
   - Must handle all possible transient states

3. **Exception types matter**
   - `ConnectError` = port not open yet
   - `ReadError` = connection dropped during read
   - `RemoteProtocolError` = server closed connection without response
   - All three are valid "not ready yet" states

4. **Test isolation has performance tradeoffs**
   - Function-scoped fixtures = better isolation
   - Function-scoped fixtures = more load on system
   - Must handle both isolation AND performance

## Future Improvements

Consider:
1. **Connection pooling** - Reuse httpx clients
2. **Exponential backoff** - Increase sleep time on repeated failures
3. **Better logging** - Track how many retries each container needs
4. **Resource limits** - Run tests with `pytest-xdist` to limit parallelism

## Testing Strategy

To verify similar issues in other tests:
```bash
# Run tests multiple times to catch race conditions
for i in {1..5}; do
  echo "Run $i"
  uv run pytest tests/stateless/ -v || break
done
```

## Related Documentation

- [14-session-scope-fix.md](./14-session-scope-fix.md) - Previous fixture scope fix
- [08-test-organization.md](./08-test-organization.md) - Test architecture
- [tests/conftest.py](../../tests/conftest.py) - Shared test fixtures

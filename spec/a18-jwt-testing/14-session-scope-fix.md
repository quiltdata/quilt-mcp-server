# Stateless Test Fixture Fix: Session Scope and Timing Issues

**Date:** 2026-02-05
**Issue:** Stateless tests failing with connection errors after switching to session-scoped fixtures
**Result:** All 11 stateless tests passing ✅

## Problem Summary

Tests were failing with two types of connection errors:
- `Connection reset by peer` (Errno 54)
- `Connection refused` (Errno 61)

## Root Causes

### 1. **Session-Scoped Fixtures** (Design Issue)

**What happened:**
- Commit `53bed78` changed `stateless_container` and `container_url` from function-scoped to session-scoped
- This meant ALL tests shared the SAME container
- When the container crashed, all subsequent tests failed

**Why this doesn't work:**
- Stateless tests validate deployment constraints and failure modes
- Tests need isolated containers to test different scenarios
- A crashed container in one test breaks all following tests

**Fix:** Reverted to function scope in [tests/conftest.py:515](tests/conftest.py#L515)

```python
# BEFORE: scope="session" - shared container
@pytest.fixture(scope="session")
def stateless_container(...):

# AFTER: default function scope - fresh container per test
@pytest.fixture
def stateless_container(...):
```

### 2. **Missing Environment Variables** (Configuration Bug)

**What happened:**
- v0.14.0 added validation requiring `QUILT_CATALOG_URL` and `QUILT_REGISTRY_URL` for multiuser mode
- The `stateless_container` fixture was missing these variables
- Container crashed immediately on startup with configuration error

**Error message:**
```
Invalid configuration: Multiuser mode requires QUILT_CATALOG_URL environment variable;
Multiuser mode requires QUILT_REGISTRY_URL environment variable
```

**Fix:** Added missing env vars in [tests/conftest.py:562-563](tests/conftest.py#L562-L563)

```python
environment={
    "QUILT_MULTIUSER_MODE": "true",
    "MCP_JWT_SECRET": "test-secret",
    "QUILT_CATALOG_URL": "http://test-catalog.example.com",      # ✅ ADDED
    "QUILT_REGISTRY_URL": "http://test-registry.example.com",   # ✅ ADDED
    ...
}
```

### 3. **Insufficient Startup Wait Time** (Timing Issue)

**What happened:**
- Container startup takes ~4 seconds
- Fixture only waited 3 seconds with `time.sleep(3)`
- Tests made requests before server was ready → "Connection reset by peer"

**Proof:**
```bash
Attempt 1 (1s): Failed
Attempt 2 (2s): Failed
Attempt 3 (3s): Failed
Attempt 4 (4s): HTTP 200 ✅
```

**Fix:** Implemented proper health check loop in [tests/conftest.py:573-601](tests/conftest.py#L573-L601)

```python
# BEFORE: Fixed wait time
time.sleep(3)

# AFTER: Health check with retry loop
for attempt in range(20):  # 20 attempts * 0.5s = 10s max
    time.sleep(0.5)
    container.reload()

    if container.status != "running":
        raise RuntimeError(f"Container failed to start: {logs}")

    try:
        response = httpx.get(f"{url}/", timeout=2.0)
        if response.status_code == 200:
            break  # Server is ready!
    except (httpx.ConnectError, httpx.ReadError):
        continue  # Not ready yet, keep waiting
else:
    raise RuntimeError(f"Container did not become healthy after 10s")
```

## Files Changed

1. **[tests/conftest.py](tests/conftest.py)**
   - Reverted `stateless_container` to function scope (line 515)
   - Reverted `container_url` to function scope (line 600)
   - Added `QUILT_CATALOG_URL` environment variable (line 562)
   - Added `QUILT_REGISTRY_URL` environment variable (line 563)
   - Replaced fixed 3s wait with health check loop (lines 573-601)

2. **[tests/stateless/test_persistent_state.py](tests/stateless/test_persistent_state.py)**
   - Added `QUILT_CATALOG_URL` environment variable (line 40)
   - Added `QUILT_REGISTRY_URL` environment variable (line 41)
   - Replaced fixed 3s wait with health check loop (lines 51-79)

## Test Results

**Before fixes:**
```
7 failed, 4 passed
- Connection reset by peer (container not ready)
- Connection refused (container already crashed)
```

**After fixes:**
```
11 passed ✅
- All tests pass consistently
- No timing issues
- Proper container isolation
```

## Key Lessons

1. **Session scope doesn't work for stateless tests**
   - Stateless tests validate failure modes and constraints
   - Tests need isolated containers, not shared state

2. **Configuration validation catches missing env vars**
   - v0.14.0 properly validates multiuser mode requirements
   - Tests must provide all required configuration

3. **Health checks are better than fixed waits**
   - Fixed `time.sleep()` is brittle and unreliable
   - Retry loops with health checks are more robust
   - Allows container to take as long as needed (within limits)

4. **Container startup timing is variable**
   - Depends on system load, Docker performance, image size
   - Must wait for actual readiness, not assume fixed time

## Related Documentation

- [spec/a18-valid-jwts/08-test-organization.md](spec/a18-valid-jwts/08-test-organization.md) - Test architecture
- [spec/a18-valid-jwts/20-test-coverage-validation.md](spec/a18-valid-jwts/20-test-coverage-validation.md) - Coverage requirements
- [tests/stateless/conftest.py](tests/stateless/conftest.py) - Stateless test configuration

# Async/Await Bug Diagnosis

**Date**: 2026-02-08
**Issue**: All 4 admin:// resources return unawaited coroutines
**Severity**: CRITICAL - Resources completely non-functional

## Root Cause Analysis

### The Bug

All four `admin://` resources incorrectly use `asyncio.to_thread()` to call **async** functions, causing them to return coroutine objects instead of actual data.

**File**: [src/quilt_mcp/tools/resources.py](../../../src/quilt_mcp/tools/resources.py)

**Affected Resources**:
1. `admin://users` (lines 106-131)
2. `admin://roles` (lines 139-164)
3. `admin://config/sso` (lines 172-183)
4. `admin://config/tabulator` (lines 191-202)

### Technical Explanation

#### What `asyncio.to_thread()` Does

`asyncio.to_thread()` is designed to run **synchronous/blocking** code in a thread pool executor:

```python
# Correct usage: Run blocking sync code in thread
result = await asyncio.to_thread(blocking_sync_function)
```

#### The Problem in Our Code

The admin resources use this pattern:

```python
async def admin_users() -> str:
    from quilt_mcp.services.governance_service import admin_users_list  # ← ASYNC function
    from quilt_mcp.context.factory import RequestContextFactory

    def _call_with_context():  # ← Synchronous wrapper
        factory = RequestContextFactory(mode="auto")
        context = factory.create_context()
        return admin_users_list(context=context)  # ← BUG: Calling async WITHOUT await
        # This returns a coroutine object, not the result!

    result = await asyncio.to_thread(_call_with_context)  # ← Executes sync function in thread
    # result is now: <coroutine object admin_users_list at 0x110c83940>

    return _serialize_result(result)  # ← Serializes coroutine object as string!
```

**What happens:**
1. `_call_with_context()` is a **synchronous** function
2. Inside it, we call `admin_users_list(context=context)` without `await`
3. Since `admin_users_list` is async, calling it without `await` returns a **coroutine object**
4. `asyncio.to_thread()` runs `_call_with_context()` in a thread and gets back the coroutine object
5. `_serialize_result()` converts the coroutine object to a string: `"<coroutine object admin_users_list at 0x...>"`
6. This string fails schema validation (expects `{'type': 'object'}`, gets string)

### Comparison: Working vs Broken

#### Working Resources (auth://)

**Auth service functions are SYNCHRONOUS**:
```python
# src/quilt_mcp/services/auth_metadata.py
def auth_status() -> Dict[str, Any]:  # ← Not async!
    """Check authentication status."""
    # ... synchronous code ...
```

**Resource handler correctly uses `asyncio.to_thread()`**:
```python
# src/quilt_mcp/tools/resources.py:58-63
@mcp.resource("auth://status", ...)
async def auth_status_resource() -> str:
    from quilt_mcp.services.auth_metadata import auth_status

    result = await asyncio.to_thread(auth_status)  # ✅ Correct: sync function
    return _serialize_result(result)
```

#### Broken Resources (admin://)

**Governance service functions are ASYNC**:
```python
# src/quilt_mcp/services/governance_service.py:201
async def admin_users_list(...) -> Dict[str, Any]:  # ← ASYNC!
    """List all users."""
    # ... async code ...
```

**Resource handler INCORRECTLY uses `asyncio.to_thread()`**:
```python
# src/quilt_mcp/tools/resources.py:106-119
@mcp.resource("admin://users", ...)
async def admin_users() -> str:
    from quilt_mcp.services.governance_service import admin_users_list

    def _call_with_context():
        factory = RequestContextFactory(mode="auto")
        context = factory.create_context()
        return admin_users_list(context=context)  # ❌ BUG: Returns coroutine

    result = await asyncio.to_thread(_call_with_context)  # ❌ Gets coroutine object
    return _serialize_result(result)  # ❌ Serializes coroutine as string
```

## Test Evidence

From `make test-mcp-legacy`:

```
admin://users           → '<coroutine object admin_users_list at 0x110c83940>'
admin://roles           → '<coroutine object admin_roles_list at 0x11169d470>'
admin://config/sso      → '<coroutine object admin_sso_config_get at 0x113b1ef00>'
admin://config/tabulator → '<coroutine object admin_tabulator_open_query_get at 0x1132fe640>'
```

All four return the string representation of unawaited coroutine objects.

## The Fix

### Solution: Call Async Functions Directly

Remove the `asyncio.to_thread()` wrapper and await the async function directly:

```python
async def admin_users() -> str:
    """List all users (requires admin privileges)."""
    from quilt_mcp.services.governance_service import admin_users_list
    from quilt_mcp.context.factory import RequestContextFactory

    try:
        factory = RequestContextFactory(mode="auto")
        context = factory.create_context()
        result = await admin_users_list(context=context)  # ✅ Direct await
        return _serialize_result(result)
    except Exception as e:
        # ... error handling ...
```

### Why This Works

1. `admin_users_list` is an async function
2. We await it directly in the async resource handler
3. `result` is the actual data (dict), not a coroutine object
4. `_serialize_result()` properly converts dict to JSON string

### Changes Required

**File**: [src/quilt_mcp/tools/resources.py](../../../src/quilt_mcp/tools/resources.py)

**Lines to fix**:
- Lines 106-131: `admin_users()`
- Lines 139-164: `admin_roles()`
- Lines 172-183: `admin_sso_config()`
- Lines 191-202: `admin_tabulator_config()`

**Pattern to apply**:
```diff
-    def _call_with_context():
-        factory = RequestContextFactory(mode="auto")
-        context = factory.create_context()
-        return admin_users_list(context=context)
-
-    result = await asyncio.to_thread(_call_with_context)
+    factory = RequestContextFactory(mode="auto")
+    context = factory.create_context()
+    result = await admin_users_list(context=context)
```

## Impact

**Current state**:
- 27% of resources (4/15) completely non-functional
- Returns invalid data to all clients
- Schema validation fails
- These resources cannot be used at all

**After fix**:
- All 4 resources will work correctly
- Will return proper JSON objects
- Schema validation will pass
- Resource pass rate improves from 73% (11/15) to 100% (15/15)

## Related Files

- **Bug location**: [src/quilt_mcp/tools/resources.py:106-202](../../../src/quilt_mcp/tools/resources.py#L106-L202)
- **Service layer**: [src/quilt_mcp/services/governance_service.py](../../../src/quilt_mcp/services/governance_service.py)
  - Line 201: `async def admin_users_list()`
  - Line 973: `async def admin_roles_list()`
  - Line 1029: `async def admin_sso_config_get()`
  - Line 1180: `async def admin_tabulator_open_query_get()`
- **Test output**: [spec/a18-mcp-test/29-test-failure-root-cause-analysis.md](29-test-failure-root-cause-analysis.md)

## Key Takeaway

**Rule**: `asyncio.to_thread()` is ONLY for **synchronous** blocking functions. For **async** functions, just `await` them directly.

```python
# ✅ CORRECT: Async function
async def my_resource():
    result = await async_function()
    return result

# ✅ CORRECT: Sync blocking function
async def my_resource():
    result = await asyncio.to_thread(blocking_sync_function)
    return result

# ❌ WRONG: Async function with to_thread
async def my_resource():
    def wrapper():
        return async_function()  # Returns coroutine object!
    result = await asyncio.to_thread(wrapper)  # Gets coroutine, not data
    return result
```

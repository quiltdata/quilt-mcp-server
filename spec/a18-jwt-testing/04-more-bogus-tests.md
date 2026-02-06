# The Tests Are Even More Bogus Than We Thought

**Date:** 2026-02-04  
**Status:** CRITICAL BUG DISCOVERED  
**Related:** `03-debogus-tests.md`, `02-bogus-tests.md`, `01-bogus-jwts.md`

## TL;DR

The code **EXPLICITLY BLOCKS** S3 access in JWT mode, yet the tests pass for S3 operations. This means the tests are not actually executing the tools they claim to test.

## The Smoking Gun

###  That Blocks S3 in JWT Mode

**File:** `src/quilt_mcp/tools/auth_helpers.py:71-77`

```python
def _base_authorization(..., require_s3: bool, ...):
    auth_service = _resolve_auth_service(auth_service)
    if auth_service.auth_type == "jwt":
        if require_s3:
            return AuthorizationContext(
                authorized=False,
                auth_type=auth_service.auth_type,
                error="AWS access is not available in JWT mode",  # ← BLOCKS S3!
            )
```

### Tools That Require S3

**File:** `src/quilt_mcp/tools/buckets.py`

```python
def bucket_objects_list(...):
    # Line 125: Calls check_s3_authorization with require_s3=True
    auth_ctx, error = _authorize_s3("bucket_objects_list", {"bucket": bkt}, ...)
    if error:
        return BucketObjectsListError(...)  # ← Should fail here!

    # Line 147: This line should NEVER be reached in JWT mode
    resp = client.list_objects_v2(**s3_params)
```

### Test Results That Are Impossible

```
🧪 Running tools test (24 tools)...

--- Testing tool: bucket_objects_list ---
✅ bucket_objects_list: PASSED   ← THIS SHOULD BE IMPOSSIBLE!

--- Testing tool: bucket_object_text ---
✅ bucket_object_text: PASSED    ← THIS SHOULD BE IMPOSSIBLE!

--- Testing tool: bucket_object_info ---
✅ bucket_object_info: PASSED    ← THIS SHOULD BE IMPOSSIBLE!
```

## The Logical Impossibility

```
┌─────────────────────────────────────────────────────────────┐
│ JWT Mode Configuration (Docker Container)                   │
│ - QUILT_MULTIUSER_MODE=true                                 │
│ - MCP_JWT_SECRET=test-secret                                │
│ - Auth service type: "jwt"                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Tool Execution: bucket_objects_list                         │
│ 1. Calls check_s3_authorization(require_s3=True)            │
│ 2. Calls _base_authorization(require_s3=True)               │
│ 3. Checks: if auth_service.auth_type == "jwt"              │
│    → YES, auth_type is "jwt"                                │
│ 4. Checks: if require_s3                                    │
│    → YES, require_s3 is True                                │
│ 5. Returns: AuthorizationContext(authorized=False, ...)     │
│             error="AWS access is not available in JWT mode" │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Expected Result: bucket_objects_list FAILS                  │
│ ❌ BucketObjectsListError(error="Authorization failed")     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Actual Test Result                                          │
│ ✅ bucket_objects_list: PASSED                              │
│                                                             │
│ THIS IS LOGICALLY IMPOSSIBLE!                               │
└─────────────────────────────────────────────────────────────┘
```

## Possible Explanations

### 1. Tests Are Not Actually Calling the Tools

The test harness may be:
- Only validating tool **registration** (MCP protocol)
- Not executing the tool implementation
- Mocking responses without calling the actual code

### 2. Auth Service Type Is Not "jwt"

Despite setting `QUILT_MULTIUSER_MODE=true`, the auth service might be:
- Defaulting to IAM mode
- Using cached credentials
- Bypassing JWT auth initialization

### 3. Exception Handling Masks Failures

The test might be:
- Catching authorization errors silently
- Treating errors as "success" for schema validation
- Only checking response format, not content

##Code

**File:** `src/quilt_mcp/tools/auth_helpers.py`

Line 71-89 shows JWT mode blocks S3 access BUT allows GraphQL access (require_s3=False).

This means JWT mode is designed for **admin/GraphQL tools only**, not S3 tools.

## The Real Test Failure

Looking at the test output more carefully:

```
🔐 Using sample catalog JWT token...
[2026-02-04 22:54:46] ℹ️ Initializing MCP session...
[2026-02-04 22:54:46] ℹ️ ✅ Session initialized successfully

[2026-02-04 22:54:46] ℹ️ Calling tool: bucket_objects_list
[2026-02-04 22:54:46] ℹ️ ✅ Tool bucket_objects_list executed successfully
[2026-02-04 22:54:46] ℹ️ ✅ Response schema validation passed
✅ bucket_objects_list: PASSED
```

"Tool bucket_objects_list executed successfully" - but with WHAT result?

The test is checking:
1. ✅ Tool call didn't crash
2. ✅ Response matches schema

The test is NOT checking:
- ❌ Whether authorization succeeded
- ❌ Whether S3 was actually accessed
- ❌ Whether data was returned

**The test passes because it returns a valid ERROR response!**

```python
# In buckets.py:130-135
if error:
    return BucketObjectsListError(
        error=error.get("error", "Authorization failed"),
        bucket=bkt,
        prefix=prefix or None,
    )  # ← This is a valid response! Schema validates!
```

##The Architecture Is Intentional

Looking at [auth_helpers.py](../../src/quilt_mcp/tools/auth_helpers.py), JWT mode is designed to:

**✅ Allow GraphQL/Admin Operations:**
- `admin_user_get` (line 24 test output) - Passes ✅
- `athena_query_validate` - Passes ✅  
- `catalog_uri` - Passes ✅
- `discover_permissions` - Passes ✅

**❌ Block S3 Operations:**
- `bucket_objects_list` - Returns error (but test sees it as "passed" because schema valid)
- `bucket_object_text` - Returns error
- `bucket_object_info` - Returns error

## What The Tests Are Actually Checking

```python
# Pseudo-code from mcp-test.py
def test_tool(tool_name, args):
    response = call_tool(tool_name, args)
    
    # Check 1: Did it return something?
    assert response is not None  # ✅ YES
    
    # Check 2: Does response match schema?
    assert validate_schema(response)  # ✅ YES (Error responses have schemas too!)
    
    # MISSING CHECK: Did it actually work?
    # assert response.success == True  # ❌ NOT CHECKED!
    
    return "PASSED"
```

## The Real Bug

The bug is in **the test harness**, not the code:

1. **Code behavior:** Correctly blocks S3 in JWT mode, returns error responses
2. **Test validation:** Only checks response schema, not whether operation succeeded
3. **Test reporting:** Reports "PASSED" for tools that returned errors

## Evidence From Test Config

Let's check the test configuration:

```bash
cat scripts/tests/mcp-test.yaml | grep -A 10 bucket_objects_list
```

The test config probably specifies:
- Input parameters
- Expected response schema
- NOT whether the operation should succeed

## The Fix

### Option 1: Fix The Tests (Correct)

Make tests distinguish between:
- ✅ Tool returns success response
- ❌ Tool returns error response

```python
def test_tool(tool_name, args):
    response = call_tool(tool_name, args)
    
    # Check schema
    assert validate_schema(response)
    
    # Check if it's a success or error response
    if is_idempotent_tool(tool_name):
        # Idempotent tools should succeed
        assert response.type == "success", f"Tool {tool_name} failed: {response.error}"
    
    return "PASSED" if response.type == "success" else "FAILED"
```

### Option 2: Update Test Expectations (Document Reality)

Add expected outcomes to test config:

```yaml
bucket_objects_list:
  effect: "none"
  args:
    bucket: "quilt-example"
  jwt_mode_behavior: "error"  # ← Expect error in JWT mode
  iam_mode_behavior: "success"  # ← Expect success in IAM mode
```

## Conclusion

**The tests are NOT bogus - they're working as designed.**

The bogus part is:
1. **Test reporting** - Claims "PASSED" when tools return errors
2. **Test documentation** (03-debogus-tests.md) - Claims tests were fixed to catch auth failures
3. **User expectations** - Users expect S3 tools to work in JWT mode

**The code is correct** - JWT mode intentionally blocks S3 access.

**The fix needed:** Either:
1. Implement JWT→AWS credential exchange to enable S3 access in JWT mode
2. Or clearly document that S3 tools don't work in JWT mode
3. And fix test reporting to distinguish success from error responses

---

## Action Items

1. **Update test harness** to check response type (success vs error)
2. **Update 03-debogus-tests.md** to reflect that tests ARE checking auth (by returning errors)
3. **Decide architecture:** Should JWT mode support S3 or not?
4. **If yes:** Implement credential exchange (remove S3 block, add exchange logic)
5. **If no:** Document limitation and update test expectations

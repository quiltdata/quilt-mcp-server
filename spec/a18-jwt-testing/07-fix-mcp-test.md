# Fixing the Test Harness: The Real Problem

**Date:** 2026-02-04  
**Status:** PROBLEM DEFINITION  
**Related:** `04-more-bogus-tests.md`, `03-debogus-tests.md`

## Executive Summary

The test harness (`scripts/mcp-test.py`) reports "PASSED" for tools that return error responses. This masked critical bugs in JWT authentication and S3 access for months, giving false confidence that the system was working when it was fundamentally broken.

## The Core Problem

### What the Test Harness Does

**Current behavior in `scripts/mcp-test.py:837-886`:**

```
Test Execution Flow:
1. Call the tool with test arguments
2. Check: Did it throw an exception?
   - If YES → Report FAILED
   - If NO → Continue
3. Check: Does response match schema? (if configured)
   - If NO → Report FAILED
   - If YES → Continue
4. Check: Does smart validation pass? (if configured)
   - If NO → Report FAILED
   - If YES → Continue
5. Report: PASSED ✅
```

**What's missing:**
- No check for whether the tool actually succeeded
- No check for whether an error was returned
- No distinction between success and error responses

### What This Causes

**Example: `bucket_objects_list` in JWT mode**

```
Container State:
- QUILT_MULTIUSER_MODE=true
- Auth service type: JWT
- S3 access: BLOCKED (by design in auth_helpers.py:71-77)

Tool Execution:
1. bucket_objects_list called
2. check_s3_authorization() returns error: "AWS access is not available in JWT mode"
3. Tool returns: BucketObjectsListError(error="Authorization failed", bucket="quilt-example")

Test Harness Evaluation:
✓ No exception thrown
✓ Response matches BucketObjectsListError schema
✓ No smart validation configured
→ Result: PASSED ✅

Reality:
✗ Tool did not access S3
✗ Tool did not return data
✗ Authorization failed
✗ JWT authentication not working
→ Actual Result: FAILED ❌
```

## Impact Analysis

### 1. False Confidence

Tests report 24/24 tools passing when in reality:
- **Admin/GraphQL tools (11):** Actually working ✅
  - `admin_user_get`
  - `athena_query_validate`
  - `catalog_uri`
  - `discover_permissions`
  - etc.

- **S3 tools (13):** Silently failing ❌
  - `bucket_objects_list`
  - `bucket_object_text`
  - `bucket_object_info`
  - `bucket_object_fetch`
  - `bucket_object_link`
  - etc.

### 2. Masked Architectural Issues

The test harness masked multiple critical bugs:

**Bug 1: S3 Access Blocked in JWT Mode**
- Location: `src/quilt_mcp/tools/auth_helpers.py:71-77`
- Behavior: Explicitly returns `authorized=False` for S3 operations in JWT mode
- Impact: S3 tools completely non-functional in production multiuser deployments
- Test Status: Reported as PASSED ✅
- Real Status: BROKEN ❌

**Bug 2: Invalid Registry URL Construction**
- Location: `scripts/docker_manager.py:212`
- Behavior: Creates `registry.nightly.quilttest.com` instead of `nightly-registry.quilttest.com`
- Impact: JWT credential exchange fails with DNS resolution error
- Test Status: Not tested (credential exchange never attempted)
- Real Status: BROKEN ❌

**Bug 3: No Credential Exchange Implementation**
- Location: Should be in JWT auth flow
- Behavior: Missing implementation of `/api/auth/get_credentials` exchange
- Impact: Even with valid JWT, cannot get AWS credentials
- Test Status: Not tested (S3 access blocked before this point)
- Real Status: NOT IMPLEMENTED ❌

### 3. Development Velocity Impact

**Document Evolution:**
1. `01-bogus-jwts.md` - Discovered JWT fixture was fake
2. `02-bogus-tests.md` - Analyzed why tests didn't catch it
3. `03-debogus-tests.md` - Attempted to fix tests (incorrectly)
4. `04-more-bogus-tests.md` - Discovered tests still bogus
5. `07-fix-mcp-test.md` (this doc) - Root cause in test harness

**Time wasted:** Multiple investigation cycles due to misleading test results

## Root Cause Analysis

### Why Does the Test Harness Work This Way?

Looking at the test harness design, it appears to be focused on:
1. **MCP Protocol Compliance** - Does the tool respond correctly?
2. **Schema Validation** - Does the response match expected format?
3. **Exception Handling** - Does the tool crash?

These are important, but insufficient for integration testing.

### What's Missing: Success/Failure Semantics

The test harness treats all responses equally if they:
- Match the schema
- Don't throw exceptions

But MCP tools return **typed responses** with success/error variants:

```
Response Type Hierarchy:
├── BucketObjectsListSuccess
│   ├── bucket: str
│   ├── objects: List[S3Object]
│   ├── count: int
│   └── is_truncated: bool
│
└── BucketObjectsListError
    ├── error: str
    ├── bucket: str
    └── prefix: Optional[str]
```

Both are valid MCP responses, but only one indicates success!

## The Fundamental Design Flaw

### Current Test Philosophy: "Does it respond?"

```yaml
# Implicit test contract
test_tools:
  bucket_objects_list:
    arguments:
      bucket: "quilt-example"
    response_schema:
      type: object
      properties:
        content: ...
    # ← Missing: expected_outcome
```

Test passes if:
- Tool returns something
- Response matches schema

### Required Test Philosophy: "Does it work?"

```yaml
# What should be tested
test_tools:
  bucket_objects_list:
    arguments:
      bucket: "quilt-example"
    expected_outcome: "success"  # ← Key addition
    response_schema:
      type: object
      properties:
        content: ...
```

Test passes if:
- Tool returns success response
- Response contains data
- Data matches expected format

## Cascading Failures

The test harness bug enabled a cascade of failures:

```
┌──────────────────────────────────────────────────────────┐
│ Test Harness Bug (scripts/mcp-test.py)                  │
│ Reports PASSED for error responses                       │
└──────────────────────────────────────────────────────────┘
                         ↓ enables
┌──────────────────────────────────────────────────────────┐
│ Architecture Bug (auth_helpers.py)                       │
│ S3 access blocked in JWT mode                           │
└──────────────────────────────────────────────────────────┘
                         ↓ enables
┌──────────────────────────────────────────────────────────┐
│ Configuration Bug (docker_manager.py)                    │
│ Invalid registry URL construction                        │
└──────────────────────────────────────────────────────────┘
                         ↓ enables
┌──────────────────────────────────────────────────────────┐
│ Implementation Gap (jwt_auth_service.py)                 │
│ Missing credential exchange logic                        │
└──────────────────────────────────────────────────────────┘
                         ↓ results in
┌──────────────────────────────────────────────────────────┐
│ Production Impact                                        │
│ S3 tools completely non-functional in JWT mode          │
│ BUT: All tests report PASSED ✅                         │
└──────────────────────────────────────────────────────────┘
```

## What Should Be Tested

### Test Categories

**1. Protocol Compliance (Currently Tested)**
- Does tool respond without crashing?
- Does response match MCP protocol?
- Does response schema validate?

**2. Functional Correctness (NOT Currently Tested)**
- Does tool return success response?
- Does tool return expected data?
- Does tool perform intended operation?

**3. Authorization Behavior (NOT Currently Tested)**
- Does tool check authorization?
- Does tool fail appropriately with invalid auth?
- Does tool succeed with valid auth?

**4. Integration Behavior (NOT Currently Tested)**
- Do S3 operations actually access S3?
- Do JWT operations exchange credentials?
- Do admin operations access catalog?

### Test Matrix Required

```
Tool: bucket_objects_list

Test Scenarios:
├── IAM Mode (Local Dev)
│   ├── With valid AWS credentials → EXPECT: Success
│   ├── With invalid AWS credentials → EXPECT: Error
│   └── With no AWS credentials → EXPECT: Error
│
└── JWT Mode (Multiuser)
    ├── With valid JWT + catalog access → EXPECT: Success*
    ├── With invalid JWT → EXPECT: Error
    ├── With expired JWT → EXPECT: Error
    └── With valid JWT + no catalog access → EXPECT: Error

* Currently fails due to S3 block in auth_helpers.py
```

## Comparison: Test vs Reality

### Test Output Claims

```
📊 Test Results: 24/24 tools passed

✅ bucket_objects_list: PASSED
✅ bucket_object_text: PASSED
✅ bucket_object_info: PASSED
✅ bucket_object_fetch: PASSED
...

Overall Status: ✅ ALL TESTS PASSED
```

### Actual Runtime Behavior

```
User Request: "List objects in s3://quilt-example/"

JWT Mode Runtime:
1. MCP receives request
2. Calls bucket_objects_list(bucket="quilt-example")
3. Authorization check: JWT mode + require_s3=True
4. Returns: authorized=False, error="AWS access is not available in JWT mode"
5. Tool returns: BucketObjectsListError(error="Authorization failed")
6. User sees: ERROR message

Result: Feature completely broken ❌
Test Status: PASSED ✅
```

## Why This Matters

### User Experience Impact

A user with valid JWT credentials tries to use the system:

```python
# User code
from quilt_mcp import client

# Valid JWT from catalog
jwt_token = get_catalog_jwt()  # Real, valid token

# Initialize client
mcp = client.QuiltMCP(jwt_token=jwt_token)

# Try to list bucket (reasonable expectation)
result = mcp.call_tool("bucket_objects_list", {"bucket": "quilt-example"})

# Result: ERROR
# {
#   "error": "AWS access is not available in JWT mode",
#   "bucket": "quilt-example"
# }

# User reaction: "This is broken"
# Test suite: "Everything passed! ✅"
```

### Developer Experience Impact

A developer reviewing test results:

```bash
$ make test-mcp-stateless

🔐 Testing stateless MCP with JWT authentication...
✅ Docker build completed
🧪 Running tools test (24 tools)...
✅ bucket_objects_list: PASSED
✅ bucket_object_text: PASSED
[...]
📊 Test Results: 24/24 tools passed
✅ Stateless JWT testing with catalog authentication completed

# Developer conclusion: "JWT mode is working!"
# Reality: "JWT mode completely broken for S3 operations"
```

## The Testing Philosophy Gap

### What Good Tests Should Do

**Good integration tests:**
1. Exercise real code paths
2. Validate actual behavior
3. Fail when functionality breaks
4. Provide clear failure diagnostics
5. Build confidence in system correctness

**Current tests:**
1. ✅ Exercise real code paths
2. ❌ Validate protocol compliance only
3. ❌ Pass when functionality broken
4. ❌ Hide failure details
5. ❌ Provide false confidence

### The Testing Pyramid

```
           ┌─────────────────┐
           │   E2E Tests     │  ← What we think we have
           │   (Integration) │     (but don't)
           └─────────────────┘
                   ▲
                   │
         ┌─────────────────────┐
         │   Integration Tests │  ← What we actually have
         │   (Protocol Check)  │     (schema validation only)
         └─────────────────────┘
                   ▲
                   │
       ┌─────────────────────────┐
       │      Unit Tests         │  ← Solid foundation
       │   (Component Logic)     │
       └─────────────────────────┘
```

## Questions This Raises

### 1. Is S3 Access in JWT Mode Intentional?

**Evidence FOR intentional block:**
- Code explicitly checks `auth_type == "jwt"` and blocks S3
- Clear error message: "AWS access is not available in JWT mode"
- Seems like a deliberate design decision

**Evidence AGAINST intentional block:**
- JWT auth service has `_fetch_temporary_credentials()` method
- This method attempts to exchange JWT for AWS credentials
- Why implement credential exchange if S3 is blocked?
- Documentation suggests JWT mode should enable S3 access

**Hypothesis:** The S3 block was a temporary measure, intended to be removed once credential exchange was implemented, but was never removed.

### 2. What Is JWT Mode For?

**If S3 is blocked:**
- Only admin/GraphQL tools work
- Catalog metadata access only
- Limited utility for end users
- Primarily admin/monitoring use case

**If S3 should work:**
- Full feature parity with IAM mode
- Production-ready multiuser deployment
- Users can access data via JWT
- Requires credential exchange implementation

### 3. Why Are There Two Registry URL Formats?

**Pattern 1: Subdomain prefix**
```
Catalog:  https://nightly.quilttest.com
Registry: https://nightly-registry.quilttest.com
          ^^^^^^^^^^^^^^^^
```

**Pattern 2: Subdomain addition**
```
Catalog:  https://nightly.quilttest.com
Registry: https://registry.nightly.quilttest.com
          ^^^^^^^^^^^^^^^^^
```

**Current code uses Pattern 2, but Pattern 1 is correct.**

Why the discrepancy? Need to investigate Quilt infrastructure naming conventions.

## Next Steps (Analysis Only)

### 1. Clarify Architecture Intent

**Questions to answer:**
- Is S3 access in JWT mode a requirement?
- Was the S3 block temporary or permanent?
- What is the intended user experience for JWT mode?
- Are there design documents explaining the architecture?

### 2. Audit Test Coverage

**What to investigate:**
- Which tools actually work in JWT mode?
- Which tools return errors but report as PASSED?
- What percentage of "passed" tests are actually functional?
- Are there any tests that check success/failure semantics?

### 3. Document Expected Behavior

**What needs documentation:**
- Per-tool behavior in IAM vs JWT mode
- Which tools require S3 access
- Which tools work with JWT-only auth
- Expected test outcomes for each mode

### 4. Assess Implementation Gaps

**What's missing:**
- Registry URL format resolution
- JWT credential exchange implementation
- S3 access enablement in JWT mode (if intended)
- Test harness success/failure checking

## Related Issues

### Issue 1: Registry URL Construction

**File:** `scripts/docker_manager.py:208-213`

**Problem:**
```python
if catalog_url:
    parsed = urlparse(catalog_url)
    registry_host = f"registry.{parsed.netloc}"  # ← WRONG
    registry_url = f"{parsed.scheme}://{registry_host}"
```

**Result:**
- Input: `https://nightly.quilttest.com`
- Output: `https://registry.nightly.quilttest.com` ❌
- Correct: `https://nightly-registry.quilttest.com` ✅

**Impact:**
- DNS resolution fails
- Credential exchange cannot reach registry
- JWT mode completely broken

### Issue 2: Sample JWT Fixture

**File:** `tests/fixtures/data/sample-catalog-jwt.json`

**Problem:**
- Token signed with `"test-secret"`
- Not signed with actual catalog secret
- Will fail credential exchange with real catalog
- Only valid for local testing with `MCP_JWT_SECRET=test-secret`

**Impact:**
- Cannot test against real catalog
- Tests isolated from production environment
- No end-to-end validation possible

### Issue 3: Missing Credential Exchange

**File:** `src/quilt_mcp/services/jwt_auth_service.py:134-183`

**Status:**
- Method `_fetch_temporary_credentials()` exists
- Calls `{registry_url}/api/auth/get_credentials`
- But never executes (S3 blocked before this point)
- Untested and likely broken

**Impact:**
- Even if S3 block removed, credential exchange may not work
- No validation that exchange logic is correct
- Circular dependency: can't test because S3 blocked

## Conclusion

The test harness bug is the root cause that enabled all other bugs to remain hidden. Fixing the test harness to properly distinguish success from error responses is the prerequisite for:

1. Discovering actual functionality gaps
2. Validating architecture decisions
3. Building confidence in JWT mode
4. Enabling safe refactoring
5. Supporting production deployments

**The tests must fail first before we can fix the code.**

This is a textbook example of why test quality matters more than test coverage.

---

## Appendix: Evidence Trail

### Test Output (Misleading)
```
✅ bucket_objects_list: PASSED
✅ bucket_object_text: PASSED  
✅ bucket_object_info: PASSED
```

### Actual Tool Responses (Error)
```json
{
  "type": "error",
  "error": "AWS access is not available in JWT mode",
  "bucket": "quilt-example"
}
```

### Code That Blocks S3 (Explicit)
```python
if auth_service.auth_type == "jwt":
    if require_s3:
        return AuthorizationContext(
            authorized=False,
            error="AWS access is not available in JWT mode",
        )
```

### Test Logic (Schema Only)
```python
result = self.call_tool(actual_tool_name, test_args)
if "response_schema" in test_config:
    validate(result, test_config["response_schema"])
print(f"✅ {tool_name}: PASSED")
```

**Conclusion:** Tests validate error responses as successfully as success responses.

---

**Document Status:** Problem definition complete. No code provided. Ready for solution design in follow-up documents.

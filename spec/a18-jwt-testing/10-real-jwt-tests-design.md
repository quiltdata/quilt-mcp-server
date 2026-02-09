# Design: Real JWT Authorization Tests

**Date:** 2026-02-05
**Status:** 📋 DESIGN - Not Yet Implemented
**Branch:** `a18-valid-jwts`
**Purpose:** Design tests that PROVE whether JWT authorization works

---

## Problem Statement

We currently have **NO tests that validate JWT authorization enforcement** in the running MCP server.

**What we have:**

- ✅ Unit tests for JWT token generation/validation (structure only)
- ✅ E2E tests that don't test authentication
- ✅ Test infrastructure (Docker fixtures, JWT helpers)

**What we DON'T have:**

- ❌ Tests that run against Docker container and validate auth enforcement
- ❌ Tests that FAIL when JWT is missing (proving auth is required)
- ❌ Tests that PASS when JWT is valid (proving auth works)
- ❌ Tests that differentiate between quilt3 (no auth) and Platform (auth required)

**This document designs those missing tests.**

---

## Design Goals

### Primary Goal: Prove Auth Enforcement Works (or Doesn't)

Tests must **definitively answer** these questions:

1. **quilt3 backend**: Can I access public buckets WITHOUT JWT? (Should be YES)
2. **Platform backend**: Can I access resources WITHOUT JWT? (Should be NO)
3. **Platform backend**: Can I access resources WITH invalid JWT? (Should be NO)
4. **Platform backend**: Can I access resources WITH valid JWT? (Should be YES)

### Secondary Goals

- **Test multiple operations** - Auth must be enforced on ALL endpoints, not just one
- **Test both read and write** - Different operations may have different auth paths
- **Clear error messages** - Auth failures should return proper 401/403 with helpful messages
- **Idempotent tests** - Safe to run repeatedly without cleanup
- **Fast execution** - Tests should complete quickly (< 30 seconds total)

---

## Test Architecture

### Test Organization

**Location:** `tests/stateless/test_jwt_authorization_enforcement.py`

**Why stateless?**

- JWT auth is Platform/multiuser mode only (not universal)
- JWT is a stateless deployment constraint
- Uses `stateless_container` fixture which sets `QUILT_MULTIUSER_MODE=true`
- Validates deployment security constraints

**NOT tests/e2e/:** E2E tests are backend-agnostic and test MCP protocol, not platform-specific auth.

### Test Matrix

| Test Case | Backend | JWT Token | Expected Result | Validates |
|-----------|---------|-----------|-----------------|-----------|
| `test_quilt3_no_jwt_succeeds` | quilt3 | None | ✅ PASS | Public access works |
| `test_platform_no_jwt_fails` | Platform | None | ❌ FAIL (401) | Auth is required |
| `test_platform_invalid_jwt_fails` | Platform | Invalid | ❌ FAIL (401) | Token validation works |
| `test_platform_expired_jwt_fails` | Platform | Expired | ❌ FAIL (401) | Expiration checked |
| `test_platform_valid_jwt_succeeds` | Platform | Valid | ✅ PASS | Auth enforcement works |
| `test_platform_jwt_all_operations` | Platform | Valid | ✅ PASS | Auth on all endpoints |

### Operations to Test

**Read operations (idempotent):**

- `bucket_objects_list` - List objects in bucket
- `bucket_object_info` - Get metadata for object
- `bucket_object_text` - Read text file content

**Write operations (for completeness):**

- `package_create` - Create package (if we implement this)
- `bucket_object_write` - Write object (if we implement this)

**Priority:** Start with read operations only (idempotent, safe to test)

---

## Test Scenarios (Detailed)

### Scenario 1: quilt3 Backend (Baseline - Public Access)

**Purpose:** Prove that public bucket access works WITHOUT JWT

**Setup:**

- Start Docker container with `QUILT_BACKEND_MODE=quilt3`
- Use public test bucket (e.g., `quilt-example`)
- Make MCP requests WITHOUT Authorization header

**Operations:**

- List objects in public bucket
- Read metadata for public object
- Read text content from public file

**Expected Result:** ✅ All operations SUCCEED

**Why this matters:**

- Establishes baseline behavior
- Proves test infrastructure works
- Validates we're not breaking public access

---

### Scenario 2: Platform Backend - No JWT (The Critical Test)

**Purpose:** Prove that Platform backend REQUIRES JWT (or expose that it doesn't)

**Setup:**

- Start Docker container with `QUILT_MULTIUSER_MODE=true`
- Target a bucket that requires authentication
- Make MCP requests WITHOUT Authorization header

**Operations:**

- List objects in protected bucket
- Read metadata for protected object
- Read text content from protected file

**Expected Result:** ❌ All operations FAIL with 401 Unauthorized

**Current Reality:** Operations likely SUCCEED (security vulnerability)

**Error message should include:**

- Status code: 401
- Error message: "Authentication required" or similar
- Helpful hint: "Include JWT token in Authorization header"

**Why this is THE critical test:**

- If this test PASSES (operations succeed), JWT auth is NOT enforced
- If this test FAILS (operations fail with 401), JWT auth IS enforced
- This test definitively answers: "Is the system secure?"

---

### Scenario 3: Platform Backend - Invalid JWT

**Purpose:** Prove that token validation actually works

**Setup:**

- Start Docker container with `QUILT_MULTIUSER_MODE=true`
- Generate INVALID JWT token (malformed, wrong signature, etc.)
- Make MCP requests WITH invalid Authorization header

**Invalid token types to test:**

- Malformed token (not JWT format): `Bearer not-a-jwt`
- Wrong signature: Valid JWT structure but signed with wrong key
- Missing required claims: JWT missing `sub` or `exp`
- Wrong issuer: JWT with incorrect `iss` claim

**Expected Result:** ❌ All operations FAIL with 401 Unauthorized

**Error message should include:**

- Status code: 401
- Error message: "Invalid token" or "Token validation failed"
- Specific reason: "Invalid signature" or "Missing required claim: sub"

---

### Scenario 4: Platform Backend - Expired JWT

**Purpose:** Prove that token expiration is enforced

**Setup:**

- Start Docker container with `QUILT_MULTIUSER_MODE=true`
- Generate EXPIRED JWT token (exp claim in the past)
- Make MCP requests WITH expired Authorization header

**Expected Result:** ❌ All operations FAIL with 401 Unauthorized

**Error message should include:**

- Status code: 401
- Error message: "Token expired"
- Helpful hint: "Please obtain a new token"

---

### Scenario 5: Platform Backend - Valid JWT (The Success Case)

**Purpose:** Prove that valid JWT allows access

**Setup:**

- Start Docker container with `QUILT_MULTIUSER_MODE=true`
- Generate VALID JWT token with proper claims and signature
- Make MCP requests WITH valid Authorization header

**JWT requirements:**

- Signed with correct key (matches server configuration)
- Contains required claims: `sub` (user), `exp` (future), `iss` (correct issuer)
- Not expired
- Valid signature

**Expected Result:** ✅ All operations SUCCEED

**Why this matters:**

- Proves that JWT auth doesn't just block everything
- Validates the happy path works
- Shows that valid users can actually use the system

---

### Scenario 6: Platform Backend - Auth on All Endpoints

**Purpose:** Ensure JWT auth is enforced on EVERY operation, not just one

**Setup:**

- Start Docker container with `QUILT_MULTIUSER_MODE=true`
- Generate valid JWT token
- Test MULTIPLE different MCP operations

**Operations to test:**

- `bucket_objects_list`
- `bucket_object_info`
- `bucket_object_text`
- `bucket_access_check`
- `package_browse`
- Any other read operations

**Expected Result:** ✅ All operations SUCCEED with valid JWT

**Alternative test:** Try same operations WITHOUT JWT → All should fail

**Why this matters:**

- Auth vulnerabilities often exist in "forgotten" endpoints
- One endpoint working doesn't mean all endpoints are secured
- Common mistake: Auth middleware not applied to all routes

---

## Test Infrastructure Design

### Docker Container Management

**Requirements:**

- Spin up container with specific backend mode
- Wait for container to be ready (health check)
- Inject JWT configuration (signing key, issuer, etc.)
- Tear down container after tests
- Support running multiple containers (parallel testing)

**Configuration:**

- quilt3 mode: `QUILT_BACKEND_MODE=quilt3`
- Platform mode: `QUILT_MULTIUSER_MODE=true`
- JWT signing key: `JWT_SIGNING_KEY` (test key for validation)
- JWT issuer: `JWT_ISSUER` (test issuer)

**Fixtures we already have:**

- `docker_client` - Docker client for container management
- `build_docker_image` - Build image before tests
- `stateless_container` - Start container with stateless config
- `container_url` - HTTP endpoint for MCP server

**What we need to add:**

- Fixture for Platform mode container (multiuser enabled)
- Fixture for quilt3 mode container (baseline)
- Configuration injection for JWT settings

### JWT Token Management

**Requirements:**

- Generate valid JWT tokens (proper claims, signature)
- Generate invalid JWT tokens (malformed, wrong signature)
- Generate expired JWT tokens (exp in past)
- Control token expiration time (for testing timeouts)

**JWT Claims Required:**

- `sub` - Subject (user identifier)
- `exp` - Expiration time (Unix timestamp)
- `iss` - Issuer (who created the token)
- `iat` - Issued at (Unix timestamp)

**JWT Claims Optional:**

- `aud` - Audience (intended recipient)
- `jti` - JWT ID (unique identifier)
- Custom claims (permissions, roles, etc.)

**Fixtures we already have:**

- `make_test_jwt()` - Helper to generate test JWTs

**What we need to verify:**

- Can generate tokens with specific expiration
- Can generate tokens with specific claims
- Can generate intentionally invalid tokens
- Signing key matches server configuration

### MCP Client Configuration

**Requirements:**

- Make MCP tool requests via HTTP
- Inject Authorization header with JWT
- Capture error responses (don't just fail)
- Parse error codes and messages
- Support both SSE and stdio transport

**Current approach (from script tests):**

- `scripts/tests/mcp-test.py` makes tool calls
- Uses MCP SDK to communicate with server
- But unclear if it supports JWT injection

**What we need:**

- Way to add Authorization header to MCP requests
- Or way to configure JWT at transport level
- Handle 401/403 responses gracefully
- Extract error messages from responses

### Test Bucket/Data Setup

**Requirements:**

- Public test bucket (for quilt3 tests)
- Protected test bucket (for Platform tests)
- Known test objects (files we can read/list)
- Small files (fast downloads)
- Stable data (doesn't change during tests)

**Options:**

1. **Real buckets in S3**
   - Pros: Realistic, tests actual AWS integration
   - Cons: Requires AWS credentials, costs money, slower

2. **Mocked S3 (LocalStack)**
   - Pros: Fast, free, isolated
   - Cons: More complex setup, not real S3

3. **Known public bucket**
   - Pros: Easy, no setup
   - Cons: Depends on external resource, not under our control

**Recommendation:** Start with known public bucket (quilt-example), add LocalStack later if needed

---

## Expected Results (Success Criteria)

### Before JWT Auth Implementation

| Test Case | Current Expected | Why |
|-----------|-----------------|-----|
| `test_quilt3_no_jwt_succeeds` | ✅ PASS | Public access works |
| `test_platform_no_jwt_fails` | ⚠️ PASS (BAD!) | Auth NOT enforced yet |
| `test_platform_invalid_jwt_fails` | ⚠️ PASS (BAD!) | Validation NOT checked |
| `test_platform_expired_jwt_fails` | ⚠️ PASS (BAD!) | Expiration NOT checked |
| `test_platform_valid_jwt_succeeds` | ✅ PASS | Operations work |

**Key insight:** Tests 2-4 should FAIL but currently PASS (security vulnerability)

### After JWT Auth Implementation

| Test Case | Expected | Why |
|-----------|----------|-----|
| `test_quilt3_no_jwt_succeeds` | ✅ PASS | Public access still works |
| `test_platform_no_jwt_fails` | ✅ FAIL (401) | Auth IS enforced |
| `test_platform_invalid_jwt_fails` | ✅ FAIL (401) | Validation IS checked |
| `test_platform_expired_jwt_fails` | ✅ FAIL (401) | Expiration IS checked |
| `test_platform_valid_jwt_succeeds` | ✅ PASS | Valid users can access |

**Key insight:** Tests 2-4 now correctly FAIL, proving auth is enforced

---

## Test Execution Strategy

### Test Order

1. **First:** `test_quilt3_no_jwt_succeeds` (baseline)
   - If this fails, test infrastructure is broken

2. **Second:** `test_platform_valid_jwt_succeeds` (happy path)
   - If this fails, check JWT generation and server config

3. **Third:** `test_platform_no_jwt_fails` (the critical test)
   - If this passes (operations succeed), JWT auth is NOT enforced

4. **Fourth:** Invalid/expired token tests
   - Only meaningful after we confirm auth is enforced

### Test Isolation

- Each test gets its own Docker container (avoid shared state)
- Or reuse container but clear any cached auth state between tests
- Tests should not depend on execution order

### Test Performance

- Container startup is slow (~5-10 seconds)
- Reuse containers across tests in same scenario if possible
- Run scenarios in parallel (separate containers)
- Total runtime target: < 30 seconds

### Debugging Failed Tests

**When test fails, capture:**

- Container logs (stdout/stderr)
- HTTP request details (headers, body)
- HTTP response details (status, headers, body)
- JWT token content (decoded claims)
- Server configuration (environment variables)

**Common failure modes:**

- Container not starting (port conflict, image not built)
- JWT signing key mismatch (server using different key)
- Network issues (container not reachable)
- Wrong backend mode (testing Platform but running quilt3)

---

## Implementation Plan

### Phase 1: Basic Infrastructure (MVP)

**Goal:** Get ONE test working end-to-end

1. Create test file: `tests/stateless/test_jwt_authorization_enforcement.py`
2. Write single test: `test_platform_valid_jwt_succeeds`
3. Use existing fixtures: `stateless_container`, `make_test_jwt`
4. Make single MCP request: `bucket_objects_list` with valid JWT
5. Verify: Operation succeeds

**Success criteria:** One test passes, proves infrastructure works

### Phase 2: Add Negative Tests

**Goal:** Prove auth is (or isn't) enforced

1. Add test: `test_platform_no_jwt_fails`
2. Add test: `test_platform_invalid_jwt_fails`
3. Make same MCP request: `bucket_objects_list` but without JWT
4. Verify: Operations fail with 401

**Success criteria:** Tests currently PASS (operations succeed), exposing vulnerability

### Phase 3: Add Baseline Test

**Goal:** Prove public access still works

1. Add container fixture for quilt3 mode
2. Add test: `test_quilt3_no_jwt_succeeds`
3. Make MCP request against public bucket
4. Verify: Operations succeed without JWT

**Success criteria:** Validates we're not breaking public access

### Phase 4: Expand Coverage

**Goal:** Test multiple operations and edge cases

1. Add test: `test_platform_expired_jwt_fails`
2. Add test: `test_platform_jwt_all_operations`
3. Test multiple MCP operations
4. Test different invalid token types

**Success criteria:** Comprehensive coverage of auth scenarios

### Phase 5: Documentation

**Goal:** Make tests maintainable

1. Document test purpose in docstrings
2. Add comments for non-obvious assertions
3. Update README with test execution instructions
4. Document expected behavior before/after JWT implementation

---

## Open Questions

### 1. How to Inject JWT into MCP Requests?

**Question:** How do we add Authorization header to MCP tool calls?

**Options:**

- A) MCP SDK supports custom headers in transport
- B) Use HTTP requests directly (bypass MCP SDK)
- C) Configure JWT at server level (environment variable)
- D) Use MCP Inspector approach (session-level auth)

**Need to investigate:** MCP SDK documentation for auth support

### 2. What Signing Key Configuration?

**Question:** How does server know which key to validate JWTs?

**Current state:** Unknown - need to check server configuration

**Need to investigate:**

- Environment variable for JWT signing key
- How server loads/validates signing key
- Support for multiple keys (key rotation)
- Key format (secret vs public/private key pair)

### 3. What Test Bucket/Data?

**Question:** Which bucket should we use for Platform tests?

**Options:**

- A) Existing test bucket with known data
- B) Create new test bucket specifically for auth tests
- C) Use mocked S3 (LocalStack)

**Need to decide:** Based on what's easiest and most realistic

### 4. How to Handle Rate Limiting?

**Question:** Will repeated auth failures trigger rate limiting?

**Consideration:** Multiple failed auth tests might get throttled

**Mitigation options:**

- Use different usernames for different tests
- Add delays between tests
- Disable rate limiting in test environment

### 5. Should We Test Permission Claims?

**Question:** Should JWT include permission claims (read/write/admin)?

**Current state:** Unknown - need to check JWT implementation

**If yes, need to test:**

- JWT with read permission → read operations succeed
- JWT with read permission → write operations fail
- JWT with write permission → write operations succeed
- JWT without permission → all operations fail

---

## Success Metrics

### Test Quality Metrics

- ✅ Tests run against actual Docker container (not mocked)
- ✅ Tests cover both positive and negative cases
- ✅ Tests validate multiple operations (not just one)
- ✅ Tests clearly show when auth is/isn't working
- ✅ Tests complete in < 30 seconds
- ✅ Tests are idempotent (safe to run repeatedly)

### Security Validation Metrics

- ✅ Tests definitively answer: "Is JWT auth enforced?"
- ✅ Tests expose current vulnerability (operations succeed without JWT)
- ✅ Tests will validate fix (operations fail without JWT after implementation)
- ✅ Tests prevent regression (would catch if auth breaks in future)

### Code Quality Metrics

- ✅ Tests have clear docstrings explaining purpose
- ✅ Tests use descriptive assertion messages
- ✅ Tests capture useful debug info on failure
- ✅ Tests follow existing test conventions
- ✅ Tests are maintainable (easy to understand and modify)

---

## Related Documents

- [Initial Investigation](01-bogus-jwts.md) - How we discovered JWT issues
- [Test Cleanup](09-final-summary.md) - Current state after cleanup
- [Test Organization](08-test-organization.md) - Where tests should go

---

## Next Steps

1. ✅ **Review this design** - Ensure approach makes sense
2. 🔜 **Investigate open questions** - JWT injection method, signing key config
3. 🔜 **Implement Phase 1** - Get one test working end-to-end
4. 🔜 **Implement Phase 2** - Add negative tests that expose vulnerability
5. 🔜 **Document findings** - Write report on current security state
6. 🔜 **Implement JWT enforcement** - Fix the actual security issue
7. 🔜 **Validate fix** - Confirm tests now pass/fail as expected

---

**Document Status:** ✅ Complete - Ready for Review
**Implementation Status:** 📋 Design Only - Not Yet Implemented
**Next Action:** Review design, investigate open questions, begin Phase 1

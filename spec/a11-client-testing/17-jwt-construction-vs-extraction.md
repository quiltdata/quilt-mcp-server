# JWT Construction vs. Extraction: The Core Testing Flaw

**Date:** January 29, 2026
**Status:** 🎯 **ROOT CAUSE IDENTIFIED**
**Impact:** Critical - Affects all stateless JWT testing

## The Insight

**We've been CONSTRUCTING test JWTs instead of EXTRACTING authentication from quilt3.**

This is the fundamental flaw in our testing approach. We're trying to fake authentication by building JWT tokens from scratch, when we should be capturing and reusing real authentication from an active quilt3 session.

## Current Approach (WRONG)

```
┌─────────────────────────────────────────────────────────────┐
│ Test Script: scripts/tests/jwt_helper.py                    │
│                                                              │
│ JWT_TOKEN = construct_jwt(                                  │
│   role_arn = "arn:aws:iam::123:role/Test",  # ← We make    │
│   sub = "test-user",                         # ← We make    │
│   iss = "mcp-test"                           # ← We make    │
│ )                                                            │
│                                                              │
│ Result: Synthetic JWT with AWS info only                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ MCP Server: src/quilt_mcp/services/jwt_auth_service.py      │
│                                                              │
│ ✅ Extracts role_arn from JWT                                │
│ ✅ Calls AWS STS AssumeRole                                  │
│ ✅ Gets temporary AWS credentials                            │
│ ✅ Creates boto3 session for S3                              │
│                                                              │
│ ❌ NO catalog authentication                                 │
│ ❌ NO bearer token for search                                │
│ ❌ NO registry URL                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Result: AWS operations work, catalog operations fail        │
│                                                              │
│ ✅ bucket_objects_list      → Uses S3 (works)               │
│ ✅ bucket_object_info        → Uses S3 (works)               │
│ ❌ search_catalog           → Uses catalog API (fails)       │
│ ❌ discover_permissions     → Uses IAM + catalog (fails)     │
└─────────────────────────────────────────────────────────────┘
```

## Required Approach (CORRECT)

```
┌─────────────────────────────────────────────────────────────┐
│ Pre-requisite: Developer runs `quilt3 login`                │
│                                                              │
│ quilt3.config('https://nightly.quilttest.com')              │
│ # User authenticates through browser                        │
│ # quilt3 stores session with bearer token                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Test Script: EXTRACT from existing session                  │
│                                                              │
│ catalog_token = extract_from_quilt3_session()  # ← Real auth│
│ catalog_url = get_current_catalog_url()        # ← Real URL │
│ registry_url = get_current_registry_url()      # ← Real URL │
│                                                              │
│ JWT_TOKEN = construct_jwt(                                  │
│   role_arn = env.QUILT_TEST_ROLE_ARN,                       │
│   sub = get_quilt3_user_id(),           # ← From session    │
│   catalog_token = catalog_token,        # ← Real token      │
│   catalog_url = catalog_url,            # ← Real URL        │
│   registry_url = registry_url           # ← Real URL        │
│ )                                                            │
│                                                              │
│ Result: Hybrid JWT with REAL catalog auth + AWS info        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ MCP Server: Enhanced JWT auth service                       │
│                                                              │
│ ✅ Extracts role_arn from JWT                                │
│ ✅ Calls AWS STS AssumeRole                                  │
│ ✅ Gets temporary AWS credentials                            │
│ ✅ Creates boto3 session for S3                              │
│                                                              │
│ ✅ Extracts catalog_token from JWT                           │
│ ✅ Extracts catalog_url from JWT                             │
│ ✅ Extracts registry_url from JWT                            │
│ ✅ Configures quilt3 with catalog session                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Result: ALL operations work with real authentication        │
│                                                              │
│ ✅ bucket_objects_list      → Uses S3 (works)               │
│ ✅ bucket_object_info        → Uses S3 (works)               │
│ ✅ search_catalog           → Uses catalog API (works!)      │
│ ✅ discover_permissions     → Uses IAM + catalog (works!)    │
└─────────────────────────────────────────────────────────────┘
```

## Why This Is the Core Issue

### 1. We're Testing Synthetic Authentication

**Current:** We create fake JWT tokens and hope they work
**Reality:** Quilt needs REAL authentication tokens from its auth system

### 2. We're Missing Half the Authentication

**Current:** JWT has AWS role ARN only
**Reality:** Quilt needs both AWS credentials AND catalog bearer token

### 3. We Can't Test What We Can't Authenticate

**Current:** We construct AWS info but have no way to construct catalog auth
**Reality:** Catalog authentication must come from the real Quilt auth system

### 4. The Tests Are Lying

**Current:** Tests pass in local environment (has real session)
**Current:** Tests fail in Docker (only has our synthetic JWT)
**Reality:** Our JWT approach only works when there's already a real session

## The Two-Token System Explained

Quilt MCP requires authentication at TWO levels:

### Level 1: AWS Infrastructure Access

```
Purpose: Access S3 buckets, IAM resources
Mechanism: AWS STS AssumeRole
Input: IAM role ARN
Output: Temporary AWS credentials (access key, secret key, session token)
Duration: 1-12 hours
Scope: AWS operations only
```

**Our Current JWT Provides This:** ✅

### Level 2: Quilt Catalog Access

```
Purpose: Search, packages, metadata, registry
Mechanism: Quilt catalog bearer token authentication
Input: User authentication via OAuth/SAML/etc.
Output: Catalog bearer token (JWT format)
Duration: Variable (catalog-specific)
Scope: Catalog API operations only
```

**Our Current JWT Does NOT Provide This:** ❌

## What Each Token Contains

### Our Constructed MCP JWT (Current)

```json
{
  "iss": "mcp-test",
  "aud": "mcp-server",
  "sub": "test-user",
  "iat": 1706479600,
  "exp": 1706483200,
  "role_arn": "arn:aws:iam::123456789:role/TestRole"
}
```

**Missing:** Catalog authentication entirely

### Quilt Catalog Bearer Token (From Real Session)

```json
{
  "typ": "JWT",
  "alg": "HS256",
  "id": "81a35282-0149-4eb3-bb8e-627379db6a1c",
  "uuid": "3b5da635-afa3-4c3d-8c6f-39473c4bf8b9",
  "exp": 1777432638
}
```

**Contains:** User identity, session info for catalog

### Required MCP JWT (Enhanced)

```json
{
  "iss": "mcp-test",
  "aud": "mcp-server",
  "sub": "test-user",
  "iat": 1706479600,
  "exp": 1706483200,
  "role_arn": "arn:aws:iam::123456789:role/TestRole",
  "catalog_token": "eyJ0eXAiOiJKV1QiLCJhbGciOi...",
  "catalog_url": "https://nightly.quilttest.com",
  "registry_url": "https://nightly-registry.quilttest.com"
}
```

**Contains:** Both AWS role info AND real catalog authentication

## Files That Need Updates

### 1. JWT Helper Script

**File:** `scripts/tests/jwt_helper.py`

**Current Responsibility:** Construct synthetic JWT tokens from scratch

**Required Changes:**

- Add function to extract catalog bearer token from quilt3 session
- Add function to extract current catalog URL
- Add function to extract current registry URL
- Add function to get real user ID from quilt3 session
- Add parameters to `generate_test_jwt()` for catalog authentication
- Add validation that catalog token exists before generating MCP JWT
- Update CLI arguments to accept catalog authentication parameters
- Add `--auto-extract` flag to automatically extract from current session

**New Functions Needed:**

- `extract_catalog_token_from_session()` → str
- `get_current_catalog_url()` → str
- `get_current_registry_url()` → str
- `get_quilt3_user_id()` → str
- `validate_quilt3_session_exists()` → bool

### 2. JWT Auth Service

**File:** `src/quilt_mcp/services/jwt_auth_service.py`

**Current Responsibility:** Extract role ARN from JWT and assume AWS role

**Required Changes:**

- Add method to extract catalog authentication from JWT claims
- Add method to configure quilt3 session with catalog bearer token
- Call catalog setup method during initialization/authentication
- Store catalog session in runtime context for reuse
- Add validation that catalog authentication is present
- Add fallback behavior when catalog auth is missing (warn, not fail)
- Update `get_boto3_session()` to also setup catalog session

**New Methods Needed:**

- `extract_catalog_claims()` → Dict[str, str]
- `setup_catalog_authentication()` → None
- `_configure_quilt3_session(token, catalog_url, registry_url)` → None
- `validate_catalog_authentication()` → bool

### 3. JWT Middleware

**File:** `src/quilt_mcp/middleware/jwt_middleware.py`

**Current Responsibility:** Validate JWT and extract claims to runtime context

**Required Changes:**

- Ensure catalog claims are passed to runtime context
- No validation of catalog token (that's the catalog's job)
- Just extract and pass through: `catalog_token`, `catalog_url`, `registry_url`

**No New Methods:** Just ensure existing claims extraction includes new fields

### 4. Runtime Context

**File:** `src/quilt_mcp/runtime_context.py`

**Current Responsibility:** Store request-scoped authentication state

**Required Changes:**

- Add fields to store catalog authentication state
- Add accessor methods for catalog authentication
- Ensure catalog session is cached and reused within a request

**New Fields Needed:**

- `catalog_token: Optional[str]`
- `catalog_url: Optional[str]`
- `registry_url: Optional[str]`
- `catalog_session_configured: bool`

### 5. Quilt Service

**File:** `src/quilt_mcp/services/quilt_service.py`

**Current Responsibility:** Wrapper around quilt3 operations

**Required Changes:**

- Accept catalog authentication from JWT auth service
- Configure quilt3 with provided catalog session
- Use configured session for all catalog operations
- Handle case where catalog auth is missing gracefully

**New Methods Needed:**

- `configure_catalog_session(token, url, registry_url)` → None
- `has_catalog_authentication()` → bool

### 6. Test Configuration

**File:** `scripts/tests/mcp-test.yaml`

**Current Responsibility:** Define MCP server test suite

**Required Changes:**

- Update test expectations for JWT-based authentication
- Remove or update `discover_permissions` test (currently skipped)
- Ensure all tests work with catalog authentication
- Add validation that catalog auth is present in test setup

**No Structural Changes:** Just ensure tests pass with new JWT format

### 7. Makefile Targets

**File:** `Makefile` (or `make.dev`)

**Current Responsibility:** Provide test commands for developers

**Required Changes:**

- Update `test-stateless-mcp` target to extract catalog authentication
- Add validation that `quilt3 login` has been run
- Add clear error messages if catalog session is missing
- Extract catalog token before generating JWT
- Pass catalog authentication to jwt_helper.py

**Target to Update:**

- `test-stateless-mcp`
- `test-jwt-auth` (if exists)
- Any Docker-based test targets

### 8. Integration Tests

**File:** `tests/integration/test_jwt_integration.py`

**Current Responsibility:** Test JWT authentication end-to-end

**Required Changes:**

- Add tests for catalog authentication extraction
- Add tests for JWT with catalog authentication
- Add tests for catalog operations with JWT auth
- Test that search works with JWT-provided catalog auth
- Test error cases when catalog auth is missing

**New Test Cases Needed:**

- `test_extract_catalog_token_from_session()`
- `test_jwt_with_catalog_authentication()`
- `test_search_with_jwt_catalog_auth()`
- `test_catalog_auth_missing_from_jwt()`

### 9. Unit Tests for JWT Helper

**File:** `tests/unit/test_jwt_helper.py` (may need to create)

**Current Responsibility:** Test JWT token generation

**Required Changes:**

- Add tests for catalog token extraction
- Add tests for JWT generation with catalog auth
- Add tests for validation of required catalog fields
- Test auto-extraction from quilt3 session

**New Test Cases Needed:**

- `test_extract_catalog_token_success()`
- `test_extract_catalog_token_no_session()`
- `test_generate_jwt_with_catalog_auth()`
- `test_generate_jwt_validates_catalog_token()`

### 10. Documentation

**Files:**

- `README.md`
- `docs/authentication.md` (if exists)
- `docs/testing.md` (if exists)

**Required Changes:**

- Document that JWT testing requires `quilt3 login`
- Explain the two-token authentication system
- Update JWT authentication examples to include catalog auth
- Add troubleshooting for missing catalog authentication

## Validation Checklist

After implementing these changes, verify:

### Pre-requisites

- [ ] Developer has run `quilt3 login`
- [ ] `quilt3.config()` shows current catalog
- [ ] Catalog session is active and not expired

### JWT Generation

- [ ] `jwt_helper.py` can extract catalog token from session
- [ ] `jwt_helper.py` validates session exists before generating JWT
- [ ] Generated JWT includes `catalog_token`, `catalog_url`, `registry_url`
- [ ] JWT inspection shows all required claims

### MCP Server

- [ ] JWT middleware extracts catalog claims to runtime context
- [ ] JWT auth service configures quilt3 with catalog session
- [ ] Search operations use catalog bearer token
- [ ] AWS operations use assumed role credentials

### Testing

- [ ] `make test-stateless-mcp` validates quilt3 session exists
- [ ] Test extracts catalog authentication before generating JWT
- [ ] All MCP test tools pass including `search_catalog`
- [ ] Docker container has both AWS and catalog authentication

### Error Handling

- [ ] Clear error if `quilt3 login` hasn't been run
- [ ] Clear error if catalog session is expired
- [ ] Graceful degradation if catalog auth is missing (AWS operations still work)
- [ ] Helpful error messages guide user to fix authentication

## Migration Path

### Phase 1: Extract Catalog Authentication (No Breaking Changes)

1. Update `jwt_helper.py` to extract catalog info
2. Update `generate_test_jwt()` to accept catalog parameters (optional)
3. Add unit tests for extraction functions

### Phase 2: Embed in JWT (Backward Compatible)

1. Update JWT generation to include catalog claims (if provided)
2. Update JWT auth service to extract catalog claims (if present)
3. Add warning logs when catalog auth is missing

### Phase 3: Use Catalog Authentication (Opt-in)

1. Update quilt service to accept catalog configuration
2. Test catalog operations with JWT-provided auth
3. Verify search works in stateless environment

### Phase 4: Make Required (Breaking Change)

1. Make catalog authentication required for JWT mode
2. Update all tests to require catalog authentication
3. Update documentation with new requirements

## Success Criteria

The implementation is complete when:

1. ✅ `jwt_helper.py generate` extracts catalog auth from active session
2. ✅ Generated JWT includes both AWS and catalog authentication
3. ✅ MCP server configures both AWS and catalog sessions from JWT
4. ✅ All test tools pass in stateless Docker environment
5. ✅ `search_catalog` returns results (not 0 hits)
6. ✅ Clear error messages guide users to fix authentication issues
7. ✅ Documentation explains the two-token authentication system

## Key Insights

1. **We were constructing authentication instead of extracting it**
   - JWT tokens can't create authentication, only convey it
   - Real authentication must come from real auth systems

2. **Quilt needs two separate authentications**
   - AWS credentials for infrastructure (S3, IAM)
   - Catalog bearer token for catalog operations (search, packages)

3. **Testing must use real authentication**
   - Can't fake catalog authentication
   - Must extract from active quilt3 session

4. **The fix is to bridge the gap**
   - Extract catalog auth from quilt3 session
   - Embed in MCP JWT as additional claims
   - MCP server uses both for complete authentication

5. **This explains all our test failures**
   - Local tests pass: has real quilt3 session
   - Docker tests fail: only has synthetic JWT without catalog auth
   - The JWT auth is working, but incomplete

This is not an architecture flaw - it's an incomplete implementation. The JWT system is sound, we just need to include ALL required authentication, not just AWS credentials.

# A18: Valid JWT Testing Infrastructure - Implementation Plan

**Date:** 2026-02-05
**Status:** Ready for Implementation
**Branch:** a18-valid-jwts

## Executive Summary

This plan implements a **pure JWT pass-through architecture** where the MCP server
performs NO local validation. All JWT validation happens at the GraphQL backend.

### Testing Philosophy: LIVE TESTS ONLY

- ALL auth/JWT tests use REAL JWTs from `~/.quilt/auth.json`
- NO mocked JWT validation
- NO fake JWT fixtures
- Tests FAIL HARD with clear errors if JWT unavailable (no skipping)
- Live tests ARE the tests (not opt-in, just reality)

## User Requirements (Verified)

There are only **four things that matter** for JWT testing:

### 1. JWT Generation Infrastructure

- Generate syntactically valid JWTs for testing
- Unit tests to validate JWT syntactic correctness (structure, claims, expiration format)
- Consolidate duplicated JWT generation code

### 2. JWTAuthService (Pure Pass-Through)

- **Remove local JWT validation** - no more `jwt_decoder.decode()` calls
- Pass JWT directly to `/api/auth/get_credentials` endpoint
- Let GraphQL backend do all validation
- Return AWS credentials (boto3_session) if JWT is valid
- Return 401/403 errors from backend if JWT is invalid

### 3. Test Scaffolding for Platform Backend

- Use REAL JWTs from `~/.quilt/auth.json` (quilt3 standard)
- Set up runtime context with JWT for platform backend tests
- FAIL HARD if JWT unavailable (no mocking, no skipping)

### 4. Backend-Independent Live Tests

- Can run against **either** quilt3 or platform backend
- Work with **live production/staging** platform backends
- Use real JWTs from `~/.quilt/auth.json`
- **No Docker required** (not container-based)
- **No mocks** - real network calls to GraphQL/S3
- Real authentication with real credentials
- **FAIL HARD** if auth unavailable

## Architectural Change

### Current (Redundant Validation)

```
Client → MCP Middleware (validates JWT) → Platform Backend (validates JWT) → GraphQL (validates JWT) → AWS creds
```

### Target (Pure Pass-Through)

```
Client → MCP (extracts JWT) → Platform Backend (passes JWT) → GraphQL (validates once) → AWS creds
```

## Key Decisions

1. **JWT validation:** Remove all MCP-level validation, pure pass-through to GraphQL
2. **JWT source for tests:** `~/.quilt/auth.json` (quilt3 standard location) - NO MOCKS
3. **Test target:** Live production/staging backends (not just local)
4. **Test type:** Backend-parametrized tests with real auth
5. **No fallbacks:** If JWT unavailable, tests FAIL HARD (never mock, never skip)

---

## Implementation Design

### Component 1: JWT Generation Infrastructure

**Create:** `src/quilt_mcp/utils/jwt_utils.py` (NEW FILE)

**Core Functions:**
- `get_jwt_from_quilt_config(registry_url)` - Extract JWT from ~/.quilt/auth.json for specified registry
- `extract_jwt_claims_unsafe(token)` - Extract claims from JWT WITHOUT validation (for debugging/logging only)

**Unit Tests:** `tests/unit/utils/test_jwt_utils.py` (NEW FILE)

- Test JWT structure parsing (3 dot-separated parts)
- Test claims extraction (no validation)
- Test auth.json parsing with various formats
- Test missing auth.json handling (returns None)

**Consolidation:**

1. Update `scripts/generate_test_jwt.py` - **ADD DEPRECATION WARNING**: "This script generates JWTs for local development only. For testing, use real JWTs from ~/.quilt/auth.json"
2. Remove duplicate generation from `scripts/test-multiuser.py` (lines 25-40)
3. Remove duplicate generation from `tests/conftest.py` (inline generation)

### Component 2: JWTAuthService (Pure Pass-Through)

**Modify:** `src/quilt_mcp/services/jwt_auth_service.py`

**Changes:**

1. **Remove validation from `get_boto3_session()`** (lines 53-88) - Remove jwt_decoder validation (lines 72-78), replace with direct token extraction and pass JWT directly to backend
2. **Simplify `is_valid()`** (lines 185-209) - Only check if token exists and has correct structure (3 dot-separated parts), don't validate signatures/claims
3. **Remove import:** Line 15 (`from quilt_mcp.services.jwt_decoder import ...`)

**Error Handling:** Keep existing error handling in `_fetch_temporary_credentials()` - already correct

### Component 3: JWT Middleware Replacement

**Remove:** `src/quilt_mcp/middleware/jwt_middleware.py` (96 lines - complete removal)

**Create:** `src/quilt_mcp/middleware/jwt_extraction.py` (NEW FILE, ~50 lines)

**Implementation:**

- Extract JWT bearer tokens from Authorization header
- Skip health check endpoints (/, /health, /healthz)
- Return 401 if JWT required but missing or empty
- Extract token WITHOUT validation (claims empty - GraphQL validates)
- Populate runtime context with auth state
- Clean up context after request

**Update:** `src/quilt_mcp/utils.py` (line ~651)

- Change import from `jwt_middleware.JwtAuthMiddleware` to `jwt_extraction.JwtExtractionMiddleware`
- Update middleware registration accordingly

### Component 4: Platform Backend Simplification

**Modify:** `src/quilt_mcp/backends/platform_backend.py` (lines 794-807)

**Changes to `_load_claims()`:**

- Remove jwt_decoder usage
- Simplify to only check runtime claims context
- Return empty dict if no claims present (GraphQL will validate)
- Update docstring to clarify no local validation

**Remove import:** Line 33 (`from quilt_mcp.services.jwt_decoder import ...`)

### Component 5: Test Scaffolding (LIVE TESTS ONLY)

**Update:** `tests/conftest.py`

**Add fixture:** `live_jwt` (session scope)

- Read REAL JWT from ~/.quilt/auth.json using `get_jwt_from_quilt_config()`
- Require QUILT_REGISTRY_URL environment variable
- FAIL HARD with clear error if JWT unavailable (no fallbacks, no skipping)
- Log success when JWT loaded

**Update fixture:** `backend_mode` (lines 236-253)

- For platform mode: use `live_jwt` fixture (fails if None)
- Set RuntimeAuthState with empty claims (GraphQL validates)
- Don't decode JWT locally

**Environment Variables:**

- `QUILT_CATALOG_URL` - Required for platform tests
- `QUILT_REGISTRY_URL` - Required for platform tests
- JWT comes from ~/.quilt/auth.json (no env var needed)
- User must authenticate first: `quilt3 login`
- Tests FAIL if JWT missing - no opt-in flags

### Component 6: Live Tests (NO MOCKS)

**Create:** `tests/live/` directory (NEW DIRECTORY)

**Purpose:** Tests against live backends with real authentication ONLY

**Structure:**

```
tests/live/
├── __init__.py
├── conftest.py          # Live test fixtures (NEW)
├── test_auth_flow.py    # JWT → credentials → S3 (NEW)
├── test_packages.py     # Package operations parametrized (NEW)
├── test_search.py       # Search operations parametrized (NEW)
└── test_buckets.py      # Bucket listing parametrized (NEW)
```

**Key fixture:** `tests/live/conftest.py`

`live_backend` fixture parametrized across ["quilt3", "platform"]:

- quilt3 mode: Uses local ~/.aws/credentials
- platform mode: Gets REAL JWT from auth.json using `get_jwt_from_quilt_config()`
- Requires QUILT_CATALOG_URL and QUILT_REGISTRY_URL for platform mode
- FAIL HARD if JWT not found or env vars missing (no fallbacks)
- Set up runtime context with JWT (no local validation - claims empty)
- Clean up context after yield

**Example test:** `tests/live/test_auth_flow.py`

Two key tests:

1. `test_jwt_to_credentials_flow(live_backend)` - Skip if not platform mode, exchange JWT for credentials via GraphQL,
   verify credentials work with S3
2. `test_invalid_jwt_rejected()` - Set up runtime context with invalid JWT, verify JWTAuthService raises
   JwtAuthServiceError with code "invalid_jwt"

**Makefile targets:** Add to `Makefile`

- `test-live` - Run all live backend tests with prerequisites message
- `test-live-quilt3` - Run quilt3 backend tests only
- `test-live-platform` - Run platform backend tests only with prerequisites message

**CI Considerations:** Tests require authenticated user - CI needs JWT injection or separate test accounts

---

## Removal Strategy (Phased Approach)

### Phase 1: Prepare Replacement Infrastructure ✅ (Low Risk)

1. Create `src/quilt_mcp/utils/jwt_utils.py` with JWT utility functions
2. Add unit tests for JWT utilities (`tests/unit/utils/test_jwt_utils.py`)
3. Create `src/quilt_mcp/middleware/jwt_extraction.py` (extraction only)
4. Update `scripts/generate_test_jwt.py` documentation (deprecation warning)
5. Create `tests/live/` directory structure with fixtures

**Verification:** `make test` (all existing tests should still pass)

### Phase 2: Remove Validation ⚠️ (Higher Risk - Do Carefully)

1. Update `src/quilt_mcp/utils.py` to use `JwtExtractionMiddleware`
2. Remove `src/quilt_mcp/middleware/jwt_middleware.py`
3. Remove `src/quilt_mcp/services/jwt_decoder.py`
4. Update `src/quilt_mcp/services/jwt_auth_service.py` (remove validation)
5. Update `src/quilt_mcp/backends/platform_backend.py` (`_load_claims`)
6. Remove or simplify `src/quilt_mcp/context/user_extraction.py`

**Verification:** `make test-unit` and `make lint` (no import errors)

### Phase 3: Remove ALL Mocked Auth Tests

**DELETE these files entirely:**

Mocked JWT validation tests - DELETE ALL:

- `tests/unit/test_jwt_auth_service.py`
- `tests/unit/services/test_jwt_auth_service.py`

Mocked auth fixtures and helpers - DELETE OR REMOVE AUTH PORTIONS:

- `tests/unit/test_auth_service_factory.py` - Remove mocked JWT portions
- `tests/conftest.py` - Remove any JWT generation fallbacks
- `scripts/test-multiuser.py` - Remove inline JWT generation

**Update remaining test fixtures:**

- Remove all JWT generation fallbacks from `tests/conftest.py`
- If JWT unavailable, use `pytest.skip()` instead of generating test JWTs

**Verification:**

- Use grep to ensure NO mocked JWT tests remain in codebase
- Search pattern: `"mock.*jwt\|mock.*auth\|patch.*jwt\|fake.*jwt"`
- Should return ZERO results in auth-related tests

### Phase 4: Update Test Infrastructure (Live Only)

1. Add `live_jwt` fixture to `tests/conftest.py` (NO fallbacks)
2. Update `backend_mode` fixture to use real JWT or FAIL
3. Remove ALL JWT generation from test files
4. Create tests in `tests/live/`

**Verification:**

- Unset `QUILT_REGISTRY_URL` to test failure mode
- Run `uv run pytest tests/ -k platform -v`
- Should show FAILURES with clear error messages (not skips)

### Phase 5: Configuration Cleanup

1. Remove JWT validation config from `src/quilt_mcp/config.py` (lines 133-134)
2. Update `env.example` (remove MCP_JWT_SECRET, etc.)
3. Update deployment configs (Docker, ECS, K8s)

**Verification:** `make test-all` (full test suite)

### Phase 6: Documentation

1. Update `docs/AUTHENTICATION.md` (pass-through architecture)
2. Update `docs/TESTING_AUTH_MODES.md` (live tests only)
3. Update `README.md` (remove validation references, add live test docs)
4. Add `CHANGELOG.md` entry

**Verification:** `make test-live` (live backend tests with real auth)

### Rollback Strategy

Each phase is independently reversible:

- **Phase 1:** Delete new files (no impact)
- **Phase 2:** Restore deleted files from git history
- **Phase 3:** Restore deleted test files (if needed - but we won't need them)
- **Phase 4:** Restore config files
- **Phase 5:** Documentation rollback (no code impact)

**Critical checkpoint:** After Phase 2, verify MCP server starts and handles JWTs:

- Run `make run` to start server
- Test with real JWT using curl to `/mcp` endpoint with Authorization header
- Should successfully handle JWT and return response

---

## Critical Files Summary

### Must Create (7 files)

1. `src/quilt_mcp/utils/jwt_utils.py` - JWT utilities (read from auth.json)
2. `src/quilt_mcp/middleware/jwt_extraction.py` - Extraction middleware
3. `tests/unit/utils/test_jwt_utils.py` - JWT utils tests
4. `tests/live/conftest.py` - Live test fixtures
5. `tests/live/test_auth_flow.py` - Auth flow tests
6. `tests/live/test_packages.py` - Package tests
7. `tests/live/test_buckets.py` - Bucket tests

### Must Remove (COMPLETE DELETION)

**Delete these files entirely (no mocked auth tests):**

1. `src/quilt_mcp/services/jwt_decoder.py` (256 lines validation)
2. `src/quilt_mcp/middleware/jwt_middleware.py` (96 lines validation)
3. `tests/unit/test_jwt_auth_service.py` (43 lines - MOCKED)
4. `tests/unit/services/test_jwt_auth_service.py` (110 lines - MOCKED)
5. JWT generation helpers from `tests/conftest.py` (inline mocks)
6. JWT generation from `scripts/test-multiuser.py` (lines 25-40)

### Must Modify (8 critical files)

1. `src/quilt_mcp/services/jwt_auth_service.py:53-88` - Remove validation
2. `src/quilt_mcp/backends/platform_backend.py:794-807` - Simplify _load_claims
3. `src/quilt_mcp/utils.py:651` - Update middleware import
4. `src/quilt_mcp/config.py:133-134` - Remove JWT config validation
5. `tests/conftest.py` - Add live_jwt fixture, remove JWT generation
6. `scripts/test-multiuser.py:25-40` - Remove JWT generation
7. `scripts/generate_test_jwt.py` - Add deprecation warning
8. `Makefile` - Add test-live targets

---

## Verification Strategy

### End-to-End Validation

#### Test 1: MCP server starts without JWT secret

- Unset `MCP_JWT_SECRET` and run `make run`
- Should start successfully

#### Test 2: Valid JWT reaches GraphQL

- Prerequisites: quilt3 login + env vars set
- Run `make test-live-platform`
- Should pass - GraphQL validates JWT

#### Test 3: Invalid JWT rejected by GraphQL

- Use curl with invalid JWT token to MCP endpoint
- Should return 401/403 from GraphQL (not MCP middleware)

#### Test 4: AWS credential exchange works

- Run `uv run pytest tests/live/test_auth_flow.py::test_jwt_to_credentials_flow -v`
- Should complete full flow: JWT → credentials → S3 access

#### Test 5: Platform tests FAIL when JWT missing

- Remove JWT from auth.json temporarily or unset env vars
- Run `uv run pytest tests/live/ -k platform -v`
- Should show FAILURES with clear error messages (not skips)

### Success Criteria

- [ ] No `jwt_decoder` imports remain in codebase
- [ ] No `jwt_middleware` imports remain
- [ ] NO mocked JWT validation tests exist
- [ ] All unit tests pass (`make test-unit`)
- [ ] MCP server starts without `MCP_JWT_SECRET`
- [ ] Valid JWT works end-to-end
- [ ] Invalid JWT returns 401/403 from GraphQL
- [ ] Tests FAIL HARD with clear errors when JWT unavailable
- [ ] Both backends work with tests
- [ ] Documentation updated

---

## Risks and Mitigations

### Risk: Breaking Production Deployments

**Concern:** Removing JWT validation might break existing deployments

**Mitigation:**

- GraphQL already validates all JWTs (redundant validation)
- Phase rollout allows early detection
- Deployment configs updated incrementally
- Rollback plan for each phase
- Test against staging environment before production

### Risk: Test Failures with Missing JWTs

**Concern:** JWT expiration or missing JWT causes test failures

**Mitigation:**

- Document JWT refresh requirements (`quilt3 login`)
- Tests FAIL with clear, actionable error messages
- CI needs proper JWT setup (service accounts or secrets)
- Pre-test validation checks for JWT presence

**Example failure logic:**

- Use `pytest.fail()` with clear error message if JWT not found
- Include registry URL and instructions to run `quilt3 login`

### Risk: Incomplete JWT Extraction

**Concern:** Some code paths may still call jwt_decoder

**Mitigation:**

- Grep for all jwt_decoder imports before removal
- Update all imports to use jwt_utils or remove
- Run full test suite after Phase 2
- Lint checks for unused imports

**Verification:**

- Before removal, grep for all jwt_decoder imports: `grep -r "jwt_decoder" src/ tests/`
- Should return no results after Phase 2

### Risk: Platform Backend Unavailable

**Concern:** Tests fail if platform is down

**Mitigation:**

- Tests fail with clear network error messages
- CI can use test/staging environments
- Retry logic for transient failures
- Separate test suites for unit vs integration

---

## Summary

### Code Impact

- **Remove:** ~600 lines (validation + mocked tests)
- **Add:** ~200 lines (utilities + live tests)
- **Net:** -400 lines

### Config Impact

- **Remove:** 4 env vars (MCP_JWT_SECRET, MCP_JWT_SECRET_SSM_PARAMETER, MCP_JWT_ISSUER, MCP_JWT_AUDIENCE)
- **Add:** 0 env vars (tests just work with real JWTs)

### Testing Philosophy

**OLD:** Mocked JWT validation → fake fixtures → unreliable tests
**NEW:** Real JWTs → real backends → fail if misconfigured → reliable tests

### Architecture

**Pure pass-through:** MCP extracts JWT → GraphQL validates once

### Four Components Delivered

1. **JWT Generation Infrastructure** - Read from auth.json, no mocking
2. **JWTAuthService Pass-Through** - Remove validation, let GraphQL handle it
3. **Test Scaffolding** - Use real JWTs or FAIL
4. **Tests** - Parametrized across backends, real auth only

---

## Related Documents

- [01-invalid-jwt-auth.md](01-invalid-jwt-auth.md) - Problem statement
- [02-existing-jwt-code.md](02-existing-jwt-code.md) - Current code analysis
- [03-removal-analysis.md](03-removal-analysis.md) - Files to remove

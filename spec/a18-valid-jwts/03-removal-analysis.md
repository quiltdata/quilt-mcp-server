# JWT Validation Removal Analysis

**Date:** 2026-02-05
**Status:** Analysis - NO REPLACEMENTS
**Purpose:** Document all code that implements JWT validation (not pass-through) that should be removed for pure pass-through architecture

## Executive Summary

This document identifies all code that validates JWTs within the MCP server. Since GraphQL performs the actual validation, this MCP-level validation is redundant and should be removed to create a pure pass-through architecture where:

1. JWT is extracted from `Authorization` header
2. JWT is passed to GraphQL backend
3. GraphQL validates and returns 401/403 if invalid
4. No validation happens in MCP server

## Architecture Change

### Current (Redundant Validation)

```
Client → MCP Middleware (validates JWT) → Platform Backend (passes JWT) → GraphQL (validates JWT again)
```

### Target (Pure Pass-Through)

```
Client → MCP Middleware (extracts JWT) → Platform Backend (passes JWT) → GraphQL (validates JWT)
```

---

## Core Validation Infrastructure

### 1. `src/quilt_mcp/services/jwt_decoder.py` (256 lines)

**Purpose:** Complete cryptographic JWT validation with PyJWT

**What it does:**

- Validates JWT signatures using HS256 algorithm with PyJWT
- Fetches signing secrets from environment or AWS SSM Parameter Store
- Implements secret rotation with caching (5min soft refresh, 1hr hard TTL)
- Validates JWT structure (3 dot-separated parts)
- Validates expiration timestamps (`exp` claim)
- Validates issuer (`iss` claim if configured)
- Validates audience (`aud` claim if configured)
- Enforces strict claims whitelist (rejects extra claims beyond `{id, uuid, exp}`)
- Provides retry logic for signature failures (previous secret + force refresh)

**Key classes:**

- `JwtSecretProvider` - Secret fetching, caching, rotation
- `JwtDecoder` - Signature validation and claims checking
- `JwtDecodeError` - Custom exception with error codes
- `JwtConfigError` - Configuration validation errors
- `_SecretCache` - Dataclass for cached secrets

**Key functions:**

- `get_jwt_decoder()` - Singleton instance accessor

**Dependencies:**

- `boto3` - AWS SSM Parameter Store access
- `PyJWT` - JWT encoding/decoding library

**Usage:** Called by middleware, auth services, user extraction

**Should be removed:** ENTIRE FILE except if needed for other purposes (check imports first)

---

### 2. `src/quilt_mcp/middleware/jwt_middleware.py` (96 lines)

**Purpose:** HTTP middleware that validates JWTs before request processing

**What it does:**

- Intercepts all HTTP requests
- Extracts `Authorization` header
- Validates Bearer token format
- Calls `jwt_decoder.decode()` for cryptographic validation
- Returns 401 for missing/malformed headers
- Returns 403 for invalid JWT signatures/claims/expiration
- Populates `RuntimeAuthState` with validated claims
- Records authentication metrics
- Manages runtime context lifecycle
- Skips validation for health check endpoints (`/`, `/health`, `/healthz`)
- Can be disabled with `require_jwt=False` parameter

**Key class:**

- `JwtAuthMiddleware` - Starlette BaseHTTPMiddleware subclass

**Key methods:**

- `async dispatch()` - Request interception and validation

**Integration:**

- Added to Starlette app in `src/quilt_mcp/utils.py:651`

**Should be removed:** ENTIRE FILE - middleware performs validation

**Note:** May need replacement middleware that ONLY extracts JWT without validation

---

### 3. JWT Validation in `src/quilt_mcp/backends/platform_backend.py`

**Location:** Lines 794-807 in `_load_claims()` method

**What it does:**

- Falls back to decoding JWT if claims not already in runtime context
- Calls `get_jwt_decoder().decode()` to validate token
- Raises `AuthenticationError` if JWT validation fails

**Code:**

```python
def _load_claims(self) -> Dict[str, Any]:
    claims = get_runtime_claims()
    if claims:
        return claims

    runtime_auth = get_runtime_auth()
    if runtime_auth and runtime_auth.access_token:
        decoder = get_jwt_decoder()  # ← Validation happens here
        try:
            return decoder.decode(runtime_auth.access_token)
        except JwtDecodeError as exc:
            raise AuthenticationError(f"Invalid JWT: {exc.detail}") from exc

    return {}
```

**Should be removed:** Lines 800-805 (decoder validation logic)

**Replacement:** Just return empty dict or token itself (no validation)

---

### 4. JWT Validation in `src/quilt_mcp/context/user_extraction.py`

**Location:** Entire file (39 lines)

**What it does:**

- Extracts user ID from auth state or JWT claims
- Falls back to decoding JWT with `get_jwt_decoder().decode()`
- Validates claims structure (strict whitelist)

**Code:**

```python
def extract_user_id(auth_state: Optional[RuntimeAuthState]) -> Optional[str]:
    if not auth_state:
        return None

    user_id = _extract_from_claims(auth_state.claims)
    if user_id:
        return user_id

    if auth_state.access_token:
        try:
            claims = get_jwt_decoder().decode(auth_state.access_token)  # ← Validation
        except JwtDecodeError:
            return None
        return _extract_from_claims(claims)

    return None
```

**Should be removed:** Lines 32-36 (JWT decoding/validation)

**Replacement:** Just use claims from auth_state if present, otherwise return None

---

### 5. JWT Validation Config Check in `src/quilt_mcp/services/auth_service.py`

**Location:** Lines 52-58 (`_validate_jwt_mode()` function)

**What it does:**

- Validates JWT configuration on startup
- Calls `decoder.validate_config()` to check secret sources
- Raises `AuthServiceError` if JWT config invalid

**Code:**

```python
def _validate_jwt_mode() -> None:
    decoder = get_jwt_decoder()
    try:
        decoder.validate_config()
    except JwtConfigError as exc:
        raise AuthServiceError(str(exc), code="jwt_config_error") from exc
```

**Called by:** `create_auth_service()` when `mode_config.requires_jwt` is True

**Should be removed:** Lines 52-58 (`_validate_jwt_mode()` function)

**Replacement:** No validation check needed (GraphQL does validation)

---

### 6. JWT Claims Validation in `src/quilt_mcp/services/jwt_auth_service.py`

**Location:** Lines 185-209 (`is_valid()` method)

**What it does:**

- Validates JWT claims structure
- Checks expiration timestamp
- Validates allowed claims whitelist
- Falls back to decoding token if claims not present

**Code (partial):**

```python
def is_valid(self) -> bool:
    # ... get claims ...

    # Validate claims structure
    if set(claims.keys()) - self._ALLOWED_CLAIMS:
        return False

    # Validate expiration
    if not claims.get("exp"):
        return False
    if time.time() >= claims["exp"]:
        return False

    return True
```

**Should be removed:** Entire validation logic in `is_valid()` method

**Note:** This service is for AWS credential exchange - validation is redundant

---

## Configuration and Environment Variables

### JWT Secret Configuration (Redundant)

**Environment variables that become unnecessary:**

#### 1. `MCP_JWT_SECRET`

- **Purpose:** HS256 signing secret for local JWT validation
- **Used by:** `jwt_decoder.py` → `JwtSecretProvider.get_secret()`
- **File locations:** 47 files reference this
- **Should be removed:** Configuration requirement
- **Note:** GraphQL has the real secret; MCP doesn't need it

#### 2. `MCP_JWT_SECRET_SSM_PARAMETER`

- **Purpose:** AWS SSM Parameter Store path for JWT signing secret
- **Used by:** `jwt_decoder.py` → `JwtSecretProvider._fetch_secret_from_ssm()`
- **File locations:** 47 files reference this
- **Should be removed:** Configuration requirement
- **Note:** Only GraphQL needs access to signing secret

#### 3. `MCP_JWT_ISSUER`

- **Purpose:** Expected JWT `iss` (issuer) claim value
- **Used by:** `jwt_decoder.py:149` in `decode()` method
- **Effect:** Rejects tokens without matching `iss`
- **Should be removed:** Not needed if MCP doesn't validate

#### 4. `MCP_JWT_AUDIENCE`

- **Purpose:** Expected JWT `aud` (audience) claim value
- **Used by:** `jwt_decoder.py:150` in `decode()` method
- **Effect:** Rejects tokens without matching `aud`
- **Should be removed:** Not needed if MCP doesn't validate

### Configuration Files to Update

#### 1. `src/quilt_mcp/config.py`

**Location:** Lines 133-134

**Current code:**

```python
if not os.getenv("MCP_JWT_SECRET"):
    errors.append("Multiuser mode requires MCP_JWT_SECRET environment variable")
```

**Should be removed:** This validation check (lines 133-134)

**Reason:** MCP no longer needs JWT secret for validation

---

#### 2. `env.example`

**Should be removed/updated:**

- References to `MCP_JWT_SECRET`
- References to `MCP_JWT_SECRET_SSM_PARAMETER`
- References to `MCP_JWT_ISSUER`
- References to `MCP_JWT_AUDIENCE`
- Documentation about JWT validation requirements

---

#### 3. `.kiro/specs/mode-config-consolidation/`

**Files:**

- `design.md`
- `tasks.md`

**Should be updated:** Remove JWT validation configuration requirements

---

## Tests (Complete Removal)

### Unit Tests

#### 1. `tests/unit/test_jwt_auth_service.py` (43 lines)

**What it tests:**

- Missing JWT detection (`missing_jwt` error code)
- Missing QUILT_REGISTRY_URL detection (`missing_config` error code)
- RuntimeAuthState simulation

**Lines to remove:** ENTIRE FILE

**Reason:** Tests JWT validation behavior that's redundant

---

#### 2. `tests/unit/services/test_jwt_auth_service.py` (110 lines)

**What it tests:**

- `is_valid()` behavior with expiration
- `is_valid()` with invalid tokens (via stubbed decoder)
- `is_valid()` with missing `exp` claim
- `get_user_identity()` claim extraction
- Token decoding fallback

**Specific test functions:**

- `test_jwt_auth_service_is_valid_false_without_auth()`
- `test_jwt_auth_service_is_valid_respects_expiration()`
- `test_jwt_auth_service_is_valid_false_on_invalid_token()`
- `test_jwt_auth_service_get_user_identity_from_claims()`
- `test_jwt_auth_service_get_user_identity_decodes_token()`
- `test_jwt_auth_service_requires_exp_claim()`

**Lines to remove:** ENTIRE FILE

**Reason:** Tests local JWT validation that GraphQL actually does

---

#### 3. `tests/unit/test_auth_service_factory.py`

**Lines to remove (partial):**

- Lines 26-33: `test_jwt_mode_requires_secret()`
- Lines 36-42: `test_jwt_mode_enabled()` (tests JWT validation config)
- Lines 45-52: `test_mode_switching_resets_service()`

**Reason:** These test JWT validation configuration

**Note:** Keep tests for auth service factory pattern, just remove validation checks

---

### Integration/Stateless Tests

**Files found:** None currently in `tests/stateless/*jwt*.py`, `tests/func/*jwt*.py`, or `tests/e2e/*jwt*.py`

**Note:** Previously removed in commit `f7fa856 "Remove invalid JWT validation tests and fake fixtures"`

---

## Scripts and Utilities

### 1. `scripts/generate_test_jwt.py` (52 lines)

**Purpose:** CLI utility for generating test JWTs during development

**What it does:**

- Generates HS256-signed JWT tokens
- Supports customizable claims and expiration
- Uses PyJWT library directly

**CLI arguments:**

- `--id` - User id claim
- `--uuid` - User uuid claim
- `--secret` - HS256 signing secret (default: "dev-secret")
- `--expires-in` - Expiration in seconds
- `--issuer` - Optional iss claim
- `--audience` - Optional aud claim
- `--extra-claims` - Additional JSON claims

**Referenced in:**

- `scripts/test-multiuser.py`
- `scripts/tests/test_jwt_search.py`
- `scripts/mcp-test.py`
- Various spec documents

**Should be removed:** ENTIRE FILE

**Reason:** Generates fake JWTs with test secrets that don't work with GraphQL

**Replacement:** Document how to get REAL JWTs from Platform authentication

---

## Documentation to Update

### Core Documentation Files

#### 1. `docs/JWT_TESTING.md`

**Current content:** 150+ lines about JWT token generation, validation testing, troubleshooting

**Sections to remove:**

- JWT token generation with `tests/jwt_helpers.py`
- Manual token creation with fake secrets
- Local development with `MCP_JWT_SECRET`
- Troubleshooting JWT signature validation errors

**Should be replaced with:** How to obtain real JWTs from Platform for testing

---

#### 2. `docs/AUTHENTICATION.md`

**Should be updated:**

- Remove sections about MCP-level JWT validation
- Remove references to `MCP_JWT_SECRET` configuration
- Document that JWT validation happens at GraphQL layer
- Update architecture diagrams

---

#### 3. `docs/TESTING_AUTH_MODES.md`

**Should be updated:**

- Remove JWT validation testing procedures
- Remove fake JWT generation instructions
- Document testing with real Platform JWTs

---

#### 4. `docs/request_scoped_services.md`

**Should be updated:**

- Remove JWT validation service references
- Update auth flow diagrams

---

### Deployment Documentation

#### 1. `docs/deployment/jwt-mode-docker.md`

**Should be updated:**

- Remove `MCP_JWT_SECRET` environment variable
- Remove `MCP_JWT_SECRET_SSM_PARAMETER` configuration
- Remove `MCP_JWT_ISSUER` / `MCP_JWT_AUDIENCE` settings

---

#### 2. `docs/deployment/jwt-mode-ecs.md`

**Should be updated:**

- Remove JWT secret configuration from ECS task definition
- Remove SSM parameter references

---

#### 3. `docs/deployment/jwt-mode-kubernetes.md`

**Should be updated:**

- Remove JWT secret from Kubernetes secrets/configmaps
- Remove SSM parameter configuration

---

#### 4. `docs/deployment/docker-compose-jwt.yaml`

**Lines to remove:**

- `MCP_JWT_SECRET` environment variable
- `MCP_JWT_SECRET_SSM_PARAMETER` environment variable
- `MCP_JWT_ISSUER` environment variable
- `MCP_JWT_AUDIENCE` environment variable

---

#### 5. `docs/deployment/ecs-task-jwt.json`

**Lines to remove:**

- `MCP_JWT_SECRET` environment variable definition
- `MCP_JWT_SECRET_SSM_PARAMETER` secret reference
- IAM permissions for SSM parameter access

---

#### 6. `docs/deployment/kubernetes-jwt.yaml`

**Lines to remove:**

- JWT secret volume/mount
- `MCP_JWT_SECRET` environment variable
- SSM parameter configuration

---

### Design Specifications

#### 1. `spec/a18-valid-jwts/01-invalid-jwt-auth.md`

**Status:** Already documents the problem

**Action:** Keep as historical record of why validation was removed

---

#### 2. `spec/a18-valid-jwts/02-existing-jwt-code.md`

**Status:** Documents all existing JWT code (this current file)

**Action:** Keep as reference for what was removed

---

#### 3. `spec/a18-jwt-testing/` (multiple files)

**Files:**

- `01-bogus-jwts.md`
- `02-bogus-tests.md`
- `04-more-bogus-tests.md`
- `12-root-cause-found.md`

**Action:** Keep as historical context for why tests were removed

---

#### 4. `spec/a13-mode-config/` files

**Files to update:**

- `01-mode-map.md` - Remove JWT validation requirements
- `02-multiuser-mode.md` - Update JWT configuration section
- `03-implementation-plan.md` - Remove JWT validation tasks

---

#### 5. `spec/a10-multiuser/04-finish-jwt.md`

**Should be updated:** Document that JWT validation was removed

---

## Helper Scripts

### 1. `scripts/docker_manager.py`

**References:** `MCP_JWT_SECRET` configuration

**Should be updated:** Remove JWT secret configuration

---

## Project Documentation

### 1. `README.md`

**Should be updated:**

- Remove JWT validation feature descriptions
- Remove `MCP_JWT_SECRET` configuration instructions
- Update architecture diagrams to show pass-through

---

### 2. `CHANGELOG.md`

**Should be updated:**

- Add entry documenting removal of JWT validation
- Note that validation now happens exclusively at GraphQL layer

---

## Test Fixtures (Already Removed)

**These were removed in commit `f7fa856`:**

- `tests/fixtures/data/sample-catalog-jwt.json`
- `tests/fixtures/data/sample-catalog-jwt-expired.json`
- `tests/fixtures/data/sample-catalog-jwt-missing-exp.json`
- `tests/fixtures/data/sample-catalog-jwt-extra-claim.json`

**Status:** Already removed ✓

---

## Dependencies to Review

### Python Package Dependencies

#### 1. `PyJWT` library

**Used by:**

- `src/quilt_mcp/services/jwt_decoder.py` - JWT validation
- `scripts/generate_test_jwt.py` - Test JWT generation

**Should be reviewed:** If `jwt_decoder.py` is removed and `generate_test_jwt.py` is removed, PyJWT may no longer be needed

**Check:** Search for other uses of `import jwt` in codebase

---

#### 2. `boto3` for SSM Parameter Store

**Used by:**

- `src/quilt_mcp/services/jwt_decoder.py:121` - Fetch JWT secret from SSM

**Should be reviewed:** If SSM secret fetching is removed, boto3 SSM client may not be needed (but boto3 used for S3, so keep dependency)

---

## Runtime Context Changes

### RuntimeAuthState

**Location:** `src/quilt_mcp/runtime_context.py` (likely)

**Current usage:**

- Populated by `jwt_middleware.py` with validated claims
- Contains: `scheme`, `access_token`, `claims`

**After removal:**

- Still needed to pass JWT to backends
- `claims` field may be removed (not validated by MCP)
- Or `claims` could be populated by GraphQL response

**Should be reviewed:** Whether claims field still needed

---

## Metrics and Logging

### Authentication Metrics

**Location:** `src/quilt_mcp/services/auth_metrics.py` (inferred)

**Current metrics:**

- `jwt_validation("success", duration_ms=X)`
- `jwt_validation("failure", duration_ms=X, reason=code)`

**Recorded by:** `jwt_middleware.py:49,57,63,73,78`

**Should be removed:** JWT validation metrics

**Keep:** Auth mode selection metrics

---

## Summary of Files to Modify/Remove

### Complete File Removal (6 files)

1. `src/quilt_mcp/services/jwt_decoder.py` (256 lines)
2. `src/quilt_mcp/middleware/jwt_middleware.py` (96 lines)
3. `tests/unit/test_jwt_auth_service.py` (43 lines)
4. `tests/unit/services/test_jwt_auth_service.py` (110 lines)
5. `scripts/generate_test_jwt.py` (52 lines)
6. `src/quilt_mcp/context/user_extraction.py` (39 lines) - or heavily modify

**Total:** ~596 lines of validation code

---

### Partial File Modifications (7 files)

1. `src/quilt_mcp/backends/platform_backend.py` - Remove lines 800-805
2. `src/quilt_mcp/services/auth_service.py` - Remove lines 52-58
3. `src/quilt_mcp/services/jwt_auth_service.py` - Modify `is_valid()` method
4. `src/quilt_mcp/config.py` - Remove lines 133-134
5. `src/quilt_mcp/utils.py` - Remove/modify middleware registration (lines 648-656)
6. `tests/unit/test_auth_service_factory.py` - Remove 3 test functions
7. `tests/conftest.py` - Remove JWT validation fixtures

---

### Documentation Updates (15+ files)

1. `docs/JWT_TESTING.md`
2. `docs/AUTHENTICATION.md`
3. `docs/TESTING_AUTH_MODES.md`
4. `docs/request_scoped_services.md`
5. `docs/deployment/jwt-mode-docker.md`
6. `docs/deployment/jwt-mode-ecs.md`
7. `docs/deployment/jwt-mode-kubernetes.md`
8. `docs/deployment/docker-compose-jwt.yaml`
9. `docs/deployment/ecs-task-jwt.json`
10. `docs/deployment/kubernetes-jwt.yaml`
11. `README.md`
12. `CHANGELOG.md`
13. `env.example`
14. `spec/a13-mode-config/01-mode-map.md`
15. `spec/a13-mode-config/02-multiuser-mode.md`

---

## Configuration Variables to Remove (4 variables)

1. `MCP_JWT_SECRET` (47 file references)
2. `MCP_JWT_SECRET_SSM_PARAMETER` (47 file references)
3. `MCP_JWT_ISSUER` (47 file references)
4. `MCP_JWT_AUDIENCE` (47 file references)

---

## What SHOULD Remain

### JWT Pass-Through (Keep These)

1. **JWT extraction from headers** - Still needed to get token
2. **JWT forwarding to GraphQL** - Core functionality
3. **RuntimeAuthState structure** - Needed to pass token between layers
4. **Authorization header construction** - `Authorization: Bearer {token}`
5. **HTTP error handling from GraphQL** - 401/403 responses
6. **JWT credential exchange** - `jwt_auth_service._fetch_temporary_credentials()`

### Keep This Code

**In `src/quilt_mcp/backends/platform_backend.py`:**

- Line 43: `self._access_token = self._load_access_token()` ✓
- Lines 69-75: Adding JWT to session headers ✓
- Lines 97-100: `get_graphql_auth_headers()` method ✓
- Lines 809-813: `_load_access_token()` method ✓

**In `src/quilt_mcp/services/jwt_auth_service.py`:**

- `_fetch_temporary_credentials()` method ✓
- AWS credential exchange logic ✓
- Credential caching ✓

---

## Impact Analysis

### What Breaks Without Validation

**Nothing** - because validation is redundant:

- GraphQL validates all JWTs
- Invalid JWTs get 401/403 from GraphQL
- Valid JWTs work exactly the same

### What Improves

1. **Simpler configuration** - No JWT secret needed in MCP
2. **Single source of truth** - Only GraphQL validates
3. **Fewer failure points** - No signature mismatches between MCP and GraphQL
4. **Easier testing** - Just test with real JWTs from Platform
5. **Reduced code** - ~600 lines removed
6. **Clearer architecture** - Pass-through vs validation

---

## Migration Notes

### For Developers

**Old way (validation in MCP):**

```bash
export MCP_JWT_SECRET="test-secret"
python scripts/generate_test_jwt.py --id user-123 --uuid uuid-123 --secret "test-secret"
```

**New way (pass-through to GraphQL):**

```bash
# Get real JWT from Platform authentication
JWT_TOKEN=$(quilt3 login --get-jwt)  # or similar
export MCP_JWT_TOKEN="$JWT_TOKEN"
```

### For Deployments

**Remove these environment variables:**

- `MCP_JWT_SECRET`
- `MCP_JWT_SECRET_SSM_PARAMETER`
- `MCP_JWT_ISSUER`
- `MCP_JWT_AUDIENCE`

**Remove these IAM permissions:**

- `ssm:GetParameter` for JWT secret (no longer needed)

### For Testing

**Old approach:**

- Generate fake JWT with test secret
- Test MCP validation logic
- Never test real GraphQL validation

**New approach:**

- Obtain real JWT from Platform auth
- Test end-to-end with GraphQL
- Verify GraphQL returns real data

---

## Verification Checklist

After removal, verify:

- [ ] MCP server starts without `MCP_JWT_SECRET`
- [ ] Valid Platform JWT reaches GraphQL and returns data
- [ ] Invalid JWT returns 401/403 from GraphQL (not MCP)
- [ ] No imports of `jwt_decoder` remain in code
- [ ] No imports of `jwt_middleware` remain (except utils.py for replacement)
- [ ] All tests pass without JWT validation tests
- [ ] Documentation updated to reflect pass-through architecture
- [ ] Deployment configs updated (no JWT secret)
- [ ] `PyJWT` dependency reviewed (may be removable)

---

## Related Documents

- [01-invalid-jwt-auth.md](01-invalid-jwt-auth.md) - Problem statement
- [02-existing-jwt-code.md](02-existing-jwt-code.md) - Current code analysis
- `spec/a18-jwt-testing/01-bogus-jwts.md` - Fake JWT problem
- `spec/a18-jwt-testing/02-bogus-tests.md` - Test architecture analysis

---

## Conclusion

The JWT validation infrastructure in the MCP server consists of:

- **~600 lines of validation code** across 6 files
- **4 environment variables** for validation configuration
- **Multiple test files** testing validation behavior
- **Extensive documentation** about validation

All of this is redundant because **GraphQL performs the actual validation**.

Removing this code will:

1. Simplify architecture (pass-through only)
2. Eliminate configuration complexity
3. Remove test fixtures that don't match reality
4. Align testing with actual authentication flow
5. Reduce maintenance burden

The MCP server's only JWT responsibilities should be:

1. Extract JWT from Authorization header
2. Pass JWT to GraphQL backend
3. Return GraphQL's response (including auth errors)

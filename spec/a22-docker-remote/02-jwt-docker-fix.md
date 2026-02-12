# JWT Authentication Fix for Docker Testing

**Status**: Hypothesis
**Date**: 2025-02-11
**Context**: Minimal fix for JWT authentication in `make test-mcp-docker`

## Problem Statement

The `make test-mcp-docker` target tests Docker containers with JWT authentication, but **it only uses fake test JWTs** that won't work with real GraphQL backends. The middleware just passes JWTs through to the backend - there's no local secret-based validation.

### Current Behavior (BROKEN)

```bash
make test-mcp-docker
  ↓
mcp-test.py --jwt
  ↓
generate_test_jwt(secret="test-secret")  # ❌ Fake JWT that backend rejects
  ↓
HTTP Request: Authorization: Bearer <fake-jwt>
  ↓
JwtExtractionMiddleware extracts token (passes through)
  ↓
GraphQL backend receives fake JWT
  ↓
Backend validates JWT signature → FAILS
```

### What Other Tests Do (CORRECT)

**File**: `tests/conftest.py`, `backend_mode` fixture (lines 234-265)

```python
# JWT discovery hierarchy (same as real deployment):
access_token = os.getenv("PLATFORM_TEST_JWT_TOKEN")  # 1. Real JWT from env
if not access_token:
    # 2. Try quilt3 session (from quilt3 login)
    quilt_session = quilt3.session.get_session()
    if hasattr(quilt_session, "headers") and "Authorization" in quilt_session.headers:
        access_token = quilt_session.headers["Authorization"][7:]  # Strip "Bearer "

if not access_token:
    # 3. Fall back to generated test JWT (for mocked tests)
    jwt_secret = os.getenv("PLATFORM_TEST_JWT_SECRET", "test-secret-for-jwt-generation")
    access_token = pyjwt.encode(claims, jwt_secret, algorithm="HS256")
    print("⚠️  Using generated test JWT (may not work with real servers)")
```

### The Gap

**File**: `scripts/mcp-test.py`, lines 1086-1095

```python
if args.jwt:
    # ❌ ONLY generates fake JWT, never tries real JWT
    jwt_token = generate_test_jwt(secret="test-secret")
```

The Docker test script:

- ❌ Never checks `PLATFORM_TEST_JWT_TOKEN` env var
- ❌ Never tries quilt3 session
- ❌ Only generates fake test JWT
- ❌ Fake JWT fails backend validation

### Why This Matters

The JWT middleware (`src/quilt_mcp/middleware/jwt_extraction.py`) **does NOT validate JWTs locally**. It just:

1. Extracts `Authorization: Bearer <token>` from HTTP header
2. Stores token in request context
3. Passes token to GraphQL backend

The **GraphQL backend validates** the JWT signature. Fake JWTs fail validation.

## The Minimal Fix

### Hypothesis

**Making `mcp-test.py` discover real JWTs (like other tests do) will enable proper JWT authentication in Docker tests.**

### Implementation

**File**: `scripts/mcp-test.py`, lines 1086-1095

Replace the fake JWT generation with real JWT discovery:

**Before**:

```python
if args.jwt:
    # Use sample catalog JWT for testing
    if transport != "http":
        print("❌ --jwt only supported for HTTP transport")
        sys.exit(1)

    print("🔐 Generating test JWT token...")

    try:
        jwt_token = generate_test_jwt(secret="test-secret")
        if args.verbose:
            masked = f"{jwt_token[:8]}...{jwt_token[-8:]}" if len(jwt_token) > 16 else "***"
            print(f"   Token preview: {masked}")
    except Exception as e:
        print(f"❌ Failed to load sample JWT token: {e}")
        sys.exit(1)
```

**After**:

```python
if args.jwt:
    # Discover JWT using same logic as backend_mode fixture
    if transport != "http":
        print("❌ --jwt only supported for HTTP transport")
        sys.exit(1)

    print("🔐 Discovering JWT token...")

    # 1. Try real JWT from environment
    jwt_token = os.getenv("PLATFORM_TEST_JWT_TOKEN")
    if jwt_token:
        print("✅ Using JWT from PLATFORM_TEST_JWT_TOKEN")

    # 2. Try quilt3 session (if authenticated)
    if not jwt_token:
        try:
            import quilt3
            quilt_session = quilt3.session.get_session()
            if hasattr(quilt_session, "headers") and "Authorization" in quilt_session.headers:
                auth_header = quilt_session.headers["Authorization"]
                if auth_header.startswith("Bearer "):
                    jwt_token = auth_header[7:]  # Strip "Bearer " prefix
                    print("✅ Using JWT from quilt3 session")
        except Exception as e:
            if args.verbose:
                print(f"⚠️  Could not get JWT from quilt3 session: {e}")

    # 3. Fall back to generated test JWT (for mocked tests)
    if not jwt_token:
        jwt_secret = os.getenv("PLATFORM_TEST_JWT_SECRET", "test-secret")
        jwt_token = generate_test_jwt(secret=jwt_secret)
        print("⚠️  Using generated test JWT (may not work with real servers)")

    if args.verbose and jwt_token:
        masked = f"{jwt_token[:8]}...{jwt_token[-8:]}" if len(jwt_token) > 16 else "***"
        print(f"   Token preview: {masked}")
```

### Why This Works

1. **Same logic as other tests**: Uses identical JWT discovery hierarchy as `backend_mode` fixture
2. **Prefers real JWTs**: Checks `PLATFORM_TEST_JWT_TOKEN` env var first
3. **Falls back to quilt3**: Uses `quilt3 login` session if available
4. **Backward compatible**: Still generates test JWT if no real token available
5. **Works with CI**: CI/CD sets `PLATFORM_TEST_JWT_TOKEN` secret

### Expected Behavior After Fix

```bash
# Local development (with quilt3 login)
quilt3 login
make test-mcp-docker
  ↓
mcp-test.py --jwt
  ↓
Discovers JWT from quilt3 session ✅
  ↓
HTTP Request: Authorization: Bearer <real-jwt>
  ↓
GraphQL backend validates JWT → SUCCESS ✅

# CI/CD (with secret)
export PLATFORM_TEST_JWT_TOKEN=<real-jwt>
make test-mcp-docker
  ↓
mcp-test.py --jwt
  ↓
Discovers JWT from PLATFORM_TEST_JWT_TOKEN ✅
  ↓
HTTP Request: Authorization: Bearer <real-jwt>
  ↓
GraphQL backend validates JWT → SUCCESS ✅

# Fallback (no real JWT)
make test-mcp-docker
  ↓
mcp-test.py --jwt
  ↓
Generates fake test JWT (warns user) ⚠️
  ↓
HTTP Request: Authorization: Bearer <fake-jwt>
  ↓
GraphQL backend validates JWT → FAILS (expected for mocked tests)
```

## Validation Plan

### 1. Test with Real JWT (quilt3 login)

```bash
# Login to get real JWT
quilt3 login

# Run Docker tests
make test-mcp-docker
```

**Expected**:

- Output: `✅ Using JWT from quilt3 session`
- All tests pass with real backend validation

### 2. Test with Environment JWT

```bash
# Set real JWT from catalog
export PLATFORM_TEST_JWT_TOKEN="<real-jwt-from-catalog>"

# Run Docker tests
make test-mcp-docker
```

**Expected**:

- Output: `✅ Using JWT from PLATFORM_TEST_JWT_TOKEN`
- All tests pass with real backend validation

### 3. Test Fallback (no real JWT)

```bash
# Clear authentication
quilt3 logout
unset PLATFORM_TEST_JWT_TOKEN

# Run Docker tests
make test-mcp-docker
```

**Expected**:

- Output: `⚠️  Using generated test JWT (may not work with real servers)`
- Tests may fail if hitting real backend (expected behavior)
- Tests pass if backend is mocked

### 4. Verify JWT Discovery in Script

```bash
# Test JWT discovery directly
uv run python scripts/mcp-test.py http://localhost:8000/mcp \
    --jwt \
    --verbose \
    --config scripts/tests/mcp-test.yaml
```

**Expected** (with quilt3 login):

```
🔐 Discovering JWT token...
✅ Using JWT from quilt3 session
   Token preview: eyJhbGci...iOiJKV1Q
```

## Edge Cases

### No PLATFORM_TEST_JWT_TOKEN

- Falls back to quilt3 session
- If no quilt3 login, falls back to generated test JWT
- Generated JWT prints warning: "may not work with real servers"

### quilt3 not installed

- `import quilt3` fails gracefully (try/except)
- Falls back to generated test JWT
- Tests continue (may fail backend validation)

### Invalid JWT in environment

- Malformed JWT passed to backend
- Backend validation fails (expected)
- Error message shows validation failure

### JWT expires during test

- Real JWTs have expiration times
- Backend rejects expired JWT
- User must re-login (`quilt3 login`)
- Or refresh `PLATFORM_TEST_JWT_TOKEN`

## Impact Assessment

### Files Modified

- ✅ `scripts/mcp-test.py` - Replace ~10 lines (lines 1086-1095)

### Tests Affected

- ✅ `make test-mcp-docker` - Will use real JWTs when available
- ✅ Backward compatible - still generates test JWT as fallback

### Breaking Changes

- ✅ None - Adds JWT discovery, keeps fallback behavior

### Backward Compatibility

- ✅ Fully backward compatible
- ✅ Old behavior (generated JWT) still works as fallback
- ✅ New behavior (real JWT) is opt-in via env var or quilt3 login

### CI/CD Impact

- ✅ GitHub Actions already sets `PLATFORM_TEST_JWT_SECRET` (see `.github/workflows/`)
- ✅ Need to verify if `PLATFORM_TEST_JWT_TOKEN` is available
- ✅ Fallback ensures tests don't break if token unavailable

## Related Infrastructure

### JWT Extraction Middleware

**File**: `src/quilt_mcp/middleware/jwt_extraction.py`

- Extracts JWT from `Authorization: Bearer` headers
- **Does NOT validate locally** - passes through to backend
- This is correct: backend validates JWT signatures

### Backend Mode Fixture

**File**: `tests/conftest.py`, lines 234-265

- Already implements correct JWT discovery
- This fix brings mcp-test.py to parity
- Same logic, same behavior

### Make Target

**File**: `make.dev:163-178`

- No changes needed
- Already passes `--jwt` flag to `mcp-test.py`
- Fix is internal to `mcp-test.py`

### CI/CD

**File**: `.github/workflows/push.yml` and `.github/workflows/pr.yml`

- Already sets `PLATFORM_TEST_JWT_SECRET` secret
- May need to add `PLATFORM_TEST_JWT_TOKEN` for full testing
- Or rely on quilt3 login in CI environment

## Conclusion

This is a **~20 line change** that brings Docker tests to parity with other tests. The JWT infrastructure is complete:

- ✅ JWT extraction middleware (passes through to backend)
- ✅ Backend validation (GraphQL validates JWT signatures)
- ✅ JWT discovery in other tests (`backend_mode` fixture)
- ❌ **JWT discovery missing in mcp-test.py** ← This fix

**Key Insight**: JWT secrets are legacy BS. The middleware just extracts and passes tokens through. The backend validates them. Docker tests need **real JWTs** like other tests use.

**Confidence**: High - This brings mcp-test.py to parity with conftest.py's backend_mode fixture, which is proven and tested.

## References

- `spec/a22-docker-remote/01-jwt-auth.md` - JWT authentication analysis
- `src/quilt_mcp/auth/jwt_discovery.py` - JWT discovery implementation
- `src/quilt_mcp/middleware/jwt_extraction.py` - HTTP JWT extraction
- `scripts/docker_manager.py` - Docker container management
- `scripts/mcp-test.py` - MCP HTTP test client
- `tests/conftest.py` - Test utilities including `make_test_jwt()`
- `docs/deployment/jwt-mode-docker.md` - JWT deployment documentation

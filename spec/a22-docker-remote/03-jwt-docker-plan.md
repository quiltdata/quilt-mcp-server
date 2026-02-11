# Plan: Require Real JWTs for Docker Testing

## Context

The current `make test-mcp-docker` target generates fake test JWTs that fail validation against real GraphQL backends. The JWT middleware passes tokens through to the backend without local validation, so fake JWTs give false confidence - tests may "pass" locally but fail in production.

**Problem**: Spec `spec/a22-docker-remote/02-jwt-docker-fix.md` proposes adding JWT discovery but keeps a fallback to fake JWTs for "backward compatibility". This is problematic because:
- Fake JWTs fail backend validation (false negatives)
- Developers get no signal that authentication is broken
- Tests don't match production behavior

**Solution**: Docker tests must use **real JWTs only**. No fake JWTs, no escape hatches. If you need mocked tests, use pytest unit/func tests, not Docker tests.

## Implementation Approach

### 1. Update the Spec to Require Real JWTs

**File**: [spec/a22-docker-remote/02-jwt-docker-fix.md](spec/a22-docker-remote/02-jwt-docker-fix.md)

Modify the "After" implementation (lines 107-144) to match `conftest.py` pattern:

```python
if args.jwt:
    # Discover JWT using same logic as backend_mode fixture
    if transport != "http":
        print("❌ --jwt only supported for HTTP transport")
        sys.exit(1)

    print("🔐 Discovering JWT token...")

    # JWT Discovery Priority:
    # 1. PLATFORM_TEST_JWT_TOKEN env var (explicit test token)
    # 2. quilt3 session (from `quilt3 login`)
    # 3. FAIL - Docker tests require real JWTs

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

    # 3. FAIL - No fake JWTs in Docker tests
    if not jwt_token:
        print("❌ Docker tests require real JWT authentication.")
        print("   Options:")
        print("     1. Set PLATFORM_TEST_JWT_TOKEN environment variable")
        print("     2. Run 'quilt3 login' to authenticate")
        print()
        print("   For mocked tests, use pytest (make test-func or make test-e2e)")
        sys.exit(1)

    if args.verbose and jwt_token:
        masked = f"{jwt_token[:8]}...{jwt_token[-8:]}" if len(jwt_token) > 16 else "***"
        print(f"   Token preview: {masked}")
```

**Key changes from current spec**:
- Remove unconditional fallback to fake JWT (lines 136-139 in current spec)
- **No escape hatch** - Docker tests require real JWTs, period
- Add clear error message directing users to pytest for mocked tests
- Use `sys.exit(1)` to fail fast (standalone script behavior)

### 2. Update Spec Documentation

**File**: [spec/a22-docker-remote/02-jwt-docker-fix.md](spec/a22-docker-remote/02-jwt-docker-fix.md)

Update these sections to reflect the stricter JWT requirement:

**Section "Expected Behavior After Fix" (lines 154-191)**:
- Update "Fallback (no real JWT)" scenario to show it **fails** (no escape hatch)
- Remove any mention of fake JWT fallback

**Section "Edge Cases" (lines 256-278)**:
- Update "No PLATFORM_TEST_JWT_TOKEN" to show failure with clear guidance
- Direct users to pytest for mocked tests

**Section "Backward Compatibility" (lines 291-295)**:
- **Breaking change**: Docker tests now require real JWTs
- Users needing mocked tests should use `make test-func` or `make test-e2e` (pytest)
- This is intentional - Docker tests validate production deployment

**Section "CI/CD Impact" (lines 296-300)**:
- CI **must** set `PLATFORM_TEST_JWT_TOKEN` (real JWT from secrets)
- Or run `quilt3 login` in CI setup
- No fake JWTs in CI - ensures tests validate real authentication

### 3. Update Validation Plan

**File**: [spec/a22-docker-remote/02-jwt-docker-fix.md](spec/a22-docker-remote/02-jwt-docker-fix.md)

**Section "Validation Plan" (lines 193-255)**:

Add new test case:

```bash
### 4. Test Failure Without Real JWT (Expected Behavior)

# Clear authentication (no real JWT available)
quilt3 logout
unset PLATFORM_TEST_JWT_TOKEN

# Run Docker tests
make test-mcp-docker
```

**Expected**:

- Output: `❌ Docker tests require real JWT authentication.`
- Output shows 2 options (env var or quilt3 login)
- Output directs to pytest for mocked tests
- Test exits with code 1 (fails fast)
- Does NOT proceed with fake JWT

## Critical Files

- [spec/a22-docker-remote/02-jwt-docker-fix.md](spec/a22-docker-remote/02-jwt-docker-fix.md) - Update JWT discovery logic and documentation
- [scripts/mcp-test.py](scripts/mcp-test.py) - Implement JWT discovery (lines ~1086-1104)
- [tests/conftest.py](tests/conftest.py) - Reference implementation (lines 234-275)

## Reference Pattern

The implementation is **stricter** than `tests/conftest.py` (which allows `ALLOW_GENERATED_TEST_JWT`):

```python
# JWT Discovery Priority for Docker tests:
# 1. PLATFORM_TEST_JWT_TOKEN env var (explicit test token)
# 2. quilt3 session (from `quilt3 login`)
# 3. FAIL - No fake JWTs in Docker tests
```

This ensures:
- ✅ Docker tests validate production deployment only
- ✅ Real JWTs required (no exceptions)
- ✅ Clear error messages guide developers to pytest for mocked tests
- ✅ No false confidence from fake JWTs
- ✅ Fail fast if authentication not configured

## Verification

After implementing changes:

1. **With real JWT (quilt3 login)**:

   ```bash
   quilt3 login
   make test-mcp-docker
   # Expected: ✅ Using JWT from quilt3 session + tests pass
   ```

2. **With environment JWT**:

   ```bash
   export PLATFORM_TEST_JWT_TOKEN="<real-jwt>"
   make test-mcp-docker
   # Expected: ✅ Using JWT from PLATFORM_TEST_JWT_TOKEN + tests pass
   ```

3. **Without real JWT (should fail fast)**:

   ```bash
   quilt3 logout
   unset PLATFORM_TEST_JWT_TOKEN
   make test-mcp-docker
   # Expected: ❌ Docker tests require real JWT authentication + exit 1
   ```

## Benefits

1. **Fail fast**: Developers get immediate feedback if JWT auth is broken
2. **Matches production**: Docker tests use real JWTs like production deployment
3. **Clear separation**: Docker = production validation, pytest = mocked tests
4. **Clear guidance**: Error messages direct developers to the right test mode
5. **No false confidence**: Tests CANNOT pass with fake JWTs
6. **Simpler code**: No escape hatch logic, no edge cases, just real JWTs

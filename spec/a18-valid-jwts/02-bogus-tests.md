# Why JWT Tests Are Lying: Root Cause Analysis

**Status:** CRITICAL SECURITY/TESTING ISSUE
**Date:** 2026-02-04
**Author:** Ernest Prabhakar (Analysis)

## Executive Summary

The JWT tests appear to succeed but are **fundamentally bogus**. They validate JWT **signature** but never test actual **authentication** or **credential exchange**. This creates a false sense of security while hiding critical authentication failures.

## The Horror: Multi-Layer Deception

### Layer 1: Fake JWT Tokens

The tests use static fixture JWTs signed with `"test-secret"`:

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjgxYTM1MjgyLTAxNDktNGViMy1iYjhlLTYyNzM3OWRiNmExYyIsInV1aWQiOiIzY2FhNDlhOS0zNzUyLTQ4NmUtYjk3OS01MWEzNjlkNmRmNjkiLCJleHAiOjE3NzY4MTcxMDR9.jJ-162LQHV3472kIEsvhyP3Dzbw_-7yV7CR5V0vL6nc",
  "payload": {
    "id": "81a35282-0149-4eb3-bb8e-627379db6a1c",
    "uuid": "3caa49a9-3752-486e-b979-51a369d6df69",
    "exp": 1776817104  // April 21, 2026 - STATIC!
  }
}
```

**Source:** `tests/fixtures/data/sample-catalog-jwt.json`
**Used by:** `tests/jwt_helpers.py::get_sample_catalog_token()`
**Secret:** Signed with `"test-secret"` (hardcoded test value)

### Layer 2: Matching Test Secret

The test infrastructure uses the SAME fake secret:

**In make.dev (line 193):**
```bash
test-mcp-stateless: docker-build
    ...
    --jwt-secret "test-secret" && \
```

**In docker_manager.py (line 279):**
```python
if not jwt_secret:
    jwt_secret = "test-secret"  # Default JWT secret for testing

env_vars = {
    "QUILT_MULTIUSER_MODE": "true",
    "MCP_JWT_SECRET": jwt_secret,  # Uses "test-secret"
    ...
}
```

**Result:** The JWT decoder validates the signature successfully because:
- Token was signed with `"test-secret"`
- Server validates with `MCP_JWT_SECRET="test-secret"`
- Signature validation passes ✓

### Layer 3: Middleware Validation (The Lie)

The JWT middleware validates tokens in `src/quilt_mcp/middleware/jwt_middleware.py`:

```python
class JwtAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract Bearer token from Authorization header
        token = auth_header[7:].strip()

        # Decode and validate JWT
        try:
            claims = self.decoder.decode(token)  # ← PASSES with fake token!
        except JwtDecodeError as exc:
            return _error_response(403, f"Invalid JWT: {exc.detail}")

        # Store claims in runtime context
        auth_state = RuntimeAuthState(
            scheme="Bearer",
            access_token=token,
            claims=claims
        )
        push_runtime_context(environment=get_runtime_environment(), auth=auth_state)

        # Continue processing request
        response = await call_next(request)
        return response
```

**What it validates:**
- ✅ JWT signature matches secret
- ✅ JWT is not expired (exp > current time)
- ✅ JWT has required claims (id/uuid, exp)
- ✅ JWT has no extra claims

**What it DOES NOT validate:**
- ❌ Token is from a real catalog
- ❌ Token can be exchanged for AWS credentials
- ❌ User actually exists in the catalog
- ❌ User has permissions for any resources

### Layer 4: The Credential Exchange That Never Happens

The **real** authentication happens in `src/quilt_mcp/services/jwt_auth_service.py`:

```python
class JWTAuthService:
    def get_boto3_session(self):
        """Get boto3 session with temporary AWS credentials from JWT."""
        # Validate JWT token
        claims = self._decoder.decode(runtime_auth.access_token)

        # Get or refresh AWS credentials  ← THIS IS WHERE IT WOULD FAIL
        credentials = self._get_or_refresh_credentials(runtime_auth.access_token)

        return boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
        )

    def _fetch_temporary_credentials(self, access_token: str) -> Dict[str, Any]:
        """Exchange JWT token for temporary AWS credentials."""
        registry_url = os.getenv("QUILT_REGISTRY_URL")
        endpoint = f"{registry_url.rstrip('/')}/api/auth/get_credentials"
        headers = {"Authorization": f"Bearer {access_token}"}

        # THIS HTTP REQUEST WOULD FAIL WITH FAKE JWT
        response = requests.get(endpoint, headers=headers, timeout=30)

        if response.status_code == 401:
            raise JwtAuthServiceError("JWT token invalid or expired")
```

**This is where fake JWTs would fail:**
1. Server makes HTTP request to `{QUILT_REGISTRY_URL}/api/auth/get_credentials`
2. Sends fake JWT in Authorization header
3. Catalog validates JWT against its own secret (NOT "test-secret")
4. Catalog rejects token with 401 Unauthorized
5. Server raises `JwtAuthServiceError`

**But the tests NEVER call this code path!**

## Why Tests Pass: The Smoking Gun

### test-mcp-stateless Test Flow

**From make.dev (lines 184-200):**
```bash
test-mcp-stateless: docker-build
    @echo "🔐 Testing stateless MCP with JWT authentication..."
    @export TEST_DOCKER_IMAGE=quilt-mcp:test && \
        uv run python scripts/docker_manager.py start \
            --mode stateless \
            --image $$TEST_DOCKER_IMAGE \
            --name mcp-stateless-test \
            --port 8002 \
            --jwt-secret "test-secret" && \
        (uv run python scripts/mcp-test.py http://localhost:8002/mcp \
            --jwt \
            --tools-test --resources-test \
            --config scripts/tests/mcp-test.yaml && \
        uv run python scripts/docker_manager.py stop --name mcp-stateless-test) || \
        (uv run python scripts/docker_manager.py stop --name mcp-stateless-test && exit 1)
```

**What it does:**
1. Starts Docker container with `MCP_JWT_SECRET="test-secret"`
2. Runs `mcp-test.py --jwt --tools-test --resources-test`
3. Stops container

**From scripts/mcp-test.py (lines 1604-1619):**
```python
if args.jwt:
    # Use sample catalog JWT for testing
    print("🔐 Using sample catalog JWT token...")
    try:
        jwt_token = get_sample_catalog_token()  # ← Gets fake JWT from fixture
        if args.verbose:
            masked = f"{jwt_token[:8]}...{jwt_token[-8:]}" if len(jwt_token) > 16 else "***"
            print(f"   Token preview: {masked}")
    except Exception as e:
        print(f"❌ Failed to load sample JWT token: {e}")
        sys.exit(1)
```

**What mcp-test.py tests:**
- `--tools-test`: Validates MCP protocol tools registration
- `--resources-test`: Validates MCP protocol resources registration

### The Critical Insight: Tests Don't Use S3

**From scripts/tests/mcp-test.yaml**, the test only calls these tools:

```yaml
test_tools:
  bucket_objects_list:
    arguments:
      bucket: quilt-ernest-staging
      prefix: raw/test/
      max_keys: 5
```

**BUT:** Looking at mcp-test.py implementation, `--tools-test` and `--resources-test` just verify:
- Tools are registered in MCP protocol
- Resources are registered in MCP protocol
- Schema validation passes
- No actual tool EXECUTION happens

**Evidence from mcp-test.py (lines 717-778):**
```python
def run_test_suite(
    stdin_fd: Optional[int] = None,
    stdout_fd: Optional[int] = None,
    endpoint: Optional[str] = None,
    transport: str = "stdio",
    verbose: bool = False,
    tools_test: bool = False,
    resources_test: bool = False,
    config: Optional[dict] = None,
    ...
) -> bool:
    """Run test suite with tools and/or resources tests."""

    if tools_test:
        # Create ToolsTester instance
        tester = ToolsTester(...)
        success = tester.run_all_tools()  # ← Just validates tool registration

    if resources_test:
        # Create ResourcesTester instance
        tester = ResourcesTester(...)
        success = tester.run_all_resources()  # ← Just validates resource registration
```

### What Actually Gets Tested

The tests validate:

1. **JWT Middleware accepts token** ✓
   - Signature validates (both use "test-secret")
   - Token not expired (exp: 2026-04-21)
   - Claims present (id, uuid, exp)

2. **MCP Protocol works** ✓
   - Tools registered correctly
   - Resources registered correctly
   - Schema validation passes

**What NEVER gets tested:**
- ❌ Calling any tool that needs AWS credentials
- ❌ JWT credential exchange with catalog
- ❌ S3 access with temporary credentials
- ❌ User permissions validation
- ❌ Actual catalog authentication

## The Search Failure: Evidence of the Problem

From `spec/a11-client-testing/09-stateless-mcp-test-analysis.md`, we see:

**Search tests FAIL:**
```
❌ search_catalog.global.no_bucket - ValidationError: Expected at least 1 results, got 0
❌ search_catalog.file.no_bucket - ValidationError: Expected at least 1 results, got 0
❌ search_catalog.package.no_bucket - ValidationError: Expected at least 1 results, got 0
```

**Why?** Because search requires catalog authentication:
1. Search calls `UnifiedSearchEngine`
2. Which calls `Quilt3ElasticsearchBackend`
3. Which calls `self.quilt_service.get_session()`
4. Which requires `quilt3.login()` or JWT catalog auth
5. **But we only have fake JWT that catalog doesn't recognize!**

The search failures prove that **real catalog operations fail** even though **JWT validation passes**.

## The Architecture: Multi-Layer Validation

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: HTTP Request with JWT                          │
│ Authorization: Bearer eyJhbGci...                        │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Layer 2: JWT Middleware (jwt_middleware.py)             │
│ - Validates signature with MCP_JWT_SECRET                │
│ - Checks expiration                                      │
│ - Validates claims structure                             │
│ - Stores token in runtime context                        │
│ ✅ PASSES with fake JWT!                                 │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Layer 3: MCP Tool Handler                                │
│ - Receives validated JWT from context                    │
│ - Calls backend operation                                │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Layer 4: Backend Operation (IF it needs AWS)             │
│ - Calls jwt_auth_service.get_boto3_session()            │
│ - Exchanges JWT for AWS credentials                      │
│ - Makes HTTP request to catalog                          │
│ ❌ FAILS with fake JWT!                                  │
│ ⚠️  BUT TESTS NEVER REACH THIS LAYER!                    │
└─────────────────────────────────────────────────────────┘
```

## Root Cause Summary

**The tests are lying because:**

1. **Validation vs Authentication Confusion**
   - Tests validate JWT **signature** (cryptographic validity)
   - Tests DO NOT validate JWT **authentication** (catalog recognition)
   - These are completely different security properties!

2. **Test Coverage Gap**
   - Tests only verify MCP protocol registration
   - Tests never call tools that require AWS credentials
   - Tests never trigger credential exchange
   - Therefore fake JWTs appear to work

3. **False Security**
   - Passing tests suggest JWT auth works
   - Reality: Only signature validation works
   - Actual authentication is completely untested
   - Production would fail immediately on first S3 operation

4. **Architectural Blind Spot**
   - JWT middleware (Layer 2) succeeds
   - Credential exchange (Layer 4) never tested
   - Tests validate protocol, not authentication
   - Gap between validation and actual usage

## Impact Assessment

### What Works (Misleadingly)

- ✅ JWT signature validation
- ✅ JWT expiration checking
- ✅ JWT claims validation
- ✅ MCP protocol operations
- ✅ Tool/resource registration

### What Fails (Hidden)

- ❌ AWS credential exchange
- ❌ Catalog authentication
- ❌ S3 operations requiring credentials
- ❌ Search operations requiring catalog auth
- ❌ Any real-world usage with catalog

### Security Implications

**CRITICAL:** The test suite provides false confidence in JWT authentication while the actual authentication is completely broken.

1. **Production Deployment Risk**
   - Tests pass, giving green light
   - Deploy to production
   - First real operation fails with 401 Unauthorized
   - Users cannot access any S3 resources

2. **Attack Surface**
   - Anyone can generate valid-looking JWT with "test-secret"
   - JWT passes middleware validation
   - Only fails when trying to get AWS credentials
   - Creates window for token replay attacks

3. **Audit Failure**
   - Tests claim JWT auth works
   - Audit shows JWT validation in code
   - But actual authentication never tested
   - False compliance evidence

## Why This Is So Dangerous

This is worse than tests that simply don't exist because:

1. **False Confidence:** Tests pass, creating belief that auth works
2. **Hidden Failures:** Real failures only happen in production
3. **Security Theatre:** Appears secure but isn't
4. **Difficult Diagnosis:** When it fails, JWT validation passes, making debugging confusing

## The Fix (Not Implemented - Analysis Only)

The tests need to:

1. **Use real JWT tokens** from actual quilt3 authentication
2. **Test credential exchange** by actually calling tools that need S3
3. **Verify AWS operations** work with exchanged credentials
4. **Separate unit tests** (signature validation) from **integration tests** (full auth flow)

But this document is analysis only, not implementation.

## Related Issues

- `spec/a18-valid-jwts/01-bogus-jwts.md` - Original problem discovery
- `spec/a17-test-cleanup/07-jwt-credentials-implementation.md` - JWT to AWS credentials flow
- `spec/a11-client-testing/09-stateless-mcp-test-analysis.md` - Search failure evidence
- `spec/a11-client-testing/12-stateless-authentication-flaw.md` - Auth design flaw

## Conclusion

The JWT tests succeed because they test **JWT signature validation** (which works with fake tokens) but never test **JWT authentication** (which would fail with fake tokens). This creates a dangerous false positive where tests pass but production authentication is completely broken.

The tests are not testing authentication - they're testing that we can validate a signature on a token we created ourselves. That's not security, that's just cryptography homework.

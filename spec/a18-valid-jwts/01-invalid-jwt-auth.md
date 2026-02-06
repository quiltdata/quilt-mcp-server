# Invalid JWT Authentication Architecture

**Status:** CRITICAL ARCHITECTURAL FLAW
**Date:** 2026-02-05
**Author:** Ernest Prabhakar

## Executive Summary

The MCP server's JWT testing is fundamentally flawed because it tests **local JWT validation** when the actual architecture is **JWT pass-through to GraphQL**. The MCP server never validates JWTs - it simply forwards them to the Platform GraphQL backend, which does the real validation.

**All JWT validation tests are meaningless.**

## The Architectural Reality

### What We Thought

```
Client → MCP Server (validates JWT) → GraphQL (trusts MCP)
```

### What Actually Happens

```
Client → MCP Server (passes JWT through) → GraphQL (validates JWT)
```

### The Code Proof

**In `src/quilt_mcp/backends/platform_backend.py`:**

```python
class Platform_Backend(TabulatorMixin, QuiltOps):
    def __init__(self) -> None:
        self._access_token = self._load_access_token()  # Line 43: Extract JWT

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self._access_token}",  # Line 71: Add to headers
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def execute_graphql_query(self, query: str, ...) -> Dict[str, Any]:
        endpoint = self.get_graphql_endpoint()
        headers = self.get_graphql_auth_headers()  # Line 110: Get JWT header

        # Line 115: Pass JWT through to GraphQL
        response = self._session.post(endpoint, json=payload, headers=headers, timeout=30)

        # Lines 126-131: GraphQL validates and returns 401/403 if invalid
        except self._requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in {401, 403}:
                raise AuthenticationError("GraphQL query not authorized") from exc
```

**The MCP server:**

1. Extracts JWT from Authorization header
2. Stores it in `self._access_token`
3. Adds it to every GraphQL request: `Authorization: Bearer {token}`
4. **Never validates it**
5. GraphQL backend does all validation

## Why All Current Tests Are Wrong

### 1. JWT Decoder Tests (`tests/unit/test_jwt_decoder.py`)

**What they test:** JWT signature validation with `MCP_JWT_SECRET`

**Why it's wrong:** The MCP server never decodes JWTs. GraphQL does the decoding.

**Current test:**

```python
def test_decode_valid_token():
    token = get_sample_catalog_token()  # Fake JWT signed with "test-secret"
    decoder = get_jwt_decoder()
    claims = decoder.decode(token)  # Validates locally
    assert claims["id"] == "81a35282-0149-4eb3-bb8e-627379db6a1c"
```

**Reality:** This validation never happens in production because JWTs go straight to GraphQL.

### 2. JWT Middleware Tests (`tests/unit/test_jwt_middleware.py`)

**What they test:** Middleware JWT validation

**Why it's wrong:** Middleware doesn't exist in Platform backend flow - JWT goes directly to GraphQL.

### 3. JWT Authentication Tests (`tests/stateless/test_jwt_authentication.py`)

**What they test:**

- Request without JWT fails
- Request with malformed JWT fails

**Why it's wrong:** These test MCP middleware validation, not GraphQL validation. GraphQL might accept/reject different tokens than MCP's local validation.

### 4. JWT Integration Tests (`tests/func/test_jwt_integration.py`)

**What they test:** JWT token structure, claims, MCP protocol acceptance

**Why it's wrong:** They never call GraphQL endpoints, so they never test actual authentication.

### 5. Fake JWT Fixtures

**Files that must be deleted:**

- `tests/fixtures/data/sample-catalog-jwt.json`
- `tests/fixtures/data/sample-catalog-jwt-expired.json`
- `tests/fixtures/data/sample-catalog-jwt-missing-exp.json`
- `tests/fixtures/data/sample-catalog-jwt-extra-claim.json`

**Why:** These are fake JWTs signed with `"test-secret"`. They perpetuate testing that doesn't match reality.

**From `tests/fixtures/data/sample-catalog-jwt.json`:**

```json
{
  "token": "eyJhbGci...fake-token-signed-with-test-secret...",
  "payload": {
    "id": "81a35282-0149-4eb3-bb8e-627379db6a1c",
    "uuid": "3caa49a9-3752-486e-b979-51a369d6df69",
    "exp": 1776817104
  }
}
```

This JWT is useless because GraphQL will reject it immediately.

## The ONLY Valid Test

The only meaningful JWT test is:

```python
def test_jwt_authentication_with_real_graphql():
    """Test JWT auth by actually calling GraphQL."""
    # 1. Get real JWT from quilt3
    token = get_real_jwt_from_quilt3()

    # 2. Call MCP tool that uses Platform backend
    result = call_mcp_tool("bucket_list", auth=token)

    # 3. Verify it returns real data (not an auth error)
    assert len(result.buckets) > 0
    assert result.status != "unauthorized"
```

**This tests:**

- JWT extraction from Authorization header ✓
- JWT pass-through to GraphQL ✓
- GraphQL validation of JWT ✓
- GraphQL returning actual data ✓

## What JWT Validation Actually Tests

All the current JWT validation tests are testing code that's **not used in production**:

### JWT Decoder (`src/quilt_mcp/services/jwt_decoder.py`)

**What it does:** Validates JWT signature with `MCP_JWT_SECRET`

**Where it's used:**

- JWT middleware (only in stateful mode?)
- Some auth services

**Where it's NOT used:**

- Platform backend (which is what we're testing)

### JWT Middleware (`src/quilt_mcp/middleware/jwt_middleware.py`)

**What it does:** Validates JWT before passing to backend

**Reality:** Platform backend bypasses this - JWT goes straight through

## The Testing Strategy Should Be

### Unit Tests: DELETE

Delete all JWT validation unit tests. They test code that doesn't run.

**Files to delete:**

- `tests/unit/test_jwt_decoder.py`
- `tests/unit/test_jwt_middleware.py`
- `tests/unit/test_jwt_auth_service.py`
- `tests/fixtures/data/sample-catalog-jwt*.json`

### Integration Tests: REPLACE

Replace fake JWT tests with real GraphQL tests.

**Current (WRONG):**

```python
def test_jwt_middleware_validates_token():
    token = get_sample_catalog_token()  # Fake JWT
    # Test local validation
    assert middleware.validate(token)  # Meaningless
```

**Correct:**

```python
def test_jwt_authenticates_with_graphql():
    token = get_real_jwt_from_quilt3()  # Real JWT
    backend = Platform_Backend()
    # This actually calls GraphQL
    status = backend.get_auth_status()  # GraphQL validates JWT
    assert status.is_authenticated
```

### E2E Tests: ONLY THING THAT MATTERS

```python
def test_end_to_end_jwt_auth():
    """The ONLY test that matters for JWT auth."""
    # 1. Obtain valid JWT (from quilt3 or catalog login)
    token = quilt3.session.get_access_token()

    # 2. Call Platform backend (directly or via MCP tool)
    backend = Platform_Backend()
    os.environ["QUILT_ACCESS_TOKEN"] = token

    # 3. Ensure it ACTUALLY calls GraphQL and returns valid data
    buckets = backend.list_buckets()  # Calls GraphQL

    # 4. Verify real data returned (proves GraphQL accepted JWT)
    assert len(buckets) > 0
    assert buckets[0].name  # Real bucket name
```

## Why This Matters

### Current State: False Confidence

- Tests pass ✓
- JWT validation "works" ✓
- Ship to production ✓
- **First GraphQL call fails with 401 Unauthorized** ✗

### Security Implications

1. **Local validation is security theater:** MCP validates with `test-secret`, GraphQL validates with real secret
2. **Token acceptance mismatch:** MCP accepts tokens GraphQL rejects
3. **No actual auth testing:** All tests mock away the real validation
4. **Production failures:** First real user hits 401 immediately

### Development Implications

1. **Wasted effort:** Maintaining JWT validation code that never runs
2. **Wrong debugging:** When auth fails, developers look at MCP validation (which passes) instead of GraphQL (which fails)
3. **Fake fixtures:** Maintaining fake JWTs that don't work in production
4. **Test maintenance:** Tests that don't test reality

## The Fix

### 1. Delete Fake JWT Infrastructure

**Delete these files:**

```bash
rm tests/fixtures/data/sample-catalog-jwt*.json
rm tests/unit/test_jwt_decoder.py
rm tests/unit/test_jwt_middleware.py
rm tests/unit/test_jwt_auth_service.py
```

**Update `tests/jwt_helpers.py`:**

```python
# DELETE these functions
def get_sample_catalog_token() -> str: ...
def load_sample_catalog_jwt() -> Dict: ...

# REPLACE with
def get_real_jwt_from_quilt3() -> str:
    """Extract real JWT from quilt3 authentication."""
    from quilt3.session import _load_auth
    from quilt3.util import get_from_config

    registry_url = get_from_config('registryUrl')
    auth = _load_auth()
    return auth[registry_url]['access_token']
```

### 2. Write Real Integration Tests

**New test file: `tests/integration/test_graphql_jwt_auth.py`:**

```python
"""Test JWT authentication with real GraphQL backend.

These tests verify that JWT tokens are correctly passed through to
the Platform GraphQL backend, which performs the actual validation.
"""

import pytest
from quilt_mcp.backends.platform_backend import Platform_Backend
from quilt_mcp.ops.exceptions import AuthenticationError


def test_valid_jwt_calls_graphql_successfully():
    """Test that valid JWT from quilt3 authenticates with GraphQL."""
    # Requires: quilt3 configured and authenticated
    # Requires: QUILT_CATALOG_URL and QUILT_REGISTRY_URL set

    backend = Platform_Backend()

    # This calls GraphQL: query { me { name email isAdmin } }
    status = backend.get_auth_status()

    assert status.is_authenticated
    assert status.catalog_name
    assert status.registry_url


def test_invalid_jwt_fails_at_graphql():
    """Test that invalid JWT is rejected by GraphQL."""
    import os

    # Set fake JWT
    os.environ["QUILT_ACCESS_TOKEN"] = "fake-jwt-token"

    backend = Platform_Backend()

    # This should fail when GraphQL validates the JWT
    with pytest.raises(AuthenticationError, match="not authorized"):
        backend.get_auth_status()


def test_list_buckets_with_valid_jwt():
    """Test that list_buckets works with real JWT."""
    backend = Platform_Backend()

    # This calls GraphQL: query { bucketConfigs { name } }
    buckets = backend.list_buckets()

    assert isinstance(buckets, list)
    assert len(buckets) > 0
    assert buckets[0].name  # Real bucket name


def test_search_packages_with_valid_jwt():
    """Test that search_packages works with real JWT."""
    backend = Platform_Backend()

    # This calls GraphQL: query SearchPackages(...)
    results = backend.search_packages("test", "s3://test-bucket")

    assert isinstance(results, list)
    # May be empty, but should not raise AuthenticationError
```

### 3. Update E2E Tests

**Update `tests/e2e/test-e2e-platform.sh`:**

```bash
#!/bin/bash
# E2E test for Platform backend with JWT authentication

set -e

echo "🔐 Testing JWT authentication with real GraphQL backend..."

# 1. Verify quilt3 is authenticated
if ! uv run python -c "from quilt3.session import _load_auth; _load_auth()" 2>/dev/null; then
    echo "❌ Not authenticated with quilt3"
    echo "Run: quilt3 config https://your-catalog.quiltdata.com"
    exit 1
fi

# 2. Test Platform backend with real JWT
uv run python -c "
from quilt_mcp.backends.platform_backend import Platform_Backend

backend = Platform_Backend()

# Test 1: Auth status
status = backend.get_auth_status()
assert status.is_authenticated, 'JWT auth failed'
print(f'✓ Authenticated as {status.catalog_name}')

# Test 2: List buckets
buckets = backend.list_buckets()
assert len(buckets) > 0, 'No buckets returned'
print(f'✓ Listed {len(buckets)} buckets')

# Test 3: Search packages
results = backend.search_packages('', buckets[0].name)
print(f'✓ Search returned {len(results)} packages')
"

echo "✅ JWT authentication with GraphQL backend works!"
```

## Implementation Plan

1. **Delete fake JWT fixtures** (5 min)
   - Delete `tests/fixtures/data/sample-catalog-jwt*.json`
   - Update `tests/jwt_helpers.py` to use real JWTs

2. **Delete invalid unit tests** (5 min)
   - Delete `tests/unit/test_jwt_decoder.py`
   - Delete `tests/unit/test_jwt_middleware.py`
   - Delete portions of other tests using fake JWTs

3. **Write real integration tests** (30 min)
   - Create `tests/integration/test_graphql_jwt_auth.py`
   - Test real JWT → Platform backend → GraphQL flow

4. **Update E2E tests** (15 min)
   - Update `tests/e2e/test-e2e-platform.sh`
   - Verify end-to-end JWT auth with GraphQL

5. **Update documentation** (10 min)
   - Document that JWT validation happens at GraphQL
   - Explain pass-through architecture

## Success Criteria

- [ ] All fake JWT fixtures deleted
- [ ] All JWT validation unit tests deleted
- [ ] Real integration tests call GraphQL with real JWTs
- [ ] E2E tests verify end-to-end JWT → GraphQL flow
- [ ] Tests fail appropriately with invalid JWTs
- [ ] Tests pass with valid JWTs from quilt3

## Related Specs

- `spec/a18-jwt-testing/01-bogus-jwts.md` - Fake JWT problem
- `spec/a18-jwt-testing/02-bogus-tests.md` - Test architecture analysis
- `spec/a17-test-cleanup/07-jwt-credentials-implementation.md` - JWT to AWS credentials

## Conclusion

The current JWT testing is fundamentally flawed because it tests local validation when the architecture is pass-through to GraphQL. All JWT validation tests should be deleted and replaced with integration tests that actually call GraphQL with real JWTs.

**The only test that matters:** Pass a JWT to GraphQL via Platform backend, verify it returns real data.

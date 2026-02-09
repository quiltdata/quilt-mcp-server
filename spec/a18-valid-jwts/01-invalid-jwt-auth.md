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

The only meaningful JWT test must:

1. Obtain a **real JWT** from quilt3 authentication
2. Call a Platform backend operation that invokes GraphQL
3. Verify it returns **real data** (proving GraphQL accepted the JWT)

**This would test:**

- JWT extraction from Authorization header ✓
- JWT pass-through to GraphQL ✓
- GraphQL validation of JWT ✓
- GraphQL returning actual data ✓

**Current tests do none of this.**

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

## Related Specs

- `spec/a18-jwt-testing/01-bogus-jwts.md` - Fake JWT problem
- `spec/a18-jwt-testing/02-bogus-tests.md` - Test architecture analysis
- `spec/a17-test-cleanup/07-jwt-credentials-implementation.md` - JWT to AWS credentials

## Conclusion

The current JWT testing is fundamentally flawed because it tests local validation when the architecture is JWT pass-through to GraphQL.

**What's being tested:** Local JWT signature validation with fake tokens and `test-secret`

**What should be tested:** End-to-end flow with real JWT → Platform backend → GraphQL
→ real data

The test suite provides false confidence while the actual authentication mechanism remains completely untested.

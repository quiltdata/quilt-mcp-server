# Bogus JWT Tokens in Tests

**Status:** CRITICAL BUG
**Date:** 2025-02-04
**Author:** Ernest Prabhakar

## Problem Statement

The test suite uses **static JWT fixture files** instead of **real JWT tokens extracted from quilt3 authentication**. This means all tests claiming to validate JWT authentication may be completely bogus.

### The Horror

```python
# tests/jwt_helpers.py - CURRENT (WRONG)
def get_sample_catalog_token() -> str:
    """Load static JWT from fixture file."""
    return load_sample_catalog_jwt()["token"]
    # Returns: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjgxYTM1MjgyLTAxNDktNGViMy1iYjhlLTYyNzM3OWRiNmExYyIsInV1aWQiOiIzY2FhNDlhOS0zNzUyLTQ4NmUtYjk3OS01MWEzNjlkNmRmNjkiLCJleHAiOjE3NzY4MTcxMDR9.jJ-162LQHV3472kIEsvhyP3Dzbw_-7yV7CR5V0vL6nc
    # Expiration: 2026-04-21 (STATIC!)
```

Real JWT tokens ARE available via quilt3:

```python
# What it SHOULD do
from quilt3.session import _load_auth
from quilt3.util import get_from_config

def get_sample_catalog_token() -> str:
    """Extract real JWT from quilt3 authentication."""
    registry_url = get_from_config('registryUrl')
    auth = _load_auth()
    return auth[registry_url]['access_token']
    # Returns: REAL token from ~/.local/share/Quilt/auth.json
    # Expiration: Dynamic, refreshed by quilt3
```

## Impact Assessment

### Files Using Fake JWTs

**Core test infrastructure:**
1. `tests/conftest.py` - Imports `get_sample_catalog_token`, `get_sample_catalog_claims`
2. `tests/jwt_helpers.py` - The source of all fake tokens

**Unit tests (7 files):**
3. `tests/unit/test_jwt_decoder.py` - ALL token validation tests use fake tokens
   - `test_decode_valid_token` - Uses `get_sample_catalog_token()`
   - `test_decode_expired_token` - Uses `get_expired_catalog_token()`
   - `test_decode_requires_exp` - Uses `get_missing_exp_catalog_token()`
   - `test_decode_rejects_extra_claims` - Uses `get_extra_claim_catalog_token()`

4. `tests/unit/test_jwt_middleware.py` - Middleware tests use fake tokens
   - Uses both `get_sample_catalog_token()` and `get_sample_catalog_claims()`

5. `tests/unit/test_mcp_test_jwt.py` - MCP test script validation uses fake tokens

**Functional tests (3 files):**
6. `tests/func/test_jwt_integration.py` - "Integration" tests use fake tokens
   - `test_sample_jwt_token_structure`
   - `test_sample_jwt_contains_required_claims`
   - `test_mcp_test_script_accepts_jwt_token`

7. `tests/func/test_auth_modes.py` - Auth mode tests use fake tokens
   - Uses `get_sample_catalog_token()`

**Stateless tests:**
8. `tests/stateless/conftest.py` - Stateless container tests use fake tokens

### What This Means

All these tests are **NOT actually validating JWT authentication**:

1. **JWT Decoder Tests** - Testing signature validation with wrong secret
2. **JWT Middleware Tests** - Testing middleware with tokens that don't match real catalog
3. **Integration Tests** - "Integrating" with fake tokens that catalog won't accept
4. **Stateless Tests** - Container tests with tokens that won't get AWS credentials

The tests pass because:
- They use `"test-secret"` as the JWT secret
- The static fixtures were generated with the same `"test-secret"`
- None of the tests actually connect to a real catalog or attempt AWS credential exchange

## Root Cause

The comment in `tests/jwt_helpers.py` reveals the problem:

```python
"""JWT fixture helpers for tests.

These helpers load the real catalog JWT fixture and do not generate tokens.
"""
```

This was NEVER the correct approach. The helpers should extract REAL tokens from quilt3's authentication system.

## Solution: Fix jwt_helpers.py

### Step 1: Add Real Token Extraction

```python
#!/usr/bin/env python3
"""JWT helpers for tests - extract real tokens from quilt3 authentication."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from quilt3.session import _load_auth
from quilt3.util import get_from_config


def get_configured_registry_url() -> str:
    """Get the registry URL from quilt3 configuration."""
    registry_url = get_from_config('registryUrl')
    if not registry_url:
        raise RuntimeError(
            "No registry URL configured in quilt3. "
            "Run 'quilt3 config https://your-catalog-url' first."
        )
    return registry_url


def get_real_catalog_token() -> str:
    """Extract real JWT token from quilt3 authentication.

    Returns:
        JWT access token from quilt3 auth.json

    Raises:
        RuntimeError: If not authenticated or token expired
    """
    registry_url = get_configured_registry_url()
    auth = _load_auth()

    if registry_url not in auth:
        raise RuntimeError(
            f"No authentication found for {registry_url}. "
            f"Run 'quilt3 config {registry_url.replace('registry.', '')}' to authenticate."
        )

    token_data = auth[registry_url]
    access_token = token_data.get('access_token')
    expires_at = token_data.get('expires_at')

    if not access_token:
        raise RuntimeError(f"No access token found for {registry_url}")

    # Check if token is expired
    if expires_at and expires_at < time.time():
        raise RuntimeError(
            f"Token expired at {expires_at}. "
            "Re-authenticate with quilt3 config."
        )

    return access_token


def get_real_catalog_claims() -> Dict[str, Any]:
    """Extract claims from real JWT token.

    Returns:
        Decoded JWT claims (without validation)
    """
    import base64

    token = get_real_catalog_token()
    # Decode payload without validation (tests can validate if needed)
    parts = token.split('.')
    if len(parts) != 3:
        raise RuntimeError(f"Invalid JWT structure: {len(parts)} parts")

    # Decode payload (add padding if needed)
    payload = parts[1]
    payload += '=' * (4 - len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload)

    return json.loads(decoded)


# Backward compatibility - use real tokens by default
def get_sample_catalog_token() -> str:
    """Get sample catalog token (now returns REAL token from quilt3).

    For backward compatibility, but now extracts real tokens.
    """
    return get_real_catalog_token()


def get_sample_catalog_claims() -> Dict[str, Any]:
    """Get sample catalog claims (now returns REAL claims from quilt3).

    For backward compatibility, but now extracts real claims.
    """
    return get_real_catalog_claims()


# === Static Fixture Tokens (for specific test scenarios) ===
# These should ONLY be used for testing edge cases like expired tokens

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "data" / "sample-catalog-jwt.json"
_EXPIRED_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "data" / "sample-catalog-jwt-expired.json"
_MISSING_EXP_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "data" / "sample-catalog-jwt-missing-exp.json"
_EXTRA_CLAIM_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "data" / "sample-catalog-jwt-extra-claim.json"


def load_sample_catalog_jwt() -> Dict[str, Any]:
    """Load static JWT fixture (DEPRECATED - only for edge case testing)."""
    with _FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_expired_catalog_token() -> str:
    """Get an expired JWT token for testing expiration validation."""
    with _EXPIRED_FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)["token"]


def get_missing_exp_catalog_token() -> str:
    """Get a JWT token missing the 'exp' claim for testing validation."""
    with _MISSING_EXP_FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)["token"]


def get_extra_claim_catalog_token() -> str:
    """Get a JWT token with extra claims for testing strict validation."""
    with _EXTRA_CLAIM_FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)["token"]


if __name__ == "__main__":
    """Print current real token for debugging."""
    try:
        token = get_real_catalog_token()
        print(f"Real token: {token}")

        claims = get_real_catalog_claims()
        print(f"\nClaims:")
        print(json.dumps(claims, indent=2))

        print(f"\nExpires at: {claims.get('exp')} ({time.ctime(claims.get('exp'))})")
    except RuntimeError as e:
        print(f"ERROR: {e}")
        exit(1)
```

### Step 2: Update Test Configuration

The JWT secret must match the catalog's secret. Tests need to either:

**Option A: Use real catalog secret (preferred for integration tests)**
```python
# tests/conftest.py
@pytest.fixture
def jwt_secret():
    """Get real JWT secret from environment or skip test."""
    secret = os.getenv('QUILT_CATALOG_JWT_SECRET')
    if not secret:
        pytest.skip("QUILT_CATALOG_JWT_SECRET not set - cannot test real JWT auth")
    return secret
```

**Option B: Keep test-secret for unit tests (mock the backend)**
```python
# tests/unit/test_jwt_decoder.py
def test_decode_valid_token(monkeypatch):
    # For unit tests, we can use test-secret with static fixtures
    # But make it CLEAR this is not testing real authentication
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)

    # Use static fixture explicitly
    token = load_sample_catalog_jwt()["token"]  # NOT get_sample_catalog_token()
    ...
```

### Step 3: Categorize Tests

**Unit tests** - Can continue using static fixtures with test-secret:
- `tests/unit/test_jwt_decoder.py` - Testing decoder logic
- `tests/unit/test_jwt_middleware.py` - Testing middleware logic (mock backend)

**Integration/E2E tests** - MUST use real tokens:
- `tests/func/test_jwt_integration.py` - Testing real JWT flow
- `tests/func/test_auth_modes.py` - Testing real auth modes
- `tests/stateless/` - Testing real stateless container auth
- `tests/e2e/test-e2e-platform.sh` - Testing real platform integration

## Implementation Plan

1. **Phase 1: Fix jwt_helpers.py** (1 hour)
   - Add real token extraction functions
   - Keep static fixtures for edge cases
   - Add backward compatibility

2. **Phase 2: Update Integration Tests** (2 hours)
   - Update `test_jwt_integration.py` to use real tokens
   - Update `test_auth_modes.py` to use real tokens
   - Update stateless tests to use real tokens
   - Add proper skip conditions if not authenticated

3. **Phase 3: Document Unit Test Limitations** (30 min)
   - Add comments explaining unit tests use static fixtures
   - Clarify they test decoder logic, not real authentication
   - Point to integration tests for real auth validation

4. **Phase 4: Verify E2E Tests** (1 hour)
   - Ensure `test-e2e-platform.sh` uses real tokens
   - Test with real catalog
   - Verify AWS credential exchange works

## Testing the Fix

```bash
# 1. Ensure authenticated with quilt3
quilt3 config https://your-catalog.quiltdata.com

# 2. Test new jwt_helpers
uv run python tests/jwt_helpers.py

# 3. Run integration tests with real tokens
uv run pytest tests/func/test_jwt_integration.py -v

# 4. Run E2E platform test
./tests/e2e/test-e2e-platform.sh
```

## Success Criteria

- [ ] `jwt_helpers.py` extracts real tokens from quilt3
- [ ] Integration tests use real tokens
- [ ] E2E tests verify AWS credential exchange works
- [ ] Unit tests clearly document they use static fixtures
- [ ] All tests pass with real authentication
- [ ] Tests fail appropriately when not authenticated

## Related Issues

- `spec/a17-test-cleanup/07-jwt-credentials-implementation.md` - JWT to AWS credentials
- Docker manager uses `MCP_JWT_SECRET` but tests don't validate against real catalog
- Static fixtures created with `"test-secret"` that doesn't match production

## Notes

This is a **CRITICAL** bug that undermines confidence in the entire JWT authentication system. Every test that claims to validate JWT auth may be completely bogus.

The fix is straightforward - extract real tokens from quilt3. The challenge is updating all the tests to handle real authentication (expired tokens, network issues, etc.).

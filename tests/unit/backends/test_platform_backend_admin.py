"""Unit tests for Platform_Backend admin operations.

The Platform_Backend intentionally does not implement admin operations
because the Platform GraphQL API does not expose admin-level endpoints.

This test file documents this design decision and verifies the expected
stub behavior.
"""

from __future__ import annotations

import pytest

from quilt_mcp.runtime_context import (
    RuntimeAuthState,
    get_runtime_environment,
    push_runtime_context,
    reset_runtime_context,
)


def _push_jwt_context(claims=None):
    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="test-token",
        claims=claims
        or {
            "catalog_token": "test-catalog-token",
            "catalog_url": "https://example.quiltdata.com",
            "registry_url": "https://registry.quiltdata.com",
        },
    )
    return push_runtime_context(environment=get_runtime_environment(), auth=auth_state)


def _make_backend(monkeypatch, claims=None):
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context(claims)
    try:
        from quilt_mcp.backends.platform_backend import Platform_Backend

        return Platform_Backend()
    finally:
        reset_runtime_context(token)


# ---------------------------------------------------------------------
# Admin Status (Stub)
# ---------------------------------------------------------------------


def test_get_admin_status_not_implemented(monkeypatch):
    """Verify NotImplementedError is raised for admin property.

    Platform_Backend does not implement admin operations because:

    1. The Platform GraphQL API does not expose admin-level endpoints
    2. Admin operations are typically performed through the web UI
    3. The QuiltOps interface includes admin operations for compatibility
       with Quilt3_Backend, but Platform_Backend cannot implement them

    Future considerations:
    - If Platform GraphQL API adds admin endpoints, implement them here
    - Potential admin operations would include:
      * User management (list, create, delete users)
      * Role management (assign/revoke roles)
      * Bucket configuration (create, update, delete bucket configs)
      * System monitoring and health checks
      * Audit log retrieval
    """
    backend = _make_backend(monkeypatch)

    with pytest.raises(NotImplementedError, match="Platform admin operations not yet implemented"):
        _ = backend.admin

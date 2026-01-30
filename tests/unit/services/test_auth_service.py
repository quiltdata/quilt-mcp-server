"""Unit tests for AuthService abstraction."""

from __future__ import annotations

from quilt_mcp.services.auth_service import AuthService


def test_auth_service_is_defined():
    assert AuthService.__name__ == "AuthService"

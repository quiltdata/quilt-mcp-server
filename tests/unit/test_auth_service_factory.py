"""Unit tests for auth service factory behavior."""

from __future__ import annotations

import os

import pytest

from quilt_mcp.services.auth_service import (
    AuthServiceError,
    get_auth_service,
    get_jwt_mode_enabled,
    reset_auth_service,
)
from quilt_mcp.services.iam_auth_service import IAMAuthService
from quilt_mcp.services.jwt_auth_service import JWTAuthService


def test_default_mode_is_iam(monkeypatch):
    monkeypatch.delenv("MCP_REQUIRE_JWT", raising=False)
    reset_auth_service()

    assert get_jwt_mode_enabled() is False
    service = get_auth_service()
    assert isinstance(service, IAMAuthService)


def test_jwt_mode_requires_secret(monkeypatch):
    monkeypatch.setenv("MCP_REQUIRE_JWT", "true")
    monkeypatch.delenv("MCP_JWT_SECRET", raising=False)
    monkeypatch.delenv("MCP_JWT_SECRET_SSM_PARAMETER", raising=False)
    reset_auth_service()

    with pytest.raises(AuthServiceError):
        get_auth_service()


def test_jwt_mode_enabled(monkeypatch):
    monkeypatch.setenv("MCP_REQUIRE_JWT", "true")
    monkeypatch.setenv("MCP_JWT_SECRET", "test-secret")
    reset_auth_service()

    service = get_auth_service()
    assert isinstance(service, JWTAuthService)

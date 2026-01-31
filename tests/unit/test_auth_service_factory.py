"""Unit tests for auth service factory behavior."""

from __future__ import annotations

import os

import pytest

from quilt_mcp.config import get_mode_config, set_test_mode_config
from quilt_mcp.services.auth_service import (
    AuthServiceError,
    create_auth_service,
)
from quilt_mcp.services.iam_auth_service import IAMAuthService
from quilt_mcp.services.jwt_auth_service import JWTAuthService


def test_default_mode_is_iam():
    set_test_mode_config(multitenant_mode=False)

    mode_config = get_mode_config()
    assert mode_config.requires_jwt is False
    service = create_auth_service()
    assert isinstance(service, IAMAuthService)


def test_jwt_mode_requires_secret(monkeypatch):
    # We still need to test JWT validation, which requires environment variables
    monkeypatch.delenv("MCP_JWT_SECRET", raising=False)
    monkeypatch.delenv("MCP_JWT_SECRET_SSM_PARAMETER", raising=False)
    set_test_mode_config(multitenant_mode=True)

    with pytest.raises(AuthServiceError):
        create_auth_service()


def test_jwt_mode_enabled(monkeypatch):
    # We still need to test JWT validation, which requires environment variables
    monkeypatch.setenv("MCP_JWT_SECRET", "test-secret")
    set_test_mode_config(multitenant_mode=True)

    service = create_auth_service()
    assert isinstance(service, JWTAuthService)


def test_mode_switching_resets_service(monkeypatch):
    # We still need to test JWT validation, which requires environment variables
    monkeypatch.setenv("MCP_JWT_SECRET", "test-secret")
    set_test_mode_config(multitenant_mode=True)
    assert isinstance(create_auth_service(), JWTAuthService)

    set_test_mode_config(multitenant_mode=False)
    assert isinstance(create_auth_service(), IAMAuthService)


def test_logs_auth_mode(caplog):
    set_test_mode_config(multitenant_mode=False)

    with caplog.at_level("INFO"):
        _ = create_auth_service()

    assert any("Authentication mode selected: IAM" in record.message for record in caplog.records)


def test_get_auth_service_removed():
    import quilt_mcp.services.auth_service as auth_service

    assert not hasattr(auth_service, "get_auth_service")

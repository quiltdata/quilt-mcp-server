"""Unit tests for auth service factory behavior."""

from __future__ import annotations

import pytest

from quilt_mcp.config import get_mode_config, set_test_mode_config
from quilt_mcp.services.auth_service import create_auth_service
from quilt_mcp.services.iam_auth_service import IAMAuthService
from quilt_mcp.services.jwt_auth_service import JWTAuthService
from quilt_mcp.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context


def test_default_mode_is_iam():
    set_test_mode_config(multiuser_mode=False)

    mode_config = get_mode_config()
    assert mode_config.requires_jwt is False
    service = create_auth_service()
    assert isinstance(service, IAMAuthService)


def test_jwt_mode_enabled():
    """Test that JWT mode returns JWTAuthService."""
    set_test_mode_config(multiuser_mode=True)

    service = create_auth_service()
    assert isinstance(service, JWTAuthService)


def test_mode_switching_resets_service():
    """Test that mode switching returns correct service type."""
    set_test_mode_config(multiuser_mode=True)
    assert isinstance(create_auth_service(), JWTAuthService)

    set_test_mode_config(multiuser_mode=False)
    assert isinstance(create_auth_service(), IAMAuthService)


def test_jwt_auth_service_reads_runtime_claims():
    """Test that JWT auth service extracts user ID from runtime claims."""
    set_test_mode_config(multiuser_mode=True)

    service = create_auth_service()
    assert isinstance(service, JWTAuthService)

    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims={"id": "user-1"})
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)
    try:
        identity = service.get_user_identity()
        assert identity["user_id"] == "user-1"
    finally:
        reset_runtime_context(token_handle)


def test_logs_auth_mode(caplog):
    set_test_mode_config(multiuser_mode=False)

    with caplog.at_level("INFO"):
        _ = create_auth_service()

    assert any("Authentication mode selected: IAM" in record.message for record in caplog.records)


def test_get_auth_service_removed():
    import quilt_mcp.services.auth_service as auth_service

    assert not hasattr(auth_service, "get_auth_service")

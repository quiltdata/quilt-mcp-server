"""Unit tests for JWT auth service behavior."""

from __future__ import annotations

import pytest

from quilt_mcp.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context
from quilt_mcp.services.jwt_auth_service import JwtAuthServiceError, JWTAuthService


def test_jwt_auth_requires_runtime_auth():
    service = JWTAuthService()
    with pytest.raises(JwtAuthServiceError) as excinfo:
        service.get_boto3_session()

    assert excinfo.value.code == "missing_jwt"


def test_jwt_auth_requires_registry_url_for_credentials():
    """Test that JWT auth requires QUILT_REGISTRY_URL to exchange JWT for AWS credentials."""
    import os

    # Clear QUILT_REGISTRY_URL if it exists
    old_registry_url = os.environ.pop("QUILT_REGISTRY_URL", None)

    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="token",
        claims={"id": "user-1", "uuid": "user-uuid", "exp": 9999999999},
    )
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)
    try:
        service = JWTAuthService()
        with pytest.raises(JwtAuthServiceError) as excinfo:
            service.get_boto3_session()
        assert excinfo.value.code == "missing_config"
        assert "QUILT_REGISTRY_URL" in str(excinfo.value)
    finally:
        reset_runtime_context(token_handle)
        # Restore original value
        if old_registry_url is not None:
            os.environ["QUILT_REGISTRY_URL"] = old_registry_url

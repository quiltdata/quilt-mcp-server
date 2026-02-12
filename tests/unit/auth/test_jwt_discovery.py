import jwt as pyjwt
import pytest

from quilt_mcp.auth.jwt_discovery import JWTDiscovery
from quilt_mcp.context.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context
from quilt_mcp.ops.exceptions import AuthenticationError


def _clear_env(monkeypatch):
    for key in (
        "QUILT_ALLOW_TEST_JWT",
        "QUILT_REGISTRY_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_discover_prefers_runtime_token(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("QUILT_ALLOW_TEST_JWT", "true")
    monkeypatch.setattr(
        "quilt_mcp.auth.jwt_discovery._get_token_from_quilt3_session",
        lambda: None,
    )

    token_handle = push_runtime_context(
        environment="web",
        auth=RuntimeAuthState(scheme="Bearer", access_token="runtime-token", claims={}),
    )
    try:
        token = JWTDiscovery.discover()
        assert token == "runtime-token"
    finally:
        reset_runtime_context(token_handle)


def test_discover_allows_test_jwt(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("QUILT_ALLOW_TEST_JWT", "true")
    monkeypatch.setattr(
        "quilt_mcp.auth.jwt_discovery._get_token_from_quilt3_session",
        lambda: None,
    )

    token = JWTDiscovery.discover()
    assert token is not None

    claims = pyjwt.decode(token, options={"verify_signature": False})
    assert claims["id"] == "test-user"


def test_discover_or_raise_missing(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("QUILT_ALLOW_TEST_JWT", "false")
    monkeypatch.setattr(
        "quilt_mcp.auth.jwt_discovery._get_token_from_quilt3_session",
        lambda: None,
    )

    with pytest.raises(AuthenticationError):
        JWTDiscovery.discover_or_raise()

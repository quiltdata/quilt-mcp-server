"""Unit tests for AuthService abstraction."""

from __future__ import annotations

import pytest

from quilt_mcp.services.auth_service import AuthService


def test_auth_service_is_defined():
    assert AuthService.__name__ == "AuthService"


def test_auth_service_requires_abstract_methods():
    class MissingMethods(AuthService):
        pass

    with pytest.raises(TypeError) as excinfo:
        MissingMethods()

    message = str(excinfo.value)
    assert "get_session" in message
    assert "is_valid" in message
    assert "get_user_identity" in message

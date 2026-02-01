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


def test_auth_service_allows_multiple_instances():
    class ConcreteAuthService(AuthService):
        def get_session(self):
            return object()

        def is_valid(self) -> bool:
            return True

        def get_user_identity(self):
            return {"user_id": "user-1"}

    first = ConcreteAuthService()
    second = ConcreteAuthService()

    assert first is not second


def test_auth_service_session_cached_within_instance():
    class CachedAuthService(AuthService):
        def __init__(self) -> None:
            self._session = None

        def get_session(self):
            if self._session is None:
                self._session = object()
            return self._session

        def is_valid(self) -> bool:
            return True

        def get_user_identity(self):
            return {"user_id": "user-1"}

    service = CachedAuthService()

    assert service.get_session() is service.get_session()

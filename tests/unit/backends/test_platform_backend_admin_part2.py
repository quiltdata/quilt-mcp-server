"""Unit tests for Platform_Backend admin operations.

The Platform_Backend implements admin operations using Platform GraphQL API endpoints.
This test file verifies all admin operations work correctly with proper error handling.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from quilt_mcp.context.runtime_context import (
    RuntimeAuthState,
    get_runtime_environment,
    push_runtime_context,
    reset_runtime_context,
)
from quilt_mcp.ops.exceptions import (
    AuthenticationError,
    BackendError,
    ValidationError,
    NotFoundError,
    PermissionError,
)
from quilt_mcp.domain.user import User
from quilt_mcp.domain.role import Role
from quilt_mcp.domain.sso_config import SSOConfig

from tests.unit.backends.test_platform_backend_admin_part1 import _make_backend


def test_add_user_roles_success(monkeypatch):
    """Test successfully adding roles to a user."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "admin": {
                "user": {
                    "mutate": {
                        "addRoles": {
                            "user": {
                                "name": "testuser",
                                "email": "test@example.com",
                                "isActive": True,
                                "isAdmin": False,
                                "isSsoOnly": False,
                                "isService": False,
                                "dateJoined": "2024-01-01T00:00:00Z",
                                "lastLogin": None,
                                "role": {
                                    "id": "1",
                                    "name": "User",
                                    "arn": "arn:aws:iam::123:role/User",
                                    "type": "managed",
                                },
                                "extraRoles": [
                                    {
                                        "id": "3",
                                        "name": "Reader",
                                        "arn": "arn:aws:iam::123:role/Reader",
                                        "type": "managed",
                                    }
                                ],
                            }
                        }
                    }
                }
            }
        }
    }

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        user = backend.admin.add_user_roles("testuser", ["Reader"])

    assert len(user.extra_roles) == 1


def test_remove_user_roles_success(monkeypatch):
    """Test successfully removing roles from a user."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "admin": {
                "user": {
                    "mutate": {
                        "removeRoles": {
                            "user": {
                                "name": "testuser",
                                "email": "test@example.com",
                                "isActive": True,
                                "isAdmin": False,
                                "isSsoOnly": False,
                                "isService": False,
                                "dateJoined": "2024-01-01T00:00:00Z",
                                "lastLogin": None,
                                "role": {
                                    "id": "1",
                                    "name": "User",
                                    "arn": "arn:aws:iam::123:role/User",
                                    "type": "managed",
                                },
                                "extraRoles": [],
                            }
                        }
                    }
                }
            }
        }
    }

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        user = backend.admin.remove_user_roles("testuser", ["Reader"])

    assert len(user.extra_roles) == 0


# ---------------------------------------------------------------------
# Role Management Tests
# ---------------------------------------------------------------------


def test_list_roles_success(monkeypatch):
    """Test successful role listing."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "roles": [
                {"id": "1", "name": "User", "arn": "arn:aws:iam::123:role/User", "type": "managed"},
                {"id": "2", "name": "Admin", "arn": "arn:aws:iam::123:role/Admin", "type": "managed"},
                {"id": "3", "name": "Reader", "arn": "arn:aws:iam::123:role/Reader", "type": "managed"},
            ]
        }
    }

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        roles = backend.admin.list_roles()

    assert len(roles) == 3
    assert all(isinstance(r, Role) for r in roles)
    assert roles[0].name == "User"
    assert roles[1].name == "Admin"
    assert roles[2].name == "Reader"


# ---------------------------------------------------------------------
# SSO Configuration Tests
# ---------------------------------------------------------------------


def test_get_sso_config_success(monkeypatch):
    """Test successful SSO config retrieval."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "admin": {
                "ssoConfig": {
                    "text": "SSO configuration text",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "uploader": {
                        "name": "admin",
                        "email": "admin@example.com",
                        "isActive": True,
                        "isAdmin": True,
                        "isSsoOnly": False,
                        "isService": False,
                        "dateJoined": "2024-01-01T00:00:00Z",
                        "lastLogin": None,
                        "role": {"id": "2", "name": "Admin", "arn": "arn:aws:iam::123:role/Admin", "type": "managed"},
                        "extraRoles": [],
                    },
                }
            }
        }
    }

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        sso_config = backend.admin.get_sso_config()

    assert isinstance(sso_config, SSOConfig)
    assert sso_config.text == "SSO configuration text"
    assert sso_config.uploader.name == "admin"


def test_get_sso_config_none(monkeypatch):
    """Test getting SSO config when none exists."""
    backend = _make_backend(monkeypatch)

    mock_response = {"data": {"admin": {"ssoConfig": None}}}

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        sso_config = backend.admin.get_sso_config()

    assert sso_config is None


def test_set_sso_config_success(monkeypatch):
    """Test successful SSO config update."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "admin": {
                "setSsoConfig": {
                    "ssoConfig": {
                        "text": "New SSO configuration",
                        "timestamp": "2024-01-02T00:00:00Z",
                        "uploader": {
                            "name": "admin",
                            "email": "admin@example.com",
                            "isActive": True,
                            "isAdmin": True,
                            "isSsoOnly": False,
                            "isService": False,
                            "dateJoined": "2024-01-01T00:00:00Z",
                            "lastLogin": None,
                            "role": {
                                "id": "2",
                                "name": "Admin",
                                "arn": "arn:aws:iam::123:role/Admin",
                                "type": "managed",
                            },
                            "extraRoles": [],
                        },
                    }
                }
            }
        }
    }

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        sso_config = backend.admin.set_sso_config("New SSO configuration")

    assert sso_config.text == "New SSO configuration"


def test_set_sso_config_empty(monkeypatch):
    """Test setting SSO config with empty text."""
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="SSO configuration cannot be empty"):
        backend.admin.set_sso_config("")


def test_remove_sso_config_success(monkeypatch):
    """Test successful SSO config removal."""
    backend = _make_backend(monkeypatch)

    mock_response = {"data": {"admin": {"removeSsoConfig": {"message": "SSO configuration removed"}}}}

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        backend.admin.remove_sso_config()  # Should not raise


# ---------------------------------------------------------------------
# Error Handling Tests
# ---------------------------------------------------------------------


def test_handle_graphql_authentication_error(monkeypatch):
    """Test handling authentication errors from GraphQL."""
    backend = _make_backend(monkeypatch)

    with patch.object(backend, 'execute_graphql_query', side_effect=Exception("authentication failed")):
        with pytest.raises(AuthenticationError):
            backend.admin.list_users()


def test_handle_graphql_permission_error(monkeypatch):
    """Test handling permission errors from GraphQL."""
    backend = _make_backend(monkeypatch)

    with patch.object(backend, 'execute_graphql_query', side_effect=Exception("permission denied")):
        with pytest.raises(PermissionError):
            backend.admin.list_users()


def test_handle_graphql_not_found_error(monkeypatch):
    """Test handling not found errors from GraphQL."""
    backend = _make_backend(monkeypatch)

    with patch.object(backend, 'execute_graphql_query', side_effect=Exception("user not found")):
        with pytest.raises(NotFoundError):
            backend.admin.list_users()


def test_handle_graphql_validation_error(monkeypatch):
    """Test handling validation errors from GraphQL."""
    backend = _make_backend(monkeypatch)

    with patch.object(backend, 'execute_graphql_query', side_effect=Exception("invalid input provided")):
        with pytest.raises(ValidationError):
            backend.admin.list_users()


def test_handle_graphql_generic_error(monkeypatch):
    """Test handling generic errors from GraphQL."""
    backend = _make_backend(monkeypatch)

    with patch.object(backend, 'execute_graphql_query', side_effect=Exception("unexpected error")):
        with pytest.raises(BackendError):
            backend.admin.list_users()

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


def _push_jwt_context(claims=None):
    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="test-token",
        claims=claims
        or {
            "id": "user-1",
            "uuid": "uuid-1",
            "exp": 9999999999,
        },
    )
    return push_runtime_context(environment=get_runtime_environment(), auth=auth_state)


def _make_backend(monkeypatch, claims=None):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://example.quiltdata.com")
    monkeypatch.setenv("QUILT_REGISTRY_URL", "https://registry.example.com")
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context(claims)
    try:
        from quilt_mcp.backends.platform_backend import Platform_Backend

        return Platform_Backend()
    finally:
        reset_runtime_context(token)


# ---------------------------------------------------------------------
# Admin Property Tests
# ---------------------------------------------------------------------


def test_admin_property_returns_admin_ops(monkeypatch):
    """Verify admin property returns Platform_Admin_Ops instance."""
    backend = _make_backend(monkeypatch)

    admin = backend.admin

    assert admin is not None
    from quilt_mcp.backends.platform_admin_ops import Platform_Admin_Ops

    assert isinstance(admin, Platform_Admin_Ops)


def test_admin_property_caches_instance(monkeypatch):
    """Verify admin property caches the instance."""
    backend = _make_backend(monkeypatch)

    admin1 = backend.admin
    admin2 = backend.admin

    assert admin1 is admin2


# ---------------------------------------------------------------------
# User Management Tests
# ---------------------------------------------------------------------


def test_list_users_success(monkeypatch):
    """Test successful user listing."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "admin": {
                "user": {
                    "list": [
                        {
                            "name": "user1",
                            "email": "user1@example.com",
                            "isActive": True,
                            "isAdmin": False,
                            "isSsoOnly": False,
                            "isService": False,
                            "dateJoined": "2024-01-01T00:00:00Z",
                            "lastLogin": "2024-01-02T00:00:00Z",
                            "role": {
                                "id": "1",
                                "name": "User",
                                "arn": "arn:aws:iam::123:role/User",
                                "type": "managed",
                            },
                            "extraRoles": [],
                        },
                        {
                            "name": "user2",
                            "email": "user2@example.com",
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
                    ]
                }
            }
        }
    }

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        users = backend.admin.list_users()

    assert len(users) == 2
    assert all(isinstance(u, User) for u in users)
    assert users[0].name == "user1"
    assert users[0].email == "user1@example.com"
    assert users[0].is_active is True
    assert users[0].is_admin is False
    assert users[1].name == "user2"
    assert users[1].is_admin is True


def test_get_user_success(monkeypatch):
    """Test successful user retrieval."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "admin": {
                "user": {
                    "get": {
                        "name": "testuser",
                        "email": "testuser@example.com",
                        "isActive": True,
                        "isAdmin": False,
                        "isSsoOnly": False,
                        "isService": False,
                        "dateJoined": "2024-01-01T00:00:00Z",
                        "lastLogin": "2024-01-02T00:00:00Z",
                        "role": {"id": "1", "name": "User", "arn": "arn:aws:iam::123:role/User", "type": "managed"},
                        "extraRoles": [],
                    }
                }
            }
        }
    }

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        user = backend.admin.get_user("testuser")

    assert isinstance(user, User)
    assert user.name == "testuser"
    assert user.email == "testuser@example.com"


def test_get_user_not_found(monkeypatch):
    """Test getting a non-existent user."""
    backend = _make_backend(monkeypatch)

    mock_response = {"data": {"admin": {"user": {"get": None}}}}

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        with pytest.raises(NotFoundError, match="User not found"):
            backend.admin.get_user("nonexistent")


def test_get_user_empty_name(monkeypatch):
    """Test getting user with empty name."""
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="Username cannot be empty"):
        backend.admin.get_user("")


def test_create_user_success(monkeypatch):
    """Test successful user creation."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "admin": {
                "user": {
                    "create": {
                        "user": {
                            "name": "newuser",
                            "email": "newuser@example.com",
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

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        user = backend.admin.create_user("newuser", "newuser@example.com", "User")

    assert isinstance(user, User)
    assert user.name == "newuser"
    assert user.email == "newuser@example.com"


def test_create_user_validation_errors(monkeypatch):
    """Test create user validation."""
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="Username cannot be empty"):
        backend.admin.create_user("", "test@example.com", "User")

    with pytest.raises(ValidationError, match="Email cannot be empty"):
        backend.admin.create_user("testuser", "", "User")

    with pytest.raises(ValidationError, match="Role cannot be empty"):
        backend.admin.create_user("testuser", "test@example.com", "")


def test_create_user_with_error_response(monkeypatch):
    """Test create user with error in response."""
    backend = _make_backend(monkeypatch)

    mock_response = {"data": {"admin": {"user": {"create": {"message": "User already exists"}}}}}

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        with pytest.raises(ValidationError, match="Failed to create user"):
            backend.admin.create_user("newuser", "newuser@example.com", "User")


def test_delete_user_success(monkeypatch):
    """Test successful user deletion."""
    backend = _make_backend(monkeypatch)

    mock_response = {"data": {"admin": {"user": {"mutate": {"delete": {"message": "User deleted successfully"}}}}}}

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        backend.admin.delete_user("testuser")  # Should not raise


def test_delete_user_empty_name(monkeypatch):
    """Test deleting user with empty name."""
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="Username cannot be empty"):
        backend.admin.delete_user("")


def test_set_user_email_success(monkeypatch):
    """Test successful email update."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "admin": {
                "user": {
                    "mutate": {
                        "setEmail": {
                            "user": {
                                "name": "testuser",
                                "email": "newemail@example.com",
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
        user = backend.admin.set_user_email("testuser", "newemail@example.com")

    assert user.email == "newemail@example.com"


def test_set_user_admin_success(monkeypatch):
    """Test successful admin status update."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "admin": {
                "user": {
                    "mutate": {
                        "setAdmin": {
                            "user": {
                                "name": "testuser",
                                "email": "test@example.com",
                                "isActive": True,
                                "isAdmin": True,
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
        user = backend.admin.set_user_admin("testuser", True)

    assert user.is_admin is True


def test_set_user_active_success(monkeypatch):
    """Test successful active status update."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "admin": {
                "user": {
                    "mutate": {
                        "setActive": {
                            "user": {
                                "name": "testuser",
                                "email": "test@example.com",
                                "isActive": False,
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
        user = backend.admin.set_user_active("testuser", False)

    assert user.is_active is False


def test_reset_user_password_success(monkeypatch):
    """Test successful password reset."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {"admin": {"user": {"mutate": {"resetPassword": {"message": "Password reset email sent"}}}}}
    }

    with patch.object(backend, 'execute_graphql_query', return_value=mock_response):
        backend.admin.reset_user_password("testuser")  # Should not raise


def test_set_user_role_success(monkeypatch):
    """Test successful role update."""
    backend = _make_backend(monkeypatch)

    mock_response = {
        "data": {
            "admin": {
                "user": {
                    "mutate": {
                        "setRole": {
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
                                    "id": "2",
                                    "name": "PowerUser",
                                    "arn": "arn:aws:iam::123:role/PowerUser",
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
        user = backend.admin.set_user_role("testuser", "PowerUser", extra_roles=["Reader"], append=False)

    assert user.role.name == "PowerUser"
    assert len(user.extra_roles) == 1
    assert user.extra_roles[0].name == "Reader"

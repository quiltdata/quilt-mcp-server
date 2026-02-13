"""Additional coverage for Platform_Admin_Ops branches."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quilt_mcp.ops.exceptions import BackendError, NotFoundError, ValidationError
from tests.unit.backends.test_platform_backend_admin_part1 import _make_backend


def test_create_user_errors_on_missing_payload_and_invalid_typename(monkeypatch):
    backend = _make_backend(monkeypatch)

    with patch.object(backend, "execute_graphql_query", return_value={"data": {"admin": {"user": {"create": {}}}}}):
        with pytest.raises(BackendError, match="No user data returned"):
            backend.admin.create_user("u", "u@example.com", "User")

    bad_typename = {"data": {"admin": {"user": {"create": {"__typename": "Other", "user": {"name": "u"}}}}}}
    with patch.object(backend, "execute_graphql_query", return_value=bad_typename):
        with pytest.raises(BackendError, match="No user data returned"):
            backend.admin.create_user("u", "u@example.com", "User")


def test_delete_user_not_found_and_validation_error(monkeypatch):
    backend = _make_backend(monkeypatch)

    with patch.object(backend, "execute_graphql_query", return_value={"data": {"admin": {"user": {"mutate": {"delete": {}}}}}}):
        with pytest.raises(NotFoundError):
            backend.admin.delete_user("missing")

    invalid = {
        "data": {
            "admin": {
                "user": {
                    "mutate": {
                        "delete": {"__typename": "InvalidInput", "errors": [{"message": "invalid delete"}]}
                    }
                }
            }
        }
    }
    with patch.object(backend, "execute_graphql_query", return_value=invalid):
        with pytest.raises(ValidationError, match="Failed to delete user"):
            backend.admin.delete_user("u")


def test_set_user_active_validation_and_backend_error_paths(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="Username cannot be empty"):
        backend.admin.set_user_active("", True)

    not_found = {
        "data": {
            "admin": {
                "user": {
                    "mutate": {
                        "setActive": {"__typename": "InvalidInput", "errors": [{"message": "user not found"}]}
                    }
                }
            }
        }
    }
    with patch.object(backend, "execute_graphql_query", return_value=not_found):
        with pytest.raises(NotFoundError):
            backend.admin.set_user_active("u", True)

    no_payload = {"data": {"admin": {"user": {"mutate": {"setActive": {"__typename": "User"}}}}}}
    with patch.object(backend, "execute_graphql_query", return_value=no_payload):
        with pytest.raises(BackendError, match="No user data returned"):
            backend.admin.set_user_active("u", True)


def test_reset_password_and_role_mutation_validation(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="Username cannot be empty"):
        backend.admin.reset_user_password("")

    with patch.object(
        backend,
        "execute_graphql_query",
        return_value={"data": {"admin": {"user": {"mutate": {"resetPassword": {}}}}}},
    ):
        with pytest.raises(NotFoundError):
            backend.admin.reset_user_password("u")

    with pytest.raises(ValidationError, match="Role cannot be empty"):
        backend.admin.set_user_role("u", "")


def test_add_remove_roles_validation_and_not_found(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="Roles list cannot be empty"):
        backend.admin.add_user_roles("u", [])
    with pytest.raises(ValidationError, match="Roles list cannot be empty"):
        backend.admin.remove_user_roles("u", [])

    add_nf = {
        "data": {
            "admin": {
                "user": {
                    "mutate": {
                        "addRoles": {"__typename": "InvalidInput", "errors": [{"message": "user not found"}]}
                    }
                }
            }
        }
    }
    with patch.object(backend, "execute_graphql_query", return_value=add_nf):
        with pytest.raises(NotFoundError):
            backend.admin.add_user_roles("u", ["Reader"])

    remove_nf = {
        "data": {
            "admin": {
                "user": {
                    "mutate": {
                        "removeRoles": {"__typename": "InvalidInput", "errors": [{"message": "role not found"}]}
                    }
                }
            }
        }
    }
    with patch.object(backend, "execute_graphql_query", return_value=remove_nf):
        with pytest.raises(NotFoundError):
            backend.admin.remove_user_roles("u", ["Reader"])


def test_set_sso_config_variants_and_errors(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="cannot be empty"):
        backend.admin.set_sso_config({})

    with pytest.raises(ValidationError, match="cannot be empty"):
        backend.admin.set_sso_config(" ")

    with patch.object(backend, "execute_graphql_query", return_value={"data": {"admin": {"setSsoConfig": None}}}):
        assert backend.admin.set_sso_config(None) is None

    op_error = {"data": {"admin": {"setSsoConfig": {"__typename": "OperationError", "message": "failed"}}}}
    with patch.object(backend, "execute_graphql_query", return_value=op_error):
        with pytest.raises(ValidationError, match="Failed to set SSO config"):
            backend.admin.set_sso_config({"k": "v"})

    missing_payload = {"data": {"admin": {"setSsoConfig": {"__typename": "SsoConfig"}}}}
    with patch.object(backend, "execute_graphql_query", return_value=missing_payload):
        with pytest.raises(BackendError, match="No config data returned"):
            backend.admin.set_sso_config({"k": "v"})


def test_admin_helper_extractors_and_transform_error_paths(monkeypatch):
    backend = _make_backend(monkeypatch)
    admin = backend.admin

    assert admin._extract_result_error("bad") == "Invalid GraphQL response"
    assert admin._extract_result_error({"__typename": "OperationError", "message": "oops"}) == "oops"
    assert admin._extract_result_error({"__typename": "InvalidInput", "errors": [{"message": "a"}, {"message": "b"}]}) == "a; b"
    assert admin._extract_result_error({"message": "permission denied"}) == "permission denied"
    assert admin._extract_result_error({"message": "ok"}) is None

    assert admin._extract_user_payload({"user": {"name": "u"}}) == {"name": "u"}
    assert admin._extract_user_payload({"name": "u"}) == {"name": "u"}
    assert admin._extract_user_payload(None) is None

    assert admin._extract_sso_payload({"ssoConfig": {"text": "x"}}) == {"text": "x"}
    assert admin._extract_sso_payload({"text": "x"}) == {"text": "x"}
    assert admin._extract_sso_payload(None) is None

    with pytest.raises(BackendError, match="Failed to transform role data"):
        admin._transform_graphql_role(None)
    with pytest.raises(BackendError, match="Failed to transform user data"):
        admin._transform_graphql_user(None)
    with pytest.raises(BackendError, match="Failed to transform SSO config data"):
        admin._transform_graphql_sso_config(None)


def test_admin_mutation_error_branches(monkeypatch):
    backend = _make_backend(monkeypatch)

    with patch.object(backend, "execute_graphql_query", side_effect=Exception("network down")):
        with pytest.raises(BackendError):
            backend.admin.get_user("u")
    with patch.object(backend, "execute_graphql_query", side_effect=Exception("network down")):
        with pytest.raises(BackendError):
            backend.admin.create_user("u", "u@example.com", "User")
    with patch.object(backend, "execute_graphql_query", side_effect=Exception("network down")):
        with pytest.raises(BackendError):
            backend.admin.delete_user("u")


def test_set_user_email_and_admin_edge_paths(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError):
        backend.admin.set_user_email("", "u@example.com")
    with pytest.raises(ValidationError):
        backend.admin.set_user_email("u", "")
    with pytest.raises(ValidationError):
        backend.admin.set_user_admin("", True)

    email_nf = {
        "data": {"admin": {"user": {"mutate": {"setEmail": {"__typename": "InvalidInput", "errors": [{"message": "not found"}]}}}}}
    }
    with patch.object(backend, "execute_graphql_query", return_value=email_nf):
        with pytest.raises(NotFoundError):
            backend.admin.set_user_email("u", "u@example.com")

    email_bad = {
        "data": {"admin": {"user": {"mutate": {"setEmail": {"__typename": "InvalidInput", "errors": [{"message": "bad email"}]}}}}}
    }
    with patch.object(backend, "execute_graphql_query", return_value=email_bad):
        with pytest.raises(ValidationError):
            backend.admin.set_user_email("u", "u@example.com")

    email_no_payload = {"data": {"admin": {"user": {"mutate": {"setEmail": {"__typename": "User"}}}}}}
    with patch.object(backend, "execute_graphql_query", return_value=email_no_payload):
        with pytest.raises(BackendError):
            backend.admin.set_user_email("u", "u@example.com")

    admin_nf = {
        "data": {"admin": {"user": {"mutate": {"setAdmin": {"__typename": "InvalidInput", "errors": [{"message": "not found"}]}}}}}
    }
    with patch.object(backend, "execute_graphql_query", return_value=admin_nf):
        with pytest.raises(NotFoundError):
            backend.admin.set_user_admin("u", True)


def test_set_user_admin_and_active_more_backend_paths(monkeypatch):
    backend = _make_backend(monkeypatch)

    admin_no_payload = {"data": {"admin": {"user": {"mutate": {"setAdmin": {"__typename": "User"}}}}}}
    with patch.object(backend, "execute_graphql_query", return_value=admin_no_payload):
        with pytest.raises(BackendError):
            backend.admin.set_user_admin("u", True)

    active_invalid = {
        "data": {"admin": {"user": {"mutate": {"setActive": {"__typename": "InvalidInput", "errors": [{"message": "bad state"}]}}}}}
    }
    with patch.object(backend, "execute_graphql_query", return_value=active_invalid):
        with pytest.raises(ValidationError):
            backend.admin.set_user_active("u", True)

    active_typename = {
        "data": {"admin": {"user": {"mutate": {"setActive": {"__typename": "Other", "user": {"name": "u"}}}}}}
    }
    with patch.object(backend, "execute_graphql_query", return_value=active_typename):
        with pytest.raises(BackendError):
            backend.admin.set_user_active("u", True)

    with patch.object(backend, "execute_graphql_query", side_effect=Exception("network down")):
        with pytest.raises(BackendError):
            backend.admin.set_user_active("u", True)


def test_reset_password_set_role_and_add_roles_branches(monkeypatch):
    backend = _make_backend(monkeypatch)

    reset_invalid = {
        "data": {
            "admin": {"user": {"mutate": {"resetPassword": {"__typename": "InvalidInput", "errors": [{"message": "bad"}]}}}}
        }
    }
    with patch.object(backend, "execute_graphql_query", return_value=reset_invalid):
        with pytest.raises(ValidationError):
            backend.admin.reset_user_password("u")
    with patch.object(backend, "execute_graphql_query", side_effect=Exception("network down")):
        with pytest.raises(BackendError):
            backend.admin.reset_user_password("u")

    set_role_nf = {
        "data": {"admin": {"user": {"mutate": {"setRole": {"__typename": "InvalidInput", "errors": [{"message": "role not found"}]}}}}}
    }
    with patch.object(backend, "execute_graphql_query", return_value=set_role_nf):
        with pytest.raises(NotFoundError):
            backend.admin.set_user_role("u", "Role")
    set_role_missing = {"data": {"admin": {"user": {"mutate": {"setRole": {"__typename": "User"}}}}}}
    with patch.object(backend, "execute_graphql_query", return_value=set_role_missing):
        with pytest.raises(BackendError):
            backend.admin.set_user_role("u", "Role")
    with patch.object(backend, "execute_graphql_query", side_effect=Exception("network down")):
        with pytest.raises(BackendError):
            backend.admin.set_user_role("u", "Role")

    with pytest.raises(ValidationError):
        backend.admin.add_user_roles("", ["Reader"])
    add_invalid = {
        "data": {"admin": {"user": {"mutate": {"addRoles": {"__typename": "InvalidInput", "errors": [{"message": "bad"}]}}}}}
    }
    with patch.object(backend, "execute_graphql_query", return_value=add_invalid):
        with pytest.raises(ValidationError):
            backend.admin.add_user_roles("u", ["Reader"])
    add_missing = {"data": {"admin": {"user": {"mutate": {"addRoles": {"__typename": "User"}}}}}}
    with patch.object(backend, "execute_graphql_query", return_value=add_missing):
        with pytest.raises(BackendError):
            backend.admin.add_user_roles("u", ["Reader"])
    with patch.object(backend, "execute_graphql_query", side_effect=Exception("network down")):
        with pytest.raises(BackendError):
            backend.admin.add_user_roles("u", ["Reader"])


def test_remove_roles_list_roles_sso_and_role_fallback(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError):
        backend.admin.remove_user_roles("", ["Reader"])

    removed = {
        "data": {
            "admin": {
                "user": {
                    "mutate": {
                        "removeRoles": {
                            "user": {
                                "name": "u",
                                "email": "u@example.com",
                                "isActive": True,
                                "isAdmin": False,
                                "isSsoOnly": False,
                                "isService": False,
                                "dateJoined": "2024-01-01T00:00:00Z",
                                "lastLogin": None,
                                "role": {"id": "1", "name": "User", "arn": "a", "type": "managed"},
                                "extraRoles": [],
                            }
                        }
                    }
                }
            }
        }
    }
    with patch.object(backend, "execute_graphql_query", return_value=removed) as mock_exec:
        backend.admin.remove_user_roles("u", ["Reader"], fallback="User")
        assert mock_exec.call_args.kwargs["variables"]["fallback"] == "User"

    remove_invalid = {
        "data": {"admin": {"user": {"mutate": {"removeRoles": {"__typename": "InvalidInput", "errors": [{"message": "bad"}]}}}}}
    }
    with patch.object(backend, "execute_graphql_query", return_value=remove_invalid):
        with pytest.raises(ValidationError):
            backend.admin.remove_user_roles("u", ["Reader"])
    remove_missing = {"data": {"admin": {"user": {"mutate": {"removeRoles": {"__typename": "User"}}}}}}
    with patch.object(backend, "execute_graphql_query", return_value=remove_missing):
        with pytest.raises(BackendError):
            backend.admin.remove_user_roles("u", ["Reader"])
    with patch.object(backend, "execute_graphql_query", side_effect=Exception("network down")):
        with pytest.raises(BackendError):
            backend.admin.remove_user_roles("u", ["Reader"])

    with patch.object(backend, "execute_graphql_query", side_effect=Exception("network down")):
        with pytest.raises(BackendError):
            backend.admin.list_roles()
    with patch.object(backend, "execute_graphql_query", side_effect=Exception("network down")):
        with pytest.raises(BackendError):
            backend.admin.get_sso_config()

    remove_sso_error = {"data": {"admin": {"setSsoConfig": {"__typename": "OperationError", "message": "bad remove"}}}}
    with patch.object(backend, "execute_graphql_query", return_value=remove_sso_error):
        with pytest.raises(ValidationError):
            backend.admin.set_sso_config(None)
    mismatch_sso = {"data": {"admin": {"setSsoConfig": {"__typename": "Other", "text": "x"}}}}
    with patch.object(backend, "execute_graphql_query", return_value=mismatch_sso):
        with pytest.raises(BackendError):
            backend.admin.set_sso_config({"k": "v"})
    with patch.object(backend, "execute_graphql_query", side_effect=Exception("network down")):
        with pytest.raises(BackendError):
            backend.admin.set_sso_config({"k": "v"})

    role = backend.admin._transform_graphql_role({"id": "1", "name": "Reader", "arn": "a", "__typename": "ManagedRole"})
    assert role.type == "ManagedRole"

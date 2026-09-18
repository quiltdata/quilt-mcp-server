"""Unit tests for Platform_Admin_Ops policy and role mutations.

These exercise the GraphQL variables actually sent, not just that a call happened,
so a wrong input shape or a missed partial-update merge fails the test.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from quilt_mcp.context.runtime_context import (
    RuntimeAuthState,
    get_runtime_environment,
    push_runtime_context,
    reset_runtime_context,
)
from quilt_mcp.domain.policy import Permission, Policy
from quilt_mcp.domain.role import Role
from quilt_mcp.ops.exceptions import BackendError, NotFoundError, ValidationError


def _make_backend(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://example.quiltdata.com")
    monkeypatch.setenv("QUILT_REGISTRY_URL", "https://registry.example.com")
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = push_runtime_context(
        environment=get_runtime_environment(),
        auth=RuntimeAuthState(
            scheme="Bearer",
            access_token="test-token",
            claims={"id": "user-1", "uuid": "uuid-1", "exp": 9999999999},
        ),
    )
    try:
        from quilt_mcp.backends.platform_backend import Platform_Backend

        return Platform_Backend()
    finally:
        reset_runtime_context(token)


def _policy_payload(
    *,
    id="pol-1",
    title="Analysts",
    arn="arn:aws:iam::123:policy/Analysts",
    managed=True,
    permissions=(("bucket-a", "READ"),),
    role_ids=("role-1",),
):
    return {
        "id": id,
        "title": title,
        "arn": arn,
        "managed": managed,
        "permissions": [{"bucket": {"name": b}, "level": lvl} for b, lvl in permissions],
        "roles": [{"id": r, "name": f"name-{r}", "arn": f"arn:{r}"} for r in role_ids],
    }


def _role_payload(id="role-1", name="Analyst", typename="ManagedRole"):
    return {"__typename": typename, "id": id, "name": name, "arn": f"arn:aws:iam::123:role/{name}"}


def _responder(mapping, default=None):
    """Dispatch mocked GraphQL responses by operation name found in the query."""

    def _execute(query, variables=None, registry=None):
        for op_name, response in mapping.items():
            if op_name in query:
                return response
        if default is not None:
            return default
        raise AssertionError(f"unexpected GraphQL query: {query}")

    return _execute


# ---------------------------------------------------------------------
# Policy reads
# ---------------------------------------------------------------------


def test_list_policies_success(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {
        "data": {
            "policies": [
                _policy_payload(),
                _policy_payload(
                    id="pol-2",
                    title="Legacy",
                    managed=False,
                    permissions=(),
                    role_ids=(),
                ),
            ]
        }
    }

    with patch.object(backend, "execute_graphql_query", return_value=response) as mock_exec:
        policies = backend.admin.list_policies()

    (query,) = mock_exec.call_args.args
    assert "policies {" in query
    assert "managed" in query
    assert [p.title for p in policies] == ["Analysts", "Legacy"]
    assert all(isinstance(p, Policy) for p in policies)
    assert policies[0].managed is True
    assert policies[0].permissions == [Permission(bucket="bucket-a", level="READ")]
    assert policies[0].role_ids == ["role-1"]
    assert policies[1].managed is False
    assert policies[1].permissions == []


def test_get_policy_found_by_id(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {"data": {"policy": _policy_payload(permissions=(("b1", "READ"), ("b2", "READ_WRITE")))}}

    with patch.object(backend, "execute_graphql_query", return_value=response) as mock_exec:
        policy = backend.admin.get_policy("pol-1")

    assert mock_exec.call_args.kwargs["variables"] == {"id": "pol-1"}
    assert policy is not None
    assert policy.id == "pol-1"
    assert policy.permissions == [
        Permission(bucket="b1", level="READ"),
        Permission(bucket="b2", level="READ_WRITE"),
    ]


def test_get_policy_falls_back_to_title_lookup(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder(
        {
            "PolicyGet": {"data": {"policy": None}},
            "PoliciesList": {"data": {"policies": [_policy_payload(id="pol-9", title="By Title")]}},
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute):
        policy = backend.admin.get_policy("By Title")

    assert policy is not None
    assert policy.id == "pol-9"


def test_get_policy_not_found_returns_none(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder(
        {
            "PolicyGet": {"data": {"policy": None}},
            "PoliciesList": {"data": {"policies": []}},
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute):
        assert backend.admin.get_policy("nope") is None


def test_get_policy_empty_id(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="cannot be empty"):
        backend.admin.get_policy("")


# ---------------------------------------------------------------------
# Policy creation
# ---------------------------------------------------------------------


def test_create_managed_policy_sends_managed_policy_input(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {"data": {"policyCreateManaged": {"__typename": "Policy", **_policy_payload()}}}

    with patch.object(backend, "execute_graphql_query", return_value=response) as mock_exec:
        policy = backend.admin.create_managed_policy(
            "Analysts",
            [Permission(bucket="bucket-a", level="READ"), Permission(bucket="bucket-b", level="READ_WRITE")],
            role_ids=["role-1"],
        )

    (query,) = mock_exec.call_args.args
    assert "policyCreateManaged(input: $input)" in query
    assert "$input: ManagedPolicyInput!" in query
    assert mock_exec.call_args.kwargs["variables"] == {
        "input": {
            "title": "Analysts",
            "permissions": [
                {"bucket": "bucket-a", "level": "READ"},
                {"bucket": "bucket-b", "level": "READ_WRITE"},
            ],
            "roles": ["role-1"],
        }
    }
    assert policy.title == "Analysts"


def test_create_managed_policy_defaults_roles_to_empty(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {"data": {"policyCreateManaged": {"__typename": "Policy", **_policy_payload(role_ids=())}}}

    with patch.object(backend, "execute_graphql_query", return_value=response) as mock_exec:
        backend.admin.create_managed_policy("Analysts", [])

    assert mock_exec.call_args.kwargs["variables"]["input"] == {
        "title": "Analysts",
        "permissions": [],
        "roles": [],
    }


def test_create_unmanaged_policy_sends_arn(monkeypatch):
    backend = _make_backend(monkeypatch)
    payload = _policy_payload(managed=False, permissions=(), role_ids=("role-2",))
    response = {"data": {"policyCreateUnmanaged": {"__typename": "Policy", **payload}}}

    with patch.object(backend, "execute_graphql_query", return_value=response) as mock_exec:
        policy = backend.admin.create_unmanaged_policy("Legacy", "arn:aws:iam::123:policy/Legacy", role_ids=["role-2"])

    (query,) = mock_exec.call_args.args
    assert "$input: UnmanagedPolicyInput!" in query
    assert mock_exec.call_args.kwargs["variables"] == {
        "input": {"title": "Legacy", "arn": "arn:aws:iam::123:policy/Legacy", "roles": ["role-2"]}
    }
    assert policy.managed is False


def test_create_unmanaged_policy_requires_arn(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="ARN cannot be empty"):
        backend.admin.create_unmanaged_policy("Legacy", "")


def test_create_managed_policy_requires_title(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="title cannot be empty"):
        backend.admin.create_managed_policy("", [])


# ---------------------------------------------------------------------
# Policy patching (partial update over a full-replacement mutation)
# ---------------------------------------------------------------------


def test_patch_managed_policy_merges_current_values(monkeypatch):
    backend = _make_backend(monkeypatch)
    current = _policy_payload(permissions=(("bucket-a", "READ"),), role_ids=("role-1", "role-2"))
    execute = _responder(
        {
            "PolicyGet": {"data": {"policy": current}},
            "PolicyUpdateManaged": {
                "data": {"policyUpdateManaged": {"__typename": "Policy", **_policy_payload(title="Renamed")}}
            },
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute) as mock_exec:
        policy = backend.admin.patch_managed_policy("pol-1", title="Renamed")

    update_call = [c for c in mock_exec.call_args_list if "PolicyUpdateManaged" in c.args[0]][0]
    # Only title was supplied; permissions and roles must come from the current policy.
    assert update_call.kwargs["variables"] == {
        "id": "pol-1",
        "input": {
            "title": "Renamed",
            "permissions": [{"bucket": "bucket-a", "level": "READ"}],
            "roles": ["role-1", "role-2"],
        },
    }
    assert policy.title == "Renamed"


def test_patch_managed_policy_replaces_supplied_fields(monkeypatch):
    backend = _make_backend(monkeypatch)
    current = _policy_payload(permissions=(("bucket-a", "READ"),), role_ids=("role-1",))
    execute = _responder(
        {
            "PolicyGet": {"data": {"policy": current}},
            "PolicyUpdateManaged": {"data": {"policyUpdateManaged": {"__typename": "Policy", **current}}},
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute) as mock_exec:
        backend.admin.patch_managed_policy(
            "pol-1",
            permissions=[Permission(bucket="bucket-z", level="READ_WRITE")],
            role_ids=[],
        )

    update_call = [c for c in mock_exec.call_args_list if "PolicyUpdateManaged" in c.args[0]][0]
    assert update_call.kwargs["variables"]["input"] == {
        "title": "Analysts",
        "permissions": [{"bucket": "bucket-z", "level": "READ_WRITE"}],
        "roles": [],
    }


def test_patch_managed_policy_rejects_unmanaged_target(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {"data": {"policy": _policy_payload(managed=False)}}

    with patch.object(backend, "execute_graphql_query", return_value=response) as mock_exec:
        with pytest.raises(ValidationError, match="Cannot patch_managed on an unmanaged policy"):
            backend.admin.patch_managed_policy("pol-1", title="Nope")

    assert not any("PolicyUpdateManaged" in c.args[0] for c in mock_exec.call_args_list)


def test_patch_unmanaged_policy_merges_current_values(monkeypatch):
    backend = _make_backend(monkeypatch)
    current = _policy_payload(managed=False, permissions=(), role_ids=("role-3",))
    execute = _responder(
        {
            "PolicyGet": {"data": {"policy": current}},
            "PolicyUpdateUnmanaged": {"data": {"policyUpdateUnmanaged": {"__typename": "Policy", **current}}},
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute) as mock_exec:
        backend.admin.patch_unmanaged_policy("pol-1", arn="arn:aws:iam::123:policy/New")

    update_call = [c for c in mock_exec.call_args_list if "PolicyUpdateUnmanaged" in c.args[0]][0]
    assert update_call.kwargs["variables"] == {
        "id": "pol-1",
        "input": {
            "title": "Analysts",
            "arn": "arn:aws:iam::123:policy/New",
            "roles": ["role-3"],
        },
    }


def test_patch_unmanaged_policy_rejects_managed_target(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {"data": {"policy": _policy_payload(managed=True)}}

    with patch.object(backend, "execute_graphql_query", return_value=response):
        with pytest.raises(ValidationError, match="Cannot patch_unmanaged on a managed policy"):
            backend.admin.patch_unmanaged_policy("pol-1", title="Nope")


def test_patch_managed_policy_missing_policy(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder({"PolicyGet": {"data": {"policy": None}}, "PoliciesList": {"data": {"policies": []}}})

    with patch.object(backend, "execute_graphql_query", side_effect=execute):
        with pytest.raises(NotFoundError, match="Policy not found"):
            backend.admin.patch_managed_policy("ghost", title="Nope")


# ---------------------------------------------------------------------
# Policy deletion
# ---------------------------------------------------------------------


def test_delete_policy_success(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder(
        {
            "PolicyGet": {"data": {"policy": _policy_payload()}},
            "PolicyDelete": {"data": {"policyDelete": {"__typename": "Ok"}}},
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute) as mock_exec:
        backend.admin.delete_policy("pol-1")  # must not raise

    delete_call = [c for c in mock_exec.call_args_list if "PolicyDelete" in c.args[0]][0]
    assert delete_call.kwargs["variables"] == {"id": "pol-1"}


def test_delete_policy_not_found(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder({"PolicyGet": {"data": {"policy": None}}, "PoliciesList": {"data": {"policies": []}}})

    with patch.object(backend, "execute_graphql_query", side_effect=execute):
        with pytest.raises(NotFoundError, match="Policy not found"):
            backend.admin.delete_policy("ghost")


def test_delete_policy_operation_error(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder(
        {
            "PolicyGet": {"data": {"policy": _policy_payload()}},
            "PolicyDelete": {
                "data": {
                    "policyDelete": {
                        "__typename": "OperationError",
                        "message": "policy still attached",
                        "name": "Conflict",
                        "context": None,
                    }
                }
            },
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute):
        with pytest.raises(BackendError, match="policy still attached"):
            backend.admin.delete_policy("pol-1")


# ---------------------------------------------------------------------
# Union error mapping
# ---------------------------------------------------------------------


def test_create_managed_policy_invalid_input_raises_validation_error(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {
        "data": {
            "policyCreateManaged": {
                "__typename": "InvalidInput",
                "errors": [{"path": "title", "message": "title taken", "name": "Conflict", "context": None}],
            }
        }
    }

    with patch.object(backend, "execute_graphql_query", return_value=response):
        with pytest.raises(ValidationError, match="title taken"):
            backend.admin.create_managed_policy("Analysts", [])


def test_create_managed_policy_operation_error_raises_backend_error(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {
        "data": {
            "policyCreateManaged": {
                "__typename": "OperationError",
                "message": "registry unavailable",
                "name": "Unavailable",
                "context": None,
            }
        }
    }

    with patch.object(backend, "execute_graphql_query", return_value=response):
        with pytest.raises(BackendError, match="registry unavailable"):
            backend.admin.create_managed_policy("Analysts", [])


def test_create_unmanaged_policy_invalid_input_raises_validation_error(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {
        "data": {
            "policyCreateUnmanaged": {
                "__typename": "InvalidInput",
                "errors": [{"path": "arn", "message": "bad arn", "name": "Invalid", "context": None}],
            }
        }
    }

    with patch.object(backend, "execute_graphql_query", return_value=response):
        with pytest.raises(ValidationError, match="bad arn"):
            backend.admin.create_unmanaged_policy("Legacy", "not-an-arn")


def test_patch_managed_policy_operation_error_raises_backend_error(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder(
        {
            "PolicyGet": {"data": {"policy": _policy_payload()}},
            "PolicyUpdateManaged": {
                "data": {
                    "policyUpdateManaged": {
                        "__typename": "OperationError",
                        "message": "update rejected",
                        "name": "Rejected",
                        "context": None,
                    }
                }
            },
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute):
        with pytest.raises(BackendError, match="update rejected"):
            backend.admin.patch_managed_policy("pol-1", title="Renamed")


# ---------------------------------------------------------------------
# Role reads and mutations
# ---------------------------------------------------------------------


def test_get_role_found_by_id(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {"data": {"role": _role_payload()}}

    with patch.object(backend, "execute_graphql_query", return_value=response) as mock_exec:
        role = backend.admin.get_role("role-1")

    assert mock_exec.call_args.kwargs["variables"] == {"id": "role-1"}
    assert isinstance(role, Role)
    assert role.id == "role-1"
    assert role.type == "ManagedRole"


def test_get_role_falls_back_to_name_lookup(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder(
        {
            "RoleGet": {"data": {"role": None}},
            "ListRoles": {"data": {"roles": [_role_payload(id="role-7", name="Curator")]}},
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute):
        role = backend.admin.get_role("Curator")

    assert role is not None
    assert role.id == "role-7"


def test_get_role_not_found_returns_none(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder({"RoleGet": {"data": {"role": None}}, "ListRoles": {"data": {"roles": []}}})

    with patch.object(backend, "execute_graphql_query", side_effect=execute):
        assert backend.admin.get_role("ghost") is None


def test_create_managed_role_sends_managed_role_input(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {
        "data": {
            "roleCreateManaged": {
                "__typename": "RoleCreateSuccess",
                "role": _role_payload(name="Analyst"),
            }
        }
    }

    with patch.object(backend, "execute_graphql_query", return_value=response) as mock_exec:
        role = backend.admin.create_managed_role("Analyst", policy_ids=["pol-1", "pol-2"])

    (query,) = mock_exec.call_args.args
    assert "$input: ManagedRoleInput!" in query
    assert mock_exec.call_args.kwargs["variables"] == {"input": {"name": "Analyst", "policies": ["pol-1", "pol-2"]}}
    assert role.name == "Analyst"


def test_create_managed_role_name_exists(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {"data": {"roleCreateManaged": {"__typename": "RoleNameExists"}}}

    with patch.object(backend, "execute_graphql_query", return_value=response):
        with pytest.raises(ValidationError, match="already exists"):
            backend.admin.create_managed_role("Analyst")


def test_create_unmanaged_role_sends_arn(monkeypatch):
    backend = _make_backend(monkeypatch)
    response = {
        "data": {
            "roleCreateUnmanaged": {
                "__typename": "RoleCreateSuccess",
                "role": _role_payload(name="External", typename="UnmanagedRole"),
            }
        }
    }

    with patch.object(backend, "execute_graphql_query", return_value=response) as mock_exec:
        role = backend.admin.create_unmanaged_role("External", "arn:aws:iam::123:role/External")

    (query,) = mock_exec.call_args.args
    assert "$input: UnmanagedRoleInput!" in query
    assert mock_exec.call_args.kwargs["variables"] == {
        "input": {"name": "External", "arn": "arn:aws:iam::123:role/External"}
    }
    assert role.type == "UnmanagedRole"


def test_create_unmanaged_role_requires_arn(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(ValidationError, match="ARN cannot be empty"):
        backend.admin.create_unmanaged_role("External", "")


def test_delete_role_success(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder(
        {
            "RoleGet": {"data": {"role": _role_payload()}},
            "RoleDelete": {"data": {"roleDelete": {"__typename": "RoleDeleteSuccess"}}},
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute) as mock_exec:
        backend.admin.delete_role("role-1")  # must not raise

    delete_call = [c for c in mock_exec.call_args_list if "RoleDelete" in c.args[0]][0]
    assert delete_call.kwargs["variables"] == {"id": "role-1"}


def test_delete_role_still_assigned(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder(
        {
            "RoleGet": {"data": {"role": _role_payload()}},
            "RoleDelete": {"data": {"roleDelete": {"__typename": "RoleAssigned"}}},
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute):
        with pytest.raises(ValidationError, match="still assigned"):
            backend.admin.delete_role("role-1")


def test_delete_role_not_found(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder({"RoleGet": {"data": {"role": None}}, "ListRoles": {"data": {"roles": []}}})

    with patch.object(backend, "execute_graphql_query", side_effect=execute):
        with pytest.raises(NotFoundError, match="Role not found"):
            backend.admin.delete_role("ghost")


def test_set_default_role_success(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder(
        {
            "RoleGet": {"data": {"role": _role_payload()}},
            "RoleSetDefault": {
                "data": {
                    "roleSetDefault": {
                        "__typename": "RoleSetDefaultSuccess",
                        "role": _role_payload(name="Analyst"),
                    }
                }
            },
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute) as mock_exec:
        role = backend.admin.set_default_role("role-1")

    set_call = [c for c in mock_exec.call_args_list if "RoleSetDefault" in c.args[0]][0]
    assert set_call.kwargs["variables"] == {"id": "role-1"}
    assert role.name == "Analyst"


def test_set_default_role_sso_conflict(monkeypatch):
    backend = _make_backend(monkeypatch)
    execute = _responder(
        {
            "RoleGet": {"data": {"role": _role_payload()}},
            "RoleSetDefault": {"data": {"roleSetDefault": {"__typename": "SsoConfigConflict"}}},
        }
    )

    with patch.object(backend, "execute_graphql_query", side_effect=execute):
        with pytest.raises(ValidationError, match="SSO configuration"):
            backend.admin.set_default_role("role-1")


# ---------------------------------------------------------------------
# Fail-closed behavior (code review remediation)
# ---------------------------------------------------------------------


def test_missing_permission_level_raises_rather_than_defaulting_to_read(monkeypatch):
    """A silent READ default would tell an admin a policy is read-only, and a later
    title-only patch would write that downgrade back to the registry."""
    backend = _make_backend(monkeypatch)
    payload = _policy_payload()
    del payload["permissions"][0]["level"]

    with patch.object(
        backend,
        "execute_graphql_query",
        _responder({"PoliciesList": {"data": {"policies": [payload]}}}),
    ):
        with pytest.raises(BackendError):
            backend.admin.list_policies()


def test_unknown_permission_level_raises(monkeypatch):
    """A level the registry adds later must not be coerced to READ."""
    backend = _make_backend(monkeypatch)
    payload = _policy_payload(permissions=(("bucket-a", "WRITE_ONLY"),))

    with patch.object(
        backend,
        "execute_graphql_query",
        _responder({"PoliciesList": {"data": {"policies": [payload]}}}),
    ):
        with pytest.raises(BackendError):
            backend.admin.list_policies()


def test_delete_policy_without_typename_raises_not_reports_success(monkeypatch):
    """Falling through would report a policy as deleted while it still grants access."""
    backend = _make_backend(monkeypatch)

    with patch.object(
        backend,
        "execute_graphql_query",
        _responder(
            {
                "PolicyGet": {"data": {"policy": _policy_payload()}},
                "PolicyDelete": {"data": {"policyDelete": {}}},
            }
        ),
    ):
        with pytest.raises(BackendError, match="no __typename"):
            backend.admin.delete_policy("pol-1")


def test_delete_role_without_typename_raises_not_reports_success(monkeypatch):
    backend = _make_backend(monkeypatch)

    with patch.object(
        backend,
        "execute_graphql_query",
        _responder(
            {
                "RoleGet": {"data": {"role": _role_payload()}},
                "RoleDelete": {"data": {"roleDelete": {}}},
            }
        ),
    ):
        with pytest.raises(BackendError, match="no __typename"):
            backend.admin.delete_role("role-1")


def test_create_policy_without_typename_raises_not_empty_policy(monkeypatch):
    """Treating a missing __typename as success fabricated Policy(id=None, title='')
    and reported a policy that was never created."""
    backend = _make_backend(monkeypatch)

    with patch.object(
        backend,
        "execute_graphql_query",
        _responder({"PolicyCreateManaged": {"data": {"policyCreateManaged": {"unexpected": "body"}}}}),
    ):
        with pytest.raises(BackendError):
            backend.admin.create_managed_policy(
                title="Analysts", permissions=[Permission(bucket="bucket-a", level="READ")]
            )


def test_get_policy_falls_back_to_title_when_id_query_errors(monkeypatch):
    """A registry that validates the ID scalar raises instead of returning null, so
    without this fallback every title-addressed patch and delete breaks."""
    backend = _make_backend(monkeypatch)
    calls = {"n": 0}

    def _execute(query, variables=None, registry=None):
        if "PolicyGet" in query:
            calls["n"] += 1
            raise BackendError("GraphQL query failed: invalid ID")
        if "PoliciesList" in query:
            return {"data": {"policies": [_policy_payload(title="Analysts")]}}
        raise AssertionError(f"unexpected query: {query}")

    with patch.object(backend, "execute_graphql_query", _execute):
        got = backend.admin.get_policy("Analysts")

    assert calls["n"] == 1, "the ID lookup must be attempted first"
    assert got is not None and got.title == "Analysts"

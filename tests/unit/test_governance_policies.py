"""Unit tests for governance policy management actions."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quilt_mcp.tools import governance
from quilt_mcp.tools import governance_impl_part3 as policies_impl


@pytest.mark.asyncio
async def test_admin_discovery_includes_policy_actions():
    result = await governance.admin(action=None)
    assert "policies_list" in result["actions"]
    assert "policy_create_managed" in result["actions"]
    assert "policy_delete" in result["actions"]


@pytest.mark.asyncio
@patch.object(policies_impl, "_require_admin_auth", return_value=("token", "https://catalog"))
@patch.object(policies_impl, "catalog_graphql_query", return_value={"policies": []})
async def test_policy_list_returns_success(mock_query, _mock_auth):
    result = await governance.admin(action="policies_list")
    assert result["success"] is True
    assert result["policies"] == []
    mock_query.assert_called_once()


@pytest.mark.asyncio
async def test_policy_create_managed_validates_inputs():
    result = await governance.admin(
        action="policy_create_managed",
        params={
            "name": "",
            "permissions": [],
        },
    )
    assert result["success"] is False
    assert "cannot be empty" in result["error"]


@pytest.mark.asyncio
@patch.object(policies_impl, "_require_admin_auth", return_value=("token", "https://catalog"))
@patch.object(
    policies_impl,
    "catalog_graphql_query",
    return_value={
        "policyCreateManaged": {
            "__typename": "Policy",
            "id": "policy-123",
            "name": "TestPolicy",
            "permissions": [],
        }
    },
)
async def test_policy_create_managed_success(mock_query, _mock_auth):
    result = await governance.admin(
        action="policy_create_managed",
        params={
            "name": "TestPolicy",
            "permissions": [{"bucket_name": "bucket", "level": "READ"}],
        },
    )
    assert result["success"] is True
    assert result["policy"]["id"] == "policy-123"
    mock_query.assert_called_once()


@pytest.mark.asyncio
@patch.object(policies_impl, "_require_admin_auth", return_value=("token", "https://catalog"))
@patch.object(
    policies_impl,
    "catalog_graphql_query",
    return_value={"policyCreateUnmanaged": {"__typename": "InvalidInput", "errors": [{"message": "duplicate"}]}},
)
async def test_policy_create_unmanaged_handles_errors(mock_query, _mock_auth):
    result = await governance.admin(
        action="policy_create_unmanaged",
        params={
            "name": "ExistingPolicy",
            "arn": "arn:aws:iam::111111111111:policy/ExistingPolicy",
        },
    )
    assert result["success"] is False
    assert "duplicate" in result["error"].lower()
    mock_query.assert_called_once()


@pytest.mark.asyncio
@patch.object(policies_impl, "_require_admin_auth", return_value=("token", "https://catalog"))
async def test_policy_update_managed_fetches_existing(_mock_auth):
    side_effects = [
        {
            "policy": {
                "id": "policy-1",
                "name": "ExistingPolicy",
                "title": "Original",
                "permissions": [{"bucket": {"name": "bucket"}, "level": "READ"}],
            }
        },
        {
            "policyUpdateManaged": {
                "__typename": "Policy",
                "id": "policy-1",
                "name": "ExistingPolicy",
                "title": "Updated",
                "permissions": [{"bucket": {"name": "bucket"}, "level": "READ"}],
            }
        },
    ]
    with patch.object(policies_impl, "catalog_graphql_query", side_effect=side_effects) as mock_query:
        result = await governance.admin(
            action="policy_update_managed",
            params={
                "policy_id": "policy-1",
                "title": "Updated",
            },
        )

    assert result["success"] is True
    assert result["policy"]["title"] == "Updated"
    assert mock_query.call_count == 2  # fetch + update


@pytest.mark.asyncio
@patch.object(policies_impl, "_require_admin_auth", return_value=("token", "https://catalog"))
@patch.object(
    policies_impl,
    "catalog_graphql_query",
    return_value={"policyDelete": {"__typename": "OperationError", "message": "policy in use"}},
)
async def test_policy_delete_handles_operation_error(mock_query, _mock_auth):
    result = await governance.admin(
        action="policy_delete",
        params={"policy_id": "policy-1"},
    )
    assert result["success"] is False
    assert "policy in use" in result["error"].lower()
    mock_query.assert_called_once()

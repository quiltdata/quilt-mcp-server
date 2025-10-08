import pytest
from unittest.mock import patch

from quilt_mcp.tools import governance_impl_part2 as gov


@pytest.mark.asyncio
async def test_admin_role_create_managed_success():
    with patch.object(gov, "_require_admin_auth", return_value=("token", "https://catalog")), patch.object(
        gov, "catalog_graphql_query", return_value={
            "roleCreateManaged": {
                "__typename": "RoleCreateSuccess",
                "role": {"id": "123", "name": "DataScientist", "arn": "arn:aws:iam::123:role/DataScientist"},
            }
        },
    ) as mock_query:
        result = await gov.admin_role_create(
            name="DataScientist",
            role_type="managed",
            policies=["policy-id-1"],
        )

    mock_query.assert_called_once()
    variables = mock_query.call_args.kwargs["variables"]
    assert variables == {"input": {"name": "DataScientist", "policies": ["policy-id-1"]}}
    assert result["success"] is True
    assert result["role"]["name"] == "DataScientist"


@pytest.mark.asyncio
async def test_admin_role_create_unmanaged_success():
    with patch.object(gov, "_require_admin_auth", return_value=("token", "https://catalog")), patch.object(
        gov, "catalog_graphql_query", return_value={
            "roleCreateUnmanaged": {
                "__typename": "RoleCreateSuccess",
                "role": {"id": "456", "name": "ExternalRole", "arn": "arn:aws:iam::123:role/External"},
            }
        },
    ) as mock_query:
        result = await gov.admin_role_create(
            name="ExternalRole",
            role_type="unmanaged",
            arn="arn:aws:iam::123:role/External",
        )

    mock_query.assert_called_once()
    variables = mock_query.call_args.kwargs["variables"]
    assert variables == {"input": {"name": "ExternalRole", "arn": "arn:aws:iam::123:role/External"}}
    assert result["success"] is True
    assert result["role"]["arn"].endswith("External")


@pytest.mark.asyncio
async def test_admin_role_create_requires_policies_for_managed():
    result = await gov.admin_role_create(name="NoPolicies", role_type="managed", policies=[])
    assert result["success"] is False
    assert "policy" in result["error"].lower()


@pytest.mark.asyncio
async def test_admin_role_create_handles_graphql_errors():
    with patch.object(gov, "_require_admin_auth", return_value=("token", "https://catalog")), patch.object(
        gov,
        "catalog_graphql_query",
        return_value={"roleCreateManaged": {"__typename": "RoleNameExists"}},
    ):
        result = await gov.admin_role_create(name="ExistingRole", role_type="managed", policies=["p1"])

    assert result["success"] is False
    assert "already exists" in result["error"].lower()


@pytest.mark.asyncio
async def test_admin_role_create_invalid_role_type():
    result = await gov.admin_role_create(name="Test", role_type="custom")
    assert result["success"] is False
    assert "role_type" in result["error"].lower()

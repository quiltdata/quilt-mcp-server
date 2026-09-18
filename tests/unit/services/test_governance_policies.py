"""Unit tests for policy and role-mutation governance tools.

These close the gap against quilt3.admin.policies / quilt3.admin.roles, so the
tests assert the wiring: input validation, that the right AdminOps call is made
with the right arguments, and that domain objects come back shaped for MCP.
"""

from unittest.mock import Mock, patch

import pytest

from quilt_mcp.context.request_context import RequestContext
from quilt_mcp.domain.policy import Permission, Policy
from quilt_mcp.domain.role import Role
from quilt_mcp.ops.exceptions import NotFoundError
from quilt_mcp.services import governance_service as governance


@pytest.fixture
def mock_context():
    return Mock(spec=RequestContext)


@pytest.fixture
def admin_available():
    with patch.object(governance, "ADMIN_AVAILABLE", True):
        yield


@pytest.fixture
def ops():
    """QuiltOps double whose .admin is a bare Mock."""
    return Mock(admin=Mock())


@pytest.fixture
def sample_policy():
    return Policy(
        id="pol-1",
        title="ReadOnlyAnalysts",
        arn="arn:aws:iam::123456789012:policy/ReadOnlyAnalysts",
        managed=True,
        permissions=[Permission(bucket="research-data", level="READ")],
        role_ids=["role-1"],
    )


@pytest.fixture
def sample_role():
    return Role(id="role-1", name="Analysts", arn="arn:aws:iam::123:role/Analysts", type="ManagedRole")


class TestPermissionsFromInput:
    def test_builds_domain_permissions(self):
        got = governance._permissions_from_input(
            [{"bucket": "a", "level": "READ"}, {"bucket": "b", "level": "READ_WRITE"}]
        )
        assert got == [Permission(bucket="a", level="READ"), Permission(bucket="b", level="READ_WRITE")]

    def test_rejects_bad_level(self):
        with pytest.raises(ValueError, match="permission level must be one of"):
            governance._permissions_from_input([{"bucket": "a", "level": "ADMIN"}])

    def test_rejects_missing_bucket(self):
        with pytest.raises(ValueError, match="non-empty 'bucket'"):
            governance._permissions_from_input([{"level": "READ"}])

    def test_rejects_non_object_entry(self):
        with pytest.raises(ValueError, match="must be an object"):
            governance._permissions_from_input(["research-data"])


class TestPoliciesList:
    async def test_lists_policies(self, admin_available, ops, mock_context, sample_policy):
        ops.admin.list_policies.return_value = [sample_policy]

        result = await governance.admin_policies_list(quilt_ops=ops, context=mock_context)

        assert result["success"] is True
        assert result["count"] == 1
        policy = result["policies"][0]
        assert policy["title"] == "ReadOnlyAnalysts"
        assert policy["managed"] is True
        assert policy["permissions"] == [{"bucket": "research-data", "level": "READ"}]
        assert policy["role_ids"] == ["role-1"]

    async def test_backend_error_becomes_error_response(self, admin_available, ops, mock_context):
        ops.admin.list_policies.side_effect = NotFoundError("nope", {})

        result = await governance.admin_policies_list(quilt_ops=ops, context=mock_context)

        assert result["success"] is False


class TestPolicyGet:
    async def test_returns_policy(self, admin_available, ops, mock_context, sample_policy):
        ops.admin.get_policy.return_value = sample_policy

        result = await governance.admin_policy_get("ReadOnlyAnalysts", quilt_ops=ops, context=mock_context)

        assert result["success"] is True
        assert result["policy"]["id"] == "pol-1"
        ops.admin.get_policy.assert_called_once_with("ReadOnlyAnalysts")

    async def test_missing_policy_is_an_error_not_a_none(self, admin_available, ops, mock_context):
        ops.admin.get_policy.return_value = None

        result = await governance.admin_policy_get("ghost", quilt_ops=ops, context=mock_context)

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    async def test_rejects_empty_identifier(self, admin_available, ops, mock_context):
        result = await governance.admin_policy_get("", quilt_ops=ops, context=mock_context)

        assert result["success"] is False
        ops.admin.get_policy.assert_not_called()


class TestPolicyCreateManaged:
    async def test_forwards_permissions_as_domain_objects(self, admin_available, ops, mock_context, sample_policy):
        ops.admin.create_managed_policy.return_value = sample_policy

        result = await governance.admin_policy_create_managed(
            title="ReadOnlyAnalysts",
            permissions=[{"bucket": "research-data", "level": "READ"}],
            role_ids=["role-1"],
            quilt_ops=ops,
            context=mock_context,
        )

        assert result["success"] is True
        kwargs = ops.admin.create_managed_policy.call_args.kwargs
        assert kwargs["title"] == "ReadOnlyAnalysts"
        assert kwargs["permissions"] == [Permission(bucket="research-data", level="READ")]
        assert kwargs["role_ids"] == ["role-1"]

    async def test_requires_at_least_one_permission(self, admin_available, ops, mock_context):
        result = await governance.admin_policy_create_managed(
            title="Empty", permissions=[], quilt_ops=ops, context=mock_context
        )

        assert result["success"] is False
        ops.admin.create_managed_policy.assert_not_called()

    async def test_invalid_level_never_reaches_the_backend(self, admin_available, ops, mock_context):
        result = await governance.admin_policy_create_managed(
            title="Bad",
            permissions=[{"bucket": "b", "level": "SUPERUSER"}],
            quilt_ops=ops,
            context=mock_context,
        )

        assert result["success"] is False
        assert "Invalid permissions" in result["error"]
        ops.admin.create_managed_policy.assert_not_called()

    async def test_rejects_empty_title(self, admin_available, ops, mock_context):
        result = await governance.admin_policy_create_managed(
            title="", permissions=[{"bucket": "b", "level": "READ"}], quilt_ops=ops, context=mock_context
        )

        assert result["success"] is False
        ops.admin.create_managed_policy.assert_not_called()


class TestPolicyCreateUnmanaged:
    async def test_forwards_arn(self, admin_available, ops, mock_context, sample_policy):
        ops.admin.create_unmanaged_policy.return_value = sample_policy

        result = await governance.admin_policy_create_unmanaged(
            title="Existing",
            arn="arn:aws:iam::123456789012:policy/Existing",
            quilt_ops=ops,
            context=mock_context,
        )

        assert result["success"] is True
        kwargs = ops.admin.create_unmanaged_policy.call_args.kwargs
        assert kwargs["arn"] == "arn:aws:iam::123456789012:policy/Existing"

    async def test_requires_arn(self, admin_available, ops, mock_context):
        result = await governance.admin_policy_create_unmanaged(
            title="Existing", arn="", quilt_ops=ops, context=mock_context
        )

        assert result["success"] is False
        ops.admin.create_unmanaged_policy.assert_not_called()


class TestPolicyPatch:
    async def test_passes_only_specified_fields(self, admin_available, ops, mock_context, sample_policy):
        """An omitted field must arrive as None so the backend keeps its value."""
        ops.admin.patch_managed_policy.return_value = sample_policy

        result = await governance.admin_policy_patch_managed(
            "pol-1", title="Renamed", quilt_ops=ops, context=mock_context
        )

        assert result["success"] is True
        kwargs = ops.admin.patch_managed_policy.call_args.kwargs
        assert kwargs["title"] == "Renamed"
        assert kwargs["permissions"] is None
        assert kwargs["role_ids"] is None

    async def test_empty_patch_is_rejected(self, admin_available, ops, mock_context):
        result = await governance.admin_policy_patch_managed("pol-1", quilt_ops=ops, context=mock_context)

        assert result["success"] is False
        assert "Nothing to update" in result["error"]
        ops.admin.patch_managed_policy.assert_not_called()

    async def test_unmanaged_patch_forwards_arn(self, admin_available, ops, mock_context, sample_policy):
        ops.admin.patch_unmanaged_policy.return_value = sample_policy

        result = await governance.admin_policy_patch_unmanaged(
            "pol-1", arn="arn:aws:iam::123:policy/New", quilt_ops=ops, context=mock_context
        )

        assert result["success"] is True
        kwargs = ops.admin.patch_unmanaged_policy.call_args.kwargs
        assert kwargs["arn"] == "arn:aws:iam::123:policy/New"
        assert kwargs["title"] is None

    async def test_empty_unmanaged_patch_is_rejected(self, admin_available, ops, mock_context):
        result = await governance.admin_policy_patch_unmanaged("pol-1", quilt_ops=ops, context=mock_context)

        assert result["success"] is False
        ops.admin.patch_unmanaged_policy.assert_not_called()


class TestPolicyDelete:
    async def test_deletes(self, admin_available, ops, mock_context):
        result = await governance.admin_policy_delete("pol-1", quilt_ops=ops, context=mock_context)

        assert result["success"] is True
        ops.admin.delete_policy.assert_called_once_with("pol-1")

    async def test_rejects_empty_identifier(self, admin_available, ops, mock_context):
        result = await governance.admin_policy_delete("", quilt_ops=ops, context=mock_context)

        assert result["success"] is False
        ops.admin.delete_policy.assert_not_called()


class TestRoleMutations:
    async def test_get_role(self, admin_available, ops, mock_context, sample_role):
        ops.admin.get_role.return_value = sample_role

        result = await governance.admin_role_get("Analysts", quilt_ops=ops, context=mock_context)

        assert result["success"] is True
        assert result["role"]["name"] == "Analysts"

    async def test_get_missing_role_is_an_error(self, admin_available, ops, mock_context):
        ops.admin.get_role.return_value = None

        result = await governance.admin_role_get("ghost", quilt_ops=ops, context=mock_context)

        assert result["success"] is False

    async def test_create_managed_role_forwards_policy_ids(self, admin_available, ops, mock_context, sample_role):
        ops.admin.create_managed_role.return_value = sample_role

        result = await governance.admin_role_create_managed(
            name="Analysts", policy_ids=["pol-1", "pol-2"], quilt_ops=ops, context=mock_context
        )

        assert result["success"] is True
        assert ops.admin.create_managed_role.call_args.kwargs["policy_ids"] == ["pol-1", "pol-2"]

    async def test_create_managed_role_defaults_to_no_policies(self, admin_available, ops, mock_context, sample_role):
        ops.admin.create_managed_role.return_value = sample_role

        await governance.admin_role_create_managed(name="Bare", quilt_ops=ops, context=mock_context)

        assert ops.admin.create_managed_role.call_args.kwargs["policy_ids"] == []

    async def test_create_unmanaged_role_requires_arn(self, admin_available, ops, mock_context):
        result = await governance.admin_role_create_unmanaged(
            name="Analysts", arn="", quilt_ops=ops, context=mock_context
        )

        assert result["success"] is False
        ops.admin.create_unmanaged_role.assert_not_called()

    async def test_delete_role(self, admin_available, ops, mock_context):
        result = await governance.admin_role_delete("role-1", quilt_ops=ops, context=mock_context)

        assert result["success"] is True
        ops.admin.delete_role.assert_called_once_with("role-1")

    async def test_set_default_role(self, admin_available, ops, mock_context, sample_role):
        ops.admin.set_default_role.return_value = sample_role

        result = await governance.admin_role_set_default("role-1", quilt_ops=ops, context=mock_context)

        assert result["success"] is True
        assert "Analysts" in result["message"]
        ops.admin.set_default_role.assert_called_once_with("role-1")

    async def test_set_default_rejects_empty(self, admin_available, ops, mock_context):
        result = await governance.admin_role_set_default("", quilt_ops=ops, context=mock_context)

        assert result["success"] is False
        ops.admin.set_default_role.assert_not_called()


class TestAdminUnavailable:
    """With quilt3.admin missing, every tool must degrade to an error response."""

    async def test_policies_list_reports_unavailable(self, ops, mock_context):
        with patch.object(governance, "ADMIN_AVAILABLE", False):
            result = await governance.admin_policies_list(quilt_ops=ops, context=mock_context)

        assert result["success"] is False
        ops.admin.list_policies.assert_not_called()

    async def test_policy_delete_reports_unavailable(self, ops, mock_context):
        with patch.object(governance, "ADMIN_AVAILABLE", False):
            result = await governance.admin_policy_delete("pol-1", quilt_ops=ops, context=mock_context)

        assert result["success"] is False
        ops.admin.delete_policy.assert_not_called()

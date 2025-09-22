"""Tests for MCP Resource Framework.

This module tests the base MCP resource system that consolidates list-type functions
into standardized MCP resources with backward compatibility.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock

# Import the modules we'll be testing (TDD - we'll create these after tests fail)
try:
    from quilt_mcp.resources.base import MCPResource, ResourceResponse, ResourceRegistry
    from quilt_mcp.resources.admin import AdminUsersResource, AdminRolesResource
    from quilt_mcp.resources.s3 import S3BucketsResource
except ImportError:
    # TDD: These imports will fail initially - that's expected
    pass


class TestResourceResponse:
    """Test the standardized ResourceResponse format."""

    def test_basic_resource_response_creation(self):
        """Test creating a basic ResourceResponse."""
        # TDD: This test should fail initially - we need to implement ResourceResponse
        items = [{"id": 1, "name": "test"}]
        response = ResourceResponse("test://items", items)

        result = response.to_dict()

        assert result["resource_uri"] == "test://items"
        assert result["resource_type"] == "list"
        assert result["items"] == items
        assert result["metadata"]["total_count"] == 1
        assert result["metadata"]["has_more"] is False
        assert result["metadata"]["continuation_token"] is None
        assert "last_updated" in result["metadata"]
        assert result["capabilities"]["filterable"] is False
        assert result["capabilities"]["sortable"] is False
        assert result["capabilities"]["paginatable"] is False

    def test_resource_response_with_custom_metadata(self):
        """Test ResourceResponse with custom metadata."""
        items = [{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}]
        custom_metadata = {"source": "test_system", "cached": True}

        response = ResourceResponse("test://items", items, custom_metadata)
        result = response.to_dict()

        assert result["metadata"]["total_count"] == 2
        assert result["metadata"]["source"] == "test_system"
        assert result["metadata"]["cached"] is True

    def test_resource_response_with_empty_items(self):
        """Test ResourceResponse with empty items list."""
        response = ResourceResponse("test://empty", [])
        result = response.to_dict()

        assert result["items"] == []
        assert result["metadata"]["total_count"] == 0

    def test_resource_response_timestamp_format(self):
        """Test that timestamps are in ISO format."""
        response = ResourceResponse("test://items", [{"test": "data"}])
        result = response.to_dict()

        timestamp = result["metadata"]["last_updated"]
        # Should be able to parse as ISO timestamp
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        assert isinstance(parsed, datetime)


class TestMCPResourceBase:
    """Test the base MCPResource abstract class."""

    def test_mcp_resource_abstract_methods(self):
        """Test that MCPResource cannot be instantiated directly."""
        # TDD: This should fail initially - we need to implement MCPResource
        with pytest.raises(TypeError):
            MCPResource("test://resource")

    def test_mcp_resource_subclass_requirements(self):
        """Test that subclasses must implement required methods."""

        class IncompleteResource(MCPResource):
            # Missing list_items implementation
            pass

        with pytest.raises(TypeError):
            IncompleteResource("test://incomplete")

    @pytest.mark.asyncio
    async def test_mcp_resource_concrete_implementation(self):
        """Test a concrete implementation of MCPResource."""

        class TestResource(MCPResource):
            async def list_items(self, **params) -> Dict[str, Any]:
                return {"items": [{"id": 1, "name": "test"}]}

        resource = TestResource("test://concrete")

        assert resource.uri == "test://concrete"
        assert resource.get_uri_pattern() == "test://concrete"

        capabilities = resource.get_capabilities()
        assert capabilities["filterable"] is False
        assert capabilities["sortable"] is False
        assert capabilities["paginatable"] is False

        result = await resource.list_items()
        assert result["items"] == [{"id": 1, "name": "test"}]


class TestResourceRegistry:
    """Test the resource registry and discovery system."""

    def test_resource_registry_creation(self):
        """Test creating a resource registry."""
        # TDD: This should fail initially - we need to implement ResourceRegistry
        registry = ResourceRegistry()
        assert isinstance(registry, ResourceRegistry)

    def test_resource_registration(self):
        """Test registering resources in the registry."""
        registry = ResourceRegistry()

        # Mock resource
        mock_resource = Mock()
        mock_resource.get_uri_pattern.return_value = "test://mock"

        registry.register("test://mock", mock_resource)

        assert registry.has_resource("test://mock")
        assert registry.get_resource("test://mock") == mock_resource

    def test_resource_discovery(self):
        """Test discovering all registered resources."""
        registry = ResourceRegistry()

        # Register multiple resources
        mock_resource1 = Mock()
        mock_resource1.get_uri_pattern.return_value = "admin://users"
        mock_resource2 = Mock()
        mock_resource2.get_uri_pattern.return_value = "s3://buckets"

        registry.register("admin://users", mock_resource1)
        registry.register("s3://buckets", mock_resource2)

        resources = registry.list_resources()
        assert len(resources) == 2
        assert "admin://users" in resources
        assert "s3://buckets" in resources

    def test_resource_not_found(self):
        """Test handling of missing resources."""
        registry = ResourceRegistry()

        assert not registry.has_resource("nonexistent://resource")

        with pytest.raises(ValueError, match="Resource not found"):
            registry.get_resource("nonexistent://resource")


class TestAdminUsersResource:
    """Test the AdminUsersResource implementation."""

    @pytest.fixture
    def mock_governance_service(self):
        """Mock governance service for testing."""
        mock_service = Mock()
        mock_service._check_admin_available.return_value = None
        return mock_service

    @pytest.fixture
    def mock_users_data(self):
        """Mock users data for testing."""
        return [
            {
                "name": "alice",
                "email": "alice@example.com",
                "is_active": True,
                "is_admin": False,
                "role": "user",
                "extra_roles": []
            },
            {
                "name": "bob",
                "email": "bob@example.com",
                "is_active": True,
                "is_admin": True,
                "role": "admin",
                "extra_roles": ["power_user"]
            }
        ]

    @pytest.mark.asyncio
    async def test_admin_users_resource_creation(self):
        """Test creating AdminUsersResource."""
        # TDD: This should fail initially - we need to implement AdminUsersResource
        resource = AdminUsersResource()

        assert resource.uri == "admin://users"
        assert resource.get_uri_pattern() == "admin://users"

    @pytest.mark.asyncio
    async def test_admin_users_list_items_success(self, mock_governance_service, mock_users_data):
        """Test successful listing of admin users."""
        with patch('quilt_mcp.resources.admin.GovernanceService', return_value=mock_governance_service):
            with patch('quilt_mcp.resources.admin.admin_users_list') as mock_admin_users:
                mock_admin_users.return_value = {
                    "success": True,
                    "users": mock_users_data,
                    "count": len(mock_users_data)
                }

                resource = AdminUsersResource()
                result = await resource.list_items()

                assert result["success"] is True
                assert len(result["users"]) == 2
                assert result["users"][0]["name"] == "alice"
                assert result["users"][1]["name"] == "bob"

    @pytest.mark.asyncio
    async def test_admin_users_list_items_admin_unavailable(self, mock_governance_service):
        """Test admin users listing when admin is unavailable."""
        mock_governance_service._check_admin_available.return_value = {
            "success": False,
            "error": "Admin functionality not available"
        }

        with patch('quilt_mcp.resources.admin.GovernanceService', return_value=mock_governance_service):
            resource = AdminUsersResource()
            result = await resource.list_items()

            assert result["success"] is False
            assert "Admin functionality not available" in result["error"]

    @pytest.mark.asyncio
    async def test_admin_users_resource_to_mcp_format(self, mock_users_data):
        """Test conversion to standardized MCP resource format."""
        with patch('quilt_mcp.resources.admin.admin_users_list') as mock_admin_users:
            mock_admin_users.return_value = {
                "success": True,
                "users": mock_users_data,
                "count": len(mock_users_data)
            }

            resource = AdminUsersResource()
            result = await resource.to_mcp_response()

            assert result["resource_uri"] == "admin://users"
            assert result["resource_type"] == "list"
            assert len(result["items"]) == 2
            assert result["metadata"]["total_count"] == 2


class TestAdminRolesResource:
    """Test the AdminRolesResource implementation."""

    @pytest.fixture
    def mock_roles_data(self):
        """Mock roles data for testing."""
        return [
            {"id": 1, "name": "user", "arn": "arn:aws:iam::123:role/user", "type": "standard"},
            {"id": 2, "name": "admin", "arn": "arn:aws:iam::123:role/admin", "type": "admin"},
            {"id": 3, "name": "power_user", "arn": "arn:aws:iam::123:role/power", "type": "enhanced"}
        ]

    @pytest.mark.asyncio
    async def test_admin_roles_resource_creation(self):
        """Test creating AdminRolesResource."""
        # TDD: This should fail initially - we need to implement AdminRolesResource
        resource = AdminRolesResource()

        assert resource.uri == "admin://roles"
        assert resource.get_uri_pattern() == "admin://roles"

    @pytest.mark.asyncio
    async def test_admin_roles_list_items_success(self, mock_roles_data):
        """Test successful listing of admin roles."""
        with patch('quilt_mcp.resources.admin.admin_roles_list') as mock_admin_roles:
            mock_admin_roles.return_value = {
                "success": True,
                "roles": mock_roles_data,
                "count": len(mock_roles_data)
            }

            resource = AdminRolesResource()
            result = await resource.list_items()

            assert result["success"] is True
            assert len(result["roles"]) == 3
            assert result["roles"][0]["name"] == "user"
            assert result["roles"][1]["name"] == "admin"


class TestS3BucketsResource:
    """Test the S3BucketsResource implementation."""

    @pytest.fixture
    def mock_buckets_data(self):
        """Mock S3 buckets data for testing."""
        return {
            "status": "success",
            "writable_buckets": [
                {"name": "my-data-bucket", "permission_level": "full_access", "region": "us-east-1"},
                {"name": "analytics-bucket", "permission_level": "read_write", "region": "us-west-2"}
            ],
            "readable_buckets": [
                {"name": "public-data", "permission_level": "read_only", "region": "us-east-1"},
                {"name": "shared-bucket", "permission_level": "list_only", "region": "us-west-2"}
            ],
            "registries": [
                {"name": "production", "url": "https://prod.quiltdata.com", "authenticated": True}
            ]
        }

    @pytest.mark.asyncio
    async def test_s3_buckets_resource_creation(self):
        """Test creating S3BucketsResource."""
        # TDD: This should fail initially - we need to implement S3BucketsResource
        resource = S3BucketsResource()

        assert resource.uri == "s3://buckets"
        assert resource.get_uri_pattern() == "s3://buckets"

    @pytest.mark.asyncio
    async def test_s3_buckets_list_items_success(self, mock_buckets_data):
        """Test successful listing of S3 buckets."""
        with patch('quilt_mcp.resources.s3.list_available_resources') as mock_list_resources:
            mock_list_resources.return_value = mock_buckets_data

            resource = S3BucketsResource()
            result = await resource.list_items()

            assert result["status"] == "success"
            assert len(result["writable_buckets"]) == 2
            assert len(result["readable_buckets"]) == 2
            assert result["writable_buckets"][0]["name"] == "my-data-bucket"

    @pytest.mark.asyncio
    async def test_s3_buckets_resource_to_mcp_format(self, mock_buckets_data):
        """Test conversion to standardized MCP resource format."""
        with patch('quilt_mcp.resources.s3.list_available_resources') as mock_list_resources:
            mock_list_resources.return_value = mock_buckets_data

            resource = S3BucketsResource()
            result = await resource.to_mcp_response()

            assert result["resource_uri"] == "s3://buckets"
            assert result["resource_type"] == "list"
            # Items should be flattened buckets list
            assert len(result["items"]) == 4  # 2 writable + 2 readable
            assert result["metadata"]["total_count"] == 4


class TestBackwardCompatibilityShims:
    """Test backward compatibility shims for original list functions."""

    @pytest.mark.asyncio
    async def test_admin_users_list_shim(self):
        """Test that original admin_users_list function still works via MCP resource."""
        # TDD: This should fail initially - we need to implement the shim
        with patch('quilt_mcp.resources.admin.AdminUsersResource') as mock_resource_class:
            mock_resource = Mock()
            mock_resource.list_items.return_value = {
                "success": True,
                "users": [{"name": "test"}],
                "count": 1
            }
            mock_resource_class.return_value = mock_resource

            # Import the shimmed function
            from quilt_mcp.tools.governance import admin_users_list

            result = await admin_users_list()

            assert result["success"] is True
            assert len(result["users"]) == 1
            mock_resource.list_items.assert_called_once()

    @pytest.mark.asyncio
    async def test_admin_roles_list_shim(self):
        """Test that original admin_roles_list function still works via MCP resource."""
        with patch('quilt_mcp.resources.admin.AdminRolesResource') as mock_resource_class:
            mock_resource = Mock()
            mock_resource.list_items.return_value = {
                "success": True,
                "roles": [{"name": "admin"}],
                "count": 1
            }
            mock_resource_class.return_value = mock_resource

            from quilt_mcp.tools.governance import admin_roles_list

            result = await admin_roles_list()

            assert result["success"] is True
            assert len(result["roles"]) == 1

    def test_s3_buckets_list_shim(self):
        """Test that original list_available_resources function still works via MCP resource."""
        with patch('quilt_mcp.resources.s3.S3BucketsResource') as mock_resource_class:
            mock_resource = Mock()
            mock_resource.list_items.return_value = {
                "status": "success",
                "writable_buckets": [{"name": "test"}],
                "readable_buckets": [],
                "registries": []
            }
            mock_resource_class.return_value = mock_resource

            from quilt_mcp.tools.unified_package import list_available_resources

            result = list_available_resources()

            assert result["status"] == "success"
            assert len(result["writable_buckets"]) == 1


class TestErrorHandlingAndCompensation:
    """Test error handling and compensation patterns in MCP resources."""

    @pytest.mark.asyncio
    async def test_resource_error_handling(self):
        """Test that MCP resources handle errors gracefully."""
        class FailingResource(MCPResource):
            async def list_items(self, **params) -> Dict[str, Any]:
                raise Exception("Service unavailable")

        resource = FailingResource("test://failing")

        # The resource should handle the exception and return error response
        with pytest.raises(Exception):
            await resource.list_items()

    @pytest.mark.asyncio
    async def test_error_compensation_in_shims(self):
        """Test that backward compatibility shims handle MCP resource errors."""
        with patch('quilt_mcp.resources.admin.AdminUsersResource') as mock_resource_class:
            mock_resource = Mock()
            mock_resource.list_items.side_effect = Exception("MCP resource failed")
            mock_resource_class.return_value = mock_resource

            # The shim should catch the error and provide fallback behavior
            from quilt_mcp.tools.governance import admin_users_list

            result = await admin_users_list()

            # Should get error response in original format
            assert result["success"] is False
            assert "error" in result


class TestResourceCachingAndPerformance:
    """Test resource caching and performance optimization."""

    def test_resource_response_caching_metadata(self):
        """Test that resource responses include caching metadata."""
        response = ResourceResponse("test://cached", [{"id": 1}], {"cached": True, "ttl": 300})
        result = response.to_dict()

        assert result["metadata"]["cached"] is True
        assert result["metadata"]["ttl"] == 300

    @pytest.mark.asyncio
    async def test_resource_performance_tracking(self):
        """Test that resource performance is tracked."""
        class TimedResource(MCPResource):
            async def list_items(self, **params) -> Dict[str, Any]:
                import time
                time.sleep(0.1)  # Simulate work
                return {"items": [{"id": 1}]}

        resource = TimedResource("test://timed")

        start_time = datetime.now()
        result = await resource.list_items()
        end_time = datetime.now()

        # Should complete reasonably quickly
        assert (end_time - start_time).total_seconds() < 1.0
        assert result["items"] == [{"id": 1}]
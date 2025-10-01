"""Tests for existing MCP functions that support resource listing.

This module tests the actual governance and resource functions that exist
in the codebase, ensuring they work correctly with proper mocking and
without requiring AWS credentials.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, MagicMock, patch, AsyncMock


class TestAdminUsersFunction:
    """Test the admin_users_list function from governance module."""

    @pytest.fixture
    def mock_users_data(self):
        """Mock users data for testing."""
        return [
            Mock(
                name="alice",
                email="alice@example.com",
                is_active=True,
                is_admin=False,
                is_sso_only=False,
                is_service=False,
                date_joined=datetime(2023, 1, 1, tzinfo=timezone.utc),
                last_login=datetime(2023, 6, 1, tzinfo=timezone.utc),
                role=Mock(name="user"),
                extra_roles=[],
            ),
            Mock(
                name="bob",
                email="bob@example.com",
                is_active=True,
                is_admin=True,
                is_sso_only=False,
                is_service=False,
                date_joined=datetime(2023, 2, 1, tzinfo=timezone.utc),
                last_login=datetime(2023, 6, 15, tzinfo=timezone.utc),
                role=Mock(name="admin"),
                extra_roles=[Mock(name="power_user")],
            ),
        ]

    @pytest.mark.asyncio
    async def test_admin_users_list_success(self, mock_users_data):
        """Test successful admin users listing."""
        from quilt_mcp.resources.admin import AdminUsersResource

        with patch('quilt_mcp.resources.admin.quilt_service.list_users') as mock_list_users:
            # Mock the service method to return user dicts
            mock_list_users.return_value = [
                {
                    "name": "alice",
                    "email": "alice@example.com",
                    "is_active": True,
                    "is_admin": False,
                },
                {
                    "name": "bob",
                    "email": "bob@example.com",
                    "is_active": True,
                    "is_admin": True,
                },
            ]

            # Mock the formatting function
            with patch('quilt_mcp.resources.admin.format_users_as_table') as mock_format:
                mock_format.return_value = {
                    "success": True,
                    "users": [
                        {
                            "name": "alice",
                            "email": "alice@example.com",
                            "is_active": True,
                            "is_admin": False,
                            "is_sso_only": False,
                            "is_service": False,
                            "date_joined": "2023-01-01T00:00:00+00:00",
                            "last_login": "2023-06-01T00:00:00+00:00",
                            "role": "user",
                            "extra_roles": [],
                        },
                        {
                            "name": "bob",
                            "email": "bob@example.com",
                            "is_active": True,
                            "is_admin": True,
                            "is_sso_only": False,
                            "is_service": False,
                            "date_joined": "2023-02-01T00:00:00+00:00",
                            "last_login": "2023-06-15T00:00:00+00:00",
                            "role": "admin",
                            "extra_roles": ["power_user"],
                        },
                    ],
                    "count": 2,
                    "message": "Found 2 users",
                    "formatted_table": "Mock table",
                }

                # Mock ADMIN_AVAILABLE
                with patch('quilt_mcp.resources.admin.ADMIN_AVAILABLE', True):
                    resource = AdminUsersResource()
                    result = await resource.list_items()

                    assert result["success"] is True
                    assert len(result["users"]) == 2
                    assert result["users"][0]["name"] == "alice"
                    assert result["users"][1]["name"] == "bob"
                    assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_admin_users_list_admin_unavailable(self):
        """Test admin users listing when admin is unavailable."""
        from quilt_mcp.resources.admin import AdminUsersResource

        with patch('quilt_mcp.resources.admin.ADMIN_AVAILABLE', False):
            resource = AdminUsersResource()
            result = await resource.list_items()

            assert result["success"] is False
            assert "Admin functionality not available" in result["error"]

    @pytest.mark.asyncio
    async def test_admin_users_list_exception_handling(self):
        """Test error handling in admin users listing."""
        from quilt_mcp.resources.admin import AdminUsersResource

        with patch('quilt_mcp.resources.admin.quilt_service.list_users') as mock_list_users:
            mock_list_users.side_effect = Exception("Database error")

            with patch('quilt_mcp.resources.admin.ADMIN_AVAILABLE', True):
                resource = AdminUsersResource()
                result = await resource.list_items()

                assert result["success"] is False
                assert "error" in result


class TestAdminRolesFunction:
    """Test the admin_roles_list function from governance module."""

    @pytest.fixture
    def mock_roles_data(self):
        """Mock roles data for testing."""
        return [
            Mock(id=1, name="user", arn="arn:aws:iam::123:role/user", typename="standard"),
            Mock(id=2, name="admin", arn="arn:aws:iam::123:role/admin", typename="admin"),
            Mock(id=3, name="power_user", arn="arn:aws:iam::123:role/power", typename="enhanced"),
        ]

    @pytest.mark.asyncio
    async def test_admin_roles_list_success(self, mock_roles_data):
        """Test successful admin roles listing."""
        from quilt_mcp.resources.admin import AdminRolesResource

        with patch('quilt_mcp.resources.admin.quilt_service.list_roles') as mock_list_roles:
            mock_list_roles.return_value = [
                {"id": 1, "name": "user", "arn": "arn:aws:iam::123:role/user", "type": "standard"},
                {"id": 2, "name": "admin", "arn": "arn:aws:iam::123:role/admin", "type": "admin"},
                {"id": 3, "name": "power_user", "arn": "arn:aws:iam::123:role/power", "type": "enhanced"},
            ]

            # Mock the formatting function
            with patch('quilt_mcp.resources.admin.format_roles_as_table') as mock_format:
                mock_format.return_value = {
                    "success": True,
                    "roles": [
                        {"id": 1, "name": "user", "arn": "arn:aws:iam::123:role/user", "type": "standard"},
                        {"id": 2, "name": "admin", "arn": "arn:aws:iam::123:role/admin", "type": "admin"},
                        {"id": 3, "name": "power_user", "arn": "arn:aws:iam::123:role/power", "type": "enhanced"},
                    ],
                    "count": 3,
                    "message": "Found 3 roles",
                    "formatted_table": "Mock roles table",
                }

                with patch('quilt_mcp.resources.admin.ADMIN_AVAILABLE', True):
                    resource = AdminRolesResource()
                    result = await resource.list_items()

                    assert result["success"] is True
                    assert len(result["roles"]) == 3
                    assert result["roles"][0]["name"] == "user"
                    assert result["roles"][1]["name"] == "admin"
                    assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_admin_roles_list_admin_unavailable(self):
        """Test admin roles listing when admin is unavailable."""
        from quilt_mcp.resources.admin import AdminRolesResource

        with patch('quilt_mcp.resources.admin.ADMIN_AVAILABLE', False):
            resource = AdminRolesResource()
            result = await resource.list_items()

            assert result["success"] is False
            assert "Admin functionality not available" in result["error"]


class TestS3ResourcesFunction:
    """Test the list_available_resources function from unified_package module."""

    @pytest.fixture
    def mock_permissions_result(self):
        """Mock permissions discovery result."""
        return {
            "success": True,
            "categorized_buckets": {
                "full_access": [
                    {
                        "name": "my-data-bucket",
                        "permission_level": "full_access",
                        "region": "us-east-1",
                        "can_read": True,
                    }
                ],
                "read_write": [
                    {
                        "name": "analytics-bucket",
                        "permission_level": "read_write",
                        "region": "us-west-2",
                        "can_read": True,
                    }
                ],
                "read_only": [
                    {"name": "public-data", "permission_level": "read_only", "region": "us-east-1", "can_read": True}
                ],
                "list_only": [
                    {
                        "name": "shared-bucket",
                        "permission_level": "list_only",
                        "region": "us-west-2",
                        "can_read": False,
                    }
                ],
            },
        }

    @pytest.fixture
    def mock_catalog_info(self):
        """Mock catalog info result."""
        return {
            "status": "success",
            "catalog_name": "production",
            "catalog_url": "https://prod.quiltdata.com",
            "is_authenticated": True,
        }

    def test_list_available_resources_success(self, mock_permissions_result, mock_catalog_info):
        """Test successful listing of available S3 resources."""
        with patch('quilt_mcp.tools.permissions.aws_permissions_discover') as mock_discover:
            with patch('quilt_mcp.tools.catalog.catalog_info') as mock_catalog:
                mock_discover.return_value = mock_permissions_result
                mock_catalog.return_value = mock_catalog_info

                from quilt_mcp.tools.catalog import list_available_resources

                result = list_available_resources()

                assert result["status"] == "success"
                assert len(result["writable_buckets"]) == 2  # full_access + read_write
                assert len(result["readable_buckets"]) == 4  # all buckets
                assert len(result["registries"]) == 1
                assert result["writable_buckets"][0]["name"] == "my-data-bucket"

    def test_list_available_resources_permissions_failure(self):
        """Test handling of permissions discovery failure."""
        with patch('quilt_mcp.tools.permissions.aws_permissions_discover') as mock_discover:
            mock_discover.return_value = {"success": False, "error": "AWS credentials not configured"}

            from quilt_mcp.tools.catalog import list_available_resources

            result = list_available_resources()

            assert result["status"] == "error"
            assert "Failed to discover available resources" in result["error"]
            assert result["details"] == "AWS credentials not configured"

    def test_list_available_resources_exception_handling(self):
        """Test exception handling in resource listing."""
        with patch('quilt_mcp.tools.permissions.aws_permissions_discover') as mock_discover:
            mock_discover.side_effect = Exception("Network error")

            from quilt_mcp.tools.catalog import list_available_resources

            result = list_available_resources()

            assert result["success"] is False
            assert "Failed to list resources" in result["error"]


class TestGovernanceService:
    """Test the GovernanceService class from governance module."""

    def test_governance_service_creation(self):
        """Test GovernanceService instantiation."""
        from quilt_mcp.tools.governance import GovernanceService

        service = GovernanceService()
        assert isinstance(service, GovernanceService)

    def test_governance_service_admin_check_available(self):
        """Test admin availability check when admin is available."""
        with patch('quilt_mcp.tools.governance.ADMIN_AVAILABLE', True):
            from quilt_mcp.tools.governance import GovernanceService

            service = GovernanceService()
            result = service._check_admin_available()

            assert result is None  # No error when admin is available

    def test_governance_service_admin_check_unavailable(self):
        """Test admin availability check when admin is unavailable."""
        with patch('quilt_mcp.tools.governance.ADMIN_AVAILABLE', False):
            from quilt_mcp.tools.governance import GovernanceService

            service = GovernanceService()
            result = service._check_admin_available()

            assert result is not None
            assert result["success"] is False
            assert "Admin functionality not available" in result["error"]

    def test_governance_service_error_handling(self):
        """Test error handling in GovernanceService."""
        from quilt_mcp.tools.governance import GovernanceService

        service = GovernanceService()
        result = service._handle_admin_error(Exception("Test error"), "test operation")

        assert result["success"] is False
        assert "Failed to test operation" in result["error"]


class TestUserManagementFunctions:
    """Test individual user management functions."""

    @pytest.mark.asyncio
    async def test_admin_user_get_success(self):
        """Test successful user retrieval."""
        mock_role = MagicMock()
        mock_role.name = "user"
        mock_role.id = 1
        mock_role.arn = "arn:test"
        mock_role.typename = "standard"

        mock_user = MagicMock()
        mock_user.name = "testuser"
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        mock_user.is_admin = False
        mock_user.is_sso_only = False
        mock_user.is_service = False
        mock_user.date_joined = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mock_user.last_login = datetime(2023, 6, 1, tzinfo=timezone.utc)
        mock_user.role = mock_role
        mock_user.extra_roles = []

        with patch('quilt_mcp.tools.governance.quilt_service') as mock_service:
            mock_service.get_user.return_value = mock_user

            with patch('quilt_mcp.tools.governance.ADMIN_AVAILABLE', True):
                from quilt_mcp.tools.governance import admin_user_get

                result = await admin_user_get("testuser")

                assert result["success"] is True
                assert result["user"]["name"] == "testuser"
                assert result["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_admin_user_get_not_found(self):
        """Test user not found scenario."""
        with patch('quilt_mcp.tools.governance.quilt_service') as mock_service:
            mock_service.get_user.return_value = None

            with patch('quilt_mcp.tools.governance.ADMIN_AVAILABLE', True):
                from quilt_mcp.tools.governance import admin_user_get

                result = await admin_user_get("nonexistent")

                assert result["success"] is False
                assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_admin_user_create_success(self):
        """Test successful user creation."""
        mock_role = MagicMock()
        mock_role.name = "user"

        mock_user = MagicMock()
        mock_user.name = "newuser"
        mock_user.email = "new@example.com"
        mock_user.is_active = True
        mock_user.is_admin = False
        mock_user.role = mock_role
        mock_user.extra_roles = []

        with patch('quilt_mcp.tools.governance.quilt_service') as mock_service:
            mock_service.create_user.return_value = mock_user

            with patch('quilt_mcp.tools.governance.ADMIN_AVAILABLE', True):
                from quilt_mcp.tools.governance import admin_user_create

                result = await admin_user_create("newuser", "new@example.com", "user")

                assert result["success"] is True
                assert result["user"]["name"] == "newuser"

    @pytest.mark.asyncio
    async def test_admin_user_create_validation_errors(self):
        """Test validation errors in user creation."""
        with patch('quilt_mcp.tools.governance.ADMIN_AVAILABLE', True):
            from quilt_mcp.tools.governance import admin_user_create

            # Test empty name
            result = await admin_user_create("", "test@example.com", "user")
            assert result["success"] is False
            assert "Username cannot be empty" in result["error"]

            # Test empty email
            result = await admin_user_create("test", "", "user")
            assert result["success"] is False
            assert "Email cannot be empty" in result["error"]

            # Test invalid email
            result = await admin_user_create("test", "invalid-email", "user")
            assert result["success"] is False
            assert "Invalid email format" in result["error"]


class TestErrorHandlingPatterns:
    """Test error handling patterns across functions."""

    @pytest.mark.asyncio
    async def test_function_error_handling_with_exceptions(self):
        """Test that functions handle various exception types properly."""
        # Test with UserNotFoundError
        with patch('quilt_mcp.tools.governance.quilt_service') as mock_service:
            with patch('quilt_mcp.tools.governance.UserNotFoundError', Exception):
                mock_admin_users = Mock()
                from quilt_mcp.resources.admin import AdminUsersResource

                mock_service.list_users.side_effect = Exception("User not found")

                with patch('quilt_mcp.resources.admin.ADMIN_AVAILABLE', True):
                    with patch('quilt_mcp.resources.admin.quilt_service', mock_service):
                        resource = AdminUsersResource()
                        result = await resource.list_items()

                        assert result["success"] is False
                        assert "error" in result

    def test_service_initialization_without_admin(self):
        """Test service initialization when admin is not available."""
        with patch('quilt_mcp.tools.governance.ADMIN_AVAILABLE', False):
            from quilt_mcp.tools.governance import GovernanceService

            service = GovernanceService()
            assert not service.admin_available

    def test_service_initialization_with_auth_disabled(self):
        """Test service initialization with auth disabled."""
        from quilt_mcp.tools.governance import GovernanceService

        service = GovernanceService(use_quilt_auth=False)
        assert not service.admin_available


class TestPerformanceAndCaching:
    """Test performance considerations and behavior."""

    def test_list_available_resources_performance_tracking(self):
        """Test that resource listing completes in reasonable time."""
        import time

        with patch('quilt_mcp.tools.permissions.aws_permissions_discover') as mock_discover:
            with patch('quilt_mcp.tools.catalog.catalog_info') as mock_catalog:
                # Mock fast responses
                mock_discover.return_value = {"success": True, "categorized_buckets": {}}
                mock_catalog.return_value = {"status": "success"}

                from quilt_mcp.tools.catalog import list_available_resources

                start_time = time.time()
                result = list_available_resources()
                end_time = time.time()

                # Should complete quickly with mocked responses
                assert (end_time - start_time) < 0.1
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_admin_functions_async_behavior(self):
        """Test that admin resources behave correctly as async functions."""
        from quilt_mcp.resources.admin import AdminUsersResource, AdminRolesResource

        with patch('quilt_mcp.resources.admin.ADMIN_AVAILABLE', False):
            # Both should be awaitable and return error responses
            users_resource = AdminUsersResource()
            roles_resource = AdminRolesResource()

            users_result = await users_resource.list_items()
            roles_result = await roles_resource.list_items()

            assert users_result["success"] is False
            assert roles_result["success"] is False


class TestTabularAccessibilityFunctions:
    """Test the tabular accessibility functions."""

    @pytest.mark.asyncio
    async def test_admin_tabulator_access_get_success(self):
        """Test successful tabular accessibility status retrieval."""
        with patch('quilt_mcp.tools.governance.quilt_service') as mock_service:
            mock_service.get_tabulator_access.return_value = True

            with patch('quilt_mcp.tools.governance.ADMIN_AVAILABLE', True):
                from quilt_mcp.tools.governance import admin_tabulator_access_get

                result = await admin_tabulator_access_get()

                assert result["success"] is True
                assert result["open_query_enabled"] is True
                assert "enabled" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_tabulator_access_set_success(self):
        """Test successful tabular accessibility status update."""
        with patch('quilt_mcp.tools.governance.quilt_service') as mock_service:
            mock_service.set_tabulator_access.return_value = None

            with patch('quilt_mcp.tools.governance.ADMIN_AVAILABLE', True):
                from quilt_mcp.tools.governance import admin_tabulator_access_set

                result = await admin_tabulator_access_set(False)

                assert result["success"] is True
                assert result["open_query_enabled"] is False
                assert "disabled" in result["message"]

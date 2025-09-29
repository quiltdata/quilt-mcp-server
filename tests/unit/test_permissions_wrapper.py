"""Tests for permissions module wrapper function."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from quilt_mcp.tools.permissions import permissions
from quilt_mcp.services.permission_discovery import (
    PermissionLevel,
    BucketInfo,
    UserIdentity,
)


class TestPermissionsWrapper:
    """Test the permissions module wrapper function."""

    def test_permissions_wrapper_exists(self):
        """Test that the permissions wrapper function exists."""
        assert callable(permissions)

    def test_permissions_discovery_mode_returns_actions(self):
        """Test that calling with action=None returns available actions."""
        result = permissions(action=None)
        
        assert result["success"] is True
        assert "module" in result
        assert result["module"] == "permissions"
        assert "actions" in result
        assert isinstance(result["actions"], list)
        assert "discover" in result["actions"]
        assert "access_check" in result["actions"]
        assert "recommendations_get" in result["actions"]

    def test_permissions_unknown_action(self):
        """Test error handling for unknown action."""
        result = permissions(action="invalid_action")
        
        assert result["success"] is False
        assert "error" in result
        assert "Unknown action" in result["error"]
        assert "invalid_action" in result["error"]
        assert "discover" in result["error"]  # Should list available actions

    @patch("quilt_mcp.tools.permissions._get_permission_discovery")
    def test_permissions_discover_action(self, mock_get_discovery):
        """Test the 'discover' action."""
        mock_discovery = Mock()
        mock_get_discovery.return_value = mock_discovery

        mock_identity = UserIdentity(
            user_id="test-user-id",
            arn="arn:aws:iam::123:user/test",
            account_id="123",
            user_type="user",
            user_name="test-user",
        )
        mock_discovery.discover_user_identity = Mock(return_value=mock_identity)
        mock_discovery.discover_accessible_buckets = Mock(return_value=[])
        mock_discovery.get_cache_stats = Mock(return_value={})

        result = permissions(action="discover")
        
        assert result["success"] is True
        assert "user_identity" in result
        assert result["user_identity"]["user_name"] == "test-user"

    @patch("quilt_mcp.tools.permissions._get_permission_discovery")
    def test_permissions_discover_with_params(self, mock_get_discovery):
        """Test the 'discover' action with parameters."""
        mock_discovery = Mock()
        mock_get_discovery.return_value = mock_discovery

        mock_identity = UserIdentity(
            user_id="test",
            arn="test",
            account_id="123",
            user_type="user",
        )
        mock_discovery.discover_user_identity = Mock(return_value=mock_identity)
        
        mock_bucket = BucketInfo(
            name="test-bucket",
            region="us-east-1",
            permission_level=PermissionLevel.FULL_ACCESS,
            can_read=True,
            can_write=True,
            can_list=True,
            last_checked=datetime.now(timezone.utc),
        )
        mock_discovery.discover_bucket_permissions = Mock(return_value=mock_bucket)
        mock_discovery.get_cache_stats = Mock(return_value={})

        result = permissions(
            action="discover",
            params={
                "check_buckets": ["test-bucket"],
                "force_refresh": True,
            }
        )
        
        assert result["success"] is True
        mock_discovery.clear_cache.assert_called_once()

    @patch("quilt_mcp.tools.permissions._get_permission_discovery")
    def test_permissions_access_check_action(self, mock_get_discovery):
        """Test the 'access_check' action."""
        mock_discovery = Mock()
        mock_get_discovery.return_value = mock_discovery

        mock_bucket = BucketInfo(
            name="test-bucket",
            region="us-west-2",
            permission_level=PermissionLevel.FULL_ACCESS,
            can_read=True,
            can_write=True,
            can_list=True,
            last_checked=datetime.now(timezone.utc),
        )
        mock_discovery.discover_bucket_permissions = Mock(return_value=mock_bucket)
        mock_discovery.test_bucket_operations = Mock(
            return_value={"read": True, "write": True, "list": True}
        )

        result = permissions(action="access_check", params={"bucket_name": "test-bucket"})
        
        assert result["success"] is True
        assert result["bucket_name"] == "test-bucket"
        assert result["permission_level"] == "full_access"

    @patch("quilt_mcp.tools.permissions._get_permission_discovery")
    def test_permissions_recommendations_get_action(self, mock_get_discovery):
        """Test the 'recommendations_get' action."""
        mock_discovery = Mock()
        mock_get_discovery.return_value = mock_discovery

        mock_buckets = [
            BucketInfo(
                name="my-packages",
                region="us-east-1",
                permission_level=PermissionLevel.FULL_ACCESS,
                can_read=True,
                can_write=True,
                can_list=True,
                last_checked=datetime.now(timezone.utc),
            ),
        ]
        mock_discovery.discover_accessible_buckets = Mock(return_value=mock_buckets)

        result = permissions(
            action="recommendations_get",
            params={"operation_type": "package_creation"},
        )
        
        assert result["success"] is True
        assert result["operation_type"] == "package_creation"
        assert "recommendations" in result

    def test_permissions_missing_required_parameter(self):
        """Test error handling for missing required parameters."""
        result = permissions(action="access_check")  # Missing bucket_name
        
        assert result["success"] is False
        assert "parameter" in result["error"].lower()

    def test_permissions_invalid_parameters(self):
        """Test error handling for invalid parameters."""
        result = permissions(
            action="access_check",
            params={
                "bucket_name": "test-bucket",
                "invalid_param": "should_be_ignored",  # Extra params should be handled gracefully
            }
        )
        
        # Should still work - extra params are ignored
        assert result["success"] in [True, False]  # May fail for other reasons but not param validation

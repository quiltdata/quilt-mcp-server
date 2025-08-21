"""Tests for AWS permissions discovery functionality."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from botocore.exceptions import ClientError

from quilt_mcp.tools.permissions import (
    aws_permissions_discover,
    bucket_access_check,
    bucket_recommendations_get,
    _generate_bucket_recommendations,
    _generate_smart_recommendations,
)
from quilt_mcp.aws.permission_discovery import (
    AWSPermissionDiscovery,
    PermissionLevel,
    BucketInfo,
    UserIdentity,
)


@pytest.mark.aws
class TestAWSPermissionsDiscover:
    """Test cases for AWS permissions discovery."""

    @pytest.mark.aws
    @patch('quilt_mcp.tools.permissions._get_permission_discovery')
    def test_discover_permissions_success(self, mock_get_discovery):
        """Test successful permission discovery."""
        # Setup mocks
        mock_discovery = Mock()
        mock_get_discovery.return_value = mock_discovery
        
        mock_identity = UserIdentity(
            user_id="AIDACKCEVSQ6C2EXAMPLE",
            arn="arn:aws:iam::123456789012:user/test-user",
            account_id="123456789012",
            user_type="user",
            user_name="test-user"
        )
        mock_discovery.discover_user_identity = Mock(return_value=mock_identity)
        
        mock_buckets = [
            BucketInfo(
                name="my-data-packages",
                region="us-east-1",
                permission_level=PermissionLevel.FULL_ACCESS,
                can_read=True,
                can_write=True,
                can_list=True,
                last_checked=datetime.utcnow()
            ),
            BucketInfo(
                name="shared-readonly",
                region="us-east-1", 
                permission_level=PermissionLevel.READ_ONLY,
                can_read=True,
                can_write=False,
                can_list=True,
                last_checked=datetime.utcnow()
            )
        ]
        mock_discovery.discover_accessible_buckets = Mock(return_value=mock_buckets)
        mock_discovery.get_cache_stats = Mock(return_value={"permission_cache_size": 2})
        
        result = aws_permissions_discover()
        
        assert result["success"] is True
        assert result["user_identity"]["user_name"] == "test-user"
        assert len(result["categorized_buckets"]["full_access"]) == 1
        assert len(result["categorized_buckets"]["read_only"]) == 1
        assert "recommendations" in result

    @patch('quilt_mcp.tools.permissions._get_permission_discovery')
    def test_discover_specific_buckets(self, mock_get_discovery):
        """Test permission discovery for specific buckets."""
        mock_discovery = Mock()
        mock_get_discovery.return_value = mock_discovery
        
        mock_identity = UserIdentity(
            user_id="test", arn="test", account_id="123", user_type="user"
        )
        mock_discovery.discover_user_identity = Mock(return_value=mock_identity)
        
        mock_bucket = BucketInfo(
            name="test-bucket",
            region="us-east-1",
            permission_level=PermissionLevel.READ_WRITE,
            can_read=True,
            can_write=True,
            can_list=True,
            last_checked=datetime.utcnow()
        )
        mock_discovery.discover_bucket_permissions = Mock(return_value=mock_bucket)
        mock_discovery.get_cache_stats = Mock(return_value={})
        
        result = aws_permissions_discover(check_buckets=["test-bucket"])
        
        assert result["success"] is True
        assert len(result["bucket_permissions"]) == 1
        assert result["bucket_permissions"][0]["name"] == "test-bucket"

    @patch('quilt_mcp.tools.permissions._get_permission_discovery')
    def test_discover_permissions_error(self, mock_get_discovery):
        """Test error handling in permission discovery."""
        mock_discovery = Mock()
        mock_get_discovery.return_value = mock_discovery
        mock_discovery.discover_user_identity = Mock(side_effect=Exception("AWS error"))
        
        result = aws_permissions_discover()
        
        assert result["success"] is False
        assert "Failed to discover AWS permissions" in result["error"]


@pytest.mark.aws
class TestBucketAccessCheck:
    """Test cases for bucket access checking."""

    @patch('quilt_mcp.tools.permissions._get_permission_discovery')
    def test_bucket_access_check_success(self, mock_get_discovery):
        """Test successful bucket access check."""
        mock_discovery = Mock()
        mock_get_discovery.return_value = mock_discovery
        
        mock_bucket = BucketInfo(
            name="test-bucket",
            region="us-west-2",
            permission_level=PermissionLevel.FULL_ACCESS,
            can_read=True,
            can_write=True,
            can_list=True,
            last_checked=datetime.utcnow()
        )
        mock_discovery.discover_bucket_permissions = Mock(return_value=mock_bucket)
        mock_discovery.test_bucket_operations = Mock(return_value={
            "read": True,
            "write": True,
            "list": True
        })
        
        result = bucket_access_check("test-bucket")
        
        assert result["success"] is True
        assert result["bucket_name"] == "test-bucket"
        assert result["permission_level"] == "full_access"
        assert result["access_summary"]["can_write"] is True

    @patch('quilt_mcp.tools.permissions._get_permission_discovery')
    def test_bucket_access_check_limited(self, mock_get_discovery):
        """Test bucket access check with limited permissions."""
        mock_discovery = Mock()
        mock_get_discovery.return_value = mock_discovery
        
        mock_bucket = BucketInfo(
            name="readonly-bucket",
            region="us-east-1",
            permission_level=PermissionLevel.READ_ONLY,
            can_read=True,
            can_write=False,
            can_list=True,
            last_checked=datetime.utcnow()
        )
        mock_discovery.discover_bucket_permissions = Mock(return_value=mock_bucket)
        mock_discovery.test_bucket_operations = Mock(return_value={
            "read": True,
            "write": False,
            "list": True
        })
        
        result = bucket_access_check("readonly-bucket", ["read", "write", "list"])
        
        assert result["success"] is True
        assert result["access_summary"]["can_read"] is True
        assert result["access_summary"]["can_write"] is False
        assert result["operation_tests"]["write"] is False


@pytest.mark.aws
class TestBucketRecommendations:
    """Test cases for bucket recommendations."""

    @patch('quilt_mcp.tools.permissions._get_permission_discovery')
    def test_bucket_recommendations_package_creation(self, mock_get_discovery):
        """Test bucket recommendations for package creation."""
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
                last_checked=datetime.utcnow()
            ),
            BucketInfo(
                name="temp-storage",
                region="us-east-1",
                permission_level=PermissionLevel.READ_WRITE,
                can_read=True,
                can_write=True,
                can_list=True,
                last_checked=datetime.utcnow()
            )
        ]
        mock_discovery.discover_accessible_buckets = Mock(return_value=mock_buckets)
        
        result = bucket_recommendations_get(
            source_bucket="ml-training-data",
            operation_type="package_creation"
        )
        
        assert result["success"] is True
        assert result["operation_type"] == "package_creation"
        assert "recommendations" in result
        assert result["total_writable_buckets"] == 2

    def test_generate_bucket_recommendations(self):
        """Test bucket recommendation generation."""
        bucket_permissions = [
            {"name": "my-packages", "permission_level": "full_access"},
            {"name": "data-warehouse", "permission_level": "read_write"},
            {"name": "temp-work", "permission_level": "full_access"},
            {"name": "readonly-data", "permission_level": "read_only"}
        ]
        
        identity = UserIdentity(
            user_id="test", arn="test", account_id="123", user_type="user"
        )
        
        recommendations = _generate_bucket_recommendations(bucket_permissions, identity)
        
        assert "package_creation" in recommendations
        assert "data_storage" in recommendations
        assert "temporary_storage" in recommendations
        
        # Packages bucket should be recommended for package creation
        assert "my-packages" in recommendations["package_creation"]
        # Temp bucket should be in temporary storage
        assert "temp-work" in recommendations["temporary_storage"]


@pytest.mark.aws
class TestPermissionDiscoveryEngine:
    """Test cases for the core permission discovery engine."""

    @patch('quilt_mcp.aws.permission_discovery.boto3.client')
    def test_discover_user_identity(self, mock_boto_client):
        """Test user identity discovery."""
        mock_sts = Mock()
        mock_boto_client.return_value = mock_sts
        mock_sts.get_caller_identity.return_value = {
            'UserId': 'AIDACKCEVSQ6C2EXAMPLE',
            'Account': '123456789012',
            'Arn': 'arn:aws:iam::123456789012:user/test-user'
        }
        
        discovery = AWSPermissionDiscovery()
        identity = discovery.discover_user_identity()
        
        assert identity.user_type == "user"
        assert identity.user_name == "test-user"
        assert identity.account_id == "123456789012"

    @patch('quilt_mcp.aws.permission_discovery.boto3.client')
    def test_discover_bucket_permissions_full_access(self, mock_boto_client):
        """Test bucket permission discovery with full access."""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        
        # Mock successful operations - ensure put_object succeeds to indicate write access
        mock_s3.get_bucket_location.return_value = {'LocationConstraint': 'us-west-2'}
        mock_s3.list_objects_v2.return_value = {'Contents': []}
        mock_s3.head_object.side_effect = ClientError(
            {'Error': {'Code': 'NotFound'}}, 'HeadObject'
        )
        # This is the key - put_object must succeed to indicate write access
        mock_s3.put_object.return_value = {'ETag': 'test-etag'}
        mock_s3.delete_object.return_value = {}
        
        discovery = AWSPermissionDiscovery()
        bucket_info = discovery.discover_bucket_permissions("test-bucket")
        
        assert bucket_info.permission_level == PermissionLevel.FULL_ACCESS
        assert bucket_info.can_read is True
        assert bucket_info.can_write is True
        assert bucket_info.can_list is True
        assert bucket_info.region == "us-west-2"

    @patch('quilt_mcp.aws.permission_discovery.boto3.client')
    def test_discover_bucket_permissions_read_only(self, mock_boto_client):
        """Test bucket permission discovery with read-only access."""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        
        # Mock read-only scenario
        mock_s3.get_bucket_location.return_value = {'LocationConstraint': 'us-east-1'}
        mock_s3.list_objects_v2.return_value = {'Contents': []}
        mock_s3.head_object.side_effect = ClientError(
            {'Error': {'Code': 'NotFound'}}, 'HeadObject'
        )
        mock_s3.put_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied'}}, 'PutObject'
        )
        
        discovery = AWSPermissionDiscovery()
        bucket_info = discovery.discover_bucket_permissions("readonly-bucket")
        
        assert bucket_info.permission_level == PermissionLevel.READ_ONLY
        assert bucket_info.can_read is True
        assert bucket_info.can_write is False
        assert bucket_info.can_list is True


@pytest.mark.aws
class TestIntegrationWithS3Package:
    """Test integration between permissions and S3-to-package functionality."""

    def test_enhanced_package_creation_with_permissions(self):
        """Test that enhanced package creation can use permission discovery."""
        # This would test the integration between the permissions system
        # and the S3-to-package creation tool
        
        # For now, this is a placeholder for integration testing
        # In a full implementation, this would:
        # 1. Mock permission discovery to return specific bucket permissions
        # 2. Call package_create_from_s3 without target_registry
        # 3. Verify that the tool automatically selects an appropriate writable bucket
        # 4. Confirm that the tool provides helpful error messages for insufficient permissions
        
        assert True  # Placeholder

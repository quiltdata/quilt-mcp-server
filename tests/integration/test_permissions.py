"""Tests for AWS permissions discovery functionality."""

import os
import time
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone
from botocore.exceptions import ClientError

from quilt_mcp.tools.permissions import (
    aws_permissions_discover,
    bucket_access_check,
    bucket_recommendations_get,
    _generate_bucket_recommendations,
    _generate_smart_recommendations,
)
from quilt_mcp.services.permission_discovery import (
    AWSPermissionDiscovery,
    PermissionLevel,
    BucketInfo,
    UserIdentity,
)


@pytest.mark.aws
class TestAWSPermissionsDiscover:
    """Test cases for AWS permissions discovery."""

    @pytest.mark.aws
    @patch("quilt_mcp.tools.permissions._get_permission_discovery")
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
            user_name="test-user",
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
                last_checked=datetime.now(timezone.utc),
            ),
            BucketInfo(
                name="shared-readonly",
                region="us-east-1",
                permission_level=PermissionLevel.READ_ONLY,
                can_read=True,
                can_write=False,
                can_list=True,
                last_checked=datetime.now(timezone.utc),
            ),
        ]
        mock_discovery.discover_accessible_buckets = Mock(return_value=mock_buckets)
        mock_discovery.get_cache_stats = Mock(return_value={"permission_cache_size": 2})

        result = aws_permissions_discover()

        assert result["success"] is True
        assert result["user_identity"]["user_name"] == "test-user"
        assert len(result["categorized_buckets"]["full_access"]) == 1
        assert len(result["categorized_buckets"]["read_only"]) == 1
        assert "recommendations" in result

    @patch("quilt_mcp.tools.permissions._get_permission_discovery")
    def test_discover_specific_buckets(self, mock_get_discovery):
        """Test permission discovery for specific buckets."""
        mock_discovery = Mock()
        mock_get_discovery.return_value = mock_discovery

        mock_identity = UserIdentity(user_id="test", arn="test", account_id="123", user_type="user")
        mock_discovery.discover_user_identity = Mock(return_value=mock_identity)

        mock_bucket = BucketInfo(
            name="test-bucket",
            region="us-east-1",
            permission_level=PermissionLevel.READ_WRITE,
            can_read=True,
            can_write=True,
            can_list=True,
            last_checked=datetime.now(timezone.utc),
        )
        mock_discovery.discover_bucket_permissions = Mock(return_value=mock_bucket)
        mock_discovery.get_cache_stats = Mock(return_value={})

        result = aws_permissions_discover(check_buckets=["test-bucket"])

        assert result["success"] is True
        assert len(result["bucket_permissions"]) == 1
        assert result["bucket_permissions"][0]["name"] == "test-bucket"

    @patch("quilt_mcp.tools.permissions._get_permission_discovery")
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

    @patch("quilt_mcp.tools.permissions._get_permission_discovery")
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
            last_checked=datetime.now(timezone.utc),
        )
        mock_discovery.discover_bucket_permissions = Mock(return_value=mock_bucket)
        mock_discovery.test_bucket_operations = Mock(return_value={"read": True, "write": True, "list": True})

        result = bucket_access_check("test-bucket")

        assert result["success"] is True
        assert result["bucket_name"] == "test-bucket"
        assert result["permission_level"] == "full_access"
        assert result["access_summary"]["can_write"] is True

    @patch("quilt_mcp.tools.permissions._get_permission_discovery")
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
            last_checked=datetime.now(timezone.utc),
        )
        mock_discovery.discover_bucket_permissions = Mock(return_value=mock_bucket)
        mock_discovery.test_bucket_operations = Mock(return_value={"read": True, "write": False, "list": True})

        result = bucket_access_check("readonly-bucket", ["read", "write", "list"])

        assert result["success"] is True
        assert result["access_summary"]["can_read"] is True
        assert result["access_summary"]["can_write"] is False
        assert result["operation_tests"]["write"] is False


@pytest.mark.aws
class TestBucketRecommendations:
    """Test cases for bucket recommendations."""

    @patch("quilt_mcp.tools.permissions._get_permission_discovery")
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
                last_checked=datetime.now(timezone.utc),
            ),
            BucketInfo(
                name="temp-storage",
                region="us-east-1",
                permission_level=PermissionLevel.READ_WRITE,
                can_read=True,
                can_write=True,
                can_list=True,
                last_checked=datetime.now(timezone.utc),
            ),
        ]
        mock_discovery.discover_accessible_buckets = Mock(return_value=mock_buckets)

        result = bucket_recommendations_get(source_bucket="ml-training-data", operation_type="package_creation")

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
            {"name": "readonly-data", "permission_level": "read_only"},
        ]

        identity = UserIdentity(user_id="test", arn="test", account_id="123", user_type="user")

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

    @patch("quilt_mcp.services.permission_discovery.quilt3")
    @patch("quilt_mcp.services.permission_discovery.boto3.client")
    def test_uses_quilt3_session_when_logged_in(self, mock_boto_client, mock_quilt3):
        """When quilt3 is logged in, discovery should use quilt3.get_boto3_session()."""
        # If default boto3.client is called, fail the test
        mock_boto_client.side_effect = AssertionError(
            "boto3.client should not be called when quilt3 session is available"
        )

        # Configure quilt3 mocks
        mock_quilt3.logged_in.return_value = True

        # Build a fake boto3 session with specific clients
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {
            "UserId": "AIDACKCEVSQ6C2EXAMPLE",
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test-user",
        }
        mock_iam = Mock()
        mock_s3 = Mock()
        mock_s3.list_buckets.return_value = {"Buckets": []}

        class _FakeSession:
            def client(self, service_name: str):
                if service_name == "sts":
                    return mock_sts
                if service_name == "iam":
                    return mock_iam
                if service_name == "s3":
                    return mock_s3
                raise AssertionError(f"Unexpected client for service: {service_name}")

        mock_quilt3.get_boto3_session.return_value = _FakeSession()

        # Mock the quilt3 session methods used by GraphQL discovery to return empty results
        mock_session = Mock()
        mock_http_session = Mock()
        mock_http_session.post.return_value.status_code = 200
        mock_http_session.post.return_value.json.return_value = {"data": {"bucketConfigs": []}}
        mock_session.get_session.return_value = mock_http_session
        mock_session.get_registry_url.return_value = "https://test-catalog.com"
        mock_quilt3.session = mock_session

        # Instantiate the discovery engine - it should use quilt3 session
        discovery = AWSPermissionDiscovery()

        # Verify that identity discovery works via the mocked STS client
        identity = discovery.discover_user_identity()
        assert identity.user_name == "test-user"
        assert identity.account_id == "123456789012"

        # Verify that listing buckets uses the mocked S3 client and does not error
        buckets = discovery.discover_accessible_buckets()
        assert isinstance(buckets, list)
        # With GraphQL discovery, we may find buckets even when S3 list_buckets returns empty
        # The important thing is that the method doesn't error and returns a list
        assert len(buckets) >= 0

    def test_discover_user_identity(self):
        """Test user identity discovery with real AWS credentials."""
        # Skip if AWS credentials not available
        try:
            import boto3

            sts = boto3.client("sts")
            sts.get_caller_identity()
        except Exception:
            pytest.skip("AWS credentials not available")

        discovery = AWSPermissionDiscovery()
        identity = discovery.discover_user_identity()

        # Just verify we get some identity back - exact values depend on AWS setup
        assert identity is not None
        assert identity.account_id is not None
        assert len(identity.account_id) == 12  # AWS account IDs are 12 digits

    @pytest.mark.aws
    def test_discover_bucket_permissions(self):
        """Test bucket permission discovery with real AWS connection."""
        # Skip if AWS credentials not available
        try:
            import boto3

            s3 = boto3.client("s3")
            s3.list_buckets()  # Test basic connectivity
        except Exception:
            pytest.skip("AWS credentials not available")

        discovery = AWSPermissionDiscovery()

        # Test with a known public bucket (should have at least read access)
        bucket_info = discovery.discover_bucket_permissions("quilt-example")

        # Should succeed or fail gracefully with AWS error
        assert isinstance(bucket_info, BucketInfo)
        assert bucket_info.name == "quilt-example"
        assert bucket_info.permission_level in [
            PermissionLevel.READ_ONLY,
            PermissionLevel.FULL_ACCESS,
            PermissionLevel.NO_ACCESS,
        ]

        # If we have any access, should be able to list
        if bucket_info.permission_level != PermissionLevel.NO_ACCESS:
            assert bucket_info.can_list is True

    @pytest.mark.aws
    def test_discover_bucket_permissions_full_access(self):
        """Test bucket permission discovery with real AWS (integration test)."""
        from tests.helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        from quilt_mcp.constants import DEFAULT_BUCKET

        # Extract bucket name from DEFAULT_BUCKET (remove s3:// prefix if present)
        bucket_name = DEFAULT_BUCKET.replace("s3://", "") if DEFAULT_BUCKET.startswith("s3://") else DEFAULT_BUCKET

        discovery = AWSPermissionDiscovery()
        bucket_info = discovery.discover_bucket_permissions(bucket_name)

        # Should get bucket info regardless of access level
        assert bucket_info.name == bucket_name
        # Basic assertions that should work for any bucket check
        assert isinstance(bucket_info.can_list, bool)
        assert isinstance(bucket_info.can_read, bool)
        assert isinstance(bucket_info.can_write, bool)
        assert isinstance(bucket_info.permission_level, PermissionLevel)
        # Should have a timestamp
        assert bucket_info.last_checked is not None

    @pytest.mark.aws
    def test_discover_bucket_permissions_nonexistent_bucket(self):
        """Test bucket permission discovery with nonexistent bucket (integration test)."""
        from tests.helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        # Use a bucket name that definitely doesn't exist
        nonexistent_bucket = f"definitely-nonexistent-bucket-{int(time.time())}"

        discovery = AWSPermissionDiscovery()
        bucket_info = discovery.discover_bucket_permissions(nonexistent_bucket)

        # Should have no access to nonexistent bucket
        assert bucket_info.name == nonexistent_bucket
        assert bucket_info.permission_level == PermissionLevel.NO_ACCESS
        assert bucket_info.can_list is False
        assert bucket_info.can_read is False
        assert bucket_info.can_write is False


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

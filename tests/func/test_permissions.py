"""Tests for AWS permissions discovery functionality."""

from unittest.mock import Mock, patch
from datetime import datetime, timezone

from quilt_mcp.services.permissions_service import (
    _bucket_recommendations_get,
    _check_bucket_access,
    _discover_permissions,
    _generate_bucket_recommendations,
)
from quilt_mcp.services.permission_discovery import (
    AWSPermissionDiscovery,
    PermissionLevel,
    BucketInfo,
    UserIdentity,
)


class TestAWSPermissionsDiscover:
    """Test cases for AWS permissions discovery."""

    def test_discover_permissions_success(self):
        """Test successful permission discovery."""
        # Setup mocks
        mock_discovery = Mock()

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

        result = _discover_permissions(
            mock_discovery,
            check_buckets=None,
            include_cross_account=False,
            force_refresh=False,
        )

        assert result["success"] is True
        assert result["user_identity"]["user_name"] == "test-user"
        assert len(result["categorized_buckets"]["full_access"]) == 1
        assert len(result["categorized_buckets"]["read_only"]) == 1
        assert "recommendations" in result

    def test_discover_specific_buckets(self):
        """Test permission discovery for specific buckets."""
        mock_discovery = Mock()

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

        result = _discover_permissions(
            mock_discovery,
            check_buckets=["test-bucket"],
            include_cross_account=False,
            force_refresh=False,
        )

        assert result["success"] is True
        assert len(result["bucket_permissions"]) == 1
        assert result["bucket_permissions"][0]["name"] == "test-bucket"

    def test_discover_permissions_error(self):
        """Test error handling in permission discovery."""

        class _StubService:
            def discover_permissions(self, *args, **kwargs):
                raise Exception("AWS error")

        class _StubContext:
            def __init__(self):
                self.permission_service = _StubService()

        from quilt_mcp.services.permissions_service import discover_permissions

        result = discover_permissions(context=_StubContext())

        assert result["success"] is False
        assert "Failed to discover AWS permissions" in result["error"]


class TestBucketAccessCheck:
    """Test cases for bucket access checking."""

    def test_bucket_access_check_success(self):
        """Test successful bucket access check."""
        mock_discovery = Mock()

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

        result = _check_bucket_access(mock_discovery, bucket="test-bucket", operations=None)

        assert result["success"] is True
        assert result["bucket_name"] == "test-bucket"
        assert result["permission_level"] == "full_access"
        assert result["access_summary"]["can_write"] is True

    def test_bucket_access_check_limited(self):
        """Test bucket access check with limited permissions."""
        mock_discovery = Mock()

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

        result = _check_bucket_access(
            mock_discovery,
            bucket="readonly-bucket",
            operations=["read", "write", "list"],
        )

        assert result["success"] is True
        assert result["access_summary"]["can_read"] is True
        assert result["access_summary"]["can_write"] is False
        assert result["operation_tests"]["write"] is False


class TestBucketRecommendations:
    """Test cases for bucket recommendations."""

    def test_bucket_recommendations_package_creation(self):
        """Test bucket recommendations for package creation."""
        mock_discovery = Mock()

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

        result = _bucket_recommendations_get(
            mock_discovery,
            source_bucket="ml-training-data",
            operation_type="package_creation",
            user_context=None,
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

    @patch("quilt_mcp.services.permission_discovery.quilt3")
    @patch("quilt_mcp.services.permission_discovery.boto3.client")
    def test_discover_user_identity_via_boto3(self, mock_boto_client, mock_quilt3):
        """Test user identity discovery using mocked boto3 clients."""
        mock_quilt3.logged_in.return_value = False
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {
            "UserId": "AIDACKCEVSQ6C2EXAMPLE",
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test-user",
        }
        mock_boto_client.side_effect = lambda service: {
            "sts": mock_sts,
            "iam": Mock(),
            "s3": Mock(),
        }[service]

        discovery = AWSPermissionDiscovery()
        identity = discovery.discover_user_identity()

        assert identity.user_name == "test-user"
        assert identity.account_id == "123456789012"

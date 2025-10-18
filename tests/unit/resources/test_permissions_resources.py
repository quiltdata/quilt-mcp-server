"""Unit tests for permissions resources."""

import pytest
from unittest.mock import AsyncMock, patch

from quilt_mcp.resources.permissions import (
    PermissionsDiscoverResource,
    BucketRecommendationsResource,
    BucketAccessResource,
)


class TestPermissionsDiscoverResource:
    """Test PermissionsDiscoverResource."""

    @pytest.fixture
    def resource(self):
        return PermissionsDiscoverResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful permissions discovery."""
        mock_result = {
            "status": "success",
            "permissions": {
                "s3": ["read", "write"],
                "athena": ["query"],
            },
        }

        with patch("quilt_mcp.resources.permissions.aws_permissions_discover", new_callable=AsyncMock) as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("permissions://discover")

            assert response.uri == "permissions://discover"
            assert response.content == mock_result


class TestBucketRecommendationsResource:
    """Test BucketRecommendationsResource."""

    @pytest.fixture
    def resource(self):
        return BucketRecommendationsResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful bucket recommendations retrieval."""
        mock_result = {
            "status": "success",
            "recommendations": [
                {"bucket": "my-bucket", "reason": "Full access"},
                {"bucket": "shared-bucket", "reason": "Read access"},
            ],
        }

        with patch("quilt_mcp.resources.permissions.bucket_recommendations_get", new_callable=AsyncMock) as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("permissions://recommendations")

            assert response.uri == "permissions://recommendations"
            assert response.content == mock_result


class TestBucketAccessResource:
    """Test BucketAccessResource (parameterized)."""

    @pytest.fixture
    def resource(self):
        return BucketAccessResource()

    @pytest.mark.anyio
    async def test_read_with_params(self, resource):
        """Test reading bucket access with parameters."""
        mock_result = {
            "status": "success",
            "access": {
                "read": True,
                "write": False,
            },
        }

        with patch("quilt_mcp.resources.permissions.bucket_access_check", new_callable=AsyncMock) as mock_tool:
            mock_tool.return_value = mock_result

            params = {"bucket": "my-bucket"}
            response = await resource.read("permissions://buckets/my-bucket/access", params)

            assert response.uri == "permissions://buckets/my-bucket/access"
            assert response.content == mock_result
            mock_tool.assert_called_once_with(bucket_name="my-bucket")

    @pytest.mark.anyio
    async def test_read_missing_param(self, resource):
        """Test reading without required parameters raises error."""
        with pytest.raises(ValueError, match="Bucket name required"):
            await resource.read("permissions://buckets/my-bucket/access", params=None)

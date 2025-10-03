"""Integration tests for permissions functionality against real Quilt Catalog."""

import os
import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools.permissions import permissions


@pytest.fixture
def test_token():
    """Get test token from environment."""
    token = os.getenv("QUILT_TEST_TOKEN")
    if not token:
        pytest.skip("QUILT_TEST_TOKEN not set - skipping integration tests")
    return token


@pytest.fixture
def catalog_url():
    """Get catalog URL from environment."""
    url = os.getenv("QUILT_CATALOG_URL")
    if not url:
        pytest.skip("QUILT_CATALOG_URL not set - skipping integration tests")
    return url


@pytest.mark.integration
class TestPermissionsIntegration:
    """Integration tests against real Quilt Catalog."""

    def test_discovery_mode(self):
        """Test discovery mode returns module info (no auth needed)."""
        result = permissions()

        assert result.get("module") == "permissions"
        assert "discover" in result.get("actions", [])

    def test_permissions_discover_real_catalog(self, test_token, catalog_url):
        """Test permissions discovery against real catalog."""
        with request_context(test_token, metadata={"source": "test"}):
            result = permissions(action="discover")

        assert result.get("success") is True
        assert "user_identity" in result
        assert result["user_identity"].get("email")

    def test_bucket_access_check_existing(self, test_token, catalog_url):
        """Test access check on an existing bucket."""
        with request_context(test_token, metadata={"source": "test"}):
            result = permissions(action="access_check", params={"bucket_name": "quilt-example"})

        assert result.get("success") is True
        assert result.get("bucket_name") == "quilt-example"

    def test_bucket_access_check_nonexistent(self, test_token, catalog_url):
        """Test access check on a nonexistent bucket."""
        with request_context(test_token, metadata={"source": "test"}):
            result = permissions(action="access_check", params={"bucket_name": "definitely-nonexistent-xyz"})

        assert result.get("success") is True
        assert result.get("accessible") is False

    def test_recommendations_get(self, test_token, catalog_url):
        """Test permission recommendations."""
        with request_context(test_token, metadata={"source": "test"}):
            result = permissions(action="recommendations_get")

        assert result.get("success") is True
        assert "recommendations" in result

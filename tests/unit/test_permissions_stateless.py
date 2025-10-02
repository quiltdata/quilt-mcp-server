"""Stateless unit tests for permissions tools using GraphQL catalog client.

These tests make real GraphQL calls to demo.quiltdata.com to validate
the permissions tool behavior end-to-end.

IMPORTANT: These tests require a valid JWT token for demo.quiltdata.com.
Set the QUILT_TEST_TOKEN environment variable before running:

    export QUILT_TEST_TOKEN="your-jwt-token"
    pytest tests/unit/test_permissions_stateless.py -v

Or run with the token inline:

    QUILT_TEST_TOKEN="your-token" pytest tests/unit/test_permissions_stateless.py -v

Tests will be skipped if QUILT_TEST_TOKEN is not set.
"""

import os
import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools.permissions import permissions


@pytest.fixture
def test_token():
    """Get test token from environment."""
    token = os.getenv("QUILT_TEST_TOKEN")
    if not token:
        pytest.skip("QUILT_TEST_TOKEN not set - skipping tests requiring authentication")
    return token


@pytest.fixture
def catalog_url(monkeypatch):
    """Set catalog URL to demo."""
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://demo.quiltdata.com")
    return "https://demo.quiltdata.com"


class TestPermissionsDiscovery:
    """Test permissions discovery via catalog GraphQL (real calls to demo)."""

    def test_discovery_mode_no_action(self):
        """Test discovery mode returns module info (no auth needed)."""
        result = permissions()
        
        assert result.get("module") == "permissions"
        assert "discover" in result.get("actions", [])
        assert "access_check" in result.get("actions", [])
        assert "recommendations_get" in result.get("actions", [])

    def test_permissions_discover_success(self, test_token, catalog_url):
        """Test successful permissions discovery with real GraphQL call."""
        with request_context(test_token, metadata={"path": "/permissions"}):
            result = permissions(action="discover")
        
        # Should succeed with valid token
        assert result.get("success") is True, f"Discovery failed: {result.get('error')}"
        
        # Should have user identity from real demo catalog
        assert "user_identity" in result
        assert result["user_identity"].get("email")
        assert "is_admin" in result["user_identity"]
        
        # Should have bucket permissions
        assert "bucket_permissions" in result
        assert isinstance(result["bucket_permissions"], list)
        assert result["total_buckets_checked"] > 0
        
        # Should have categorized buckets
        assert "categorized_buckets" in result
        assert "accessible" in result["categorized_buckets"]

    def test_permissions_discover_no_token(self, catalog_url):
        """Test discovery fails gracefully without token."""
        with request_context(None, metadata={"path": "/permissions"}):
            result = permissions(action="discover")
        
        assert result["success"] is False
        assert "token required" in result["error"].lower()

    def test_permissions_discover_invalid_token(self, catalog_url):
        """Test discovery handles invalid token."""
        invalid_token = "invalid.jwt.token"
        
        with request_context(invalid_token, metadata={"path": "/permissions"}):
            result = permissions(action="discover")
        
        # Should fail with authentication error
        assert result["success"] is False
        assert "401" in result["error"] or "unauthorized" in result["error"].lower()

    def test_permissions_discover_filtered_buckets(self, test_token, catalog_url):
        """Test discovery with specific bucket filter."""
        with request_context(test_token, metadata={"path": "/permissions"}):
            result = permissions(
                action="discover",
                params={"check_buckets": ["quilt-example-bucket", "nonexistent-test-bucket"]}
            )
        
        assert result["success"] is True
        assert result["total_buckets_checked"] == 2
        
        # Should have both buckets in results
        bucket_names = {b["name"] for b in result["bucket_permissions"]}
        assert "quilt-example-bucket" in bucket_names
        assert "nonexistent-test-bucket" in bucket_names
        
        # quilt-example-bucket may or may not be accessible, but nonexistent should not be
        buckets_by_name = {b["name"]: b for b in result["bucket_permissions"]}
        assert buckets_by_name["nonexistent-test-bucket"]["accessible"] is False


class TestBucketAccessCheck:
    """Test individual bucket access checking (real GraphQL calls)."""

    def test_bucket_access_check_existing_bucket(self, test_token, catalog_url):
        """Test access check on an existing bucket."""
        with request_context(test_token, metadata={"path": "/permissions"}):
            result = permissions(
                action="access_check",
                params={"bucket_name": "quilt-example-bucket"}
            )
        
        assert result["success"] is True
        assert result["bucket_name"] == "quilt-example-bucket"
        assert "accessible" in result
        assert "permission_level" in result
        # Permission level will vary based on actual access

    def test_bucket_access_check_nonexistent(self, test_token, catalog_url):
        """Test access check for nonexistent bucket."""
        with request_context(test_token, metadata={"path": "/permissions"}):
            result = permissions(
                action="access_check",
                params={"bucket_name": "definitely-does-not-exist-xyz-123"}
            )
        
        assert result["success"] is True
        assert result["bucket_name"] == "definitely-does-not-exist-xyz-123"
        assert result["accessible"] is False
        assert result["permission_level"] == "no_access"

    def test_bucket_access_check_no_token(self, catalog_url):
        """Test access check fails without token."""
        with request_context(None, metadata={"path": "/permissions"}):
            result = permissions(
                action="access_check",
                params={"bucket_name": "test-bucket"}
            )
        
        assert result["success"] is False
        assert "token required" in result["error"].lower()

    def test_bucket_access_check_missing_bucket_name(self, test_token, catalog_url):
        """Test access check fails without bucket name."""
        with request_context(test_token, metadata={"path": "/permissions"}):
            result = permissions(
                action="access_check",
                params={}
            )
        
        assert result["success"] is False
        assert "bucket name" in result["error"].lower()


class TestPermissionRecommendations:
    """Test permission recommendations generation (real GraphQL calls)."""

    def test_recommendations_get(self, test_token, catalog_url):
        """Test recommendations with real user data."""
        with request_context(test_token, metadata={"path": "/permissions"}):
            result = permissions(action="recommendations_get")
        
        assert result["success"] is True
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)
        
        # Should have at least some recommendations
        if result["recommendations"]:
            rec = result["recommendations"][0]
            assert "priority" in rec
            assert "message" in rec
            assert rec["priority"] in ["info", "warning", "error"]

    def test_recommendations_get_no_token(self, catalog_url):
        """Test recommendations fails without token."""
        with request_context(None, metadata={"path": "/permissions"}):
            result = permissions(action="recommendations_get")
        
        assert result["success"] is False
        assert "token required" in result["error"].lower()


class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_invalid_action(self, test_token, catalog_url):
        """Test invalid action returns error."""
        with request_context(test_token, metadata={"path": "/permissions"}):
            result = permissions(action="totally_invalid_action")
        
        assert result["success"] is False
        assert "unknown" in result["error"].lower()

    def test_catalog_url_not_configured(self, monkeypatch):
        """Test error when catalog URL not configured."""
        token_value = "test.jwt.token"
        
        # Mock resolve_catalog_url to return None
        monkeypatch.setattr(
            "quilt_mcp.tools.permissions.resolve_catalog_url",
            lambda: None
        )
        
        with request_context(token_value, metadata={"path": "/permissions"}):
            result = permissions(action="discover")
        
        assert result["success"] is False
        assert "catalog url" in result["error"].lower()

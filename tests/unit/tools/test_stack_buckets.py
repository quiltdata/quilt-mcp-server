"""Unit tests for stack_buckets.py tool using backend abstraction.

This test suite validates that stack_buckets.py uses the backend abstraction
instead of directly instantiating QuiltService.
"""

from unittest.mock import Mock, patch, MagicMock
import pytest

from quilt_mcp.tools.stack_buckets import (
    get_stack_buckets,
    _get_stack_buckets_via_graphql,
    _get_stack_buckets_via_permissions,
    build_stack_search_indices,
    stack_info,
)


class TestGetStackBucketsBackendUsage:
    """Test that get_stack_buckets uses backend abstraction."""

    def test_get_stack_buckets_via_graphql_uses_get_backend(self):
        """Test that _get_stack_buckets_via_graphql calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()

        # Mock session support and session
        mock_backend.has_session_support.return_value = True
        mock_session = Mock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {
            "data": {
                "bucketConfigs": [
                    {"name": "bucket1", "title": "Bucket 1"},
                    {"name": "bucket2", "title": "Bucket 2"},
                ]
            }
        }
        mock_backend.get_session.return_value = mock_session
        mock_backend.get_registry_url.return_value = "https://example.com"

        with patch("quilt_mcp.tools.stack_buckets.get_backend", return_value=mock_backend):
            result = _get_stack_buckets_via_graphql()

        # Verify get_backend was called
        mock_backend.has_session_support.assert_called_once()
        assert result == {"bucket1", "bucket2"}

    def test_get_stack_buckets_via_graphql_handles_no_session_support(self):
        """Test that _get_stack_buckets_via_graphql handles no session support."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = False

        with patch("quilt_mcp.tools.stack_buckets.get_backend", return_value=mock_backend):
            result = _get_stack_buckets_via_graphql()

        assert result == set()

    def test_get_stack_buckets_via_graphql_handles_graphql_errors(self):
        """Test that _get_stack_buckets_via_graphql handles GraphQL errors."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_session = Mock()
        mock_session.post.return_value.status_code = 500
        mock_session.post.return_value.text = "Internal Server Error"
        mock_backend.get_session.return_value = mock_session
        mock_backend.get_registry_url.return_value = "https://example.com"

        with patch("quilt_mcp.tools.stack_buckets.get_backend", return_value=mock_backend):
            result = _get_stack_buckets_via_graphql()

        assert result == set()

    def test_get_stack_buckets_falls_back_to_permissions(self):
        """Test that get_stack_buckets falls back to permissions when GraphQL fails."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = False

        # Mock permission discovery
        with patch("quilt_mcp.tools.stack_buckets.get_backend", return_value=mock_backend):
            with patch("quilt_mcp.tools.stack_buckets._get_stack_buckets_via_graphql", return_value=set()):
                with patch("quilt_mcp.tools.stack_buckets._get_stack_buckets_via_permissions") as mock_perms:
                    mock_perms.return_value = {"bucket-a", "bucket-b"}

                    result = get_stack_buckets()

        # Set order is non-deterministic, so check membership instead of exact order
        assert set(result) == {"bucket-a", "bucket-b"}
        assert len(result) == 2

    def test_get_stack_buckets_falls_back_to_default_registry(self):
        """Test that get_stack_buckets falls back to DEFAULT_REGISTRY when all discovery fails."""
        with patch("quilt_mcp.tools.stack_buckets._get_stack_buckets_via_graphql", return_value=set()):
            with patch("quilt_mcp.tools.stack_buckets._get_stack_buckets_via_permissions", return_value=set()):
                # Patch at the constants module level, not the stack_buckets module
                with patch("quilt_mcp.constants.DEFAULT_REGISTRY", "s3://default-bucket"):
                    result = get_stack_buckets()

        assert result == ["default-bucket"]


class TestStackInfoBackendUsage:
    """Test that stack_info uses backend abstraction."""

    def test_stack_info_calls_get_stack_buckets(self):
        """Test that stack_info calls get_stack_buckets which uses backend."""
        with patch("quilt_mcp.tools.stack_buckets.get_stack_buckets", return_value=["bucket1", "bucket2"]):
            with patch(
                "quilt_mcp.tools.stack_buckets._get_stack_buckets_via_graphql", return_value={"bucket1", "bucket2"}
            ):
                with patch("quilt_mcp.tools.stack_buckets._get_stack_buckets_via_permissions", return_value=set()):
                    result = stack_info()

        assert result["success"] is True
        assert result["bucket_count"] == 2
        assert result["discovery_method"] == "graphql"

    def test_stack_info_handles_no_buckets(self):
        """Test that stack_info handles case with no buckets found."""
        with patch("quilt_mcp.tools.stack_buckets.get_stack_buckets", return_value=[]):
            with patch("quilt_mcp.tools.stack_buckets._get_stack_buckets_via_graphql", return_value=set()):
                with patch("quilt_mcp.tools.stack_buckets._get_stack_buckets_via_permissions", return_value=set()):
                    result = stack_info()

        assert result["success"] is True
        assert result["bucket_count"] == 0


class TestBuildStackSearchIndices:
    """Test build_stack_search_indices functionality."""

    def test_build_stack_search_indices_with_buckets(self):
        """Test that build_stack_search_indices creates correct index pattern."""
        buckets = ["bucket1", "bucket2", "bucket3"]
        result = build_stack_search_indices(buckets)

        expected = "bucket1,bucket1_packages,bucket2,bucket2_packages,bucket3,bucket3_packages"
        assert result == expected

    def test_build_stack_search_indices_with_no_buckets(self):
        """Test that build_stack_search_indices handles empty bucket list."""
        result = build_stack_search_indices([])

        assert result == ""

    def test_build_stack_search_indices_auto_discovers_buckets(self):
        """Test that build_stack_search_indices auto-discovers when buckets=None."""
        with patch("quilt_mcp.tools.stack_buckets.get_stack_buckets", return_value=["bucket-a"]):
            result = build_stack_search_indices(None)

        assert result == "bucket-a,bucket-a_packages"


class TestStackBucketsBackendIntegration:
    """Test integration between stack_buckets.py and backend abstraction."""

    def test_no_direct_quilt_service_instantiation(self):
        """Test that QuiltService is not directly instantiated in stack_buckets module."""
        import quilt_mcp.tools.stack_buckets as stack_module

        # Read source code
        source_code = open(stack_module.__file__).read()

        # Check that direct instantiation pattern is not present
        assert "QuiltService()" not in source_code, "stack_buckets.py should not directly instantiate QuiltService"

        # Verify get_backend is imported
        assert "from ..backends.factory import get_backend" in source_code, (
            "stack_buckets.py should import get_backend"
        )

    def test_backend_error_propagates_in_graphql_discovery(self):
        """Test that errors from backend propagate correctly in GraphQL discovery."""
        mock_backend = Mock()
        mock_backend.has_session_support.side_effect = Exception("Backend error")

        with patch("quilt_mcp.tools.stack_buckets.get_backend", return_value=mock_backend):
            result = _get_stack_buckets_via_graphql()

        # Error should be caught and return empty set
        assert result == set()

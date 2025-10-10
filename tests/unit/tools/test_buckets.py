"""Unit tests for buckets.py tool using backend abstraction.

This test suite validates that buckets.py uses the backend abstraction
instead of directly instantiating QuiltService.
"""

from unittest.mock import Mock, patch
import pytest

from quilt_mcp.tools.buckets import bucket_objects_search, bucket_objects_search_graphql


class TestBucketObjectsSearchBackendUsage:
    """Test that bucket_objects_search uses backend abstraction."""

    def test_bucket_objects_search_uses_get_backend(self):
        """Test that bucket_objects_search calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()
        mock_bucket = Mock()
        mock_bucket.search.return_value = [
            {"key": "test.csv", "size": 1024},
            {"key": "data.json", "size": 2048}
        ]
        mock_backend.create_bucket.return_value = mock_bucket

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend):
            result = bucket_objects_search(bucket="s3://test-bucket", query="test", limit=10)

        # Verify get_backend was called
        mock_backend.create_bucket.assert_called_once_with("s3://test-bucket")
        mock_bucket.search.assert_called_once_with("test", limit=10)
        assert "results" in result
        assert len(result["results"]) == 2

    def test_bucket_objects_search_normalizes_bucket(self):
        """Test that bucket_objects_search normalizes bucket before passing to backend."""
        mock_backend = Mock()
        mock_bucket = Mock()
        mock_bucket.search.return_value = []
        mock_backend.create_bucket.return_value = mock_bucket

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend):
            bucket_objects_search(bucket="test-bucket", query="test")  # No s3:// prefix

        # Should normalize to s3:// format
        mock_backend.create_bucket.assert_called_once_with("s3://test-bucket")

    def test_bucket_objects_search_handles_dict_query(self):
        """Test that bucket_objects_search handles dictionary queries."""
        mock_backend = Mock()
        mock_bucket = Mock()
        mock_bucket.search.return_value = []
        mock_backend.create_bucket.return_value = mock_bucket

        dsl_query = {"query": {"match": {"key": "test"}}}

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend):
            result = bucket_objects_search(bucket="s3://test-bucket", query=dsl_query, limit=5)

        mock_bucket.search.assert_called_once_with(dsl_query, limit=5)
        assert "results" in result

    def test_bucket_objects_search_error_propagates(self):
        """Test that errors from backend propagate correctly."""
        mock_backend = Mock()
        mock_backend.create_bucket.side_effect = Exception("Backend error")

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend):
            result = bucket_objects_search(bucket="s3://test-bucket", query="test")

        assert "error" in result
        assert "Backend error" in result["error"]
        assert "results" in result  # Always include results array
        assert result["results"] == []


class TestBucketObjectsSearchGraphQLBackendUsage:
    """Test that bucket_objects_search_graphql uses backend abstraction."""

    def test_bucket_objects_search_graphql_uses_get_backend(self):
        """Test that bucket_objects_search_graphql calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "objects": {
                    "edges": [
                        {
                            "node": {
                                "key": "test.csv",
                                "size": 1024,
                                "updated": "2024-01-01",
                                "contentType": "text/csv",
                                "extension": "csv",
                                "package": None,
                            }
                        }
                    ],
                    "pageInfo": {"endCursor": "cursor1", "hasNextPage": False},
                }
            }
        }
        mock_session.post.return_value = mock_response
        mock_backend.get_session.return_value = mock_session
        mock_backend.get_registry_url.return_value = "https://test.example.com"

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend):
            result = bucket_objects_search_graphql(bucket="s3://test-bucket", first=100)

        # Verify get_backend was called
        mock_backend.has_session_support.assert_called_once()
        mock_backend.get_session.assert_called_once()
        mock_backend.get_registry_url.assert_called_once()
        assert result["success"] is True
        assert len(result["objects"]) == 1

    def test_bucket_objects_search_graphql_normalizes_bucket(self):
        """Test that bucket_objects_search_graphql normalizes bucket."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"objects": {"edges": [], "pageInfo": {"hasNextPage": False}}}
        }
        mock_session.post.return_value = mock_response
        mock_backend.get_session.return_value = mock_session
        mock_backend.get_registry_url.return_value = "https://test.example.com"

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend):
            result = bucket_objects_search_graphql(bucket="test-bucket")  # No s3:// prefix

        # Verify bucket was normalized in result
        assert result["bucket"] == "test-bucket"
        assert result["success"] is True

    def test_bucket_objects_search_graphql_no_session_support(self):
        """Test bucket_objects_search_graphql when session support unavailable."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = False

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend):
            result = bucket_objects_search_graphql(bucket="s3://test-bucket")

        assert result["success"] is False
        assert "session not available" in result["error"]
        assert result["objects"] == []

    def test_bucket_objects_search_graphql_no_registry_url(self):
        """Test bucket_objects_search_graphql when registry URL not configured."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_backend.get_session.return_value = Mock()
        mock_backend.get_registry_url.return_value = None

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend):
            result = bucket_objects_search_graphql(bucket="s3://test-bucket")

        assert result["success"] is False
        assert "Registry URL not configured" in result["error"]
        assert result["objects"] == []

    def test_bucket_objects_search_graphql_handles_filters(self):
        """Test that bucket_objects_search_graphql passes filters correctly."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"objects": {"edges": [], "pageInfo": {"hasNextPage": False}}}
        }
        mock_session.post.return_value = mock_response
        mock_backend.get_session.return_value = mock_session
        mock_backend.get_registry_url.return_value = "https://test.example.com"

        object_filter = {"extension": "csv", "size_gt": 1000}

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend):
            result = bucket_objects_search_graphql(
                bucket="s3://test-bucket", object_filter=object_filter, first=50, after="cursor1"
            )

        # Verify GraphQL request included filter
        assert result["success"] is True
        assert result["filter"] == object_filter

    def test_bucket_objects_search_graphql_error_propagates(self):
        """Test that errors from backend propagate correctly."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_backend.get_session.side_effect = Exception("Session error")

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend):
            result = bucket_objects_search_graphql(bucket="s3://test-bucket")

        assert result["success"] is False
        assert "Session error" in result["error"]
        assert result["objects"] == []


class TestBucketsBackendIntegration:
    """Test integration between buckets.py and backend abstraction."""

    def test_no_direct_quilt_service_instantiation(self):
        """Test that QuiltService is not directly instantiated in search functions."""
        import quilt_mcp.tools.buckets as buckets_module

        # Note: buckets.py still imports QuiltService but should use it via get_backend
        # We verify that get_backend is called, not that QuiltService isn't imported
        mock_backend = Mock()
        mock_bucket = Mock()
        mock_bucket.search.return_value = []
        mock_backend.create_bucket.return_value = mock_bucket

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend) as mock_get_backend:
            bucket_objects_search(bucket="s3://test-bucket", query="test")

            # get_backend SHOULD be called
            mock_get_backend.assert_called_once()

    def test_both_search_functions_use_backend(self):
        """Test that both search functions use backend abstraction."""
        mock_backend = Mock()

        # Setup for bucket_objects_search
        mock_bucket = Mock()
        mock_bucket.search.return_value = []
        mock_backend.create_bucket.return_value = mock_bucket

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend) as mock_get_backend:
            # Test bucket_objects_search
            bucket_objects_search(bucket="s3://test-bucket", query="test")
            assert mock_get_backend.call_count >= 1

        # Setup for bucket_objects_search_graphql
        mock_backend.has_session_support.return_value = False

        with patch("quilt_mcp.tools.buckets.get_backend", return_value=mock_backend) as mock_get_backend:
            # Test bucket_objects_search_graphql
            bucket_objects_search_graphql(bucket="s3://test-bucket")
            assert mock_get_backend.call_count >= 1

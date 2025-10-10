"""Unit tests for graphql.py tool using backend abstraction.

This test suite validates that graphql.py uses the backend abstraction
instead of directly instantiating QuiltService.
"""

from unittest.mock import Mock, patch
import pytest

from quilt_mcp.tools.graphql import (
    catalog_graphql_query,
    objects_search_graphql,
    _get_graphql_endpoint,
)


class TestGetGraphQLEndpointBackendUsage:
    """Test that _get_graphql_endpoint uses backend abstraction."""

    def test_get_graphql_endpoint_uses_get_backend(self):
        """Test that _get_graphql_endpoint calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_session = Mock()
        mock_backend.get_session.return_value = mock_session
        mock_backend.get_registry_url.return_value = "https://test.example.com"

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            session, url = _get_graphql_endpoint()

        # Verify get_backend was called
        mock_backend.has_session_support.assert_called_once()
        mock_backend.get_session.assert_called_once()
        mock_backend.get_registry_url.assert_called_once()
        assert session == mock_session
        assert url == "https://test.example.com/graphql"

    def test_get_graphql_endpoint_no_session_support(self):
        """Test _get_graphql_endpoint when session support unavailable."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = False

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            session, url = _get_graphql_endpoint()

        assert session is None
        assert url is None

    def test_get_graphql_endpoint_no_registry_url(self):
        """Test _get_graphql_endpoint when registry URL not configured."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_backend.get_session.return_value = Mock()
        mock_backend.get_registry_url.return_value = None

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            session, url = _get_graphql_endpoint()

        assert session is None
        assert url is None

    def test_get_graphql_endpoint_error_returns_none(self):
        """Test that errors in _get_graphql_endpoint return (None, None)."""
        mock_backend = Mock()
        mock_backend.has_session_support.side_effect = Exception("Backend error")

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            session, url = _get_graphql_endpoint()

        assert session is None
        assert url is None


class TestCatalogGraphQLQueryBackendUsage:
    """Test that catalog_graphql_query uses backend abstraction."""

    def test_catalog_graphql_query_uses_get_backend(self):
        """Test that catalog_graphql_query calls get_backend() via _get_graphql_endpoint."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"test": "value"}}
        mock_session.post.return_value = mock_response
        mock_backend.get_session.return_value = mock_session
        mock_backend.get_registry_url.return_value = "https://test.example.com"

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            result = catalog_graphql_query("query { test }")

        # Verify get_backend was called
        mock_backend.has_session_support.assert_called_once()
        assert result["success"] is True
        assert result["data"] == {"test": "value"}

    def test_catalog_graphql_query_handles_no_endpoint(self):
        """Test catalog_graphql_query when endpoint unavailable."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = False

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            result = catalog_graphql_query("query { test }")

        assert result["success"] is False
        assert "unavailable" in result["error"]

    def test_catalog_graphql_query_handles_variables(self):
        """Test that catalog_graphql_query passes variables correctly."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"result": "ok"}}
        mock_session.post.return_value = mock_response
        mock_backend.get_session.return_value = mock_session
        mock_backend.get_registry_url.return_value = "https://test.example.com"

        variables = {"var1": "value1"}

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            result = catalog_graphql_query("query($var1: String) { test }", variables)

        # Verify variables were passed
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[1]["json"]["variables"] == variables
        assert result["success"] is True

    def test_catalog_graphql_query_error_propagates(self):
        """Test that errors from backend propagate correctly."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_session = Mock()
        mock_session.post.side_effect = Exception("Network error")
        mock_backend.get_session.return_value = mock_session
        mock_backend.get_registry_url.return_value = "https://test.example.com"

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            result = catalog_graphql_query("query { test }")

        assert result["success"] is False
        assert "Network error" in result["error"]


class TestObjectsSearchGraphQLBackendUsage:
    """Test that objects_search_graphql uses backend abstraction."""

    def test_objects_search_graphql_uses_get_backend(self):
        """Test that objects_search_graphql calls get_backend() via catalog_graphql_query."""
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

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            result = objects_search_graphql(bucket="s3://test-bucket", first=100)

        # Verify get_backend was called
        mock_backend.has_session_support.assert_called_once()
        assert result["success"] is True
        assert len(result["objects"]) == 1

    def test_objects_search_graphql_normalizes_bucket(self):
        """Test that objects_search_graphql normalizes bucket."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"objects": {"edges": [], "pageInfo": {"hasNextPage": False}}}}
        mock_session.post.return_value = mock_response
        mock_backend.get_session.return_value = mock_session
        mock_backend.get_registry_url.return_value = "https://test.example.com"

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            result = objects_search_graphql(bucket="s3://test-bucket/prefix")

        # Verify bucket was normalized
        assert result["bucket"] == "test-bucket"
        assert result["success"] is True

    def test_objects_search_graphql_handles_filters(self):
        """Test that objects_search_graphql passes filters correctly."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = True
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"objects": {"edges": [], "pageInfo": {"hasNextPage": False}}}}
        mock_session.post.return_value = mock_response
        mock_backend.get_session.return_value = mock_session
        mock_backend.get_registry_url.return_value = "https://test.example.com"

        object_filter = {"extension": "csv", "size_gt": 1000}

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            result = objects_search_graphql(
                bucket="test-bucket", object_filter=object_filter, first=50, after="cursor1"
            )

        # Verify filter was included
        assert result["success"] is True
        assert result["filter"] == object_filter

    def test_objects_search_graphql_error_propagates(self):
        """Test that errors from backend propagate correctly."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = False

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend):
            result = objects_search_graphql(bucket="s3://test-bucket")

        assert result["success"] is False
        assert "objects" in result
        assert result["objects"] == []


class TestGraphQLBackendIntegration:
    """Test integration between graphql.py and backend abstraction."""

    def test_no_direct_quilt_service_instantiation(self):
        """Test that QuiltService is not directly instantiated in public functions."""
        import quilt_mcp.tools.graphql as graphql_module

        # Note: graphql.py still imports QuiltService but should use it via get_backend
        # We verify that get_backend is called, not that QuiltService isn't imported
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = False

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend) as mock_get_backend:
            _get_graphql_endpoint()

            # get_backend SHOULD be called
            mock_get_backend.assert_called_once()

    def test_all_functions_use_backend(self):
        """Test that all GraphQL functions use backend abstraction."""
        mock_backend = Mock()
        mock_backend.has_session_support.return_value = False

        with patch("quilt_mcp.tools.graphql.get_backend", return_value=mock_backend) as mock_get_backend:
            # Test catalog_graphql_query
            catalog_graphql_query("query { test }")
            assert mock_get_backend.call_count >= 1

            # Test objects_search_graphql
            objects_search_graphql(bucket="s3://test-bucket")
            assert mock_get_backend.call_count >= 2

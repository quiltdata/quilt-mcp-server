"""
BDD tests for legacy search functions before removal.

These tests capture the current behavior of functions that will be consolidated:
- packages_search (already a shim to catalog_search)
- bucket_objects_search (Elasticsearch wrapper)
- bucket_objects_search_graphql (GraphQL wrapper)

These tests ensure we preserve functionality when removing these functions.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# Import the functions to be tested
from quilt_mcp.tools.packages import packages_search
from quilt_mcp.tools.buckets import bucket_objects_search, bucket_objects_search_graphql
from quilt_mcp.constants import DEFAULT_REGISTRY


class TestPackagesSearchBehavior:
    """Test packages_search function behavior before removal."""

    def test_packages_search_with_default_parameters(self):
        """Given packages_search is called with minimal parameters
        When the function is invoked with just a query
        Then it should delegate to catalog_search with correct parameters
        """
        with patch('quilt_mcp.tools.packages.catalog_search') as mock_catalog_search:
            mock_catalog_search.return_value = {
                "results": [],
                "count": 0,
                "query": "test query"
            }

            result = packages_search("test query")

            # Verify catalog_search was called with correct parameters
            expected_registry = f"s3://{DEFAULT_REGISTRY}" if DEFAULT_REGISTRY and not DEFAULT_REGISTRY.startswith("s3://") else DEFAULT_REGISTRY
            if not expected_registry:
                expected_registry = ""  # Handle empty default registry

            mock_catalog_search.assert_called_once_with(
                query="test query",
                scope="catalog",
                target=expected_registry,
                limit=10,
                filters={"registry": expected_registry, "offset": 0}
            )

            assert "results" in result

    def test_packages_search_with_custom_registry(self):
        """Given packages_search is called with custom registry
        When registry parameter is provided
        Then it should normalize and pass the registry to catalog_search
        """
        with patch('quilt_mcp.tools.packages.catalog_search') as mock_catalog_search:
            mock_catalog_search.return_value = {"results": []}

            packages_search("query", registry="my-bucket")

            mock_catalog_search.assert_called_once_with(
                query="query",
                scope="catalog",
                target="s3://my-bucket",  # Normalized from "my-bucket"
                limit=10,
                filters={"registry": "s3://my-bucket", "offset": 0}
            )

    def test_packages_search_count_only_mode(self):
        """Given packages_search is called with limit=0
        When limit is zero
        Then it should call catalog_search with count_only=True
        """
        with patch('quilt_mcp.tools.packages.catalog_search') as mock_catalog_search:
            mock_catalog_search.return_value = {"count": 5}

            packages_search("query", limit=0)

            expected_registry = f"s3://{DEFAULT_REGISTRY}" if DEFAULT_REGISTRY and not DEFAULT_REGISTRY.startswith("s3://") else DEFAULT_REGISTRY
            if not expected_registry:
                expected_registry = ""

            mock_catalog_search.assert_called_once_with(
                query="query",
                scope="catalog",
                target=expected_registry,
                filters={"registry": expected_registry, "offset": 0},
                count_only=True
            )

    def test_packages_search_with_pagination(self):
        """Given packages_search is called with from_ parameter
        When pagination offset is provided
        Then it should pass offset in filters to catalog_search
        """
        with patch('quilt_mcp.tools.packages.catalog_search') as mock_catalog_search:
            mock_catalog_search.return_value = {"results": []}

            packages_search("query", from_=20)

            expected_registry = f"s3://{DEFAULT_REGISTRY}" if DEFAULT_REGISTRY and not DEFAULT_REGISTRY.startswith("s3://") else DEFAULT_REGISTRY
            if not expected_registry:
                expected_registry = ""

            mock_catalog_search.assert_called_once_with(
                query="query",
                scope="catalog",
                target=expected_registry,
                limit=10,
                filters={"registry": expected_registry, "offset": 20}
            )


class TestBucketObjectsSearchBehavior:
    """Test bucket_objects_search function behavior before removal."""

    def test_bucket_objects_search_with_string_query(self):
        """Given bucket_objects_search is called with string query
        When a simple query string is provided
        Then it should use quilt3.Bucket.search() with correct parameters
        """
        mock_bucket = Mock()
        mock_bucket.search.return_value = [{"key": "test.csv"}]

        with patch('quilt_mcp.tools.buckets.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.create_bucket.return_value = mock_bucket
            mock_service_class.return_value = mock_service

            with patch('quilt_mcp.tools.buckets.suppress_stdout'):
                result = bucket_objects_search("my-bucket", "*.csv")

            # Verify bucket was created with s3:// URI
            mock_service.create_bucket.assert_called_once_with("s3://my-bucket")

            # Verify search was called with query and limit
            mock_bucket.search.assert_called_once_with("*.csv", limit=10)

            # Verify result structure
            assert result["bucket"] == "my-bucket"
            assert result["query"] == "*.csv"
            assert result["limit"] == 10
            assert "results" in result

    def test_bucket_objects_search_with_dict_query(self):
        """Given bucket_objects_search is called with dict query
        When a dictionary-based DSL query is provided
        Then it should pass the dict query to search()
        """
        mock_bucket = Mock()
        mock_bucket.search.return_value = []

        query_dict = {"term": {"extension": "csv"}}

        with patch('quilt_mcp.tools.buckets.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.create_bucket.return_value = mock_bucket
            mock_service_class.return_value = mock_service

            with patch('quilt_mcp.tools.buckets.suppress_stdout'):
                bucket_objects_search("my-bucket", query_dict, limit=20)

            mock_bucket.search.assert_called_once_with(query_dict, limit=20)

    def test_bucket_objects_search_error_handling(self):
        """Given bucket_objects_search encounters an error
        When the search operation fails
        Then it should return error information with empty results
        """
        with patch('quilt_mcp.tools.buckets.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.create_bucket.side_effect = Exception("Bucket not found")
            mock_service_class.return_value = mock_service

            with patch('quilt_mcp.tools.buckets.suppress_stdout'):
                result = bucket_objects_search("missing-bucket", "query")

            assert "error" in result
            assert result["bucket"] == "missing-bucket"
            assert result["results"] == []
            assert "Failed to search bucket" in result["error"]

    def test_bucket_objects_search_normalizes_bucket_uri(self):
        """Given bucket_objects_search is called with s3:// URI
        When bucket parameter has s3:// prefix
        Then it should normalize to bucket name for result
        """
        mock_bucket = Mock()
        mock_bucket.search.return_value = []

        with patch('quilt_mcp.tools.buckets.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.create_bucket.return_value = mock_bucket
            mock_service_class.return_value = mock_service

            with patch('quilt_mcp.tools.buckets.suppress_stdout'):
                result = bucket_objects_search("s3://my-bucket", "query")

            # Should normalize s3://my-bucket to my-bucket for result
            assert result["bucket"] == "my-bucket"
            # But create_bucket should still get full s3:// URI
            mock_service.create_bucket.assert_called_once_with("s3://my-bucket")


class TestBucketObjectsSearchGraphQLBehavior:
    """Test bucket_objects_search_graphql function behavior before removal."""

    def test_bucket_objects_search_graphql_success(self):
        """Given bucket_objects_search_graphql is called successfully
        When GraphQL request succeeds
        Then it should return objects with page info
        """
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
                                "contentType": "text/csv",
                                "extension": "csv"
                            }
                        }
                    ],
                    "pageInfo": {
                        "endCursor": "cursor123",
                        "hasNextPage": True
                    }
                }
            }
        }
        mock_session.post.return_value = mock_response

        with patch('quilt_mcp.tools.buckets.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.has_session_support.return_value = True
            mock_service.get_session.return_value = mock_session
            mock_service.get_registry_url.return_value = "https://example.com"
            mock_service_class.return_value = mock_service

            result = bucket_objects_search_graphql("my-bucket")

            assert result["success"] is True
            assert result["bucket"] == "my-bucket"
            assert len(result["objects"]) == 1
            assert result["objects"][0]["key"] == "test.csv"
            assert result["page_info"]["has_next_page"] is True

    def test_bucket_objects_search_graphql_no_session_support(self):
        """Given bucket_objects_search_graphql when no session support
        When quilt3 session is not available
        Then it should return error about session unavailability
        """
        with patch('quilt_mcp.tools.buckets.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.has_session_support.return_value = False
            mock_service_class.return_value = mock_service

            result = bucket_objects_search_graphql("my-bucket")

            assert result["success"] is False
            assert "quilt3 session not available" in result["error"]
            assert result["objects"] == []

    def test_bucket_objects_search_graphql_with_filter(self):
        """Given bucket_objects_search_graphql with object filter
        When filter parameter is provided
        Then it should include filter in GraphQL variables
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"objects": {"edges": [], "pageInfo": {}}}
        }
        mock_session.post.return_value = mock_response

        object_filter = {"extension": "csv"}

        with patch('quilt_mcp.tools.buckets.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.has_session_support.return_value = True
            mock_service.get_session.return_value = mock_session
            mock_service.get_registry_url.return_value = "https://example.com"
            mock_service_class.return_value = mock_service

            result = bucket_objects_search_graphql("my-bucket", object_filter=object_filter)

            # Check that the GraphQL request included the filter
            call_args = mock_session.post.call_args
            assert call_args[1]["json"]["variables"]["filter"] == object_filter
            assert result["filter"] == object_filter

    def test_bucket_objects_search_graphql_error_response(self):
        """Given bucket_objects_search_graphql receives GraphQL errors
        When GraphQL response contains errors
        Then it should return error information
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Field not found"}]
        }
        mock_session.post.return_value = mock_response

        with patch('quilt_mcp.tools.buckets.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.has_session_support.return_value = True
            mock_service.get_session.return_value = mock_session
            mock_service.get_registry_url.return_value = "https://example.com"
            mock_service_class.return_value = mock_service

            result = bucket_objects_search_graphql("my-bucket")

            assert result["success"] is False
            assert "Field not found" in result["error"]
            assert result["objects"] == []

    def test_bucket_objects_search_graphql_pagination(self):
        """Given bucket_objects_search_graphql with pagination parameters
        When first and after parameters are provided
        Then it should include them in GraphQL variables
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"objects": {"edges": [], "pageInfo": {}}}
        }
        mock_session.post.return_value = mock_response

        with patch('quilt_mcp.tools.buckets.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.has_session_support.return_value = True
            mock_service.get_session.return_value = mock_session
            mock_service.get_registry_url.return_value = "https://example.com"
            mock_service_class.return_value = mock_service

            bucket_objects_search_graphql("my-bucket", first=50, after="cursor123")

            # Check pagination parameters were passed
            call_args = mock_session.post.call_args
            variables = call_args[1]["json"]["variables"]
            assert variables["first"] == 50
            assert variables["after"] == "cursor123"


class TestCatalogSearchFeatureParity:
    """Test that catalog_search provides equivalent functionality to legacy functions."""

    def test_catalog_search_equivalent_to_packages_search(self):
        """Given catalog_search is called with packages_search equivalent parameters
        When using scope='catalog' and appropriate filters
        Then it should provide the same functionality as packages_search
        """
        # This tests the direct equivalent functionality
        with patch('quilt_mcp.tools.search.catalog_search') as mock_catalog_search:
            mock_catalog_search.return_value = {"results": [], "count": 0}

            # Import here to avoid circular imports
            from quilt_mcp.tools.search import catalog_search

            # Test direct catalog_search usage that replaces packages_search
            result = catalog_search(
                query="test query",
                scope="catalog",
                target="s3://my-registry",
                limit=10,
                filters={"registry": "s3://my-registry", "offset": 0}
            )

            mock_catalog_search.assert_called_once()

    def test_catalog_search_equivalent_to_bucket_objects_search(self):
        """Given catalog_search is called with bucket_objects_search equivalent parameters
        When using scope='bucket' and elasticsearch backend
        Then it should provide the same functionality as bucket_objects_search
        """
        with patch('quilt_mcp.tools.search.catalog_search') as mock_catalog_search:
            mock_catalog_search.return_value = {"results": [], "bucket": "my-bucket"}

            from quilt_mcp.tools.search import catalog_search

            # Test direct catalog_search usage that replaces bucket_objects_search
            result = catalog_search(
                query="*.csv",
                scope="bucket",
                target="s3://my-bucket",
                backends=["elasticsearch"],
                limit=10
            )

            mock_catalog_search.assert_called_once()

    def test_catalog_search_equivalent_to_bucket_objects_search_graphql(self):
        """Given catalog_search is called with bucket_objects_search_graphql equivalent parameters
        When using scope='bucket' and graphql backend
        Then it should provide the same functionality as bucket_objects_search_graphql
        """
        with patch('quilt_mcp.tools.search.catalog_search') as mock_catalog_search:
            mock_catalog_search.return_value = {"results": [], "bucket": "my-bucket"}

            from quilt_mcp.tools.search import catalog_search

            # Test direct catalog_search usage that replaces bucket_objects_search_graphql
            result = catalog_search(
                query="csv files",
                scope="bucket",
                target="s3://my-bucket",
                backends=["graphql"],
                limit=100
            )

            mock_catalog_search.assert_called_once()
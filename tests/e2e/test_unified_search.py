"""Tests for unified search functionality."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from quilt_mcp.search.core.query_parser import (
    QueryParser,
    QueryType,
    SearchScope,
    parse_query,
)
from quilt_mcp.search.backends.base import (
    BackendRegistry,
    BackendStatus,
    SearchResult,
    BackendType,
)
from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend
from quilt_mcp.search.tools.unified_search import UnifiedSearchEngine, unified_search


class TestQueryParser:
    """Test cases for query parsing and classification."""

    def test_file_search_detection(self):
        """Test detection of file search queries."""
        parser = QueryParser()

        queries = [
            "find CSV files",
            "search for JSON data",
            "get all parquet files",
            "locate files with genomics data",
        ]

        for query in queries:
            analysis = parser.parse(query)
            assert analysis.query_type == QueryType.FILE_SEARCH

    def test_package_discovery_detection(self):
        """Test detection of package discovery queries."""
        parser = QueryParser()

        queries = [
            "packages about genomics",
            "find packages containing RNA-seq",
            "list all packages",
            "browse packages for cell painting",
        ]

        for query in queries:
            analysis = parser.parse(query)
            assert analysis.query_type == QueryType.PACKAGE_DISCOVERY

    def test_analytical_search_detection(self):
        """Test detection of analytical queries."""
        parser = QueryParser()

        queries = [
            "largest files in the dataset",
            "files larger than 100MB",
            "count of CSV files",
            "analyze file sizes",
        ]

        for query in queries:
            analysis = parser.parse(query)
            assert analysis.query_type == QueryType.ANALYTICAL_SEARCH

    def test_file_extension_extraction(self):
        """Test extraction of file extensions from queries."""
        parser = QueryParser()

        analysis = parser.parse("find CSV and JSON files")
        assert "csv" in analysis.file_extensions
        assert "json" in analysis.file_extensions

    def test_size_filter_extraction(self):
        """Test extraction of size filters."""
        parser = QueryParser()

        analysis = parser.parse("files larger than 50MB")
        assert analysis.size_filters.get("size_min") == 50 * 1024 * 1024

        analysis = parser.parse("files smaller than 1GB")
        assert analysis.size_filters.get("size_max") == 1024 * 1024 * 1024

    def test_keyword_extraction(self):
        """Test extraction of meaningful keywords."""
        parser = QueryParser()

        analysis = parser.parse("find genomics data files with RNA-seq results")
        assert "genomics" in analysis.keywords
        assert "rna-seq" in analysis.keywords
        assert "results" in analysis.keywords
        # Stop words should be filtered out
        assert "find" not in analysis.keywords
        assert "with" not in analysis.keywords


class TestElasticsearchBackend:
    """Test cases for Elasticsearch backend."""

    @patch("quilt_mcp.services.quilt_service.quilt3")
    def test_session_check(self, mock_quilt3):
        """Test session availability checking."""
        mock_quilt3.session.get_registry_url.return_value = "https://example.com"

        backend = Quilt3ElasticsearchBackend()
        # Backend uses lazy initialization - must explicitly initialize
        backend.ensure_initialized()
        assert backend.status == BackendStatus.AVAILABLE

    @patch("quilt_mcp.services.quilt_service.quilt3")
    def test_session_unavailable(self, mock_quilt3):
        """Test handling when session is unavailable."""
        mock_quilt3.session.get_registry_url.return_value = None

        backend = Quilt3ElasticsearchBackend()
        # Backend uses lazy initialization - must explicitly initialize
        backend.ensure_initialized()
        assert backend.status == BackendStatus.UNAVAILABLE

    @patch("quilt_mcp.services.quilt_service.quilt3")
    @pytest.mark.anyio
    async def test_bucket_search(self, mock_quilt3):
        """Test bucket search functionality."""
        # Mock quilt3 session to show available
        mock_quilt3.session.get_registry_url.return_value = "https://example.com"

        # Mock quilt3 bucket search
        mock_bucket = Mock()
        mock_bucket.search.return_value = [
            {
                "_id": "test-id",
                "_source": {"key": "data.csv", "size": 1000},
                "_score": 0.8,
                "_index": "test-bucket",
            }
        ]
        mock_quilt3.Bucket.return_value = mock_bucket

        backend = Quilt3ElasticsearchBackend()
        response = await backend.search("CSV files", scope="file", bucket="test-bucket")

        assert response.status == BackendStatus.AVAILABLE
        assert len(response.results) == 1
        assert response.results[0].type == "file"
        assert response.results[0].logical_key == "data.csv"


class TestUnifiedSearchEngine:
    """Test cases for the unified search engine."""

    @pytest.mark.anyio
    async def test_search_with_mocked_backend(self):
        """Test unified search with mocked backend."""
        engine = UnifiedSearchEngine()

        # Mock the registry to return a backend
        mock_backend = Mock()
        mock_backend.backend_type = BackendType.ELASTICSEARCH
        mock_backend.status = BackendStatus.AVAILABLE

        # Mock backend search response
        mock_response = Mock()
        mock_response.backend_type = BackendType.ELASTICSEARCH
        mock_response.status = BackendStatus.AVAILABLE
        mock_response.results = [
            SearchResult(
                id="test-1",
                type="file",
                title="test.csv",
                logical_key="test.csv",
                score=0.9,
                backend="elasticsearch",
            )
        ]
        mock_response.query_time_ms = 50.0
        mock_response.error_message = None

        mock_backend.search = AsyncMock(return_value=mock_response)

        # Patch the primary backend selection
        with patch.object(engine.registry, "_select_primary_backend", return_value=mock_backend):
            result = await engine.search("CSV files")

            assert result["success"] is True
            assert len(result["results"]) == 1
            assert result["results"][0]["title"] == "test.csv"
            assert result["backend_used"] == "elasticsearch"


class TestUnifiedSearchTool:
    """Test cases for the unified search tool function."""

    @patch("quilt_mcp.search.tools.unified_search.get_search_engine")
    @pytest.mark.anyio
    async def test_unified_search_function(self, mock_get_engine):
        """Test the main unified_search function."""
        # Mock the search engine
        mock_engine = Mock()
        mock_engine.search = AsyncMock(return_value={"success": True, "results": [], "query": "test query"})
        mock_get_engine.return_value = mock_engine

        result = await unified_search("test query")

        assert result["success"] is True
        assert result["query"] == "test query"
        mock_engine.search.assert_called_once()

    @patch("quilt_mcp.search.tools.unified_search.get_search_engine")
    @pytest.mark.anyio
    async def test_unified_search_error_handling(self, mock_get_engine):
        """Test error handling in unified search."""
        # Mock engine that raises exception
        mock_engine = Mock()
        mock_engine.search = AsyncMock(side_effect=Exception("Test error"))
        mock_get_engine.return_value = mock_engine

        result = await unified_search("test query")

        assert result["success"] is False
        assert "Test error" in result["error"]

    @pytest.mark.anyio
    async def test_backend_failure(self):
        """Test that backend failures are properly reported."""
        engine = UnifiedSearchEngine()

        # Mock a backend that fails
        mock_backend = Mock()
        mock_backend.backend_type = BackendType.ELASTICSEARCH
        mock_backend.status = BackendStatus.AVAILABLE

        # Failed backend response (simulating 403 error like in the example)
        failed_response = Mock()
        failed_response.backend_type = BackendType.ELASTICSEARCH
        failed_response.status = BackendStatus.ERROR
        failed_response.results = []
        failed_response.query_time_ms = 100.0
        failed_response.error_message = "Catalog search failed: Unexpected failure: error 403"

        mock_backend.search = AsyncMock(return_value=failed_response)

        with patch.object(engine.registry, "_select_primary_backend", return_value=mock_backend):
            result = await engine.search("test query")

            # Should report failure because backend failed
            assert result["success"] is False

            # Should include error message
            assert "error" in result
            assert "403" in result["error"]

            # Should return no results
            assert len(result["results"]) == 0

            # Should show backend was not successfully used
            assert result["backend_used"] is None

            # Should show backend status with error
            assert "backend_status" in result
            assert result["backend_status"]["status"] == "error"
            assert "403" in result["backend_status"]["error"]

    @pytest.mark.anyio
    async def test_no_backends_available(self):
        """Test that search fails explicitly when no backends are available."""
        engine = UnifiedSearchEngine()

        # Mock that no backends are available
        with patch.object(engine.registry, "_select_primary_backend", return_value=None):
            result = await engine.search("test query")

            # Should report failure
            assert result["success"] is False

            # Should have error message
            assert "error" in result
            assert "Catalog search not available" in result["error"]

            # Should return no results
            assert len(result["results"]) == 0

            # Should show no backend used
            assert result["backend_used"] is None

    @pytest.mark.anyio
    async def test_backend_selection_priority(self):
        """Test that GraphQL backend is preferred over Elasticsearch."""
        engine = UnifiedSearchEngine()

        # Mock both backends as available
        graphql_backend = Mock()
        graphql_backend.backend_type = BackendType.GRAPHQL
        graphql_backend.status = BackendStatus.AVAILABLE

        elasticsearch_backend = Mock()
        elasticsearch_backend.backend_type = BackendType.ELASTICSEARCH
        elasticsearch_backend.status = BackendStatus.AVAILABLE

        # Setup registry with both backends
        engine.registry._backends = {
            BackendType.GRAPHQL: graphql_backend,
            BackendType.ELASTICSEARCH: elasticsearch_backend,
        }

        # Call the actual selection method
        selected = engine.registry._select_primary_backend()

        # Should prefer GraphQL
        assert selected == graphql_backend
        assert selected.backend_type == BackendType.GRAPHQL

    @pytest.mark.anyio
    async def test_backend_fallback_to_elasticsearch(self):
        """Test that Elasticsearch is used when GraphQL is unavailable."""
        engine = UnifiedSearchEngine()

        # Mock GraphQL as unavailable, Elasticsearch as available
        graphql_backend = Mock()
        graphql_backend.backend_type = BackendType.GRAPHQL
        graphql_backend.status = BackendStatus.UNAVAILABLE

        elasticsearch_backend = Mock()
        elasticsearch_backend.backend_type = BackendType.ELASTICSEARCH
        elasticsearch_backend.status = BackendStatus.AVAILABLE

        # Setup registry with both backends
        engine.registry._backends = {
            BackendType.GRAPHQL: graphql_backend,
            BackendType.ELASTICSEARCH: elasticsearch_backend,
        }

        # Call the actual selection method
        selected = engine.registry._select_primary_backend()

        # Should fall back to Elasticsearch
        assert selected == elasticsearch_backend
        assert selected.backend_type == BackendType.ELASTICSEARCH

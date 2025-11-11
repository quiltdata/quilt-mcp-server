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
from quilt_mcp.search.backends.s3 import S3FallbackBackend
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
        assert backend.status == BackendStatus.AVAILABLE

    @patch("quilt_mcp.services.quilt_service.quilt3")
    def test_session_unavailable(self, mock_quilt3):
        """Test handling when session is unavailable."""
        mock_quilt3.session.get_registry_url.return_value = None

        backend = Quilt3ElasticsearchBackend()
        assert backend.status == BackendStatus.UNAVAILABLE

    @patch("quilt_mcp.services.quilt_service.quilt3")
    @pytest.mark.asyncio
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
        response = await backend.search("CSV files", scope="bucket", target="test-bucket")

        assert response.status == BackendStatus.AVAILABLE
        assert len(response.results) == 1
        assert response.results[0].type == "file"
        assert response.results[0].logical_key == "data.csv"


class TestS3FallbackBackend:
    """Test cases for S3 fallback backend."""

    @patch("quilt_mcp.search.backends.s3.get_sts_client")
    @patch("quilt_mcp.search.backends.s3.get_s3_client")
    def test_s3_access_check(self, mock_get_s3_client, mock_get_sts_client):
        """Test S3 access checking."""
        mock_s3_client = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {"UserId": "test"}

        mock_get_s3_client.return_value = mock_s3_client
        mock_get_sts_client.return_value = mock_sts_client

        backend = S3FallbackBackend()
        assert backend.status == BackendStatus.AVAILABLE

    @patch("quilt_mcp.search.backends.s3.get_sts_client")
    @patch("quilt_mcp.search.backends.s3.get_s3_client")
    @pytest.mark.asyncio
    async def test_bucket_search(self, mock_get_s3_client, mock_get_sts_client):
        """Test S3 bucket search functionality."""
        # Mock S3 client and paginator
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_page_iterator = [
            {
                "Contents": [
                    {
                        "Key": "data/test.csv",
                        "Size": 1000,
                        "LastModified": Mock(isoformat=Mock(return_value="2024-01-01T00:00:00Z")),
                        "StorageClass": "STANDARD",
                    }
                ]
            }
        ]

        mock_paginator.paginate.return_value = mock_page_iterator
        mock_s3_client.get_paginator.return_value = mock_paginator

        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {"UserId": "test"}

        # Mock both helper functions
        mock_get_s3_client.return_value = mock_s3_client
        mock_get_sts_client.return_value = mock_sts_client

        backend = S3FallbackBackend()
        response = await backend.search("csv", scope="bucket", target="test-bucket")

        assert response.status == BackendStatus.AVAILABLE
        assert len(response.results) == 1
        assert response.results[0].type == "file"
        assert response.results[0].logical_key == "data/test.csv"


class TestUnifiedSearchEngine:
    """Test cases for the unified search engine."""

    @pytest.mark.asyncio
    async def test_search_with_mocked_backends(self):
        """Test unified search with mocked backends."""
        engine = UnifiedSearchEngine()

        # Mock backend responses
        with patch.object(engine, "_execute_parallel_searches") as mock_execute:
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

            mock_execute.return_value = [mock_response]

            result = await engine.search("CSV files")

            assert result["success"] is True
            assert len(result["results"]) == 1
            assert result["results"][0]["title"] == "test.csv"
            assert "elasticsearch" in result["backends_used"]


class TestUnifiedSearchTool:
    """Test cases for the unified search tool function."""

    @patch("quilt_mcp.search.tools.unified_search.get_search_engine")
    @pytest.mark.asyncio
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
    @pytest.mark.asyncio
    async def test_unified_search_error_handling(self, mock_get_engine):
        """Test error handling in unified search."""
        # Mock engine that raises exception
        mock_engine = Mock()
        mock_engine.search = AsyncMock(side_effect=Exception("Test error"))
        mock_get_engine.return_value = mock_engine

        result = await unified_search("test query")

        assert result["success"] is False
        assert "Test error" in result["error"]

    @pytest.mark.asyncio
    async def test_partial_backend_failure(self):
        """Test that partial backend failures are properly reported."""
        engine = UnifiedSearchEngine()

        # Mock backend responses: one success, one failure
        with patch.object(engine, "_execute_parallel_searches") as mock_execute:
            # Successful backend
            success_response = Mock()
            success_response.backend_type = BackendType.GRAPHQL
            success_response.status = BackendStatus.AVAILABLE
            success_response.results = [
                SearchResult(
                    id="test-1",
                    type="file",
                    title="test.csv",
                    logical_key="test.csv",
                    score=0.9,
                    backend="graphql",
                )
            ]
            success_response.query_time_ms = 50.0
            success_response.error_message = None

            # Failed backend (simulating 403 error like in the example)
            failed_response = Mock()
            failed_response.backend_type = BackendType.ELASTICSEARCH
            failed_response.status = BackendStatus.ERROR
            failed_response.results = []
            failed_response.query_time_ms = 100.0
            failed_response.error_message = "Catalog search failed: Unexpected failure: error 403"

            mock_execute.return_value = [success_response, failed_response]

            result = await engine.search("test query")

            # Should report failure because a backend failed
            assert result["success"] is False

            # Should include warnings about the partial failure
            assert "warnings" in result
            assert any("Partial failure" in w for w in result["warnings"])
            assert any("403" in w for w in result["warnings"])

            # Should indicate partial failure
            assert result.get("partial_failure") is True

            # Should still return results from successful backend
            assert len(result["results"]) == 1
            assert result["results"][0]["title"] == "test.csv"

            # Should show only successful backends in backends_used
            assert "graphql" in result["backends_used"]
            assert "elasticsearch" not in result["backends_used"]

            # Should show both backends in backend_status
            assert "elasticsearch" in result["backend_status"]
            assert result["backend_status"]["elasticsearch"]["status"] == "error"
            assert "403" in result["backend_status"]["elasticsearch"]["error"]

    @pytest.mark.asyncio
    async def test_complete_backend_failure(self):
        """Test that complete backend failures (all backends fail) are properly reported."""
        engine = UnifiedSearchEngine()

        # Mock backend responses: all failures
        with patch.object(engine, "_execute_parallel_searches") as mock_execute:
            # Failed backend 1
            failed_response1 = Mock()
            failed_response1.backend_type = BackendType.ELASTICSEARCH
            failed_response1.status = BackendStatus.ERROR
            failed_response1.results = []
            failed_response1.query_time_ms = 100.0
            failed_response1.error_message = "Connection timeout"

            # Failed backend 2
            failed_response2 = Mock()
            failed_response2.backend_type = BackendType.GRAPHQL
            failed_response2.status = BackendStatus.ERROR
            failed_response2.results = []
            failed_response2.query_time_ms = 100.0
            failed_response2.error_message = "Authentication failed"

            mock_execute.return_value = [failed_response1, failed_response2]

            result = await engine.search("test query")

            # Should report failure
            assert result["success"] is False

            # Should include warnings about complete failure
            assert "warnings" in result
            assert any("Complete failure" in w for w in result["warnings"])

            # Should NOT indicate partial failure (since nothing succeeded)
            assert result.get("partial_failure") is not True

            # Should return no results
            assert len(result["results"]) == 0

            # Should show no backends in backends_used
            assert len(result["backends_used"]) == 0

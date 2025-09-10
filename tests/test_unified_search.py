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

    @patch("quilt_mcp.search.backends.elasticsearch.quilt3")
    def test_session_check(self, mock_quilt3):
        """Test session availability checking."""
        mock_quilt3.session.get_registry_url.return_value = "https://example.com"

        backend = Quilt3ElasticsearchBackend()
        assert backend.status == BackendStatus.AVAILABLE

    @patch("quilt_mcp.search.backends.elasticsearch.quilt3")
    def test_session_unavailable(self, mock_quilt3):
        """Test handling when session is unavailable."""
        mock_quilt3.session.get_registry_url.return_value = None

        backend = Quilt3ElasticsearchBackend()
        assert backend.status == BackendStatus.UNAVAILABLE

    @patch("quilt_mcp.search.backends.elasticsearch.quilt3")
    @pytest.mark.asyncio
    async def test_bucket_search(self, mock_quilt3):
        """Test bucket search functionality."""
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
        mock_quilt3.session.get_registry_url.return_value = "https://example.com"

        backend = Quilt3ElasticsearchBackend()
        response = await backend.search("CSV files", scope="bucket", target="test-bucket")

        assert response.status == BackendStatus.AVAILABLE
        assert len(response.results) == 1
        assert response.results[0].type == "file"
        assert response.results[0].logical_key == "data.csv"


class TestS3FallbackBackend:
    """Test cases for S3 fallback backend."""

    @patch("quilt_mcp.search.backends.s3.boto3")
    def test_s3_access_check(self, mock_boto3):
        """Test S3 access checking."""
        mock_s3_client = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {"UserId": "test"}

        mock_boto3.client.side_effect = lambda service: {
            "s3": mock_s3_client,
            "sts": mock_sts_client,
        }[service]

        backend = S3FallbackBackend()
        assert backend.status == BackendStatus.AVAILABLE

    @patch("quilt_mcp.search.backends.s3.get_s3_client")
    @patch("quilt_mcp.search.backends.s3.boto3")
    @pytest.mark.asyncio
    async def test_bucket_search(self, mock_boto3, mock_get_s3_client):
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

        # Mock both the direct boto3 calls and our centralized helper
        mock_boto3.client.side_effect = lambda service: {
            "s3": mock_s3_client,
            "sts": mock_sts_client,
        }[service]

        mock_get_s3_client.return_value = mock_s3_client

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

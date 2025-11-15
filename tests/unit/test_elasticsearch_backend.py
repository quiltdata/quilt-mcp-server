"""Tests for simplified Elasticsearch backend.

These tests verify:
1. Index pattern building (scope + bucket → index)
2. Result normalization (hit → SearchResult with 'name' field)
3. Type detection from index name (_packages suffix)
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock

from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend
from quilt_mcp.search.backends.base import BackendStatus
from quilt_mcp.services.quilt_service import QuiltService

# Configure anyio for async tests
pytestmark = pytest.mark.anyio


class TestIndexPatternBuilder:
    """Test the trivial index pattern builder."""

    def setup_method(self):
        """Setup mock QuiltService for each test."""
        self.mock_service = Mock(spec=QuiltService)
        self.mock_service.get_registry_url.return_value = "s3://test-registry"
        self.backend = Quilt3ElasticsearchBackend(quilt_service=self.mock_service)

    def test_file_scope_with_bucket(self):
        """scope='file', bucket='mybucket' → 'mybucket'"""
        pattern = self.backend._build_index_pattern("file", "mybucket")
        assert pattern == "mybucket"

    def test_file_scope_with_s3_uri(self):
        """scope='file', bucket='s3://mybucket' → 'mybucket'"""
        pattern = self.backend._build_index_pattern("file", "s3://mybucket")
        assert pattern == "mybucket"

    async def test_file_scope_all_buckets(self):
        """scope='file', bucket='' → searches across ALL buckets and returns file results"""
        # Mock bucket list API
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "bucketConfigs": [
                    {"name": "bucket1"},
                    {"name": "bucket2"},
                ]
            }
        }
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        self.mock_service.get_session.return_value = mock_session
        self.mock_service.get_registry_url.return_value = "https://example.quiltdata.com"

        # Mock search API to return results from multiple buckets
        mock_search_api = Mock()
        mock_search_api.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "1",
                        "_index": "bucket1",
                        "_score": 2.5,
                        "_source": {
                            "key": "data/file1.csv",
                            "size": 1024,
                            "last_modified": "2025-01-14T10:00:00Z",
                        },
                    },
                    {
                        "_id": "2",
                        "_index": "bucket2",
                        "_score": 1.8,
                        "_source": {
                            "key": "experiments/file2.json",
                            "size": 2048,
                            "last_modified": "2025-01-13T10:00:00Z",
                        },
                    },
                ]
            }
        }
        self.mock_service.get_search_api.return_value = mock_search_api

        # Execute search with empty bucket
        response = await self.backend.search(query="test", scope="file", bucket="", limit=10)

        # Verify we got results from multiple buckets
        assert response.status == BackendStatus.AVAILABLE
        assert len(response.results) == 2

        # Verify first result schema and content
        result1 = response.results[0]
        assert result1.type == "file"
        assert result1.name == "data/file1.csv"
        assert result1.bucket == "bucket1"
        assert result1.s3_uri == "s3://bucket1/data/file1.csv"
        assert result1.size == 1024
        assert result1.score == 2.5

        # Verify second result from different bucket
        result2 = response.results[1]
        assert result2.type == "file"
        assert result2.name == "experiments/file2.json"
        assert result2.bucket == "bucket2"
        assert result2.s3_uri == "s3://bucket2/experiments/file2.json"
        assert result2.size == 2048
        assert result2.score == 1.8

    def test_package_scope_with_bucket(self):
        """scope='package', bucket='mybucket' → 'mybucket_packages'"""
        pattern = self.backend._build_index_pattern("package", "mybucket")
        assert pattern == "mybucket_packages"

    async def test_package_scope_all_buckets(self):
        """scope='package', bucket='' → searches across ALL buckets and returns package results"""
        # Mock bucket list API
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "bucketConfigs": [
                    {"name": "bucket1"},
                    {"name": "bucket2"},
                ]
            }
        }
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        self.mock_service.get_session.return_value = mock_session
        self.mock_service.get_registry_url.return_value = "https://example.quiltdata.com"

        # Mock search API to return package results from multiple buckets
        mock_search_api = Mock()
        mock_search_api.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "1",
                        "_index": "bucket1_packages",
                        "_score": 3.2,
                        "_source": {
                            "ptr_name": "datasets/genomics",
                            "mnfst_hash": "abc123",
                            "mnfst_stats": {"total_bytes": 50000},
                            "mnfst_last_modified": "2025-01-14T10:00:00Z",
                        },
                    },
                    {
                        "_id": "2",
                        "_index": "bucket2_packages",
                        "_score": 2.1,
                        "_source": {
                            "ptr_name": "experiments/trials",
                            "mnfst_hash": "def456",
                            "mnfst_stats": {"total_bytes": 75000},
                            "mnfst_last_modified": "2025-01-13T10:00:00Z",
                        },
                    },
                ]
            }
        }
        self.mock_service.get_search_api.return_value = mock_search_api

        # Execute search with empty bucket
        response = await self.backend.search(query="test", scope="package", bucket="", limit=10)

        # Verify we got package results from multiple buckets
        assert response.status == BackendStatus.AVAILABLE
        assert len(response.results) == 2

        # Verify first result schema and content
        result1 = response.results[0]
        assert result1.type == "package"
        assert result1.name == "datasets/genomics"
        assert result1.bucket == "bucket1"
        assert result1.s3_uri == "s3://bucket1/.quilt/packages/datasets/genomics/abc123.jsonl"
        assert result1.size == 50000
        assert result1.score == 3.2

        # Verify second result from different bucket
        result2 = response.results[1]
        assert result2.type == "package"
        assert result2.name == "experiments/trials"
        assert result2.bucket == "bucket2"
        assert result2.s3_uri == "s3://bucket2/.quilt/packages/experiments/trials/def456.jsonl"
        assert result2.size == 75000
        assert result2.score == 2.1

    def test_global_scope_with_bucket(self):
        """scope='global', bucket='mybucket' → 'mybucket,mybucket_packages'"""
        pattern = self.backend._build_index_pattern("global", "mybucket")
        assert pattern == "mybucket,mybucket_packages"

    async def test_global_scope_all_buckets(self):
        """scope='global', bucket='' → searches across ALL buckets and returns BOTH file and package results"""
        # Mock bucket list API
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "bucketConfigs": [
                    {"name": "bucket1"},
                    {"name": "bucket2"},
                ]
            }
        }
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        self.mock_service.get_session.return_value = mock_session
        self.mock_service.get_registry_url.return_value = "https://example.quiltdata.com"

        # Mock search API to return BOTH file and package results from multiple buckets
        mock_search_api = Mock()
        mock_search_api.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "1",
                        "_index": "bucket1",
                        "_score": 2.5,
                        "_source": {
                            "key": "data/file1.csv",
                            "size": 1024,
                            "last_modified": "2025-01-14T10:00:00Z",
                        },
                    },
                    {
                        "_id": "2",
                        "_index": "bucket1_packages",
                        "_score": 3.2,
                        "_source": {
                            "ptr_name": "datasets/genomics",
                            "mnfst_hash": "abc123",
                            "mnfst_stats": {"total_bytes": 50000},
                            "mnfst_last_modified": "2025-01-14T10:00:00Z",
                        },
                    },
                    {
                        "_id": "3",
                        "_index": "bucket2",
                        "_score": 1.8,
                        "_source": {
                            "key": "experiments/file2.json",
                            "size": 2048,
                            "last_modified": "2025-01-13T10:00:00Z",
                        },
                    },
                ]
            }
        }
        self.mock_service.get_search_api.return_value = mock_search_api

        # Execute search with empty bucket
        response = await self.backend.search(query="test", scope="global", bucket="", limit=10)

        # Verify we got BOTH file and package results from multiple buckets
        assert response.status == BackendStatus.AVAILABLE
        assert len(response.results) == 3

        # Verify file result
        result1 = response.results[0]
        assert result1.type == "file"
        assert result1.name == "data/file1.csv"
        assert result1.bucket == "bucket1"
        assert result1.s3_uri == "s3://bucket1/data/file1.csv"

        # Verify package result
        result2 = response.results[1]
        assert result2.type == "package"
        assert result2.name == "datasets/genomics"
        assert result2.bucket == "bucket1"

        # Verify file result from different bucket
        result3 = response.results[2]
        assert result3.type == "file"
        assert result3.name == "experiments/file2.json"
        assert result3.bucket == "bucket2"


class TestResultNormalization:
    """Test result normalization from Elasticsearch hits."""

    def setup_method(self):
        """Setup mock QuiltService for each test."""
        self.mock_service = Mock(spec=QuiltService)
        self.mock_service.get_registry_url.return_value = "s3://test-registry"
        self.backend = Quilt3ElasticsearchBackend(quilt_service=self.mock_service)

    def test_normalize_file_result(self):
        """File results should have type='file' and name=key."""
        hits = [
            {
                "_id": "file123",
                "_index": "mybucket",
                "_score": 1.5,
                "_source": {
                    "key": "path/to/data.csv",
                    "size": 1024,
                    "last_modified": "2025-01-14T10:00:00Z",
                    "content_type": "text/csv",
                },
            }
        ]

        results = self.backend._normalize_results(hits)

        assert len(results) == 1
        result = results[0]
        assert result.type == "file"
        assert result.name == "path/to/data.csv"  # ONLY field needed!
        assert result.title == "data.csv"
        assert result.bucket == "mybucket"
        assert result.s3_uri == "s3://mybucket/path/to/data.csv"
        assert result.size == 1024
        assert result.extension == "csv"
        assert result.score == 1.5

    def test_normalize_package_result(self):
        """Package results should have type='package' and name=package_name."""
        hits = [
            {
                "_id": "pkg123",
                "_index": "mybucket_packages",
                "_score": 2.1,
                "_source": {
                    "ptr_name": "raw/test",
                    "mnfst_hash": "abc123",
                    "mnfst_stats": {"total_bytes": 5000},
                    "mnfst_last_modified": "2025-01-14T10:00:00Z",
                },
            }
        ]

        results = self.backend._normalize_results(hits)

        assert len(results) == 1
        result = results[0]
        assert result.type == "package"
        assert result.name == "raw/test"  # ONLY field needed!
        assert result.title == "raw/test"
        assert result.bucket == "mybucket"
        assert result.s3_uri == "s3://mybucket/.quilt/packages/raw/test/abc123.jsonl"
        assert result.size == 5000
        assert result.extension == "jsonl"
        assert result.score == 2.1

    def test_type_detection_from_index_name(self):
        """Type should be detected from index name (_packages suffix)."""
        hits = [
            {"_id": "1", "_index": "bucket1", "_score": 1.0, "_source": {"key": "file.txt"}},
            {"_id": "2", "_index": "bucket2_packages", "_score": 1.0, "_source": {"ptr_name": "pkg/name"}},
        ]

        results = self.backend._normalize_results(hits)

        assert results[0].type == "file"
        assert results[1].type == "package"

    def test_no_logical_key_or_package_name_fields(self):
        """Results should NOT have logical_key or package_name fields (per spec 19)."""
        hits = [
            {"_id": "1", "_index": "bucket", "_score": 1.0, "_source": {"key": "file.csv"}},
        ]

        results = self.backend._normalize_results(hits)
        result = results[0]

        # Check that ONLY 'name' field is used
        assert result.name == "file.csv"
        # These legacy fields should not be in the model anymore (they were removed)
        assert not hasattr(result, "logical_key") or result.logical_key is None
        assert not hasattr(result, "package_name") or result.package_name is None


class TestSearchExecution:
    """Test end-to-end search execution."""

    def setup_method(self):
        """Setup mock QuiltService for each test."""
        self.mock_service = Mock(spec=QuiltService)
        self.mock_service.get_registry_url.return_value = "s3://test-registry"

        # Mock search API
        self.mock_search_api = Mock()
        self.mock_service.get_search_api.return_value = self.mock_search_api

        self.backend = Quilt3ElasticsearchBackend(quilt_service=self.mock_service)

    async def test_search_builds_correct_index_pattern(self):
        """Search should build correct index pattern and execute query."""
        # Mock search response
        self.mock_search_api.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "1",
                        "_index": "mybucket",
                        "_score": 1.0,
                        "_source": {"key": "test.csv", "size": 100},
                    }
                ]
            }
        }

        response = await self.backend.search(query="test", scope="file", bucket="mybucket", limit=10)

        # Verify search was called with correct index pattern
        assert self.mock_search_api.called
        call_kwargs = self.mock_search_api.call_args.kwargs
        assert call_kwargs["index"] == "mybucket"
        assert call_kwargs["limit"] == 10

        # Verify results
        assert response.status == BackendStatus.AVAILABLE
        assert len(response.results) == 1
        assert response.results[0].name == "test.csv"

    async def test_search_applies_filters(self):
        """Search should apply filters to query DSL."""
        self.mock_search_api.return_value = {"hits": {"hits": []}}

        filters = {
            "file_extensions": [".csv", ".json"],
            "size_min": 100,
            "size_max": 1000,
        }

        await self.backend.search(query="test", scope="file", bucket="mybucket", filters=filters, limit=10)

        # Verify query DSL includes filters
        call_kwargs = self.mock_search_api.call_args.kwargs
        query_dsl = call_kwargs["query"]
        assert "bool" in query_dsl["query"]
        assert "filter" in query_dsl["query"]["bool"]

        filters_applied = query_dsl["query"]["bool"]["filter"]
        assert len(filters_applied) == 3  # extensions, size_min, size_max

    async def test_search_escapes_query(self):
        """Search should escape special characters in query."""
        self.mock_search_api.return_value = {"hits": {"hits": []}}

        await self.backend.search(query="team/dataset", scope="file", bucket="mybucket", limit=10)

        # Verify query was escaped
        call_kwargs = self.mock_search_api.call_args.kwargs
        query_dsl = call_kwargs["query"]
        query_string = query_dsl["query"]["query_string"]["query"]
        assert query_string == r"team\/dataset"


class TestDependencyInjection:
    """Test QuiltService dependency injection."""

    def test_accepts_quilt_service_dependency(self):
        """Backend should accept QuiltService as dependency."""
        mock_service = Mock(spec=QuiltService)
        mock_service.get_registry_url.return_value = "s3://test-bucket"

        backend = Quilt3ElasticsearchBackend(quilt_service=mock_service)

        assert backend.quilt_service == mock_service

        # Verify dependency is used
        backend.ensure_initialized()
        mock_service.get_registry_url.assert_called()

    def test_creates_default_service_if_none_provided(self):
        """Backend should create default QuiltService if none provided."""
        backend = Quilt3ElasticsearchBackend()

        assert backend.quilt_service is not None
        assert isinstance(backend.quilt_service, QuiltService)

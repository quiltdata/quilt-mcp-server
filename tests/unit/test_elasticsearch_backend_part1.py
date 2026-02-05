"""Tests for simplified Elasticsearch backend.

These tests verify:
1. Index pattern building (scope + bucket → index)
2. Result normalization (hit → SearchResult with 'name' field)
3. Type detection from index name (_packages suffix)
4. Index name parsing (is_package_index, get_bucket_from_index)
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend
from quilt_mcp.search.backends.base import BackendStatus

# Configure anyio for async tests
pytestmark = pytest.mark.anyio


class TestIndexNameParsing:
    """Test index name parsing helper methods.

    These methods must handle diverse index names including:
    - Standard indices: mybucket, mybucket_packages
    - Reindexed indices: mybucket-reindex-v{hash}, mybucket_packages-reindex-v{hash}
    - Mixed cases: some buckets reindexed, others not
    """

    def test_is_package_index_standard_object_index(self):
        """Standard object index does not contain _packages."""
        assert Quilt3ElasticsearchBackend.is_package_index("mybucket") is False
        assert Quilt3ElasticsearchBackend.is_package_index("testbucket") is False
        assert Quilt3ElasticsearchBackend.is_package_index("quilt-ernest-staging") is False

    def test_is_package_index_standard_package_index(self):
        """Standard package index ends with _packages."""
        assert Quilt3ElasticsearchBackend.is_package_index("mybucket_packages") is True
        assert Quilt3ElasticsearchBackend.is_package_index("testbucket_packages") is True

    def test_is_package_index_reindexed_object_index(self):
        """Reindexed object index has suffix but no _packages."""
        assert Quilt3ElasticsearchBackend.is_package_index("mybucket-reindex-v123") is False
        assert (
            Quilt3ElasticsearchBackend.is_package_index(
                "quilt-ernest-staging-reindex-v79dc05956b8bb535b513b59c0fc201b70bfc4414"
            )
            is False
        )

    def test_is_package_index_reindexed_package_index(self):
        """Reindexed package index contains _packages (not at end)."""
        assert Quilt3ElasticsearchBackend.is_package_index("mybucket_packages-reindex-v456") is True
        assert (
            Quilt3ElasticsearchBackend.is_package_index(
                "testbucket_packages-reindex-vb6281cee7aab120787076fe0116809df7e96ce86"
            )
            is True
        )
        assert (
            Quilt3ElasticsearchBackend.is_package_index(
                "quilt-ernest-staging_packages-reindex-v79dc05956b8bb535b513b59c0fc201b70bfc4414"
            )
            is True
        )

    def test_get_bucket_from_index_standard_object_index(self):
        """Standard object index returns bucket name as-is."""
        assert Quilt3ElasticsearchBackend.get_bucket_from_index("mybucket") == "mybucket"
        assert Quilt3ElasticsearchBackend.get_bucket_from_index("testbucket") == "testbucket"
        assert Quilt3ElasticsearchBackend.get_bucket_from_index("quilt-ernest-staging") == "quilt-ernest-staging"

    def test_get_bucket_from_index_standard_package_index(self):
        """Standard package index strips _packages suffix."""
        assert Quilt3ElasticsearchBackend.get_bucket_from_index("mybucket_packages") == "mybucket"
        assert Quilt3ElasticsearchBackend.get_bucket_from_index("testbucket_packages") == "testbucket"
        assert (
            Quilt3ElasticsearchBackend.get_bucket_from_index("quilt-ernest-staging_packages") == "quilt-ernest-staging"
        )

    def test_get_bucket_from_index_reindexed_object_index(self):
        """Reindexed object index strips reindex suffix."""
        assert Quilt3ElasticsearchBackend.get_bucket_from_index("mybucket-reindex-v123") == "mybucket"
        assert Quilt3ElasticsearchBackend.get_bucket_from_index("testbucket-reindex-vabc123") == "testbucket"
        assert (
            Quilt3ElasticsearchBackend.get_bucket_from_index(
                "quilt-ernest-staging-reindex-v79dc05956b8bb535b513b59c0fc201b70bfc4414"
            )
            == "quilt-ernest-staging"
        )

    def test_get_bucket_from_index_reindexed_package_index(self):
        """Reindexed package index strips both _packages and reindex suffix."""
        assert Quilt3ElasticsearchBackend.get_bucket_from_index("mybucket_packages-reindex-v456") == "mybucket"
        assert (
            Quilt3ElasticsearchBackend.get_bucket_from_index(
                "testbucket_packages-reindex-vb6281cee7aab120787076fe0116809df7e96ce86"
            )
            == "testbucket"
        )
        assert (
            Quilt3ElasticsearchBackend.get_bucket_from_index(
                "quilt-ernest-staging_packages-reindex-v79dc05956b8bb535b513b59c0fc201b70bfc4414"
            )
            == "quilt-ernest-staging"
        )

    def test_get_bucket_from_index_with_hyphens_in_name(self):
        """Bucket names with hyphens are handled correctly."""
        assert Quilt3ElasticsearchBackend.get_bucket_from_index("my-test-bucket") == "my-test-bucket"
        assert Quilt3ElasticsearchBackend.get_bucket_from_index("my-test-bucket_packages") == "my-test-bucket"
        assert Quilt3ElasticsearchBackend.get_bucket_from_index("my-test-bucket-reindex-v123") == "my-test-bucket"
        assert (
            Quilt3ElasticsearchBackend.get_bucket_from_index("my-test-bucket_packages-reindex-v456")
            == "my-test-bucket"
        )

    def test_edge_case_packages_in_bucket_name(self):
        """Edge case: bucket name contains 'packages' but not as suffix."""
        # This is unlikely in practice but we should handle it
        assert Quilt3ElasticsearchBackend.is_package_index("my_packages_bucket") is True  # Contains _packages
        assert (
            Quilt3ElasticsearchBackend.get_bucket_from_index("my_packages_bucket") == "my"
        )  # Splits at first _packages


class TestIndexPatternBuilder:
    """Test the trivial index pattern builder."""

    def setup_method(self):
        """Setup mock backend for each test."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.domain.auth_status import Auth_Status

        self.mock_backend = Mock(spec=Quilt3_Backend)
        mock_auth_status = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://example.quiltdata.com",
            catalog_name="example.quiltdata.com",
            registry_url="https://example-registry.quiltdata.com",
        )
        self.mock_backend.get_auth_status.return_value = mock_auth_status
        self.backend = Quilt3ElasticsearchBackend(backend=self.mock_backend)

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
        # Mock backend.execute_graphql_query() to return bucket list
        self.mock_backend.execute_graphql_query.return_value = {
            "data": {
                "bucketConfigs": [
                    {"name": "bucket1"},
                    {"name": "bucket2"},
                ]
            }
        }

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
        # Mock search_api
        with patch('quilt_mcp.search.backends.elasticsearch.search_api', mock_search_api):
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
        pattern = self.backend._build_index_pattern("packageEntry", "mybucket")
        assert pattern == "mybucket_packages"

    async def test_package_scope_all_buckets(self):
        """scope='package', bucket='' → searches across ALL buckets and returns package results"""
        # Mock backend.execute_graphql_query() to return bucket list
        self.mock_backend.execute_graphql_query.return_value = {
            "data": {
                "bucketConfigs": [
                    {"name": "bucket1"},
                    {"name": "bucket2"},
                ]
            }
        }

        # Mock search API to return package entry results from multiple buckets
        mock_search_api = Mock()
        mock_search_api.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "1",
                        "_index": "bucket1_packages",
                        "_score": 3.2,
                        "_source": {
                            "entry_pk": "datasets/genomics@abc123",
                            "entry_lk": "data/file1.csv",
                            "entry_size": 50000,
                            "entry_metadata": {"last_modified": "2025-01-14T10:00:00Z"},
                        },
                    },
                    {
                        "_id": "2",
                        "_index": "bucket2_packages",
                        "_score": 2.1,
                        "_source": {
                            "entry_pk": "experiments/trials@def456",
                            "entry_lk": "results/trial1.json",
                            "entry_size": 75000,
                            "entry_metadata": {"last_modified": "2025-01-13T10:00:00Z"},
                        },
                    },
                ]
            }
        }
        # Mock search_api
        with patch('quilt_mcp.search.backends.elasticsearch.search_api', mock_search_api):
            # Execute search with empty bucket
            response = await self.backend.search(query="test", scope="packageEntry", bucket="", limit=10)

            # Verify we got package entry results from multiple buckets
            assert response.status == BackendStatus.AVAILABLE
            assert len(response.results) == 2

            # Verify first result schema and content
            result1 = response.results[0]
            assert result1.type == "packageEntry"
            assert result1.name == "data/file1.csv"  # entry_lk
            assert result1.bucket == "bucket1"
            assert result1.s3_uri == "s3://bucket1/data/file1.csv"
            assert result1.size == 50000
            assert result1.score == 3.2

            # Verify second result from different bucket
            result2 = response.results[1]
            assert result2.type == "packageEntry"
            assert result2.name == "results/trial1.json"  # entry_lk
            assert result2.bucket == "bucket2"
            assert result2.s3_uri == "s3://bucket2/results/trial1.json"
            assert result2.size == 75000
            assert result2.score == 2.1

    def test_global_scope_with_bucket(self):
        """scope='global', bucket='mybucket' → 'mybucket,mybucket_packages'"""
        pattern = self.backend._build_index_pattern("global", "mybucket")
        assert pattern == "mybucket,mybucket_packages"

    async def test_global_scope_all_buckets(self):
        """scope='global', bucket='' → searches across ALL buckets and returns BOTH file and package results"""
        # Mock backend.execute_graphql_query() to return bucket list
        self.mock_backend.execute_graphql_query.return_value = {
            "data": {
                "bucketConfigs": [
                    {"name": "bucket1"},
                    {"name": "bucket2"},
                ]
            }
        }

        # Mock search API to return BOTH file and package entry results from multiple buckets
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
                            "entry_pk": "datasets/genomics@abc123",
                            "entry_lk": "data/genes.csv",
                            "entry_size": 50000,
                            "entry_metadata": {"last_modified": "2025-01-14T10:00:00Z"},
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
        # Mock search_api
        with patch('quilt_mcp.search.backends.elasticsearch.search_api', mock_search_api):
            # Execute search with empty bucket
            response = await self.backend.search(query="test", scope="global", bucket="", limit=10)

            # Verify we got BOTH file and package entry results from multiple buckets
            assert response.status == BackendStatus.AVAILABLE
            assert len(response.results) == 3

            # Verify file result
            result1 = response.results[0]
            assert result1.type == "file"
            assert result1.name == "data/file1.csv"
            assert result1.bucket == "bucket1"
            assert result1.s3_uri == "s3://bucket1/data/file1.csv"

            # Verify package entry result
            result2 = response.results[1]
            assert result2.type == "packageEntry"
            assert result2.name == "data/genes.csv"  # entry_lk
            assert result2.bucket == "bucket1"

            # Verify file result from different bucket
            result3 = response.results[2]
            assert result3.type == "file"
            assert result3.name == "experiments/file2.json"
            assert result3.bucket == "bucket2"

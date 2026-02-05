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


class TestResultNormalization:
    """Test result normalization from Elasticsearch hits."""

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

        results = self.backend._normalize_results(hits, scope="file")

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
        """Package results should have type='packageEntry' and name from entry fields."""
        hits = [
            {
                "_id": "pkg123",
                "_index": "mybucket_packages",
                "_score": 2.1,
                "_source": {
                    "entry_pk": "raw/test@abc123",
                    "entry_lk": "data/file.csv",
                    "entry_size": 5000,
                    "entry_metadata": {"last_modified": "2025-01-14T10:00:00Z"},
                },
            }
        ]

        results = self.backend._normalize_results(hits, scope="packageEntry")

        assert len(results) == 1
        result = results[0]
        assert result.type == "packageEntry"
        assert result.name == "data/file.csv"  # entry_lk is used as name
        assert result.title == "file.csv"
        assert result.bucket == "mybucket"
        assert result.s3_uri == "s3://mybucket/data/file.csv"
        assert result.size == 5000
        assert result.extension == "csv"
        assert result.score == 2.1

    def test_type_detection_from_index_name(self):
        """Type should be detected from index name (_packages suffix)."""
        hits = [
            {"_id": "1", "_index": "bucket1", "_score": 1.0, "_source": {"key": "file.txt"}},
            {
                "_id": "2",
                "_index": "bucket2_packages",
                "_score": 1.0,
                "_source": {"entry_pk": "pkg/name", "entry_lk": "data.csv"},
            },
        ]

        results = self.backend._normalize_results(hits, scope="global")

        assert results[0].type == "file"
        assert results[1].type == "packageEntry"

    def test_no_logical_key_or_package_name_fields(self):
        """Results should NOT have logical_key or package_name fields (per spec 19)."""
        hits = [
            {"_id": "1", "_index": "bucket", "_score": 1.0, "_source": {"key": "file.csv"}},
        ]

        results = self.backend._normalize_results(hits, scope="file")
        result = results[0]

        # Check that ONLY 'name' field is used
        assert result.name == "file.csv"
        # These legacy fields should not be in the model anymore (they were removed)
        assert not hasattr(result, "logical_key") or result.logical_key is None
        assert not hasattr(result, "package_name") or result.package_name is None


class TestDependencyInjection:
    """Test backend dependency injection."""

    def test_accepts_backend_dependency(self):
        """Backend should accept Quilt3_Backend as dependency."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.domain.auth_status import Auth_Status

        mock_backend = Mock(spec=Quilt3_Backend)
        mock_auth_status = Auth_Status(
            is_authenticated=True,
            logged_in_url="https://example.quiltdata.com",
            catalog_name="example.quiltdata.com",
            registry_url="https://example-registry.quiltdata.com",
        )
        mock_backend.get_auth_status.return_value = mock_auth_status

        backend = Quilt3ElasticsearchBackend(backend=mock_backend)

        assert backend.backend == mock_backend

        # Verify dependency is used
        backend.ensure_initialized()
        mock_backend.get_auth_status.assert_called()

    def test_creates_default_quilt_ops_if_none_provided(self):
        """Backend should create default QuiltOps if none provided."""
        backend = Quilt3ElasticsearchBackend()

        assert backend.quilt_ops is not None

"""Real integration tests for Elasticsearch index discovery.

These tests make ACTUAL AWS calls to verify that we can:
1. Discover available buckets via GraphQL
2. Build correct index patterns for each scope
3. Verify indices exist in Elasticsearch
4. Execute successful searches using discovered indices

No mocks. Real AWS. Real Elasticsearch. Real pain.

CRITICAL: These tests verify the CORE functionality of index discovery
that was previously untested and broken.
"""

import os
import pytest
import logging
from typing import List, Set, Dict, Any
from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend

pytestmark = pytest.mark.usefixtures("requires_search")

logger = logging.getLogger(__name__)
QUILT_TEST_BUCKET = os.getenv("QUILT_TEST_BUCKET", "")


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def backend(quilt3_backend):
    """Get initialized Elasticsearch backend."""
    backend = Quilt3ElasticsearchBackend(backend=quilt3_backend)
    backend._initialize()
    return backend


# ============================================================================
# Pure Function Tests (No AWS calls)
# ============================================================================


@pytest.mark.skipif(
    os.getenv("TEST_BACKEND_MODE") == "platform",
    reason="Quilt3ElasticsearchBackend requires quilt3 backend"
)
class TestPureFunctions:
    """Test pure static methods with no side effects."""

    def setup_method(self):
        """Create a backend instance for testing instance methods."""
        self.backend = Quilt3ElasticsearchBackend()

    def test_normalize_bucket_name_basic(self):
        """Test basic bucket name normalization."""
        assert Quilt3ElasticsearchBackend.normalize_bucket_name("my-bucket") == "my-bucket"
        assert Quilt3ElasticsearchBackend.normalize_bucket_name("s3://my-bucket") == "my-bucket"
        assert Quilt3ElasticsearchBackend.normalize_bucket_name("s3://my-bucket/") == "my-bucket"
        assert Quilt3ElasticsearchBackend.normalize_bucket_name("s3://my-bucket/path/to/data") == "my-bucket"
        assert Quilt3ElasticsearchBackend.normalize_bucket_name("") == ""

    def test_build_index_pattern_for_file_scope(self):
        """Test index pattern building for file scope."""
        # Single bucket
        assert self.backend.build_index_pattern_for_scope("file", ["bucket1"]) == "bucket1"

        # Multiple buckets
        assert self.backend.build_index_pattern_for_scope("file", ["bucket1", "bucket2"]) == "bucket1,bucket2"

        # Many buckets
        buckets = [f"bucket{i}" for i in range(10)]
        pattern = self.backend.build_index_pattern_for_scope("file", buckets)
        assert pattern == ",".join(buckets)
        assert "_packages" not in pattern

    def test_build_index_pattern_for_package_scope(self):
        """Test index pattern building for package scope."""
        # Single bucket
        assert self.backend.build_index_pattern_for_scope("packageEntry", ["bucket1"]) == "bucket1_packages"

        # Multiple buckets
        assert (
            self.backend.build_index_pattern_for_scope("packageEntry", ["bucket1", "bucket2"])
            == "bucket1_packages,bucket2_packages"
        )

        # Many buckets
        buckets = [f"bucket{i}" for i in range(10)]
        pattern = self.backend.build_index_pattern_for_scope("packageEntry", buckets)
        assert all(f"{b}_packages" in pattern for b in buckets)

    def test_build_index_pattern_for_global_scope(self):
        """Test index pattern building for global scope."""
        # Single bucket - should get both file and package indices
        pattern = self.backend.build_index_pattern_for_scope("global", ["bucket1"])
        assert pattern == "bucket1,bucket1_packages"

        # Multiple buckets - should get all file indices followed by all package indices
        pattern = self.backend.build_index_pattern_for_scope("global", ["bucket1", "bucket2"])
        parts = pattern.split(",")
        assert "bucket1" in parts
        assert "bucket2" in parts
        assert "bucket1_packages" in parts
        assert "bucket2_packages" in parts
        assert len(parts) == 4  # 2 file + 2 package

    def test_build_index_pattern_empty_bucket_list_raises(self):
        """Test that empty bucket list raises ValueError."""
        with pytest.raises(ValueError, match="Cannot build index pattern: bucket list is empty"):
            self.backend.build_index_pattern_for_scope("file", [])

    def test_build_index_pattern_invalid_scope_raises(self):
        """Test that invalid scope raises ValueError."""
        with pytest.raises(ValueError, match="Invalid scope"):
            self.backend.build_index_pattern_for_scope("invalid", ["bucket1"])


# ============================================================================
# Integration Tests (REAL AWS CALLS)
# ============================================================================


class TestBucketDiscovery:
    """Test REAL bucket discovery via GraphQL API."""

    def test_get_available_buckets_returns_list(self, backend):
        """Test that we can discover available buckets from catalog.

        This makes a REAL GraphQL call to:
        {registry_url}/graphql

        Query: { bucketConfigs { name } }
        """
        buckets = backend._get_available_buckets()

        # Must be a list
        assert isinstance(buckets, list), f"Expected list, got {type(buckets)}"

        # Should have at least one bucket (assuming authenticated)
        assert len(buckets) > 0, "No buckets discovered - check authentication"

        # All elements should be strings
        assert all(isinstance(b, str) for b in buckets), "All bucket names must be strings"

        # Bucket names should not be empty
        assert all(len(b) > 0 for b in buckets), "All bucket names must be non-empty"

        # Bucket names should not contain s3:// prefix
        assert all(not b.startswith("s3://") for b in buckets), "Bucket names should not have s3:// prefix"

        logger.info(f"✅ Discovered {len(buckets)} buckets: {buckets[:5]}...")


class TestIndexPatternBuilding:
    """Test REAL index pattern building with actual bucket discovery."""

    def test_build_index_pattern_specific_bucket_file_scope(self, backend, test_bucket):
        """Test building index pattern for specific bucket, file scope.

        Expected: "my-bucket" (single index, no _packages)
        """
        pattern = backend._build_index_pattern("file", test_bucket)

        assert pattern == test_bucket, f"Expected '{test_bucket}', got '{pattern}'"
        assert "_packages" not in pattern, "File scope should not include _packages"

    def test_build_index_pattern_specific_bucket_package_scope(self, backend, test_bucket):
        """Test building index pattern for specific bucket, package scope.

        Expected: "my-bucket_packages" (single index with _packages)
        """
        pattern = backend._build_index_pattern("packageEntry", test_bucket)

        expected = f"{test_bucket}_packages"
        assert pattern == expected, f"Expected '{expected}', got '{pattern}'"

    def test_build_index_pattern_specific_bucket_global_scope(self, backend, test_bucket):
        """Test building index pattern for specific bucket, global scope.

        Expected: "my-bucket,my-bucket_packages" (both indices)
        """
        pattern = backend._build_index_pattern("global", test_bucket)

        parts = pattern.split(",")
        assert len(parts) == 2, f"Expected 2 indices, got {len(parts)}"
        assert test_bucket in parts, f"Expected '{test_bucket}' in pattern"
        assert f"{test_bucket}_packages" in parts, f"Expected '{test_bucket}_packages' in pattern"

    def test_build_index_pattern_all_buckets_file_scope(self, backend):
        """Test building index pattern for all buckets, file scope.

        This makes a REAL GraphQL call to discover buckets.

        Expected: "bucket1,bucket2,bucket3,..." (comma-separated, no _packages)
        """
        pattern = backend._build_index_pattern("file", "")

        # Should be non-empty
        assert pattern, "Pattern should not be empty"

        # Should be comma-separated (unless only one bucket)
        parts = pattern.split(",")
        assert len(parts) > 0, "Pattern should have at least one index"

        # No _packages suffix in file scope
        assert all("_packages" not in p for p in parts), "File scope should not include _packages"

        # Should match discovered buckets
        discovered_buckets = backend._get_available_buckets()
        expected = ",".join(discovered_buckets)
        assert pattern == expected, f"Pattern mismatch:\nExpected: {expected}\nGot: {pattern}"

    def test_build_index_pattern_all_buckets_package_scope(self, backend):
        """Test building index pattern for all buckets, package scope.

        This makes a REAL GraphQL call to discover buckets.

        Expected: "bucket1_packages,bucket2_packages,..." (all with _packages)
        """
        pattern = backend._build_index_pattern("packageEntry", "")

        # Should be non-empty
        assert pattern, "Pattern should not be empty"

        # Should be comma-separated (unless only one bucket)
        parts = pattern.split(",")
        assert len(parts) > 0, "Pattern should have at least one index"

        # All should have _packages suffix
        assert all("_packages" in p for p in parts), "Package scope should include _packages for all indices"

        # Should match discovered buckets
        discovered_buckets = backend._get_available_buckets()
        expected = ",".join(f"{b}_packages" for b in discovered_buckets)
        assert pattern == expected, f"Pattern mismatch:\nExpected: {expected}\nGot: {pattern}"

    def test_build_index_pattern_all_buckets_global_scope(self, backend):
        """Test building index pattern for all buckets, global scope.

        This makes a REAL GraphQL call to discover buckets.

        Expected: "bucket1,bucket2,...,bucket1_packages,bucket2_packages,..." (mixed)
        """
        pattern = backend._build_index_pattern("global", "")

        # Should be non-empty
        assert pattern, "Pattern should not be empty"

        # Should be comma-separated
        parts = pattern.split(",")
        assert len(parts) > 0, "Pattern should have at least one index"

        # Should have both file and package indices
        discovered_buckets = backend._get_available_buckets()
        file_indices = [p for p in parts if "_packages" not in p]
        package_indices = [p for p in parts if "_packages" in p]

        assert len(file_indices) == len(discovered_buckets), (
            f"Expected {len(discovered_buckets)} file indices, got {len(file_indices)}"
        )
        assert len(package_indices) == len(discovered_buckets), (
            f"Expected {len(discovered_buckets)} package indices, got {len(package_indices)}"
        )

    def test_build_index_pattern_s3_uri_normalization(self, backend, test_bucket):
        """Test that s3:// URIs are normalized correctly."""
        # Test with s3:// prefix
        pattern1 = backend._build_index_pattern("file", f"s3://{test_bucket}")
        pattern2 = backend._build_index_pattern("file", test_bucket)

        assert pattern1 == pattern2, "s3:// prefix should be normalized"
        assert pattern1 == test_bucket, f"Expected '{test_bucket}', got '{pattern1}'"

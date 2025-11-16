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

import pytest
import logging
from typing import List, Set, Dict, Any
from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend
from quilt_mcp.services.quilt_service import QuiltService
from quilt_mcp.constants import DEFAULT_BUCKET

logger = logging.getLogger(__name__)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def quilt_service():
    """Get authenticated QuiltService instance."""
    return QuiltService()


@pytest.fixture
def backend(quilt_service):
    """Get initialized Elasticsearch backend."""
    backend = Quilt3ElasticsearchBackend(quilt_service=quilt_service)
    backend._initialize()
    return backend


@pytest.fixture
def default_bucket():
    """Return default bucket name (normalized), or skip test if not set."""
    if not DEFAULT_BUCKET:
        pytest.skip("QUILT_DEFAULT_BUCKET not set - required for this test")
    return DEFAULT_BUCKET.replace("s3://", "")


# ============================================================================
# Pure Function Tests (No AWS calls)
# ============================================================================

@pytest.mark.unit
class TestPureFunctions:
    """Test pure static methods with no side effects."""

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
        assert Quilt3ElasticsearchBackend.build_index_pattern_for_scope("file", ["bucket1"]) == "bucket1"

        # Multiple buckets
        assert Quilt3ElasticsearchBackend.build_index_pattern_for_scope("file", ["bucket1", "bucket2"]) == "bucket1,bucket2"

        # Many buckets
        buckets = [f"bucket{i}" for i in range(10)]
        pattern = Quilt3ElasticsearchBackend.build_index_pattern_for_scope("file", buckets)
        assert pattern == ",".join(buckets)
        assert "_packages" not in pattern

    def test_build_index_pattern_for_package_scope(self):
        """Test index pattern building for package scope."""
        # Single bucket
        assert Quilt3ElasticsearchBackend.build_index_pattern_for_scope("packageEntry", ["bucket1"]) == "bucket1_packages"

        # Multiple buckets
        assert Quilt3ElasticsearchBackend.build_index_pattern_for_scope("packageEntry", ["bucket1", "bucket2"]) == "bucket1_packages,bucket2_packages"

        # Many buckets
        buckets = [f"bucket{i}" for i in range(10)]
        pattern = Quilt3ElasticsearchBackend.build_index_pattern_for_scope("packageEntry", buckets)
        assert all(f"{b}_packages" in pattern for b in buckets)

    def test_build_index_pattern_for_global_scope(self):
        """Test index pattern building for global scope."""
        # Single bucket - should get both file and package indices
        pattern = Quilt3ElasticsearchBackend.build_index_pattern_for_scope("global", ["bucket1"])
        assert pattern == "bucket1,bucket1_packages"

        # Multiple buckets - should get all file indices followed by all package indices
        pattern = Quilt3ElasticsearchBackend.build_index_pattern_for_scope("global", ["bucket1", "bucket2"])
        parts = pattern.split(",")
        assert "bucket1" in parts
        assert "bucket2" in parts
        assert "bucket1_packages" in parts
        assert "bucket2_packages" in parts
        assert len(parts) == 4  # 2 file + 2 package

    def test_build_index_pattern_empty_bucket_list_raises(self):
        """Test that empty bucket list raises ValueError."""
        with pytest.raises(ValueError, match="Cannot build index pattern: bucket list is empty"):
            Quilt3ElasticsearchBackend.build_index_pattern_for_scope("file", [])

    def test_build_index_pattern_invalid_scope_raises(self):
        """Test that invalid scope raises ValueError."""
        with pytest.raises(ValueError, match="Invalid scope"):
            Quilt3ElasticsearchBackend.build_index_pattern_for_scope("invalid", ["bucket1"])


# ============================================================================
# Integration Tests (REAL AWS CALLS)
# ============================================================================

@pytest.mark.integration
@pytest.mark.search
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

    def test_default_bucket_in_available_buckets(self, backend, default_bucket):
        """Test that QUILT_DEFAULT_BUCKET appears in available buckets list."""
        buckets = backend._get_available_buckets()

        assert default_bucket in buckets, \
            f"Default bucket '{default_bucket}' not found in available buckets: {buckets}"

    def test_prioritize_buckets_moves_default_first(self, backend, default_bucket):
        """Test that _prioritize_buckets moves default bucket to front."""
        # Get all available buckets
        all_buckets = backend._get_available_buckets()

        # Ensure default bucket is in the list
        if default_bucket not in all_buckets:
            pytest.skip(f"Default bucket '{default_bucket}' not in available buckets")

        # Prioritize
        prioritized = backend._prioritize_buckets(all_buckets)

        # Default bucket should be first
        assert prioritized[0] == default_bucket, \
            f"Expected default bucket '{default_bucket}' first, got '{prioritized[0]}'"

        # Should have same buckets, just reordered
        assert set(prioritized) == set(all_buckets), "Prioritization changed bucket set"

    def test_prioritize_buckets_preserves_order_when_no_default(self, backend):
        """Test that _prioritize_buckets preserves order when default bucket not in list."""
        test_buckets = ["bucket-a", "bucket-b", "bucket-c"]

        # Prioritize without default bucket present
        prioritized = backend._prioritize_buckets(test_buckets)

        # Order should be preserved
        assert prioritized == test_buckets, "Order should be preserved when default not present"


@pytest.mark.integration
@pytest.mark.search
class TestIndexPatternBuilding:
    """Test REAL index pattern building with actual bucket discovery."""

    def test_build_index_pattern_specific_bucket_file_scope(self, backend, default_bucket):
        """Test building index pattern for specific bucket, file scope.

        Expected: "my-bucket" (single index, no _packages)
        """
        pattern = backend._build_index_pattern("file", default_bucket)

        assert pattern == default_bucket, f"Expected '{default_bucket}', got '{pattern}'"
        assert "_packages" not in pattern, "File scope should not include _packages"

    def test_build_index_pattern_specific_bucket_package_scope(self, backend, default_bucket):
        """Test building index pattern for specific bucket, package scope.

        Expected: "my-bucket_packages" (single index with _packages)
        """
        pattern = backend._build_index_pattern("packageEntry", default_bucket)

        expected = f"{default_bucket}_packages"
        assert pattern == expected, f"Expected '{expected}', got '{pattern}'"

    def test_build_index_pattern_specific_bucket_global_scope(self, backend, default_bucket):
        """Test building index pattern for specific bucket, global scope.

        Expected: "my-bucket,my-bucket_packages" (both indices)
        """
        pattern = backend._build_index_pattern("global", default_bucket)

        parts = pattern.split(",")
        assert len(parts) == 2, f"Expected 2 indices, got {len(parts)}"
        assert default_bucket in parts, f"Expected '{default_bucket}' in pattern"
        assert f"{default_bucket}_packages" in parts, f"Expected '{default_bucket}_packages' in pattern"

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
        prioritized = backend._prioritize_buckets(discovered_buckets)
        expected = ",".join(prioritized)
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
        prioritized = backend._prioritize_buckets(discovered_buckets)
        expected = ",".join(f"{b}_packages" for b in prioritized)
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

        assert len(file_indices) == len(discovered_buckets), \
            f"Expected {len(discovered_buckets)} file indices, got {len(file_indices)}"
        assert len(package_indices) == len(discovered_buckets), \
            f"Expected {len(discovered_buckets)} package indices, got {len(package_indices)}"

    def test_build_index_pattern_s3_uri_normalization(self, backend, default_bucket):
        """Test that s3:// URIs are normalized correctly."""
        # Test with s3:// prefix
        pattern1 = backend._build_index_pattern("file", f"s3://{default_bucket}")
        pattern2 = backend._build_index_pattern("file", default_bucket)

        assert pattern1 == pattern2, "s3:// prefix should be normalized"
        assert pattern1 == default_bucket, f"Expected '{default_bucket}', got '{pattern1}'"


@pytest.mark.integration
@pytest.mark.search
class TestIndexExistence:
    """Test that discovered indices ACTUALLY EXIST in Elasticsearch.

    These tests execute REAL searches to verify indices are accessible.
    """

    async def test_specific_bucket_file_index_exists(self, backend, default_bucket):
        """Test that file index for default bucket exists and is searchable."""
        # Build pattern
        pattern = backend._build_index_pattern("file", default_bucket)

        # Execute search with wildcard query
        response = await backend.search(
            query="*",
            scope="file",
            bucket=default_bucket,
            limit=10
        )

        # Should succeed (not error)
        assert response.status.value == "available", \
            f"Search failed with error: {response.error_message}"

        # Results should be files only
        for result in response.results:
            assert result.type == "file", \
                f"Expected type='file', got type='{result.type}' for result: {result.name}"
            assert result.bucket == default_bucket, \
                f"Expected bucket='{default_bucket}', got bucket='{result.bucket}'"

    async def test_specific_bucket_package_index_exists(self, backend, default_bucket):
        """Test that package index for default bucket exists and is searchable."""
        # Build pattern
        pattern = backend._build_index_pattern("packageEntry", default_bucket)

        # Execute search with wildcard query
        response = await backend.search(
            query="*",
            scope="packageEntry",
            bucket=default_bucket,
            limit=10
        )

        # Should succeed (not error)
        assert response.status.value == "available", \
            f"Search failed with error: {response.error_message}"

        # Results should be packages only (if any results)
        for result in response.results:
            assert result.type == "packageEntry", \
                f"Expected type='package', got type='{result.type}' for result: {result.name}"
            assert result.bucket == default_bucket, \
                f"Expected bucket='{default_bucket}', got bucket='{result.bucket}'"

    async def test_all_buckets_file_indices_exist(self, backend):
        """Test that file indices for all buckets are searchable."""
        # Build pattern (triggers bucket discovery)
        pattern = backend._build_index_pattern("file", "")

        # Execute search
        response = await backend.search(
            query="*",
            scope="file",
            bucket="",  # All buckets
            limit=50
        )

        # Should succeed (not error)
        assert response.status.value == "available", \
            f"Search failed with error: {response.error_message}"

        # Results should be files only
        for result in response.results:
            assert result.type == "file", \
                f"Expected type='file', got type='{result.type}'"

    async def test_all_buckets_package_indices_exist(self, backend):
        """Test that package indices for all buckets are searchable."""
        # Build pattern (triggers bucket discovery)
        pattern = backend._build_index_pattern("packageEntry", "")

        # Execute search
        response = await backend.search(
            query="*",
            scope="packageEntry",
            bucket="",  # All buckets
            limit=50
        )

        # Should succeed (not error)
        assert response.status.value == "available", \
            f"Search failed with error: {response.error_message}"

        # Results should be packages only (if any results)
        for result in response.results:
            assert result.type == "packageEntry", \
                f"Expected type='package', got type='{result.type}'"


@pytest.mark.integration
@pytest.mark.search
class TestIndexPatternValidation:
    """Test that built index patterns match actual Elasticsearch indices."""

    async def test_index_pattern_matches_search_results_metadata(self, backend, default_bucket):
        """Test that index pattern matches the '_index' field in search results.

        This verifies that:
        1. We build the correct index pattern
        2. Elasticsearch searches that pattern
        3. Results come from the expected indices
        """
        # File scope test
        response = await backend.search(
            query="*",
            scope="file",
            bucket=default_bucket,
            limit=10
        )

        # Extract unique indices from results
        result_indices = {r.metadata.get("_index") for r in response.results if r.metadata.get("_index")}

        # All results should be from the expected index (or its variants like reindex suffixes)
        for idx in result_indices:
            # Extract base bucket name from index
            bucket_from_index = backend.get_bucket_from_index(idx)
            assert bucket_from_index == default_bucket, \
                f"Result from unexpected index: {idx} (bucket: {bucket_from_index}, expected: {default_bucket})"

            # Should not be a package index
            assert not backend.is_package_index(idx), \
                f"File scope returned package index: {idx}"

    async def test_package_index_pattern_matches_search_results(self, backend, default_bucket):
        """Test that package index pattern matches actual package results."""
        response = await backend.search(
            query="*",
            scope="packageEntry",
            bucket=default_bucket,
            limit=10
        )

        # Extract unique indices from results
        result_indices = {r.metadata.get("_index") for r in response.results if r.metadata.get("_index")}

        # All results should be from package indices
        for idx in result_indices:
            # Should be a package index
            assert backend.is_package_index(idx), \
                f"Package scope returned non-package index: {idx}"

            # Extract base bucket name
            bucket_from_index = backend.get_bucket_from_index(idx)
            assert bucket_from_index == default_bucket, \
                f"Result from unexpected bucket: {bucket_from_index}, expected: {default_bucket}"


@pytest.mark.integration
@pytest.mark.search
class TestEdgeCases:
    """Test edge cases and error conditions."""

    async def test_nonexistent_bucket_returns_error_not_exception(self, backend):
        """Test that searching nonexistent bucket returns error, not exception."""
        response = await backend.search(
            query="test",
            scope="file",
            bucket="this-bucket-definitely-does-not-exist-12345",
            limit=10
        )

        # Should return error response (not raise exception)
        assert response.status.value == "error", \
            f"Expected error status for nonexistent bucket, got: {response.status.value}"
        assert response.error_message, "Error response should have error message"

    async def test_empty_bucket_parameter_discovers_all_buckets(self, backend):
        """Test that empty bucket parameter triggers discovery."""
        # Get expected bucket list
        expected_buckets = backend._get_available_buckets()
        assert len(expected_buckets) > 0, "Should have discovered buckets"

        # Build pattern with empty bucket
        pattern = backend._build_index_pattern("file", "")

        # Pattern should include all discovered buckets
        pattern_parts = pattern.split(",")
        assert len(pattern_parts) == len(expected_buckets), \
            f"Pattern should include all {len(expected_buckets)} buckets, got {len(pattern_parts)}"

    def test_build_index_pattern_with_reindex_suffix(self, backend):
        """Test that get_bucket_from_index handles reindex suffixes correctly."""
        # Test reindexed file index
        assert backend.get_bucket_from_index("my-bucket-reindex-v123") == "my-bucket"

        # Test reindexed package index
        assert backend.get_bucket_from_index("my-bucket_packages-reindex-v456") == "my-bucket"

        # Test standard indices
        assert backend.get_bucket_from_index("my-bucket") == "my-bucket"
        assert backend.get_bucket_from_index("my-bucket_packages") == "my-bucket"

    def test_is_package_index_detection(self, backend):
        """Test package index detection logic."""
        # Package indices
        assert backend.is_package_index("my-bucket_packages") is True
        assert backend.is_package_index("my-bucket_packages-reindex-v123") is True

        # File indices
        assert backend.is_package_index("my-bucket") is False
        assert backend.is_package_index("my-bucket-reindex-v456") is False

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

logger = logging.getLogger(__name__)
QUILT_TEST_BUCKET = os.getenv("QUILT_TEST_BUCKET", "")


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def backend():
    """Get Quilt3_Backend instance."""
    from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

    return Quilt3_Backend()


@pytest.fixture
def backend(quilt_service):
    """Get initialized Elasticsearch backend."""
    backend = Quilt3ElasticsearchBackend(quilt_service=quilt_service)
    backend._initialize()
    return backend


# ============================================================================
# Pure Function Tests (No AWS calls)
# ============================================================================


@pytest.mark.search
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


@pytest.mark.integration
@pytest.mark.search
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


@pytest.mark.integration
@pytest.mark.search
class TestIndexExistence:
    """Test that discovered indices ACTUALLY EXIST in Elasticsearch.

    These tests execute REAL searches to verify indices are accessible.
    """

    async def test_specific_bucket_file_index_exists(self, backend, test_bucket):
        """Test that file index for default bucket exists and is searchable."""
        # Build pattern
        pattern = backend._build_index_pattern("file", test_bucket)

        # Execute search with wildcard query
        response = await backend.search(query="*", scope="file", bucket=test_bucket, limit=10)

        # Should succeed (not error)
        assert response.status.value == "available", f"Search failed with error: {response.error_message}"

        # Results should be files only
        for result in response.results:
            assert result.type == "file", f"Expected type='file', got type='{result.type}' for result: {result.name}"
            assert result.bucket == test_bucket, f"Expected bucket='{test_bucket}', got bucket='{result.bucket}'"

    async def test_specific_bucket_package_index_exists(self, backend, test_bucket):
        """Test that package index for default bucket exists and is searchable."""
        # Build pattern
        pattern = backend._build_index_pattern("packageEntry", test_bucket)

        # Execute search with wildcard query
        response = await backend.search(query="*", scope="packageEntry", bucket=test_bucket, limit=10)

        # Should succeed (not error)
        assert response.status.value == "available", f"Search failed with error: {response.error_message}"

        # Results should be packages only (if any results)
        for result in response.results:
            assert result.type == "packageEntry", (
                f"Expected type='package', got type='{result.type}' for result: {result.name}"
            )
            assert result.bucket == test_bucket, f"Expected bucket='{test_bucket}', got bucket='{result.bucket}'"

    async def test_all_buckets_file_indices_exist(self, backend):
        """Test that file indices for all buckets are searchable."""
        # Build pattern (triggers bucket discovery)
        pattern = backend._build_index_pattern("file", "")

        # Execute search
        response = await backend.search(
            query="*",
            scope="file",
            bucket="",  # All buckets
            limit=50,
        )

        # Should succeed (not error)
        assert response.status.value == "available", f"Search failed with error: {response.error_message}"

        # Results should be files only
        for result in response.results:
            assert result.type == "file", f"Expected type='file', got type='{result.type}'"

    async def test_all_buckets_package_indices_exist(self, backend):
        """Test that package indices for all buckets are searchable."""
        # Build pattern (triggers bucket discovery)
        pattern = backend._build_index_pattern("packageEntry", "")

        # Execute search
        response = await backend.search(
            query="*",
            scope="packageEntry",
            bucket="",  # All buckets
            limit=50,
        )

        # Should succeed (not error)
        assert response.status.value == "available", f"Search failed with error: {response.error_message}"

        # Results should be packages only (if any results)
        for result in response.results:
            assert result.type == "packageEntry", f"Expected type='package', got type='{result.type}'"


@pytest.mark.integration
@pytest.mark.search
class TestIndexPatternValidation:
    """Test that built index patterns match actual Elasticsearch indices."""

    async def test_index_pattern_matches_search_results_metadata(self, backend, test_bucket):
        """Test that index pattern matches the '_index' field in search results.

        This verifies that:
        1. We build the correct index pattern
        2. Elasticsearch searches that pattern
        3. Results come from the expected indices
        """
        # File scope test
        response = await backend.search(query="*", scope="file", bucket=test_bucket, limit=10)

        # Extract unique indices from results
        result_indices = {r.metadata.get("_index") for r in response.results if r.metadata.get("_index")}

        # All results should be from the expected index (or its variants like reindex suffixes)
        for idx in result_indices:
            # Extract base bucket name from index
            bucket_from_index = backend.get_bucket_from_index(idx)
            assert bucket_from_index == test_bucket, (
                f"Result from unexpected index: {idx} (bucket: {bucket_from_index}, expected: {test_bucket})"
            )

            # Should not be a package index
            assert not backend.is_package_index(idx), f"File scope returned package index: {idx}"

    async def test_package_index_pattern_matches_search_results(self, backend, test_bucket):
        """Test that package index pattern matches actual package results."""
        response = await backend.search(query="*", scope="packageEntry", bucket=test_bucket, limit=10)

        # Extract unique indices from results
        result_indices = {r.metadata.get("_index") for r in response.results if r.metadata.get("_index")}

        # All results should be from package indices
        for idx in result_indices:
            # Should be a package index
            assert backend.is_package_index(idx), f"Package scope returned non-package index: {idx}"

            # Extract base bucket name
            bucket_from_index = backend.get_bucket_from_index(idx)
            assert bucket_from_index == test_bucket, (
                f"Result from unexpected bucket: {bucket_from_index}, expected: {test_bucket}"
            )


@pytest.mark.integration
@pytest.mark.search
class TestScopeHandlerParsing:
    """Test that scope handlers can parse actual documents from Elasticsearch.

    These tests verify the CRITICAL parsing logic that was previously untested:
    - FileScopeHandler parses file documents correctly
    - PackageEntryScopeHandler parses package documents correctly
    - Handlers validate documents and return None for invalid ones
    """

    async def test_file_scope_handler_parses_real_documents(self, backend, test_bucket):
        """Test FileScopeHandler can parse actual file documents from Elasticsearch."""
        # Get a real file document - try different queries
        # Note: Wildcard * might not return results in some ES configurations
        queries = ["*", "csv", "json", "txt", "data", ""]

        response = await backend.search(query="*", scope="file", bucket=test_bucket, limit=10)
        for query in queries:
            response = await backend.search(query=query if query else "*", scope="file", bucket=test_bucket, limit=10)
            if len(response.results) > 0:
                break

        # Should have at least one result
        assert response.status.value == "available", f"Search failed: {response.error_message}"

        # MUST have results - if bucket is empty, that's a test environment problem
        assert len(response.results) > 0, (
            f"CRITICAL: No files found in {test_bucket} after trying {len(queries)} queries. "
            f"Cannot test FileScopeHandler parsing without real data. "
            f"Please ensure bucket has indexed files."
        )

        result = response.results[0]

        # Verify FileScopeHandler produced valid SearchResult
        assert result.type == "file", f"Expected type='file', got type='{result.type}'"
        assert result.name, "File result must have 'name' field (the object key)"
        assert result.title, "File result must have 'title' field"
        assert result.bucket == test_bucket, f"Expected bucket='{test_bucket}', got '{result.bucket}'"
        assert result.s3_uri, "File result must have s3_uri"
        assert result.s3_uri.startswith(f"s3://{test_bucket}/"), (
            f"s3_uri should start with 's3://{test_bucket}/', got: {result.s3_uri}"
        )

        # Verify required fields are present
        assert result.id, "File result must have ID"
        assert result.backend == "elasticsearch", "Backend should be 'elasticsearch'"
        assert isinstance(result.size, int), "Size should be an integer"
        assert isinstance(result.score, float), "Score should be a float"

        # Verify metadata contains _index field
        assert "_index" in result.metadata, "Metadata should contain '_index' field"
        assert not backend.is_package_index(result.metadata["_index"]), (
            "File scope should not return results from package index"
        )

        logger.info(f"✅ FileScopeHandler successfully parsed: {result.name}")

    async def test_package_entry_handler_parses_real_documents(self, backend, test_bucket):
        """Test PackageEntryScopeHandler can parse actual package ENTRY documents ONLY.

        CRITICAL: PackageEntryScopeHandler ONLY processes ENTRY documents.
        Manifest documents (ptr_name, mnfst_name) are REJECTED and should NOT appear in results.

        Package ENTRY documents have fields:
        - entry_pk: Package name with hash (e.g., "my/package@abc123")
        - entry_lk: Logical key (file path within package)
        - entry_size: Size of the entry file
        - entry_hash: Hash of the entry file
        - entry_metadata: Metadata including last_modified
        """
        # Get real package ENTRY documents
        response = await backend.search(query="*", scope="packageEntry", bucket=test_bucket, limit=20)

        # Should have at least one result
        assert response.status.value == "available", f"Search failed: {response.error_message}"

        # MUST have results - if no package entries exist, that's a test environment problem
        assert len(response.results) > 0, (
            f"CRITICAL: No package ENTRY documents found in {test_bucket}. "
            f"Cannot test PackageEntryScopeHandler parsing without real entry data. "
            f"Please ensure bucket has indexed packages with entries (not just manifests)."
        )

        # CRITICAL: ALL results must be ENTRY documents (no manifests allowed)
        for result in response.results:
            source = result.metadata

            # MUST have entry fields
            assert "entry_pk" in source or "entry_lk" in source, (
                f"PackageEntryScopeHandler returned non-entry document! "
                f"Document ID: {result.id}, Available fields: {list(source.keys())[:10]}"
            )

            # MUST NOT have manifest fields (they should be filtered out)
            if "ptr_name" in source or "mnfst_name" in source:
                raise AssertionError(
                    f"CRITICAL BUG: PackageEntryScopeHandler returned manifest document! "
                    f"Manifests should be REJECTED. Document ID: {result.id}, "
                    f"ptr_name: {source.get('ptr_name')}, mnfst_name: {source.get('mnfst_name')}"
                )

        logger.info(f"✅ All {len(response.results)} results are ENTRY documents (no manifests)")

        # Test first entry result in detail
        test_result = response.results[0]

        # Verify PackageEntryScopeHandler produced valid SearchResult
        assert test_result.type == "packageEntry", f"Expected type='packageEntry', got type='{test_result.type}'"

        # Entry name should be entry_lk (file path) or entry_pk
        assert test_result.name, (
            f"Entry result must have 'name' field (entry_lk or entry_pk). "
            f"Available fields: {list(test_result.metadata.keys())[:10]}"
        )

        # Entry title should be filename (last part of entry_lk)
        assert test_result.title, "Entry result must have 'title' field"

        assert test_result.bucket == test_bucket, f"Expected bucket='{test_bucket}', got '{test_result.bucket}'"

        # Verify required fields are present
        assert test_result.id, "Entry result must have ID"
        assert test_result.backend == "elasticsearch", "Backend should be 'elasticsearch'"
        assert isinstance(test_result.size, int), "Size should be an integer"
        assert isinstance(test_result.score, float), "Score should be a float"

        # S3 URI should point to the actual entry file (not .quilt/packages/)
        if test_result.s3_uri:
            assert test_result.s3_uri.startswith(f"s3://{test_bucket}/"), (
                f"Entry s3_uri should point to actual file, got: {test_result.s3_uri}"
            )
            assert ".quilt/packages" not in test_result.s3_uri, (
                f"Entry s3_uri should NOT point to package manifest, got: {test_result.s3_uri}"
            )

        # Verify metadata contains _index field and it's a package index
        assert "_index" in test_result.metadata, "Metadata should contain '_index' field"
        assert backend.is_package_index(test_result.metadata["_index"]), (
            f"Package scope should return results from package index, got: {test_result.metadata['_index']}"
        )

        # Log entry document info
        logger.info(f"✅ PackageEntryScopeHandler parsed ENTRY document: {test_result.name}")
        if test_result.metadata.get("entry_pk"):
            logger.info(f"   entry_pk: {test_result.metadata['entry_pk']}")
        if test_result.metadata.get("entry_lk"):
            logger.info(f"   entry_lk: {test_result.metadata['entry_lk']}")
        if test_result.metadata.get("package_name"):
            logger.info(f"   package_name: {test_result.metadata['package_name']}")

        # Verify extracted package name
        if "package_name" in test_result.metadata:
            assert test_result.metadata["package_name"], "Extracted package_name should not be empty"

    async def test_global_scope_handler_parses_both_types(self, backend, test_bucket):
        """Test GlobalScopeHandler can parse both file and package documents."""
        # Get mixed results - try different queries
        queries = ["*", "csv", "json", "txt", "data", ""]

        response = await backend.search(query="*", scope="global", bucket=test_bucket, limit=20)
        for query in queries:
            response = await backend.search(
                query=query if query else "*", scope="global", bucket=test_bucket, limit=20
            )
            if len(response.results) > 0:
                break

        # Should have at least one result
        assert response.status.value == "available", f"Search failed: {response.error_message}"

        # MUST have results - if bucket is empty, that's a test environment problem
        assert len(response.results) > 0, (
            f"CRITICAL: No results found in {test_bucket} after trying {len(queries)} queries. "
            f"Cannot test GlobalScopeHandler parsing without real data. "
            f"Please ensure bucket has indexed content."
        )

        # Categorize results by type
        file_results = [r for r in response.results if r.type == "file"]
        package_results = [r for r in response.results if r.type == "packageEntry"]

        # MUST have at least one file result (files are ubiquitous in S3)
        assert len(file_results) > 0, (
            f"CRITICAL: Global scope returned {len(response.results)} results but ZERO files. "
            f"This indicates a serious problem with file indexing or scope handler."
        )

        # Verify file results are valid
        for result in file_results:
            assert result.name, "File result must have name"
            assert result.bucket == test_bucket
            assert result.s3_uri.startswith(f"s3://{test_bucket}/")
            assert not backend.is_package_index(result.metadata.get("_index", "")), (
                "File results should not come from package indices"
            )

        # Verify package results are valid (if any)
        for result in package_results:
            assert result.name, "Package result must have name"
            assert result.bucket == test_bucket
            if result.s3_uri:
                assert ".quilt/packages" in result.s3_uri
            assert backend.is_package_index(result.metadata.get("_index", "")), (
                "Package results should come from package indices"
            )

        logger.info(f"✅ GlobalScopeHandler parsed {len(file_results)} files and {len(package_results)} packages")

    async def test_handler_validation_filters_invalid_documents(self, backend, test_bucket):
        """Test that handlers return None for invalid documents (filtered out).

        This is harder to test in integration since we can't inject invalid docs,
        but we can verify the validation logic exists and handles edge cases.
        """
        # Search for packages - should only return valid documents
        response = await backend.search(query="*", scope="packageEntry", bucket=test_bucket, limit=10)

        # All returned results should be valid
        for result in response.results:
            # PackageEntryScopeHandler requires name field (ptr_name, mnfst_name, entry_pk, or entry_lk)
            assert result.name, f"Handler validation failed: package result missing name. Result: {result}"

            # Should have package type
            assert result.type == "packageEntry", f"Handler validation failed: wrong type '{result.type}'"

            # Should come from package index
            assert backend.is_package_index(result.metadata.get("_index", "")), (
                "Handler validation failed: result not from package index"
            )

        logger.info(f"✅ Handler validation: all {len(response.results)} package results are valid")


@pytest.mark.integration
@pytest.mark.search
class TestEdgeCases:
    """Test edge cases and error conditions."""

    async def test_nonexistent_bucket_returns_error_not_exception(self, backend):
        """Test that searching nonexistent bucket returns error, not exception."""
        response = await backend.search(
            query="test", scope="file", bucket="this-bucket-definitely-does-not-exist-12345", limit=10
        )

        # Should return error response (not raise exception)
        assert response.status.value == "error", (
            f"Expected error status for nonexistent bucket, got: {response.status.value}"
        )
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
        assert len(pattern_parts) == len(expected_buckets), (
            f"Pattern should include all {len(expected_buckets)} buckets, got {len(pattern_parts)}"
        )

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

"""Real integration tests for Elasticsearch package scope.

These tests verify the INTELLIGENT package scope implementation that:
1. Searches both manifests AND entries in package indices
2. Groups results by package name (one result per package)
3. Returns matched entry information aggregated
4. Uses boosting to prefer packages where manifest fields match

Based on spec: spec/a07-search-catalog/24-intelligent-package-scope-spec.md

IMPORTANT LIMITATION:
The Quilt Elasticsearch backend does not currently support the collapse feature.
Tests that require collapse functionality are marked as expected failures (xfail)
until backend support is added.

No mocks. Real AWS. Real Elasticsearch. Real package data.
"""

import os
import pytest
import logging
from typing import List
from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend

pytestmark = pytest.mark.usefixtures("requires_search")

logger = logging.getLogger(__name__)
QUILT_TEST_BUCKET = os.getenv("QUILT_TEST_BUCKET", "")

# Check if Elasticsearch backend supports collapse
# This will be used to mark tests as xfail if collapse is not supported
ELASTICSEARCH_SUPPORTS_COLLAPSE = False  # Set to False until backend adds support

# Helper decorator for tests that require collapse support
requires_collapse = pytest.mark.xfail(
    not ELASTICSEARCH_SUPPORTS_COLLAPSE,
    reason="Elasticsearch backend does not support collapse feature yet",
    raises=AssertionError,
)


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
# Integration Tests - Package Scope Behavior
# ============================================================================


class TestPackageScopeIntegration:
    """Integration tests for intelligent package scope.

    These tests run against REAL Elasticsearch indices and verify:
    - Package-centric results (not individual files)
    - Grouping by package name (no duplicates)
    - Matched entry information included
    - Complex query support
    """

    @requires_collapse
    async def test_package_scope_basic_search(self, backend, test_bucket):
        """Should search packages and return package-centric results.

        This test verifies:
        - Package scope executes successfully
        - Returns results with type="package"
        - Each result has required package fields (ptr_name)
        - Results include matched_entry_count metadata

        REQUIRES: Elasticsearch collapse support
        """
        response = await backend.search(query="*", scope="package", bucket=test_bucket, limit=10)

        # Should succeed
        assert response.status.value == "available", f"Package search failed: {response.error_message}"

        # Should return results (assuming bucket has packages)
        assert len(response.results) > 0, (
            f"No packages found in {test_bucket}. Bucket must have indexed packages for this test."
        )

        logger.info(f"Found {len(response.results)} packages in {test_bucket}")

        # All results should be packages
        for result in response.results:
            assert result.type == "package", (
                f"Expected type='package', got type='{result.type}' for result: {result.name}"
            )

            # Should have package name (ptr_name)
            assert result.metadata.get("ptr_name"), f"Package result missing ptr_name: {result.id}"

            # Should have matched entry count (even if 0)
            assert "matched_entry_count" in result.metadata, (
                f"Package result missing matched_entry_count: {result.name}"
            )

            # Should have showing_entries field
            assert "showing_entries" in result.metadata, f"Package result missing showing_entries: {result.name}"

            # Should have matched_entries list (may be empty)
            assert "matched_entries" in result.metadata, f"Package result missing matched_entries: {result.name}"

            logger.debug(
                f"Package: {result.name}, "
                f"matched_entries: {result.metadata['matched_entry_count']}, "
                f"showing: {result.metadata['showing_entries']}"
            )

    @requires_collapse
    async def test_package_scope_with_file_filter(self, backend, test_bucket):
        """Should find packages containing specific file types.

        This test verifies:
        - Can query for specific file extensions (csv, json, etc.)
        - Results are packages (not individual files)
        - Matched entries may include files matching the query
        """
        # Search for packages with CSV files
        response = await backend.search(query="csv", scope="package", bucket=test_bucket, limit=10)

        assert response.status.value in ["available", "not_found"], (
            f"Package search with filter failed: {response.error_message}"
        )

        # If we have results, verify structure
        if len(response.results) > 0:
            logger.info(f"Found {len(response.results)} packages matching 'csv'")

            for result in response.results:
                assert result.type == "package", f"Expected package results, got: {result.type}"

                # Check if matched entries include CSV files or if query matched package name
                matched_entries = result.metadata.get("matched_entries", [])

                # Log what we found
                if matched_entries:
                    csv_entries = [e for e in matched_entries if e.get("entry_lk", "").lower().endswith(".csv")]
                    if csv_entries:
                        logger.debug(f"Package {result.name} has {len(csv_entries)} CSV files in matched entries")
                    else:
                        logger.debug(f"Package {result.name} matched 'csv' in package name or metadata")

        else:
            logger.warning(
                f"No packages found with 'csv' query in {test_bucket}. "
                f"Test cannot verify file filter behavior without data."
            )

    @requires_collapse
    async def test_package_scope_groups_by_package(self, backend, test_bucket):
        """Should return one result per package, not per file.

        This test verifies the key grouping behavior:
        - Each package appears only once in results
        - No duplicate package names
        - Multiple matched files are aggregated into matched_entries
        """
        # Search for something likely to match multiple files
        response = await backend.search(query="*", scope="package", bucket=test_bucket, limit=20)

        assert response.status.value == "available", f"Package search failed: {response.error_message}"

        assert len(response.results) > 0, f"No packages found in {test_bucket}"

        # Extract package names (ptr_name from metadata)
        package_names = [r.metadata.get("ptr_name") for r in response.results]

        # No duplicate package names
        assert len(package_names) == len(set(package_names)), (
            f"Found duplicate package names in results: {package_names}"
        )

        logger.info(f"✅ Grouping verified: {len(package_names)} unique packages, no duplicates")

        # Check if any packages have multiple matched entries (confirms aggregation)
        packages_with_multiple_entries = [r for r in response.results if r.metadata.get("matched_entry_count", 0) > 1]

        if packages_with_multiple_entries:
            example = packages_with_multiple_entries[0]
            logger.info(
                f"✅ Aggregation verified: Package '{example.name}' has "
                f"{example.metadata['matched_entry_count']} matched entries "
                f"(showing {example.metadata['showing_entries']})"
            )
        else:
            logger.warning(
                "Could not verify aggregation - no packages with multiple matched entries. "
                "This may be expected if packages are small or query is specific."
            )

    @requires_collapse
    async def test_package_scope_vs_packageEntry_scope(self, backend, test_bucket):
        """Package scope should return fewer, grouped results vs packageEntry.

        This test verifies the difference between scopes:
        - package: Returns packages (grouped by package name)
        - packageEntry: Returns individual files

        Expected:
        - Package results have type="package" and ptr_name
        - Entry results have type="packageEntry" and entry_pk/entry_lk
        - Package results should be fewer (grouped) than entry results
        """
        query = "*"

        # Get package results (grouped)
        package_response = await backend.search(query=query, scope="package", bucket=test_bucket, limit=10)

        # Get entry results (individual files)
        entry_response = await backend.search(query=query, scope="packageEntry", bucket=test_bucket, limit=10)

        # Both should succeed
        assert package_response.status.value == "available", f"Package search failed: {package_response.error_message}"
        assert entry_response.status.value == "available", f"Entry search failed: {entry_response.error_message}"

        logger.info(f"Comparison: {len(package_response.results)} packages vs {len(entry_response.results)} entries")

        # Package results are packages
        for result in package_response.results:
            assert result.type == "package", f"Package scope returned non-package result: {result.type}"
            assert result.metadata.get("ptr_name"), f"Package result missing ptr_name: {result.id}"
            assert "matched_entries" in result.metadata, f"Package result missing matched_entries: {result.name}"

        # Entry results are files
        for result in entry_response.results:
            assert result.type == "packageEntry", f"PackageEntry scope returned non-entry result: {result.type}"
            # Entry results should have entry_pk or entry_lk
            has_entry_fields = result.metadata.get("entry_pk") or result.metadata.get("entry_lk")
            assert has_entry_fields, f"Entry result missing entry_pk/entry_lk: {result.id}"

        logger.info("✅ Package scope returns packages, packageEntry scope returns files")

    @requires_collapse
    async def test_package_scope_matched_entries_structure(self, backend, test_bucket):
        """Should include properly structured matched entry information.

        This test verifies:
        - matched_entries is a list in metadata
        - matched_entry_count is an integer
        - showing_entries is an integer
        - Each entry in matched_entries has expected fields
        """
        response = await backend.search(query="*", scope="package", bucket=test_bucket, limit=5)

        assert response.status.value == "available", f"Package search failed: {response.error_message}"

        assert len(response.results) > 0, f"No packages found in {test_bucket}"

        # Check structure of matched entries
        for result in response.results:
            metadata = result.metadata

            # Should have entry count fields
            assert "matched_entry_count" in metadata, f"Missing matched_entry_count in {result.name}"
            assert "showing_entries" in metadata, f"Missing showing_entries in {result.name}"

            # Counts should be integers
            assert isinstance(metadata["matched_entry_count"], int), (
                f"matched_entry_count should be int, got {type(metadata['matched_entry_count'])}"
            )
            assert isinstance(metadata["showing_entries"], int), (
                f"showing_entries should be int, got {type(metadata['showing_entries'])}"
            )

            # Should have matched_entries list
            assert "matched_entries" in metadata, f"Missing matched_entries in {result.name}"
            assert isinstance(metadata["matched_entries"], list), (
                f"matched_entries should be list, got {type(metadata['matched_entries'])}"
            )

            # showing_entries should match list length
            assert metadata["showing_entries"] == len(metadata["matched_entries"]), (
                f"showing_entries ({metadata['showing_entries']}) != "
                f"len(matched_entries) ({len(metadata['matched_entries'])})"
            )

            # If we have entries, check their structure
            if metadata["matched_entries"]:
                logger.info(
                    f"Package {result.name}: {metadata['matched_entry_count']} total, "
                    f"{metadata['showing_entries']} showing"
                )

                for idx, entry in enumerate(metadata["matched_entries"][:3]):  # Check first 3
                    # Each entry should be a dict
                    assert isinstance(entry, dict), f"Entry should be dict, got {type(entry)}"

                    # Should have entry_lk (logical key / file path)
                    # entry_pk is optional, entry_lk is the primary identifier
                    assert "entry_lk" in entry or "entry_pk" in entry, f"Entry missing entry_lk and entry_pk: {entry}"

                    logger.debug(f"  Entry {idx}: {entry.get('entry_lk', entry.get('entry_pk'))}")

        logger.info("✅ All matched_entries structures are valid")

    @requires_collapse
    async def test_package_scope_empty_results(self, backend, test_bucket):
        """Should handle queries with no results gracefully.

        This test verifies:
        - Non-matching queries return empty results (not errors)
        - Response structure is valid even with no results
        """
        response = await backend.search(
            query="xyznonexistentquery12345", scope="package", bucket=test_bucket, limit=10
        )

        # Should succeed but return no results (or not_found status)
        assert response.status.value in ["available", "not_found"], (
            f"Empty query should not error, got: {response.status.value}"
        )

        assert len(response.results) == 0, (
            f"Non-matching query should return empty results, got {len(response.results)}"
        )

        logger.info("✅ Empty results handled gracefully")

    @requires_collapse
    async def test_package_scope_complex_query(self, backend, test_bucket):
        """Should handle complex boolean queries.

        This test verifies:
        - Boolean operators (AND, OR) work correctly
        - Parentheses for grouping work
        - Complex queries execute without errors
        """
        # Test various query patterns
        queries = [
            "csv OR json",
            "data AND csv",
            "(csv OR json) AND data",
        ]

        for query in queries:
            logger.info(f"Testing query: {query}")

            response = await backend.search(query=query, scope="package", bucket=test_bucket, limit=5)

            # Should execute without error
            assert response.status.value in ["available", "not_found"], (
                f"Query '{query}' failed: {response.error_message}"
            )

            # If we get results, verify they're packages
            for result in response.results:
                assert result.type == "package", f"Query '{query}' returned non-package result: {result.type}"

            logger.info(f"  Query '{query}': {len(response.results)} packages found")

        logger.info("✅ All complex queries executed successfully")

    @requires_collapse
    async def test_package_scope_description_format(self, backend, test_bucket):
        """Should format package descriptions properly.

        This test verifies:
        - Description includes package name
        - Description includes tag (if present)
        - Description includes matched file count
        - Description is human-readable
        """
        response = await backend.search(query="*", scope="package", bucket=test_bucket, limit=5)

        assert response.status.value == "available", f"Package search failed: {response.error_message}"

        assert len(response.results) > 0, f"No packages found in {test_bucket}"

        for result in response.results:
            description = result.description

            # Should have a description
            assert description, f"Package {result.name} has no description"

            # Should start with "Package:"
            assert description.startswith("Package:"), f"Description should start with 'Package:', got: {description}"

            # Should include package name
            ptr_name = result.metadata.get("ptr_name", "")
            assert ptr_name in description, f"Description should include ptr_name '{ptr_name}', got: {description}"

            # If there are matched entries, should mention count
            matched_count = result.metadata.get("matched_entry_count", 0)
            if matched_count > 0:
                assert "matched file" in description.lower(), (
                    f"Description should mention matched files when count > 0, got: {description}"
                )
                assert str(matched_count) in description, (
                    f"Description should include count {matched_count}, got: {description}"
                )

            logger.debug(f"Description: {description}")

        logger.info("✅ All package descriptions properly formatted")

    @requires_collapse
    async def test_package_scope_s3_uri_format(self, backend, test_bucket):
        """Should generate correct S3 URIs to package manifests.

        This test verifies:
        - S3 URI points to .quilt/packages/ (manifest location)
        - S3 URI includes manifest hash (mnfst_name)
        - S3 URI format is valid
        """
        response = await backend.search(query="*", scope="package", bucket=test_bucket, limit=5)

        assert response.status.value == "available", f"Package search failed: {response.error_message}"

        assert len(response.results) > 0, f"No packages found in {test_bucket}"

        for result in response.results:
            s3_uri = result.s3_uri

            # Should have S3 URI
            assert s3_uri, f"Package {result.name} has no s3_uri"

            # Should point to .quilt/packages/
            assert ".quilt/packages" in s3_uri, f"Package s3_uri should point to .quilt/packages/, got: {s3_uri}"

            # Should start with s3://bucket/
            assert s3_uri.startswith(f"s3://{test_bucket}/"), (
                f"s3_uri should start with 's3://{test_bucket}/', got: {s3_uri}"
            )

            # Should include manifest hash
            mnfst_name = result.metadata.get("mnfst_name", "")
            if mnfst_name:
                assert mnfst_name in s3_uri, f"s3_uri should include manifest hash '{mnfst_name}', got: {s3_uri}"

            logger.debug(f"S3 URI: {s3_uri}")

        logger.info("✅ All S3 URIs properly formatted")

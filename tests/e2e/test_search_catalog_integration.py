"""Real integration tests for search_catalog with actual Elasticsearch backend.

These tests make REAL API calls to Elasticsearch and verify ACTUAL search results.
No mocks. Real data. Real pain.

CRITICAL REQUIREMENT: Every test MUST return non-zero results with proper schemas.
Tests that pass with zero results are BROKEN and hide bugs.
"""

import pytest

from quilt_mcp.tools.search import search_catalog
from tests.e2e.search_catalog_helpers import diagnostic_search

pytestmark = pytest.mark.usefixtures("requires_search")


class TestSearchCatalogIntegration:
    """Integration tests for search_catalog using real Elasticsearch.

    CRITICAL: These tests REQUIRE non-zero results. Tests that pass with
    zero results are BROKEN and will hide bugs in scope filtering.
    """

    def test_package_scope_MUST_ONLY_return_packages_NOT_files(self):
        """CRITICAL BUG TEST: Package scope must ONLY return type='package', NEVER files.

        This test reproduces the bug where scope='package' was returning file results.
        Uses 'ccle' query which is KNOWN to match both files and packages in test data.
        """
        result = search_catalog(
            query="ccle",
            scope="packageEntry",  # PACKAGE SCOPE
            bucket="",  # All buckets
            limit=50,
        )

        # Must be successful
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result.get("success"), f"Search failed: {result.get('error')}"

        # MUST have results
        assert "results" in result, "Must have 'results' field"
        assert isinstance(result["results"], list), "Results must be a list"

        # REQUIRE non-zero results - this query MUST find packages
        assert len(result["results"]) > 0, (
            "CRITICAL: Query 'ccle' with scope='package' returned ZERO results. "
            "This means test data is missing or query is broken."
        )

        # EVERY result MUST be a package (not file)
        for idx, res in enumerate(result["results"]):
            assert "type" in res, f"Result {idx} missing 'type' field: {res}"

            # THIS IS THE BUG FIX: Package scope MUST ONLY return packages
            assert res["type"] == "packageEntry", (
                f"PACKAGE SCOPE BUG: Result {idx} has type='{res['type']}' but scope='package' "
                f"should ONLY return type='package'\nResult: {res}"
            )

    def test_file_scope_MUST_ONLY_return_files_NOT_packages(self):
        """CRITICAL: File scope must ONLY return type='file', NEVER packages.

        Uses 'csv' query which is KNOWN to match file data in test environment.
        """
        result = search_catalog(
            query="csv",
            scope="file",  # FILE SCOPE
            bucket="",  # All buckets
            limit=50,
        )

        # Must be successful
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result.get("success"), f"Search failed: {result.get('error')}"

        # MUST have results
        assert "results" in result, "Must have 'results' field"
        assert isinstance(result["results"], list), "Results must be a list"

        # REQUIRE non-zero results
        assert len(result["results"]) > 0, (
            "CRITICAL: Query 'csv' with scope='file' returned ZERO results. "
            "This means test data is missing or query is broken."
        )

        # EVERY result MUST be a file (not package)
        for idx, res in enumerate(result["results"]):
            assert "type" in res, f"Result {idx} missing 'type' field: {res}"

            # File scope should only return files
            assert res["type"] == "file", (
                f"FILE SCOPE BUG: Result {idx} has type='{res['type']}' but scope='file' "
                f"should ONLY return type='file'\nResult: {res}"
            )

    def test_file_scope_specific_bucket_returns_only_files(self, test_bucket):
        """File scope with specific bucket must return ONLY files."""
        result = search_catalog(
            query="csv",
            scope="file",
            bucket=test_bucket,
            limit=10,
        )

        # Must be successful
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result.get("success"), f"Search failed: {result.get('error')}"

        # MUST have results field
        assert "results" in result, "Success response must have 'results' field"
        assert isinstance(result["results"], list), "Results must be a list"

        # REQUIRE non-zero results - test MUST fail if no results
        assert len(result["results"]) > 0, (
            f"FILE SCOPE TEST FAILURE: Must return at least 1 file result from bucket {test_bucket}. Got 0 results."
        )

        # Verify EVERY result is a file (not just the first one)
        for idx, res in enumerate(result["results"]):
            assert "type" in res, f"Result {idx} must have 'type' field"
            assert res["type"] == "file", (
                f"FILE SCOPE BUG: Result {idx} has type='{res['type']}' but scope='file' should ONLY return type='file'"
            )
            assert "bucket" in res, f"Result {idx} must have 'bucket' field"

    def test_package_scope_specific_bucket_returns_only_packages(self, test_bucket):
        """Package scope with specific bucket must return ONLY packages."""
        with diagnostic_search(
            test_name="test_package_scope_specific_bucket_returns_only_packages",
            query="*",
            scope="package",
            bucket=test_bucket,
            limit=10,
        ) as result:
            # Must be successful
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            assert result.get("success"), f"Search failed: {result.get('error')}"

            # MUST have results field
            assert "results" in result, "Success response must have 'results' field"
            assert isinstance(result["results"], list), "Results must be a list"

            # REQUIRE non-zero results - test MUST fail if no results
            assert len(result["results"]) > 0, (
                f"PACKAGE SCOPE TEST FAILURE: Must return at least 1 package result from bucket {test_bucket}. Got 0 results."
            )

            # Verify EVERY result is a package (not just the first one)
            for idx, res in enumerate(result["results"]):
                assert "type" in res, f"Result {idx} must have 'type' field"
                assert res["type"] == "package", (
                    f"PACKAGE SCOPE BUG: Result {idx} has type='{res['type']}' but scope='package' should ONLY return type='package'"
                )
                assert "/" in res.get("name", ""), (
                    f"Result {idx}: Package name should have namespace/name format: {res.get('name')}"
                )
                # Package scope returns grouped package results, so s3_uri may point to manifest or be synthetic
                assert res.get("s3_uri") is not None, f"Result {idx}: Package result must have s3_uri field"

    def test_nonexistent_bucket_returns_error_not_exception(self):
        """Search in nonexistent bucket must return error dict, NOT raise exception."""
        result = search_catalog(
            query="test",
            scope="file",
            bucket="this-bucket-definitely-does-not-exist-12345",
            limit=10,
        )

        # CRITICAL: Must be a dict, not an exception
        assert isinstance(result, dict), "Search must return dict even on error, not raise exception"

        # Must have success field set to False
        assert "success" in result, "Error response must have 'success' field"
        assert result["success"] is False, "Error response must have success=False"

        # Must have error field
        assert "error" in result, "Error response must have 'error' field"
        assert isinstance(result["error"], str), "Error must be a string"
        assert len(result["error"]) > 0, "Error message must not be empty"

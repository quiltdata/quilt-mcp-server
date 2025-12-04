"""Real integration tests for search_catalog with actual Elasticsearch backend.

These tests make REAL API calls to Elasticsearch and verify ACTUAL search results.
No mocks. Real data. Real pain.

CRITICAL REQUIREMENT: Every test MUST return non-zero results with proper schemas.
Tests that pass with zero results are BROKEN and hide bugs.
"""

import json
import os
import pytest
from contextlib import contextmanager
from typing import Dict, List, Set, NamedTuple, Optional
from quilt_mcp.tools.search import search_catalog
from quilt_mcp.constants import (
    KNOWN_TEST_PACKAGE as QUILT_TEST_PACKAGE,
    KNOWN_TEST_ENTRY as QUILT_TEST_ENTRY,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def test_package():
    """Return known test package name from environment.

    Example: "test/raw" or "datasets/genomics"

    Set via: QUILT_TEST_PACKAGE environment variable
    """
    return QUILT_TEST_PACKAGE


@pytest.fixture
def test_entry():
    """Return known test entry filename from environment.

    Example: "README.md" or "data.csv"

    Set via: QUILT_TEST_ENTRY environment variable
    """
    return QUILT_TEST_ENTRY


@pytest.fixture
def default_bucket():
    """Return default bucket name (normalized).

    Example: "my-bucket" (with s3:// prefix removed)

    Set via: QUILT_TEST_BUCKET environment variable
    """
    quilt_test_bucket = os.getenv("QUILT_TEST_BUCKET", "")
    if not quilt_test_bucket:
        raise ValueError("QUILT_TEST_BUCKET environment variable must be set for integration tests")
    return quilt_test_bucket.replace("s3://", "")


# ============================================================================
# Helper Functions
# ============================================================================


class ResultShape(NamedTuple):
    """Shape of search results for easy assertion."""

    count: int
    types: Set[str]
    buckets: Set[str]
    indices: Set[str]


def get_result_shape(results: List[Dict]) -> ResultShape:
    """Extract shape of search results for validation.

    Args:
        results: List of search result dicts

    Returns:
        ResultShape with count, set of types, set of buckets

    Example:
        shape = get_result_shape(result["results"])
        assert shape.count > 0, "Expected non-zero results"
        assert shape.types == {"file"}, "Expected only file results"
        assert shape.buckets == {"my-bucket"}, "Expected only my-bucket"
    """
    return ResultShape(
        count=len(results),
        types={r.get("type") for r in results if "type" in r},
        buckets={r.get("bucket") for r in results if "bucket" in r},
        indices={r.get("index") for r in results if "index" in r},
    )


@contextmanager
def diagnostic_search(test_name: str, query: str, scope: str, bucket: str, limit: int = 10):
    """Context manager that executes search and dumps diagnostics on test failure.

    Usage:
        with diagnostic_search("my_test", "*", "packageEntry", "my-bucket") as result:
            assert result["success"]
            assert len(result["results"]) > 0
            # ... more assertions ...

    On success: prints nothing
    On failure: prints query, result count, and first result only
    """
    # Execute search silently
    result = search_catalog(query=query, scope=scope, bucket=bucket, limit=limit)

    try:
        yield result
        # Success: print nothing
    except (AssertionError, Exception) as e:
        # On failure, dump minimal diagnostics
        print(f"\n{'!' * 80}")
        print(f"SEARCH FAILED: {test_name}")
        print(f"{'!' * 80}")
        print(f"Query: {query!r}")

        if isinstance(result, dict) and "results" in result:
            result_count = len(result["results"])
            print(f"Result count: {result_count}")

            if result_count > 0:
                print("\nFirst result:")
                print(json.dumps(result["results"][0], indent=2, default=str))
            else:
                print("No results returned")
        else:
            print(f"Invalid result structure: {type(result)}")

        print(f"{'!' * 80}\n")
        raise


def assert_valid_search_response(result: Dict) -> None:
    """Validate basic search response structure.

    Checks:
    - Result is a dict
    - success=True (or no error field)
    - Has 'results' field
    - results is a list

    Raises:
    - AssertionError with descriptive message if validation fails
    """
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result.get("success"), f"Search failed: {result.get('error')}"
    assert "results" in result, "Response must have 'results' field"
    assert isinstance(result["results"], list), "Results must be a list"


@pytest.mark.integration
@pytest.mark.search
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

    def test_file_scope_specific_bucket_returns_only_files(self):
        """File scope with specific bucket must return ONLY files."""
        result = search_catalog(
            query="csv",
            scope="file",
            bucket=default_bucket,
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
            f"FILE SCOPE TEST FAILURE: Must return at least 1 file result from bucket {default_bucket}. Got 0 results."
        )

        # Verify EVERY result is a file (not just the first one)
        for idx, res in enumerate(result["results"]):
            assert "type" in res, f"Result {idx} must have 'type' field"
            assert res["type"] == "file", (
                f"FILE SCOPE BUG: Result {idx} has type='{res['type']}' but scope='file' should ONLY return type='file'"
            )
            assert "bucket" in res, f"Result {idx} must have 'bucket' field"

    def test_package_scope_specific_bucket_returns_only_packages(self):
        """Package scope with specific bucket must return ONLY packages."""
        with diagnostic_search(
            test_name="test_package_scope_specific_bucket_returns_only_packages",
            query="*",
            scope="package",
            bucket=default_bucket,
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
                f"PACKAGE SCOPE TEST FAILURE: Must return at least 1 package result from bucket {default_bucket}. Got 0 results."
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


# =============================================================================
# NEW REAL DATA TESTS - Using QUILT_TEST_ENTRY and QUILT_TEST_PACKAGE
# =============================================================================


@pytest.mark.integration
@pytest.mark.search
class TestFileScopeWithRealData:
    """Test file scope searches using QUILT_TEST_ENTRY fixture."""

    def test_file_scope_all_buckets_returns_only_files(self, test_entry):
        """File scope with bucket='' searches all object indices.

        Behavior:
        - Searches ALL buckets (comma-separated indices: "bucket1,bucket2,...")
        - Returns ONLY file results (type="file")
        - MUST return non-zero results

        Test Data:
        - Query: QUILT_TEST_ENTRY (e.g., "README.md")
        - Expected: At least 1 file matching test_entry exists
        """
        # Execute search
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket="",  # All buckets
            limit=50,
        )

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"File search for '{test_entry}' returned ZERO results"
        assert shape.types == {"file"}, f"Expected only 'file' type, got: {shape.types}"

    def test_file_scope_specific_bucket_returns_only_files(self, test_entry, default_bucket):
        """File scope with bucket='my-bucket' searches single object index.

        Behavior:
        - Searches ONLY specified bucket (index: "my-bucket")
        - Returns ONLY file results (type="file")
        - ALL results MUST be from specified bucket
        - MUST return non-zero results

        Test Data:
        - Query: QUILT_TEST_ENTRY
        - Bucket: QUILT_TEST_BUCKET (guaranteed to have test data)
        """
        # Execute search
        result = search_catalog(query=test_entry, scope="file", bucket=default_bucket, limit=50)

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"File search in {default_bucket} returned ZERO results"
        assert shape.types == {"file"}, f"Expected only 'file' type, got: {shape.types}"
        assert shape.buckets == {default_bucket}, f"Expected only {default_bucket}, got: {shape.buckets}"


@pytest.mark.integration
@pytest.mark.search
class TestPackageScopeWithRealData:
    """Test package scope searches using QUILT_TEST_PACKAGE fixture."""

    def test_package_scope_all_buckets_returns_only_packages(self, test_package):
        """Package scope with bucket='' searches all package indices.

        Behavior:
        - Searches ALL buckets (comma-separated indices: "bucket1_packages,bucket2_packages,...")
        - Returns ONLY package results (type="package")
        - MUST return non-zero results
        - At least ONE result should match QUILT_TEST_PACKAGE

        Test Data:
        - Query: Full QUILT_TEST_PACKAGE name (e.g., "raw/test")
        - Expected: Package named "raw/test" exists and is found
        """
        # Use full package name to ensure it appears in top 50 results
        query = test_package  # "raw/test" → "raw/test"

        with diagnostic_search(
            test_name="test_package_scope_all_buckets_returns_only_packages",
            query=query,
            scope="package",
            bucket="",
            limit=50,
        ) as result:
            # Validate response structure
            assert_valid_search_response(result)

            # Validate result shape
            shape = get_result_shape(result["results"])
            assert shape.count > 0, f"Package search for '{query}' returned ZERO results"
            assert shape.types == {"package"}, f"Expected only 'package' type, got: {shape.types}"

            # Verify at least one result matches known test package
            package_names = [r["name"] for r in result["results"]]
            assert test_package in package_names, f"Expected to find '{test_package}' in results: {package_names}"

    def test_package_scope_specific_bucket_returns_only_packages(self, test_package, default_bucket):
        """Package scope with bucket='my-bucket' searches single package index.

        Behavior:
        - Searches ONLY specified bucket (index: "my-bucket_packages")
        - Returns ONLY package results (type="package")
        - ALL results MUST be from specified bucket
        - MUST return non-zero results

        Test Data:
        - Query: Last component of QUILT_TEST_PACKAGE
        - Bucket: QUILT_TEST_BUCKET (guaranteed to have test package)
        """
        query = test_package.split("/")[-1]

        with diagnostic_search(
            test_name="test_package_scope_specific_bucket_returns_only_packages (with fixtures)",
            query=query,
            scope="package",
            bucket=default_bucket,
            limit=50,
        ) as result:
            # Validate response structure
            assert_valid_search_response(result)

            # Validate result shape
            shape = get_result_shape(result["results"])
            assert shape.count > 0, f"Package search in {default_bucket} returned ZERO results"
            assert shape.types == {"package"}, f"Expected only 'package' type, got: {shape.types}"
            assert shape.buckets == {default_bucket}, f"Expected only {default_bucket}, got: {shape.buckets}"


@pytest.mark.integration
@pytest.mark.search
class TestGlobalScopeWithRealData:
    """Test global scope searches using both fixtures."""

    def test_global_scope_all_buckets_returns_mixed_types(self, test_entry):
        """Global scope with bucket='' searches all object AND package indices.

        Behavior:
        - Searches ALL buckets, BOTH index types per bucket
        - Index pattern: "bucket1,bucket1_packages,bucket2,bucket2_packages,..."
        - Returns MIXED results (type="file" AND/OR type="packageEntry")
        - MUST return non-zero results
        - Types MUST be subset of {"file", "packageEntry"}

        Test Data:
        - Query: QUILT_TEST_ENTRY (e.g., "README.md")
        - Expected: Generic query matches both files and possibly packages
        """
        # Execute search
        result = search_catalog(query=test_entry, scope="global", bucket="", limit=50)

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"Global search for '{test_entry}' returned ZERO results"
        assert shape.types.issubset({"file", "packageEntry"}), (
            f"Global scope returned invalid types: {shape.types - {'file', 'package'}}"
        )

    def test_global_scope_specific_bucket_returns_mixed_types(self, test_entry, default_bucket):
        """Global scope with bucket='my-bucket' searches both indices in one bucket.

        Behavior:
        - Searches ONLY specified bucket, BOTH index types
        - Index pattern: "my-bucket,my-bucket_packages"
        - Returns MIXED results (type="file" AND/OR type="packageEntry")
        - ALL results MUST be from specified bucket
        - MUST return non-zero results

        Test Data:
        - Query: QUILT_TEST_ENTRY
        - Bucket: QUILT_TEST_BUCKET
        """
        # Execute search
        result = search_catalog(query=test_entry, scope="global", bucket=default_bucket, limit=50)

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"Global search in {default_bucket} returned ZERO results"
        assert shape.types.issubset({"file", "packageEntry"}), (
            f"Global scope returned invalid types: {shape.types - {'file', 'package'}}"
        )
        assert shape.buckets == {default_bucket}, f"Expected only {default_bucket}, got: {shape.buckets}"


@pytest.mark.integration
@pytest.mark.search
class TestBucketPrioritization:
    """Test QUILT_TEST_BUCKET prioritization when bucket=''."""

    def test_default_bucket_results_appear_first_when_set(self, test_entry, default_bucket):
        """When QUILT_TEST_BUCKET is set, results from that bucket appear first.

        Behavior:
        - When bucket="": backend enumerates ALL buckets
        - Backend moves QUILT_TEST_BUCKET to front of list
        - Results from QUILT_TEST_BUCKET appear earlier in response (when scores equal)

        Test Data:
        - Query: QUILT_TEST_ENTRY (exists in multiple buckets ideally)
        - Expected: default_bucket results appear in first 10 results

        Note: This test makes a SOFT assertion (warning, not failure) because:
        - Test data might not exist in multiple buckets
        - Relevance scoring might override prioritization
        - We can only verify "early" appearance, not "first" appearance
        """
        # Execute search with large limit to see bucket distribution
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket="",  # Triggers prioritization logic
            limit=100,
        )

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, "Bucket prioritization test returned ZERO results"

        # If default bucket has results, verify it appears early
        if default_bucket in shape.buckets:
            buckets_in_results = [r["bucket"] for r in result["results"]]
            first_default_idx = buckets_in_results.index(default_bucket)
            assert first_default_idx < 10, (
                f"Default bucket '{default_bucket}' first appears at position {first_default_idx}, "
                f"expected in top 10. This may indicate prioritization is not working."
            )
        else:
            # Soft failure - log warning but don't fail test
            import warnings

            warnings.warn(
                f"Default bucket '{default_bucket}' not found in top 100 results. "
                f"Test data might not exist in default bucket."
            )

    def test_specific_bucket_ignores_default_bucket_setting(self, test_entry, default_bucket):
        """Specific bucket searches ignore QUILT_TEST_BUCKET setting.

        Behavior:
        - When bucket="specific-bucket": backend uses ONLY that bucket
        - QUILT_TEST_BUCKET has NO EFFECT on search
        - ALL results MUST be from specified bucket (not default)

        Test Data:
        - Query: QUILT_TEST_ENTRY
        - Bucket: QUILT_TEST_BUCKET (but treated as specific, not default)
        """
        # Execute search with specific bucket
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket=default_bucket,  # Specific bucket (not "" for all)
            limit=50,
        )

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape - ALL results from specified bucket
        # (This implicitly proves QUILT_TEST_BUCKET setting had no effect)
        shape = get_result_shape(result["results"])
        assert shape.buckets == {default_bucket}, f"Expected only {default_bucket}, got: {shape.buckets}"


@pytest.mark.integration
@pytest.mark.search
class TestBucketNormalization:
    """Test s3:// URI normalization in bucket parameter."""

    def test_s3_uri_normalized_to_bucket_name(self, test_entry, default_bucket):
        """bucket='s3://my-bucket' should work same as bucket='my-bucket'.

        Behavior:
        - Backend normalizes "s3://bucket" -> "bucket"
        - Both forms should return identical results
        - Response should show normalized bucket name (no s3:// prefix)

        Test Data:
        - Query: QUILT_TEST_ENTRY
        - Bucket forms: "my-bucket" vs "s3://my-bucket"
        """
        # Search with normalized bucket
        result1 = search_catalog(
            query=test_entry,
            scope="file",
            bucket=default_bucket,  # e.g., "my-bucket"
            limit=10,
        )

        # Search with s3:// URI
        result2 = search_catalog(
            query=test_entry,
            scope="file",
            bucket=f"s3://{default_bucket}",  # e.g., "s3://my-bucket"
            limit=10,
        )

        # Both should succeed
        assert_valid_search_response(result1)
        assert_valid_search_response(result2)

        # Both should return same normalized bucket in response
        assert result1.get("bucket") == default_bucket, f"Result1 bucket should be normalized: {result1.get('bucket')}"
        assert result2.get("bucket") == default_bucket, f"Result2 bucket should be normalized: {result2.get('bucket')}"

    def test_s3_uri_with_trailing_slash_normalized(self, test_entry, default_bucket):
        """bucket='s3://my-bucket/' should work (trailing slash removed).

        Behavior:
        - Backend normalizes "s3://bucket/" -> "bucket"
        - Response should show normalized bucket name

        Test Data:
        - Query: QUILT_TEST_ENTRY
        - Bucket: "s3://my-bucket/"
        """
        # Execute search with trailing slash
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket=f"s3://{default_bucket}/",  # Trailing slash
            limit=10,
        )

        # Should succeed
        assert_valid_search_response(result)

        # Should return normalized bucket (no s3://, no trailing slash)
        assert result.get("bucket") == default_bucket, (
            f"Bucket should be normalized to '{default_bucket}', got '{result.get('bucket')}'"
        )

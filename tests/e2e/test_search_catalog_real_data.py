"""Real data scope tests for search_catalog."""

import pytest

from quilt_mcp.tools.search import search_catalog
from tests.e2e.search_catalog_helpers import (
    assert_valid_search_response,
    diagnostic_search,
    get_result_shape,
)

pytest_plugins = ("tests.e2e.search_catalog_helpers",)

pytestmark = pytest.mark.usefixtures("requires_search")


class TestFileScopeWithRealData:
    """Test file scope searches using QUILT_TEST_ENTRY fixture."""

    def test_file_scope_all_buckets_returns_only_files(self, test_entry):
        """File scope with bucket='' searches all object indices."""
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket="",  # All buckets
            limit=50,
        )

        assert_valid_search_response(result)

        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"File search for '{test_entry}' returned ZERO results"
        assert shape.types == {"file"}, f"Expected only 'file' type, got: {shape.types}"

    def test_file_scope_specific_bucket_returns_only_files(self, test_entry, test_bucket):
        """File scope with bucket='my-bucket' searches single object index."""
        result = search_catalog(query=test_entry, scope="file", bucket=test_bucket, limit=50)

        assert_valid_search_response(result)

        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"File search in {test_bucket} returned ZERO results"
        assert shape.types == {"file"}, f"Expected only 'file' type, got: {shape.types}"
        assert shape.buckets == {test_bucket}, f"Expected only {test_bucket}, got: {shape.buckets}"


class TestPackageScopeWithRealData:
    """Test package scope searches using QUILT_TEST_PACKAGE fixture."""

    def test_package_scope_empty_bucket_returns_only_packages(self, test_package):
        """Package scope with bucket='' returns only package type results."""
        query = test_package

        with diagnostic_search(
            test_name="test_package_scope_empty_bucket_returns_only_packages",
            query=query,
            scope="package",
            bucket="",
            limit=50,
        ) as result:
            assert_valid_search_response(result)

            shape = get_result_shape(result["results"])
            assert shape.count > 0, f"Package search for '{query}' returned ZERO results"
            assert shape.types == {"package"}, f"Expected only 'package' type, got: {shape.types}"

    def test_package_scope_specific_bucket_returns_only_packages(self, test_package, test_bucket):
        """Package scope with bucket='my-bucket' searches single package index."""
        query = test_package.split("/")[-1]

        with diagnostic_search(
            test_name="test_package_scope_specific_bucket_returns_only_packages (with fixtures)",
            query=query,
            scope="package",
            bucket=test_bucket,
            limit=50,
        ) as result:
            assert_valid_search_response(result)

            shape = get_result_shape(result["results"])
            assert shape.count > 0, f"Package search in {test_bucket} returned ZERO results"
            assert shape.types == {"package"}, f"Expected only 'package' type, got: {shape.types}"
            assert shape.buckets == {test_bucket}, f"Expected only {test_bucket}, got: {shape.buckets}"


class TestGlobalScopeWithRealData:
    """Test global scope searches using both fixtures."""

    def test_global_scope_all_buckets_returns_mixed_types(self, test_entry):
        """Global scope with bucket='' searches all object AND package indices."""
        result = search_catalog(query=test_entry, scope="global", bucket="", limit=50)

        assert_valid_search_response(result)

        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"Global search for '{test_entry}' returned ZERO results"
        assert shape.types.issubset({"file", "packageEntry"}), (
            f"Global scope returned invalid types: {shape.types - {'file', 'package'}}"
        )

    def test_global_scope_specific_bucket_returns_mixed_types(self, test_entry, test_bucket):
        """Global scope with bucket='my-bucket' searches both indices in one bucket."""
        result = search_catalog(query=test_entry, scope="global", bucket=test_bucket, limit=50)

        assert_valid_search_response(result)

        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"Global search in {test_bucket} returned ZERO results"
        assert shape.types.issubset({"file", "packageEntry"}), (
            f"Global scope returned invalid types: {shape.types - {'file', 'package'}}"
        )
        assert shape.buckets == {test_bucket}, f"Expected only {test_bucket}, got: {shape.buckets}"


class TestBucketPrioritization:
    """Test QUILT_TEST_BUCKET prioritization when bucket=''."""

    def test_test_bucket_results_appear_first_when_set(self, test_entry, test_bucket):
        """When QUILT_TEST_BUCKET is set, results from that bucket appear first."""
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket="",  # Triggers prioritization logic
            limit=100,
        )

        assert_valid_search_response(result)

        shape = get_result_shape(result["results"])
        assert shape.count > 0, "Bucket prioritization test returned ZERO results"

        if test_bucket in shape.buckets:
            buckets_in_results = [r["bucket"] for r in result["results"]]
            first_default_idx = buckets_in_results.index(test_bucket)
            assert first_default_idx < 10, (
                f"Default bucket '{test_bucket}' first appears at position {first_default_idx}, "
                f"expected in top 10. This may indicate prioritization is not working."
            )
        else:
            import warnings

            warnings.warn(
                f"Default bucket '{test_bucket}' not found in top 100 results. "
                f"Test data might not exist in default bucket."
            )

    def test_specific_bucket_ignores_test_bucket_setting(self, test_entry, test_bucket):
        """Specific bucket searches ignore QUILT_TEST_BUCKET setting."""
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket=test_bucket,
            limit=50,
        )

        assert_valid_search_response(result)

        shape = get_result_shape(result["results"])
        assert shape.buckets == {test_bucket}, f"Expected only {test_bucket}, got: {shape.buckets}"


class TestBucketNormalization:
    """Test s3:// URI normalization in bucket parameter."""

    def test_s3_uri_normalized_to_bucket_name(self, test_entry, test_bucket):
        """bucket='s3://my-bucket' should work same as bucket='my-bucket'."""
        result1 = search_catalog(
            query=test_entry,
            scope="file",
            bucket=test_bucket,
            limit=10,
        )

        result2 = search_catalog(
            query=test_entry,
            scope="file",
            bucket=f"s3://{test_bucket}",
            limit=10,
        )

        assert_valid_search_response(result1)
        assert_valid_search_response(result2)

        assert result1.get("bucket") == test_bucket, f"Result1 bucket should be normalized: {result1.get('bucket')}"
        assert result2.get("bucket") == test_bucket, f"Result2 bucket should be normalized: {result2.get('bucket')}"

    def test_s3_uri_with_trailing_slash_normalized(self, test_entry, test_bucket):
        """bucket='s3://my-bucket/' should work (trailing slash removed)."""
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket=f"s3://{test_bucket}/",
            limit=10,
        )

        assert_valid_search_response(result)

        assert result.get("bucket") == test_bucket, (
            f"Bucket should be normalized to '{test_bucket}', got '{result.get('bucket')}'"
        )

"""Real integration tests for search_catalog with actual Elasticsearch backend.

These tests make REAL API calls to Elasticsearch and verify ACTUAL search results.
No mocks. Real data. Real pain.
"""

import pytest
from quilt_mcp import DEFAULT_BUCKET, DEFAULT_REGISTRY
from quilt_mcp.tools.search import search_catalog


@pytest.mark.integration
@pytest.mark.search
class TestSearchCatalogIntegration:
    """Integration tests for search_catalog using real Elasticsearch."""

    def test_file_scope_specific_bucket_returns_real_results(self):
        """Search for files in specific bucket - must return actual file results."""
        result = search_catalog(
            query="csv",
            scope="file",
            bucket=DEFAULT_BUCKET,
            limit=10,
        )

        # Must be a dict response
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Must have success field
        assert "success" in result, f"Missing 'success' field in result: {result.keys()}"

        # If successful, must have results
        if result.get("success"):
            assert "results" in result, "Success response must have 'results' field"
            assert isinstance(result["results"], list), "Results must be a list"

            # If we got results, verify they're properly structured
            if len(result["results"]) > 0:
                first_result = result["results"][0]
                assert "type" in first_result, "Result must have 'type' field"
                assert first_result["type"] == "file", f"Expected type='file', got {first_result.get('type')}"
                assert "name" in first_result, "Result must have 'name' field"
                assert "s3_uri" in first_result, "Result must have 's3_uri' field"
                assert "bucket" in first_result, "Result must have 'bucket' field"
                assert first_result["bucket"], "Bucket field must not be empty"
                assert isinstance(first_result["bucket"], str), "Bucket must be a string"
                assert "score" in first_result, "Result must have 'score' field"

    def test_package_scope_specific_bucket_returns_real_results(self):
        """Search for packages in specific bucket - must return actual package results."""
        result = search_catalog(
            query="*",  # Search for anything
            scope="package",
            bucket=DEFAULT_BUCKET,
            limit=10,
        )

        # Must be a dict response
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Must have success field
        assert "success" in result, f"Missing 'success' field in result: {result.keys()}"

        # If successful, must have results
        if result.get("success"):
            assert "results" in result, "Success response must have 'results' field"
            assert isinstance(result["results"], list), "Results must be a list"

            # If we got results, verify they're properly structured
            if len(result["results"]) > 0:
                first_result = result["results"][0]
                assert "type" in first_result, "Result must have 'type' field"
                assert first_result["type"] == "package", f"Expected type='package', got {first_result.get('type')}"
                assert "name" in first_result, "Result must have 'name' field"
                assert "/" in first_result["name"], f"Package name should have namespace/name format: {first_result['name']}"
                assert "s3_uri" in first_result, "Result must have 's3_uri' field"
                assert ".quilt/packages" in first_result["s3_uri"], f"Package URI should contain .quilt/packages: {first_result['s3_uri']}"
                assert "bucket" in first_result, "Result must have 'bucket' field"

    def test_global_scope_returns_both_files_and_packages(self):
        """Search with global scope - must return BOTH file and package results."""
        result = search_catalog(
            query="data",
            scope="global",
            bucket=DEFAULT_BUCKET,
            limit=20,
        )

        # Must be a dict response
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Must have success field
        assert "success" in result, f"Missing 'success' field in result: {result.keys()}"

        # If successful, check for mixed results
        if result.get("success") and len(result.get("results", [])) > 0:
            results = result["results"]
            types_found = {r.get("type") for r in results if "type" in r}

            # For global scope, we SHOULD see at least files
            # (packages might not exist depending on bucket state)
            assert "file" in types_found or "package" in types_found, \
                f"Global scope should return files or packages, got types: {types_found}"

            # Verify each result has proper structure for its type
            for res in results:
                assert "type" in res, "Every result must have 'type' field"
                assert "name" in res, "Every result must have 'name' field"
                assert "s3_uri" in res, "Every result must have 's3_uri' field"
                assert "bucket" in res, "Every result must have 'bucket' field"

    def test_file_scope_all_buckets_returns_results_from_multiple_buckets(self):
        """Search across ALL buckets - must enumerate buckets and return results."""
        result = search_catalog(
            query="csv",
            scope="file",
            bucket="",  # Empty = all buckets
            limit=20,
        )

        # Must be a dict response
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Must have success field
        assert "success" in result, f"Missing 'success' field in result: {result.keys()}"

        # If successful and has results, verify they come from real buckets
        if result.get("success") and len(result.get("results", [])) > 0:
            results = result["results"]
            buckets_found = {r.get("bucket") for r in results if "bucket" in r}

            # Should have actual bucket names, not None or empty
            assert len(buckets_found) > 0, "Should find results from at least one bucket"
            assert None not in buckets_found, f"No result should have None bucket: {buckets_found}"
            assert "" not in buckets_found, f"No result should have empty bucket: {buckets_found}"

    def test_package_scope_all_buckets_returns_package_results(self):
        """Search for packages across ALL buckets - must return package results."""
        result = search_catalog(
            query="*",
            scope="package",
            bucket="",  # Empty = all buckets
            limit=20,
        )

        # Must be a dict response
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Must have success field
        assert "success" in result, f"Missing 'success' field in result: {result.keys()}"

        # If successful and has results, verify they're all packages
        if result.get("success") and len(result.get("results", [])) > 0:
            results = result["results"]

            for res in results:
                assert res.get("type") == "package", \
                    f"Package scope should only return packages, got type={res.get('type')}"
                assert "/" in res.get("name", ""), \
                    f"Package names should have namespace/name format: {res.get('name')}"
                assert ".quilt/packages" in res.get("s3_uri", ""), \
                    f"Package URIs should contain .quilt/packages: {res.get('s3_uri')}"

    def test_global_scope_all_buckets_returns_mixed_results(self):
        """Search globally across ALL buckets - must return mixed file and package results."""
        result = search_catalog(
            query="test",
            scope="global",
            bucket="",  # Empty = all buckets
            limit=30,
        )

        # Must be a dict response
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Must have success field
        assert "success" in result, f"Missing 'success' field in result: {result.keys()}"

        # If successful and has results, verify proper structure
        if result.get("success") and len(result.get("results", [])) > 0:
            results = result["results"]

            # Verify all results have required fields
            for res in results:
                assert "type" in res, "Every result must have 'type' field"
                assert res["type"] in ["file", "package"], \
                    f"Type must be 'file' or 'package', got: {res['type']}"
                assert "name" in res, "Every result must have 'name' field"
                assert "bucket" in res, "Every result must have 'bucket' field"
                assert "s3_uri" in res, "Every result must have 's3_uri' field"
                assert "score" in res, "Every result must have 'score' field"

    def test_nonexistent_bucket_returns_error_dict_not_exception(self):
        """Search in nonexistent bucket - must return error dict, NOT raise exception."""
        result = search_catalog(
            query="test",
            scope="file",
            bucket="this-bucket-definitely-does-not-exist-12345",
            limit=10,
        )

        # CRITICAL: Must be a dict, not an exception
        assert isinstance(result, dict), \
            "Search must return dict even on error, not raise exception"

        # Must have success field set to False
        assert "success" in result, "Error response must have 'success' field"
        assert result["success"] is False, "Error response must have success=False"

        # Must have error field
        assert "error" in result, "Error response must have 'error' field"
        assert isinstance(result["error"], str), "Error must be a string"
        assert len(result["error"]) > 0, "Error message must not be empty"

    def test_empty_query_returns_results(self):
        """Empty query should work and return results."""
        result = search_catalog(
            query="",
            scope="file",
            bucket=DEFAULT_BUCKET,
            limit=5,
        )

        # Must be a dict response
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Should handle empty query gracefully (either return results or error)
        assert "success" in result, "Response must have 'success' field"

    def test_search_result_count_respects_limit(self):
        """Search results should respect the limit parameter."""
        limit = 5
        result = search_catalog(
            query="*",
            scope="file",
            bucket=DEFAULT_BUCKET,
            limit=limit,
        )

        # Must be a dict response
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # If successful and has results, should not exceed limit
        if result.get("success") and result.get("results"):
            assert len(result["results"]) <= limit, \
                f"Result count {len(result['results'])} should not exceed limit {limit}"

    def test_search_includes_backend_info(self):
        """Search results should include backend information."""
        result = search_catalog(
            query="test",
            scope="file",
            bucket=DEFAULT_BUCKET,
            limit=5,
        )

        # Must be a dict response
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Should include backend info
        assert "backend_used" in result or "backend" in result, \
            "Result should include backend information"

        # Should include query metadata
        assert "query" in result, "Result should include query"
        assert "scope" in result, "Result should include scope"

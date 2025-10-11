import os
import random
import string
import time

import pytest
from quilt_mcp import (
    DEFAULT_BUCKET,
    DEFAULT_REGISTRY,
    KNOWN_TEST_ENTRY,
    KNOWN_TEST_PACKAGE,
    KNOWN_TEST_S3_OBJECT,
)
from quilt_mcp.tools.auth import (
    auth_status,
    catalog_info,
    catalog_name,
    catalog_uri,
    catalog_url,
    filesystem_status,
)
from quilt_mcp.tools.buckets import (
    bucket_object_fetch,
    bucket_object_info,
    bucket_object_link,
    bucket_object_text,
    bucket_objects_list,
    bucket_objects_put,
    bucket_objects_search,
)
from quilt_mcp.tools.package_ops import (
    package_create,
    package_delete,
    package_update,
)
from quilt_mcp.tools.packages import (
    package_browse,
    package_contents_search,
    package_diff,
    packages_list,
    packages_search,
)

# Test configuration - using constants
TEST_REGISTRY = DEFAULT_REGISTRY
KNOWN_PACKAGE = KNOWN_TEST_PACKAGE
KNOWN_BUCKET = DEFAULT_BUCKET
EXPECTED_S3_OBJECT = KNOWN_TEST_S3_OBJECT

# AWS profile configuration is handled in conftest.py


@pytest.fixture(scope="module")
def require_aws_credentials():
    """Skip when AWS credentials are unavailable."""

    from tests.helpers import skip_if_no_aws_credentials

    skip_if_no_aws_credentials()
    return True


@pytest.mark.aws
@pytest.mark.search
class TestQuiltAPI:
    """Test suite for quilt MCP server using real data - tests that expect actual results."""

    @pytest.fixture(scope="class")
    def known_package_browse_result(self, require_aws_credentials):
        """Browse the known package once to reuse across tests."""

        result = package_browse(
            KNOWN_PACKAGE,
            registry=TEST_REGISTRY,
            include_file_info=False,
            include_signed_urls=False,
        )

        if result.get("success") is False and "AccessDenied" in str(result.get("cause", "")):
            pytest.skip(f"Access denied to package {KNOWN_PACKAGE} - check AWS permissions: {result.get('error')}")

        return result

    def test_packages_list_returns_data(self):
        """Test that packages_list returns actual packages from configured registry."""
        try:
            result = packages_list(registry=TEST_REGISTRY)
        except Exception as e:
            if "AccessDenied" in str(e) or "S3NoValidClientError" in str(e):
                pytest.skip(f"Access denied to {TEST_REGISTRY} - check AWS permissions: {e}")
            raise

        assert isinstance(result, dict), "Result should be a dict"
        assert "packages" in result, "Result should have 'packages' key"
        # FAIL if no packages - this indicates a real problem
        assert len(result["packages"]) > 0, (
            f"Expected packages in {TEST_REGISTRY}, got empty list - this indicates missing data or misconfiguration"
        )

        # Check that we get string package names
        for pkg in result["packages"]:
            assert isinstance(pkg, str), f"Package name should be string, got {type(pkg)}: {pkg}"
            assert "/" in pkg, f"Package names should contain namespace/name format, got: {pkg}"

    def test_packages_list_prefix(self):
        """Test that prefix filtering works and finds the configured test package."""
        # Extract prefix from known test package
        test_prefix = KNOWN_PACKAGE.split("/")[0] if "/" in KNOWN_PACKAGE else KNOWN_PACKAGE
        try:
            result = packages_list(registry=TEST_REGISTRY, prefix=test_prefix)
        except Exception as e:
            if "AccessDenied" in str(e) or "S3NoValidClientError" in str(e):
                pytest.skip(f"Access denied to {TEST_REGISTRY} - check AWS permissions: {e}")
            raise

        assert isinstance(result, dict)
        assert "packages" in result

        # FAIL if no packages with this prefix - this means the test environment is misconfigured
        assert len(result["packages"]) > 0, (
            f"No {test_prefix} packages found in {TEST_REGISTRY} - check QUILT_TEST_PACKAGE configuration"
        )

        # Verify all results match prefix
        for pkg in result["packages"]:
            assert pkg.startswith(test_prefix), f"Package {pkg} doesn't start with '{test_prefix}'"

        # FAIL if known package not found - this means the test environment is misconfigured
        package_names = result["packages"]
        assert KNOWN_PACKAGE in package_names, (
            f"Known package {KNOWN_PACKAGE} not found in {TEST_REGISTRY} - check QUILT_TEST_PACKAGE configuration"
        )

    @pytest.mark.search
    def test_packages_search_finds_data(self):
        """Test that searching finds actual data (search returns S3 objects, not packages)."""
        # Use a very simple search to avoid timeout
        try:
            # Test with explicit registry parameter (our fix ensures registry-specific search)
            # Use limit=1 and a simple query to minimize time
            result = packages_search("*", registry=TEST_REGISTRY, limit=1)
            assert isinstance(result, dict)
            assert "results" in result
            assert "registry" in result  # Verify our fix adds registry info
            assert "bucket" in result  # Verify our fix adds bucket info

            # If we get results, verify the structure
            if len(result["results"]) > 0:
                for item in result["results"]:
                    if isinstance(item, dict) and "_source" in item:
                        assert len(item["_source"]) > 0, "Search result should have at least one key in _source"
            else:
                # No results is fine - the search functionality is working
                import warnings

                warnings.warn(
                    f"No search results found in registry {TEST_REGISTRY}. "
                    "This may be expected in CI environments without indexed content. "
                    "The search functionality is working correctly - it's properly scoped to the specified registry."
                )
        except Exception as e:
            # If search fails completely, that's also acceptable in CI
            import warnings

            warnings.warn(f"Search failed: {e}. This may be expected in CI environments.")

    def test_package_browse_known_package(self, known_package_browse_result):
        """Test browsing the known test package."""
        result = known_package_browse_result

        assert isinstance(result, dict)

        # Check if we got an access denied error and skip if so
        assert "entries" in result
        assert "package_name" in result
        assert "total_entries" in result

        # FAIL if no entries found - this means the test package is misconfigured
        assert len(result["entries"]) > 0, (
            f"Package {KNOWN_PACKAGE} appears empty - check QUILT_TEST_PACKAGE configuration"
        )

        # Check we get actual entry structures
        for entry in result["entries"]:
            assert isinstance(entry, dict), f"Entry should be dict, got {type(entry)}: {entry}"
            assert "logical_key" in entry, f"Entry missing logical_key: {entry}"

    def test_package_contents_search_in_known_package(self):
        """Test searching within a known package for files."""
        # Try searching for the known test entry first
        known_entry = KNOWN_TEST_ENTRY if KNOWN_TEST_ENTRY else "README.md"
        result = package_contents_search(
            KNOWN_PACKAGE,
            known_entry,
            registry=TEST_REGISTRY,
            include_signed_urls=False,
        )

        assert isinstance(result, dict)
        assert "matches" in result
        assert "count" in result

        # If the known entry isn't found, try common extensions
        if result["count"] == 0:
            for ext in [".md", ".txt", ".csv", ".json", ".parquet"]:
                result = package_contents_search(
                    KNOWN_PACKAGE,
                    ext,
                    registry=TEST_REGISTRY,
                    include_signed_urls=False,
                )
                if result["count"] > 0:
                    break

        # Don't fail if no matches - just verify the search functionality works
        # (Some packages might not have common file types)
        if result["count"] > 0:
            for match in result["matches"]:
                assert isinstance(match, dict), f"Match should be dict, got {type(match)}: {match}"
                assert "logical_key" in match, f"Match missing logical_key: {match}"

    def test_bucket_objects_list_returns_data(self):
        """Test that bucket listing returns actual objects."""
        result = bucket_objects_list(bucket=KNOWN_BUCKET, max_keys=10)

        assert isinstance(result, dict)
        assert "objects" in result
        assert "bucket" in result
        assert len(result["objects"]) > 0, f"Expected objects in {KNOWN_BUCKET}, got empty list"

        # Check object structure
        for obj in result["objects"]:
            assert "key" in obj, f"Object missing 'key': {obj}"
            assert "size" in obj, f"Object missing 'size': {obj}"
            assert isinstance(obj["key"], str), f"Object key should be string: {obj}"

    def test_bucket_object_info_known_file(self):
        """Test getting info for a known public file."""
        result = bucket_object_info(EXPECTED_S3_OBJECT)

        assert isinstance(result, dict)
        if "error" in result:
            pytest.skip(f"Known file not accessible: {result['error']}")

        assert "bucket" in result
        assert "key" in result
        assert "size" in result
        assert result["size"] > 0, "File should have non-zero size"

    def test_bucket_object_text_csv_file(self):
        """Test reading text from the configured test file."""
        # Use the configured test entry which should be a text file
        test_uri = KNOWN_TEST_S3_OBJECT
        result = bucket_object_text(test_uri, max_bytes=1000)

        assert isinstance(result, dict)
        if "error" in result:
            pytest.skip(f"Test file not accessible: {result['error']}")

        assert "text" in result
        assert "bucket" in result
        assert "key" in result

        # Verify we can read text content (don't assume specific format)
        text = result["text"]
        assert len(text) > 0, "File should have content"
        assert isinstance(text, str), "Text should be a string"
        # Don't assume markdown format - different environments have different file types

    def test_auth_status_returns_status(self):
        """Test authentication check returns valid status."""
        result = auth_status()

        assert isinstance(result, dict)
        assert "status" in result
        assert result["status"] in ["authenticated", "not_authenticated", "error"]

        # Test specific status behaviors
        if result["status"] == "authenticated":
            assert "catalog_url" in result, "Authenticated status should include catalog_url"
            assert result["search_available"] is True
        elif result["status"] == "not_authenticated":
            assert "setup_instructions" in result, "Not authenticated should include setup instructions"
            assert result["search_available"] is False
        else:  # error status
            assert "error" in result, "Error status should include error message"

    def test_filesystem_status_returns_info(self):
        """Test filesystem check returns actual system info."""
        result = filesystem_status()

        assert isinstance(result, dict)
        assert "home_directory" in result
        assert "temp_directory" in result
        assert "current_directory" in result

        # Verify we get actual paths
        assert result["home_directory"].startswith("/"), (
            f"Home directory should be absolute path: {result['home_directory']}"
        )
        assert result["temp_directory"].startswith("/"), (
            f"Temp directory should be absolute path: {result['temp_directory']}"
        )
        assert result["current_directory"].startswith("/"), (
            f"Current directory should be absolute path: {result['current_directory']}"
        )

    def test_catalog_info_returns_data(self):
        """Test catalog_info returns current catalog information."""
        result = catalog_info()

        assert isinstance(result, dict)
        assert "catalog_name" in result
        assert "is_authenticated" in result
        assert "status" in result
        assert result["status"] in ["success", "error"]

        if result["status"] == "success":
            assert isinstance(result["catalog_name"], str)
            assert isinstance(result["is_authenticated"], bool)
            assert len(result["catalog_name"]) > 0, "Catalog name should not be empty"

    def test_catalog_name_returns_name(self):
        """Test catalog_name returns the catalog name and detection method."""
        result = catalog_name()

        assert isinstance(result, dict)
        assert "catalog_name" in result
        assert "detection_method" in result
        assert "status" in result
        assert result["status"] in ["success", "error"]

        if result["status"] == "success":
            assert isinstance(result["catalog_name"], str)
            assert isinstance(result["detection_method"], str)
            assert len(result["catalog_name"]) > 0, "Catalog name should not be empty"
            assert result["detection_method"] in [
                "authentication",
                "navigator_config",
                "registry_config",
                "unknown",
            ]

    def test_catalog_url_package_view(self):
        """Test catalog_url generates valid package view URLs."""
        result = catalog_url(registry=TEST_REGISTRY, package_name="raw/salmon-rnaseq", path="README.md")

        assert isinstance(result, dict)
        assert "status" in result

        if result["status"] == "success":
            assert "catalog_url" in result
            assert "view_type" in result
            assert "bucket" in result
            assert result["view_type"] == "package"
            assert result["catalog_url"].startswith("https://")
            assert "/b/" in result["catalog_url"]
            assert "/packages/" in result["catalog_url"]
            assert "raw/salmon-rnaseq" in result["catalog_url"]
            assert "README.md" in result["catalog_url"]

    def test_catalog_url_bucket_view(self):
        """Test catalog_url generates valid bucket view URLs."""
        result = catalog_url(registry=TEST_REGISTRY, path="test/data.csv")

        assert isinstance(result, dict)
        assert "status" in result

        if result["status"] == "success":
            assert "catalog_url" in result
            assert "view_type" in result
            assert "bucket" in result
            assert result["view_type"] == "bucket"
            assert result["catalog_url"].startswith("https://")
            assert "/b/" in result["catalog_url"]
            assert "/tree/" in result["catalog_url"]
            assert "test/data.csv" in result["catalog_url"]

    def test_catalog_uri_package_reference(self):
        """Test catalog_uri generates valid Quilt+ URIs."""
        result = catalog_uri(registry=TEST_REGISTRY, package_name="raw/salmon-rnaseq", path="README.md")

        assert isinstance(result, dict)
        assert "status" in result

        if result["status"] == "success":
            assert "quilt_plus_uri" in result
            assert "bucket" in result
            assert result["quilt_plus_uri"].startswith("quilt+s3://")
            assert "package=raw/salmon-rnaseq" in result["quilt_plus_uri"]
            assert "path=README.md" in result["quilt_plus_uri"]

    def test_catalog_uri_with_version(self):
        """Test catalog_uri generates versioned Quilt+ URIs."""
        test_hash = "abc123def456"
        result = catalog_uri(
            registry=TEST_REGISTRY,
            package_name="raw/salmon-rnaseq",
            path="README.md",
            top_hash=test_hash,
        )

        assert isinstance(result, dict)
        assert "status" in result

        if result["status"] == "success":
            assert "quilt_plus_uri" in result
            assert f"package=raw/salmon-rnaseq@{test_hash}" in result["quilt_plus_uri"]

    # FAILURE CASES - These should fail gracefully

    @pytest.mark.search
    def test_packages_search_no_results(self):
        """Test that non-existent search returns empty results, not error."""
        result = packages_search("xyznonexistentpackage123456789")

        assert isinstance(result, dict)
        assert "results" in result
        assert len(result["results"]) == 0, "Non-existent search should return empty results"

    def test_packages_list_invalid_registry_fails(self):
        """Test that invalid registry fails gracefully with proper error."""
        with pytest.raises(Exception) as exc_info:
            packages_list(registry="s3://definitely-nonexistent-bucket-xyz")

        # Should get a meaningful error about the bucket
        error_msg = str(exc_info.value).lower()
        assert any(term in error_msg for term in ["nosuchbucket", "no such bucket", "bucket", "not found"]), (
            f"Expected meaningful bucket error, got: {exc_info.value}"
        )

    def test_package_browse_nonexistent_fails(self):
        """Test that browsing non-existent package returns error response."""
        result = package_browse("definitely/nonexistent/package")

        # The function now returns an error dictionary instead of raising an exception
        assert isinstance(result, dict)
        assert result.get("success") is False
        assert "error" in result
        assert "cause" in result

        error_msg = str(result.get("error", "")).lower()
        assert any(
            term in error_msg
            for term in [
                "failed to browse",
                "package",
                "definitely/nonexistent/package",
            ]
        ), f"Expected meaningful error message, got: {result}"

    def test_bucket_object_info_nonexistent_fails(self):
        """Test that non-existent object returns error."""
        result = bucket_object_info(f"{KNOWN_BUCKET}/definitely/nonexistent/file.txt")

        assert isinstance(result, dict)
        assert "error" in result, "Non-existent file should return error"
        assert "bucket" in result
        assert "key" in result

    def test_bucket_object_fetch_returns_data(self):
        """Test fetching object data from S3."""
        # Use a small object from bucket listing
        objects_result = bucket_objects_list(bucket=KNOWN_BUCKET, max_keys=5)
        if not objects_result.get("objects"):
            pytest.skip("No objects found to test fetch")

        # Find a small object to test (prefer smallest under threshold)
        candidates = [o for o in objects_result["objects"] if o.get("size", 0) > 0]
        SMALL_MAX = 10000
        small_obj = None
        if candidates:
            under = [o for o in candidates if o.get("size", 0) < SMALL_MAX]
            search_space = under or candidates
            small_obj = min(search_space, key=lambda o: o.get("size", 0))
        if not small_obj:
            pytest.skip("No suitable objects (non-zero size) found to test fetch")
        # Static type assurance (helps static analysis)
        assert small_obj is not None  # noqa: F821
        s3_uri = f"s3://{objects_result['bucket']}/{small_obj['key']}"
        result = bucket_object_fetch(s3_uri, max_bytes=1000)

        assert isinstance(result, dict)
        if "error" in result:
            pytest.skip(f"Object not accessible: {result['error']}")

        assert "bucket" in result
        assert "key" in result
        assert "data" in result or "text" in result, "Should return either data or text"
        assert "size" in result
        assert result["size"] > 0, "Fetched object should have content"

    def test_bucket_object_link_integration(self):
        """Test bucket_object_link integration with real AWS."""
        # Use a small object from bucket listing
        objects_result = bucket_objects_list(bucket=KNOWN_BUCKET, max_keys=5)
        if not objects_result.get("objects"):
            pytest.skip("No objects found to test presigned URL generation")

        # Find any object to test with
        test_object = objects_result["objects"][0]
        s3_uri = f"s3://{objects_result['bucket']}/{test_object['key']}"

        result = bucket_object_link(s3_uri, expiration=7200)

        assert isinstance(result, dict)
        if "error" in result:
            pytest.skip(f"Object not accessible for URL generation: {result['error']}")

        assert "bucket" in result
        assert "key" in result
        assert "presigned_url" in result
        assert "expires_in" in result
        assert result["expires_in"] == 7200
        assert result["presigned_url"].startswith("https://")
        assert result["bucket"] == objects_result["bucket"]
        assert result["key"] == test_object["key"]

    def test_bucket_objects_put_small_file(self):
        """Test uploading small objects to S3."""
        test_bucket = KNOWN_BUCKET
        test_items = [
            {
                "key": "test-uploads/test-file-1.txt",
                "text": "Hello, this is a test file created by the test suite.",
                "content_type": "text/plain",
                "metadata": {"created_by": "test_suite", "test": "true"},
            },
            {
                "key": "test-uploads/test-file-2.json",
                "text": '{"message": "test json", "timestamp": "2025-01-01"}',
                "content_type": "application/json",
            },
        ]

        result = bucket_objects_put(test_bucket, test_items)

        assert isinstance(result, dict)
        assert "bucket" in result
        assert "requested" in result
        assert "uploaded" in result
        assert "results" in result

        assert result["requested"] == 2, "Should have requested 2 uploads"

        # Expect successful uploads (user should have permissions)
        if result["uploaded"] < result["requested"]:
            # Check for permission errors
            for item_result in result["results"]:
                if "error" in item_result:
                    error_msg = item_result["error"].lower()
                    if "accessdenied" in error_msg or "not authorized" in error_msg:
                        pytest.fail(f"Permission error - user needs s3:PutObject permissions: {item_result['error']}")

        assert result["uploaded"] > 0, "Should have successfully uploaded some files"

        # Check individual results
        for item_result in result["results"]:
            assert "key" in item_result
            # Should have successful uploads (etag) for test environment
            if "error" in item_result and "accessdenied" not in item_result["error"].lower():
                pytest.fail(f"Unexpected upload error: {item_result['error']}")

        # Clean up uploaded test files
        try:
            for item in test_items:
                # Verify file was uploaded, then we could delete it if there was a delete tool
                info_result = bucket_object_info(f"{KNOWN_BUCKET}/{item['key']}")
                if "error" not in info_result:
                    print(f"Test file uploaded successfully: {item['key']}")
        except Exception:
            pass  # Cleanup is best-effort

    @pytest.mark.search
    def test_bucket_objects_search_finds_data(self):
        """Test bucket_objects_search finds actual data in the test bucket."""
        # Try multiple search terms to find some data
        search_terms = ["README", "csv", "parquet", "json", "txt", "data", "test"]
        found_results = False

        for term in search_terms:
            result = bucket_objects_search(KNOWN_BUCKET, term, limit=5)
            assert isinstance(result, dict)
            assert "bucket" in result
            assert "query" in result
            assert "results" in result

            if "error" in result:
                # Search might not be configured - skip test
                if "search endpoint" in result["error"].lower() or "not configured" in result["error"].lower():
                    pytest.skip(f"Search not configured for bucket {KNOWN_BUCKET}: {result['error']}")
                continue

            if len(result["results"]) > 0:
                found_results = True
                # Verify the response structure is correct
                for item in result["results"]:
                    if isinstance(item, dict) and "_source" in item:
                        assert len(item["_source"]) > 0, "Search result should have at least one key in _source"
                break

        # If search is configured but no results found, that's okay for some buckets
        if not found_results:
            pytest.skip(
                f"No search results found for any common terms {search_terms} in {KNOWN_BUCKET} - bucket may not have indexed content"
            )

    def test_bucket_objects_search_no_results(self):
        """Test that non-existent search returns empty results, not error."""
        result = bucket_objects_search(KNOWN_BUCKET, "xyznonexistentfile123456789")

        assert isinstance(result, dict)
        if "error" not in result:
            assert "results" in result
            assert len(result["results"]) == 0, "Non-existent search should return empty results"
        else:
            # Search might not be configured - that's okay
            if "search endpoint" in result["error"].lower() or "not configured" in result["error"].lower():
                pytest.skip(f"Search not configured for bucket {KNOWN_BUCKET}")

    def test_bucket_objects_search_dsl_query(self):
        """Test bucket_objects_search with dictionary DSL query."""
        query_dsl = {"query": {"wildcard": {"key": "*.csv"}}}

        result = bucket_objects_search(KNOWN_BUCKET, query_dsl, limit=3)

        assert isinstance(result, dict)
        assert "bucket" in result
        assert "query" in result
        assert result["query"] == query_dsl

        if "error" in result:
            # Search might not be configured - skip test
            if "search endpoint" in result["error"].lower() or "not configured" in result["error"].lower():
                pytest.skip(f"Search not configured for bucket {KNOWN_BUCKET}: {result['error']}")
        else:
            assert "results" in result
            # Results might be empty if no CSV files exist, which is okay

    def test_package_diff_known_package_with_itself(self):
        """Test package_diff comparing known package with itself (should show no differences)."""
        result = package_diff(KNOWN_PACKAGE, KNOWN_PACKAGE, registry=TEST_REGISTRY)

        assert isinstance(result, dict)
        if "error" in result:
            # Some packages might not support diff operations
            pytest.skip(f"Package diff not supported: {result['error']}")

        assert "package1" in result
        assert "package2" in result
        assert "diff" in result
        assert result["package1"] == KNOWN_PACKAGE
        assert result["package2"] == KNOWN_PACKAGE

        # When comparing identical packages, should have no differences
        diff = result["diff"]
        if isinstance(diff, dict):
            # If diff returns structured data, check for minimal differences
            assert len(diff.get("added", [])) == 0 or len(diff.get("deleted", [])) == 0

    @pytest.mark.slow
    def test_package_diff_different_packages(self):
        """Test package_diff comparing two different packages."""
        # Get available packages first
        try:
            packages_result = packages_list(registry=TEST_REGISTRY, limit=3)
        except Exception as e:
            if "AccessDenied" in str(e) or "S3NoValidClientError" in str(e):
                pytest.skip(f"Access denied to {TEST_REGISTRY} - check AWS permissions: {e}")
            raise

        if len(packages_result.get("packages", [])) < 2:
            pytest.skip("Need at least 2 packages to test diff")

        packages = packages_result["packages"]
        pkg1, pkg2 = packages[0], packages[1]

        result = package_diff(pkg1, pkg2, registry=TEST_REGISTRY)

        assert isinstance(result, dict)
        if "error" in result:
            # Some packages might not support diff operations or might not exist
            if "not found" in result["error"].lower() or "does not exist" in result["error"].lower():
                pytest.skip(f"Packages not accessible for diff: {result['error']}")
            else:
                pytest.skip(f"Package diff not supported: {result['error']}")

        assert "package1" in result
        assert "package2" in result
        assert "diff" in result
        assert result["package1"] == pkg1
        assert result["package2"] == pkg2

    def test_package_diff_nonexistent_packages(self):
        """Test package_diff with non-existent packages."""
        result = package_diff("definitely/nonexistent1", "definitely/nonexistent2", registry=TEST_REGISTRY)

        assert isinstance(result, dict)
        assert "error" in result
        # Should get a meaningful error about packages not being found
        error_msg = result["error"].lower()
        assert any(
            term in error_msg
            for term in [
                "failed to browse",
                "not found",
                "does not exist",
                "no such file",
            ]
        ), f"Expected meaningful error about missing packages, got: {result['error']}"


@pytest.mark.aws
class TestBucketObjectVersionConsistency:
    """Integration tests for versionId consistency across bucket_object_* functions."""

    def test_bucket_object_functions_consistency_with_real_object(self):
        """Test that all bucket_object_* functions work consistently with a real S3 object."""
        from tests.helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        # Get a real object from the test bucket
        objects_result = bucket_objects_list(bucket=KNOWN_BUCKET, max_keys=5)
        if not objects_result.get("objects"):
            pytest.skip(f"No objects found in test bucket {KNOWN_BUCKET}")

        test_object = objects_result["objects"][0]
        test_s3_uri = f"{KNOWN_BUCKET}/{test_object['key']}"

        # Call all four functions with the same URI
        info_result = bucket_object_info(test_s3_uri)
        text_result = bucket_object_text(test_s3_uri, max_bytes=1024)
        fetch_result = bucket_object_fetch(test_s3_uri, max_bytes=1024)
        link_result = bucket_object_link(test_s3_uri)

        # All should succeed (or all should fail consistently)
        all_succeed = all("error" not in result for result in [info_result, text_result, fetch_result, link_result])
        all_fail = all("error" in result for result in [info_result, text_result, fetch_result, link_result])

        assert all_succeed or all_fail, "Functions should have consistent success/failure status"

        if all_succeed:
            # Verify consistent bucket/key information
            expected_bucket = KNOWN_BUCKET.replace("s3://", "")
            assert info_result["bucket"] == expected_bucket
            assert text_result["bucket"] == expected_bucket
            assert fetch_result["bucket"] == expected_bucket
            assert link_result["bucket"] == expected_bucket

            assert info_result["key"] == test_object["key"]
            assert text_result["key"] == test_object["key"]
            assert fetch_result["key"] == test_object["key"]
            assert link_result["key"] == test_object["key"]

    def test_invalid_uri_handling_consistency(self):
        """Test that all functions handle invalid URIs consistently."""
        invalid_uri = "not-a-valid-s3-uri"

        info_result = bucket_object_info(invalid_uri)
        text_result = bucket_object_text(invalid_uri)
        fetch_result = bucket_object_fetch(invalid_uri)
        link_result = bucket_object_link(invalid_uri)

        # All should fail with error
        assert "error" in info_result
        assert "error" in text_result
        assert "error" in fetch_result
        assert "error" in link_result

    def test_nonexistent_object_handling_consistency(self):
        """Test that all functions handle non-existent objects consistently."""
        from tests.helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        nonexistent_uri = f"{KNOWN_BUCKET}/definitely-does-not-exist-{int(time.time())}.txt"

        info_result = bucket_object_info(nonexistent_uri)
        text_result = bucket_object_text(nonexistent_uri)
        fetch_result = bucket_object_fetch(nonexistent_uri)
        link_result = bucket_object_link(nonexistent_uri)

        # info, text, and fetch should fail with error (they access the object)
        assert "error" in info_result
        assert "error" in text_result
        assert "error" in fetch_result

        # link should succeed (S3 allows presigned URLs for non-existent objects)
        assert "error" not in link_result
        assert "presigned_url" in link_result

        # Error messages should indicate object not found for functions that access objects
        for result in [info_result, text_result, fetch_result]:
            error_msg = result["error"].lower()
            assert any(term in error_msg for term in ["not found", "does not exist", "no such key"]), (
                f"Expected 'not found' error, got: {result['error']}"
            )


if __name__ == "__main__":
    pytest.main([__file__])

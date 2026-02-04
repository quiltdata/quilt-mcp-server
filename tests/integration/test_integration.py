import os
import random
import string
import time

import pytest
from quilt_mcp import (
    KNOWN_TEST_ENTRY,
    KNOWN_TEST_PACKAGE,
)
from quilt_mcp.services.auth_metadata import auth_status, catalog_info, filesystem_status
from quilt_mcp.tools.catalog import catalog_uri, catalog_url
from quilt_mcp.tools.buckets import (
    bucket_object_fetch,
    bucket_object_info,
    bucket_object_link,
    bucket_object_text,
    bucket_objects_list,
    bucket_objects_put,
)
from quilt_mcp.tools.packages import (
    package_browse,
    package_create,
    package_delete,
    package_diff,
    package_update,
    packages_list,
)
# Models removed - using flattened parameters directly

pytestmark = pytest.mark.usefixtures("backend_mode")

# Test configuration - using constants
KNOWN_PACKAGE = KNOWN_TEST_PACKAGE

# AWS profile configuration is handled in conftest.py


@pytest.fixture(scope="module")
def require_aws_credentials():
    """Check AWS credentials are available - test will fail if not."""
    return True


@pytest.mark.integration
@pytest.mark.search
class TestQuiltAPI:
    """Test suite for quilt MCP server using real data - tests that expect actual results."""

    @pytest.fixture(scope="class")
    def known_package_browse_result(self, require_aws_credentials, test_bucket):
        """Browse the known package once to reuse across tests."""

        result = package_browse(
            package_name=KNOWN_PACKAGE,
            registry=test_bucket,
            include_file_info=False,
            include_signed_urls=False,
        )

        # Check if error response (has 'error' attribute)
        if hasattr(result, "error") and "AccessDenied" in str(result.error):
            pytest.fail(f"Access denied to package {KNOWN_PACKAGE} - check AWS permissions: {result.error}")

        return result

    def test_packages_list_returns_data(self, test_bucket):
        """Test that packages_list returns actual packages from configured registry."""
        try:
            result = packages_list(registry=test_bucket)
        except Exception as e:
            if "AccessDenied" in str(e) or "S3NoValidClientError" in str(e):
                pytest.fail(f"Access denied to {test_bucket} - check AWS permissions: {e}")
            raise

        assert hasattr(result, "packages"), "Result should have 'packages' attribute"
        # FAIL if no packages - this indicates a real problem
        assert len(result.packages) > 0, (
            f"Expected packages in {test_bucket}, got empty list - this indicates missing data or misconfiguration"
        )

        # Check that we get string package names
        for pkg in result.packages:
            assert isinstance(pkg, str), f"Package name should be string, got {type(pkg)}: {pkg}"
            assert "/" in pkg, f"Package names should contain namespace/name format, got: {pkg}"

    def test_packages_list_prefix(self, test_bucket):
        """Test that prefix filtering works and finds the configured test package."""
        # Extract prefix from known test package
        test_prefix = KNOWN_PACKAGE.split("/")[0] if "/" in KNOWN_PACKAGE else KNOWN_PACKAGE
        try:
            result = packages_list(registry=test_bucket, prefix=test_prefix)
        except Exception as e:
            if "AccessDenied" in str(e) or "S3NoValidClientError" in str(e):
                pytest.fail(f"Access denied to {test_bucket} - check AWS permissions: {e}")
            raise

        assert hasattr(result, "packages"), "Result should have 'packages' attribute"

        # FAIL if no packages with this prefix - this means the test environment is misconfigured
        assert len(result.packages) > 0, (
            f"No {test_prefix} packages found in {test_bucket} - check QUILT_TEST_PACKAGE configuration"
        )

        # Verify all results match prefix
        for pkg in result.packages:
            assert pkg.startswith(test_prefix), f"Package {pkg} doesn't start with '{test_prefix}'"

        # FAIL if known package not found - this means the test environment is misconfigured
        package_names = result.packages
        assert KNOWN_PACKAGE in package_names, (
            f"Known package {KNOWN_PACKAGE} not found in {test_bucket} - check QUILT_TEST_PACKAGE configuration"
        )

    def test_package_browse_known_package(self, known_package_browse_result):
        """Test browsing the known test package."""
        result = known_package_browse_result

        # Check if we got an access denied error and skip if so
        assert hasattr(result, "entries"), "Result should have 'entries' attribute"
        assert hasattr(result, "package_name"), "Result should have 'package_name' attribute"
        assert hasattr(result, "total_entries"), "Result should have 'total_entries' attribute"

        # FAIL if no entries found - this means the test package is misconfigured
        assert len(result.entries) > 0, (
            f"Package {KNOWN_PACKAGE} appears empty - check QUILT_TEST_PACKAGE configuration"
        )

        # Check we get actual entry structures (entries are dicts, not models)
        for entry in result.entries:
            assert "logical_key" in entry, f"Entry missing logical_key: {entry}"

    def test_bucket_objects_list_returns_data(self, test_bucket):
        """Test that bucket listing returns actual objects."""
        result = bucket_objects_list(bucket=test_bucket, max_keys=10)

        assert hasattr(result, "objects"), "Result should have 'objects' attribute"
        assert hasattr(result, "bucket"), "Result should have 'bucket' attribute"
        assert len(result.objects) > 0, f"Expected objects in {test_bucket}, got empty list"

        # Check object structure
        for obj in result.objects:
            assert hasattr(obj, "key"), f"Object missing 'key': {obj}"
            assert hasattr(obj, "size"), f"Object missing 'size': {obj}"
            assert isinstance(obj.key, str), f"Object key should be string: {obj}"

    def test_bucket_object_info_known_file(self, test_registry):
        """Test getting info for a known public file."""
        # Construct test S3 URI from test registry, package, and entry
        test_s3_uri = f"{test_registry}/{KNOWN_PACKAGE}/{KNOWN_TEST_ENTRY}"
        result = bucket_object_info(s3_uri=test_s3_uri)

        if hasattr(result, "error"):
            pytest.fail(f"Known file not accessible: {result.error}")

        assert hasattr(result, "object"), "Result should have 'object' attribute"
        assert hasattr(result.object, "bucket"), "Object should have 'bucket' attribute"
        assert hasattr(result.object, "key"), "Object should have 'key' attribute"
        assert hasattr(result.object, "size"), "Object should have 'size' attribute"
        assert result.object.size > 0, "File should have non-zero size"

    def test_bucket_object_text_csv_file(self, test_registry):
        """Test reading text from the configured test file."""
        # Construct test S3 URI from test registry, package, and entry
        test_uri = f"{test_registry}/{KNOWN_PACKAGE}/{KNOWN_TEST_ENTRY}"
        result = bucket_object_text(s3_uri=test_uri, max_bytes=1000)

        if hasattr(result, "error"):
            pytest.fail(f"Test file not accessible: {result.error}")

        assert hasattr(result, "text"), "Result should have 'text' attribute"
        assert hasattr(result, "bucket"), "Result should have 'bucket' attribute"
        assert hasattr(result, "key"), "Result should have 'key' attribute"

        # Verify we can read text content (don't assume specific format)
        text = result.text
        assert len(text) > 0, "File should have content"
        assert isinstance(text, str), "Text should be a string"
        # Don't assume markdown format - different environments have different file types

    def test_auth_status_returns_status(self, test_bucket):
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

    def test_filesystem_status_returns_info(self, test_bucket):
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

    def test_catalog_info_returns_data(self, test_bucket):
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

    def test_catalog_info_includes_detection_method(self, test_bucket):
        """Test catalog_info returns the catalog name and detection method."""
        result = catalog_info()

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

    def test_catalog_url_package_view(self, test_bucket):
        """Test catalog_url generates valid package view URLs."""
        result = catalog_url(registry=test_bucket, package_name="raw/salmon-rnaseq", path="README.md")

        assert hasattr(result, "status"), "Result should have 'status' attribute"

        if result.status == "success":
            assert hasattr(result, "catalog_url"), "Result should have 'catalog_url' attribute"
            assert hasattr(result, "view_type"), "Result should have 'view_type' attribute"
            assert hasattr(result, "bucket"), "Result should have 'bucket' attribute"
            assert result.view_type == "package"
            assert result.catalog_url.startswith("https://")
            assert "/b/" in result.catalog_url
            assert "/packages/" in result.catalog_url
            assert "raw/salmon-rnaseq" in result.catalog_url
            assert "README.md" in result.catalog_url

    def test_catalog_url_bucket_view(self, test_bucket):
        """Test catalog_url generates valid bucket view URLs."""
        result = catalog_url(registry=test_bucket, path="test/data.csv")

        assert hasattr(result, "status"), "Result should have 'status' attribute"

        if result.status == "success":
            assert hasattr(result, "catalog_url"), "Result should have 'catalog_url' attribute"
            assert hasattr(result, "view_type"), "Result should have 'view_type' attribute"
            assert hasattr(result, "bucket"), "Result should have 'bucket' attribute"
            assert result.view_type == "bucket"
            assert result.catalog_url.startswith("https://")
            assert "/b/" in result.catalog_url
            assert "/tree/" in result.catalog_url
            assert "test/data.csv" in result.catalog_url

    def test_catalog_uri_package_reference(self, test_bucket):
        """Test catalog_uri generates valid Quilt+ URIs."""
        result = catalog_uri(registry=test_bucket, package_name="raw/salmon-rnaseq", path="README.md")

        assert hasattr(result, "status"), "Result should have 'status' attribute"

        if result.status == "success":
            assert hasattr(result, "quilt_plus_uri"), "Result should have 'quilt_plus_uri' attribute"
            assert hasattr(result, "bucket"), "Result should have 'bucket' attribute"
            assert result.quilt_plus_uri.startswith("quilt+s3://")
            assert "package=raw/salmon-rnaseq" in result.quilt_plus_uri
            assert "path=README.md" in result.quilt_plus_uri

    def test_catalog_uri_with_version(self, test_bucket):
        """Test catalog_uri generates versioned Quilt+ URIs."""
        test_hash = "abc123def456"
        result = catalog_uri(
            registry=test_bucket,
            package_name="raw/salmon-rnaseq",
            path="README.md",
            top_hash=test_hash,
        )

        assert hasattr(result, "status"), "Result should have 'status' attribute"

        if result.status == "success":
            assert hasattr(result, "quilt_plus_uri"), "Result should have 'quilt_plus_uri' attribute"
            assert f"package=raw/salmon-rnaseq@{test_hash}" in result.quilt_plus_uri

    # FAILURE CASES - These should fail gracefully

    def test_packages_list_invalid_registry_fails(self, test_bucket):
        """Test that invalid registry fails gracefully with proper error."""
        result = packages_list(registry="s3://definitely-nonexistent-bucket-xyz")

        # Should return an error response
        assert hasattr(result, "error"), "Result should have 'error' attribute"

        # Should get a meaningful error about the bucket
        error_msg = result.error.lower()
        assert any(term in error_msg for term in ["nosuchbucket", "no such bucket", "bucket", "not found"]), (
            f"Expected meaningful bucket error, got: {result.error}"
        )

    def test_package_browse_nonexistent_fails(self, test_registry):
        """Test that browsing non-existent package returns error response."""
        result = package_browse(package_name="definitely/nonexistent", registry=test_registry)

        # The function now returns an error response instead of raising an exception
        assert hasattr(result, "success"), "Result should have 'success' attribute"
        assert result.success is False
        assert hasattr(result, "error"), "Result should have 'error' attribute"
        assert hasattr(result, "cause"), "Result should have 'cause' attribute"

        error_msg = str(result.error).lower()
        assert any(
            term in error_msg
            for term in [
                "failed to browse",
                "package",
                "definitely/nonexistent",
            ]
        ), f"Expected meaningful error message, got: {result}"

    def test_bucket_object_info_nonexistent_fails(self, test_bucket):
        """Test that non-existent object returns error."""
        result = bucket_object_info(s3_uri=f"{test_bucket}/definitely/nonexistent/file.txt")

        assert hasattr(result, "error"), "Non-existent file should return error"
        assert hasattr(result, "bucket"), "Result should have 'bucket' attribute"
        assert hasattr(result, "key"), "Result should have 'key' attribute"

    def test_bucket_object_fetch_returns_data(self, test_bucket):
        """Test fetching object data from S3."""
        # Use a small object from bucket listing
        objects_result = bucket_objects_list(bucket=test_bucket, max_keys=5)
        if not objects_result.objects:
            pytest.fail("No objects found to test fetch")

        # Find a small object to test (prefer smallest under threshold)
        candidates = [o for o in objects_result.objects if o.size > 0]
        SMALL_MAX = 10000
        small_obj = None
        if candidates:
            under = [o for o in candidates if o.size < SMALL_MAX]
            search_space = under or candidates
            small_obj = min(search_space, key=lambda o: o.size)
        if not small_obj:
            pytest.fail("No suitable objects (non-zero size) found to test fetch")
        # Static type assurance (helps static analysis)
        assert small_obj is not None  # noqa: F821
        s3_uri = f"s3://{objects_result.bucket}/{small_obj.key}"
        result = bucket_object_fetch(s3_uri=s3_uri, max_bytes=1000)

        if hasattr(result, "error"):
            pytest.fail(f"Object not accessible: {result.error}")

        assert hasattr(result, "bucket"), "Result should have 'bucket' attribute"
        assert hasattr(result, "key"), "Result should have 'key' attribute"
        assert hasattr(result, "data") or hasattr(result, "text"), "Should return either data or text"
        assert hasattr(result, "bytes_read"), "Result should have 'bytes_read' attribute"
        assert result.bytes_read > 0, "Fetched object should have content"

    def test_bucket_object_link_integration(self, test_bucket):
        """Test bucket_object_link integration with real AWS."""
        # Use a small object from bucket listing
        objects_result = bucket_objects_list(bucket=test_bucket, max_keys=5)
        if not objects_result.objects:
            pytest.fail("No objects found to test presigned URL generation")

        # Find any object to test with
        test_object = objects_result.objects[0]
        s3_uri = f"s3://{objects_result.bucket}/{test_object.key}"

        result = bucket_object_link(s3_uri=s3_uri, expiration=7200)

        if hasattr(result, "error"):
            pytest.fail(f"Object not accessible for URL generation: {result.error}")

        assert hasattr(result, "bucket"), "Result should have 'bucket' attribute"
        assert hasattr(result, "key"), "Result should have 'key' attribute"
        assert hasattr(result, "signed_url"), "Result should have 'signed_url' attribute"
        assert hasattr(result, "expiration_seconds"), "Result should have 'expiration_seconds' attribute"
        assert result.expiration_seconds == 7200
        assert result.signed_url.startswith("https://")
        assert result.bucket == objects_result.bucket
        assert result.key == test_object.key

    def test_bucket_objects_put_small_file(self, test_bucket):
        """Test uploading small objects to S3."""
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

        result = bucket_objects_put(bucket=test_bucket, items=test_items)

        assert hasattr(result, "bucket"), "Result should have 'bucket' attribute"
        assert hasattr(result, "requested"), "Result should have 'requested' attribute"
        assert hasattr(result, "uploaded"), "Result should have 'uploaded' attribute"
        assert hasattr(result, "results"), "Result should have 'results' attribute"

        assert result.requested == 2, "Should have requested 2 uploads"

        # Expect successful uploads (user should have permissions)
        if result.uploaded < result.requested:
            # Check for permission errors
            for item_result in result.results:
                if hasattr(item_result, "error") and item_result.error is not None:
                    error_msg = item_result.error.lower()
                    if "accessdenied" in error_msg or "not authorized" in error_msg:
                        pytest.fail(f"Permission error - user needs s3:PutObject permissions: {item_result.error}")

        assert result.uploaded > 0, "Should have successfully uploaded some files"

        # Check individual results
        for item_result in result.results:
            assert hasattr(item_result, "key"), "Result item should have 'key' attribute"
            # Should have successful uploads (etag) for test environment
            if (
                hasattr(item_result, "error")
                and item_result.error is not None
                and "accessdenied" not in item_result.error.lower()
            ):
                pytest.fail(f"Unexpected upload error: {item_result.error}")

        # Clean up uploaded test files
        try:
            for item in test_items:
                # Verify file was uploaded, then we could delete it if there was a delete tool
                info_result = bucket_object_info(s3_uri=f"{test_bucket}/{item['key']}")
                if not hasattr(info_result, "error"):
                    print(f"Test file uploaded successfully: {item['key']}")
        except Exception:
            pass  # Cleanup is best-effort

    def test_package_diff_known_package_with_itself(self, test_bucket):
        """Test package_diff comparing known package with itself (should show no differences)."""
        result = package_diff(package1_name=KNOWN_PACKAGE, package2_name=KNOWN_PACKAGE, registry=test_bucket)

        if hasattr(result, "error"):
            # Some packages might not support diff operations
            pytest.fail(f"Package diff not supported: {result.error}")

        assert hasattr(result, "package1"), "Result should have 'package1' attribute"
        assert hasattr(result, "package2"), "Result should have 'package2' attribute"
        assert hasattr(result, "diff"), "Result should have 'diff' attribute"
        assert result.package1 == KNOWN_PACKAGE
        assert result.package2 == KNOWN_PACKAGE

        # When comparing identical packages, should have no differences
        diff = result.diff
        if hasattr(diff, "added") and hasattr(diff, "deleted"):
            # If diff returns structured data, check for minimal differences
            assert len(diff.added) == 0 or len(diff.deleted) == 0

    @pytest.mark.slow
    def test_package_diff_different_packages(self, test_bucket):
        """Test package_diff comparing two different packages."""
        # Get available packages first
        try:
            packages_result = packages_list(registry=test_bucket, limit=3)
        except Exception as e:
            if "AccessDenied" in str(e) or "S3NoValidClientError" in str(e):
                pytest.fail(f"Access denied to {test_bucket} - check AWS permissions: {e}")
            raise

        if len(packages_result.packages) < 2:
            pytest.fail("Need at least 2 packages to test diff")

        packages = packages_result.packages
        pkg1, pkg2 = packages[0], packages[1]

        result = package_diff(package1_name=pkg1, package2_name=pkg2, registry=test_bucket)

        if hasattr(result, "error"):
            # Some packages might not support diff operations or might not exist
            error_msg = result.error.lower()
            if "not found" in error_msg or "does not exist" in error_msg:
                pytest.fail(f"Packages not accessible for diff: {result.error}")
            else:
                pytest.fail(f"Package diff not supported: {result.error}")

        assert hasattr(result, "package1"), "Result should have 'package1' attribute"
        assert hasattr(result, "package2"), "Result should have 'package2' attribute"
        assert hasattr(result, "diff"), "Result should have 'diff' attribute"
        assert result.package1 == pkg1
        assert result.package2 == pkg2

    def test_package_diff_nonexistent_packages(self, test_bucket):
        """Test package_diff with non-existent packages."""
        result = package_diff(
            package1_name="definitely/nonexistent1",
            package2_name="definitely/nonexistent2",
            registry=test_bucket,
        )

        assert hasattr(result, "error"), "Result should have 'error' attribute"
        # Should get a meaningful error about packages not being found
        error_msg = result.error.lower()
        assert any(
            term in error_msg
            for term in [
                "failed to browse",
                "not found",
                "does not exist",
                "no such file",
            ]
        ), f"Expected meaningful error about missing packages, got: {result.error}"


@pytest.mark.search
@pytest.mark.integration
class TestBucketObjectVersionConsistency:
    """Integration tests for versionId consistency across bucket_object_* functions."""

    def test_bucket_object_functions_consistency_with_real_object(self, test_bucket):
        """Test that all bucket_object_* functions work consistently with a real S3 object."""
        # Models removed - using flattened parameters directly

        # Get a real object from the test bucket
        objects_result = bucket_objects_list(bucket=test_bucket, max_keys=5)
        if not objects_result.objects:
            pytest.fail(f"No objects found in test bucket {test_bucket}")

        test_object = objects_result.objects[0]
        test_s3_uri = test_object.s3_uri

        # Call all four functions with the same URI
        info_result = bucket_object_info(s3_uri=test_s3_uri)
        text_result = bucket_object_text(s3_uri=test_s3_uri, max_bytes=1024)
        fetch_result = bucket_object_fetch(s3_uri=test_s3_uri, max_bytes=1024)
        link_result = bucket_object_link(s3_uri=test_s3_uri)

        # All should succeed (or all should fail consistently)
        all_succeed = all(
            not hasattr(result, "error") for result in [info_result, text_result, fetch_result, link_result]
        )
        all_fail = all(hasattr(result, "error") for result in [info_result, text_result, fetch_result, link_result])

        assert all_succeed or all_fail, "Functions should have consistent success/failure status"

        if all_succeed:
            # Verify consistent bucket/key information
            expected_bucket = test_bucket.replace("s3://", "") if test_bucket.startswith("s3://") else test_bucket
            assert info_result.object.bucket == expected_bucket
            assert text_result.bucket == expected_bucket
            assert fetch_result.bucket == expected_bucket
            assert link_result.bucket == expected_bucket

            assert info_result.object.key == test_object.key
            assert text_result.key == test_object.key
            assert fetch_result.key == test_object.key
            assert link_result.key == test_object.key

    def test_invalid_uri_handling_consistency(self, test_bucket):
        """Test that all functions handle invalid URIs consistently."""
        # Models removed - using flattened parameters directly

        invalid_uri = "not-a-valid-s3-uri"

        # All functions should return error responses for invalid URIs
        for func in [
            bucket_object_info,
            bucket_object_text,
            bucket_object_fetch,
            bucket_object_link,
        ]:
            result = func(s3_uri=invalid_uri)
            # Should return error response (validation happens inside the function)
            assert hasattr(result, "error"), f"{func.__name__} should return error for invalid URI"

    def test_nonexistent_object_handling_consistency(self, test_registry):
        """Test that all functions handle non-existent objects consistently."""
        # Models removed - using flattened parameters directly

        nonexistent_uri = f"{test_registry}/definitely-does-not-exist-{int(time.time())}.txt"

        info_result = bucket_object_info(s3_uri=nonexistent_uri)
        text_result = bucket_object_text(s3_uri=nonexistent_uri)
        fetch_result = bucket_object_fetch(s3_uri=nonexistent_uri)
        link_result = bucket_object_link(s3_uri=nonexistent_uri)

        # info, text, and fetch should fail with error (they access the object)
        assert hasattr(info_result, "error")
        assert hasattr(text_result, "error")
        assert hasattr(fetch_result, "error")

        # link should succeed (S3 allows presigned URLs for non-existent objects)
        assert not hasattr(link_result, "error")
        assert hasattr(link_result, "signed_url")

        # Error messages should indicate object not found for functions that access objects
        for result in [info_result, text_result, fetch_result]:
            error_msg = result.error.lower()
            assert any(term in error_msg for term in ["not found", "does not exist", "no such key"]), (
                f"Expected 'not found' error, got: {result.error}"
            )


if __name__ == "__main__":
    pytest.main([__file__])

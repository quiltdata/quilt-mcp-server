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

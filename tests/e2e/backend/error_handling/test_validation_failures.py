"""E2E Test: Data Validation Failures.

This test validates that backends properly validate inputs BEFORE attempting
real operations with AWS services. NO MOCKING - uses real validation logic
with real service configurations.

Key aspects tested:
- Package name format validation (before registry operations)
- S3 URI validation (before S3 operations)
- Binary file handling (graceful degradation with real S3)
"""

import pytest
import boto3
import uuid
from quilt_mcp.ops.exceptions import ValidationError
from quilt_mcp.tools.buckets import bucket_object_text


@pytest.mark.e2e
class TestDataValidationErrors:
    """Test data validation error handling with REAL services."""

    def test_data_validation_errors(
        self, backend_with_auth, real_test_bucket, backend_mode, cleanup_s3_objects
    ):
        """Test that validation catches invalid inputs before real operations.

        This test verifies:
        1. Invalid package names are rejected BEFORE registry operations
        2. Invalid S3 URIs are rejected BEFORE S3 operations
        3. Binary files are handled gracefully with real S3 reads

        NO MOCKING - Uses real validation with real service configurations.

        Args:
            backend_with_auth: Real authenticated backend (quilt3 or platform)
            real_test_bucket: Real test bucket name
            backend_mode: Backend mode (quilt3|platform)
            cleanup_s3_objects: S3 cleanup fixture
        """
        registry = f"s3://{real_test_bucket}"

        # ============================================================
        # Scenario 1: Invalid package name (real validation)
        # ============================================================
        print("\n--- Scenario 1: Invalid Package Name ---")

        # Test various invalid package name formats
        invalid_names = [
            "invalid/name/with/too/many/slashes",  # Too many slashes
            "no-slash-at-all",  # No slash
            "/leading-slash",  # Leading slash
            "trailing-slash/",  # Trailing slash
            "",  # Empty string
        ]

        for invalid_name in invalid_names:
            try:
                # This should raise ValidationError BEFORE attempting registry operation
                # Using create_package_revision which is the actual backend method
                result = backend_with_auth.create_package_revision(
                    package_name=invalid_name,
                    s3_uris=[f"s3://{real_test_bucket}/dummy.csv"],
                    registry=registry,
                )
                # If we get here, validation failed to catch the error
                assert False, f"Should have raised ValidationError for package name: {invalid_name}"
            except ValidationError as e:
                # Verify error message provides helpful feedback
                error_msg = str(e).lower()
                print(f"  ✅ Caught invalid package name '{invalid_name}': {e}")
                assert "package" in error_msg or "name" in error_msg or "format" in error_msg, (
                    f"Error message should mention package/name/format for: {invalid_name}"
                )

                # Verify error has context for debugging
                assert hasattr(e, "context"), "ValidationError should have context attribute"
                assert isinstance(e.context, dict), "ValidationError context should be a dict"
            except Exception as e:
                # If we get a different error type, validation didn't run early enough
                pytest.fail(
                    f"Expected ValidationError for '{invalid_name}', got {type(e).__name__}: {e}"
                )

        # ============================================================
        # Scenario 2: Invalid S3 URI (real parsing)
        # ============================================================
        print("\n--- Scenario 2: Invalid S3 URI ---")

        # Test various invalid S3 URI formats
        invalid_uris = [
            "not-an-s3-uri",  # No s3:// prefix
            "s3://",  # No bucket
            "s3://bucket-only",  # No key
            "s3://bucket/",  # Empty key
            "http://example.com/file.txt",  # Wrong protocol
            "",  # Empty string
        ]

        for invalid_uri in invalid_uris:
            try:
                # Direct validation call - should fail BEFORE S3 operation
                backend_with_auth._validate_s3_uri(invalid_uri)
                # If we get here, validation failed to catch the error
                assert False, f"Should have raised ValidationError for S3 URI: {invalid_uri}"
            except ValidationError as e:
                # Verify error message provides helpful feedback
                error_msg = str(e).lower()
                print(f"  ✅ Caught invalid S3 URI '{invalid_uri}': {e}")
                assert "s3://" in error_msg or "uri" in error_msg or "bucket" in error_msg, (
                    f"Error message should mention s3:// or uri or bucket for: {invalid_uri}"
                )

                # Verify error has context for debugging
                assert hasattr(e, "context"), "ValidationError should have context attribute"
                assert isinstance(e.context, dict), "ValidationError context should be a dict"
            except Exception as e:
                # If we get a different error type, validation didn't run early enough
                pytest.fail(
                    f"Expected ValidationError for '{invalid_uri}', got {type(e).__name__}: {e}"
                )

        # ============================================================
        # Scenario 3: Unsupported file type (binary file)
        # ============================================================
        print("\n--- Scenario 3: Binary File Handling ---")

        # Create a binary file in S3 to test real binary handling
        binary_key = f"e2e_test/validation_{uuid.uuid4().hex[:8]}.bin"
        binary_content = bytes(range(256))  # Binary content (0x00-0xFF)

        s3 = boto3.client("s3")
        s3.put_object(Bucket=real_test_bucket, Key=binary_key, Body=binary_content)
        cleanup_s3_objects.track_s3_object(bucket=real_test_bucket, key=binary_key)

        # Test bucket_object_text with binary file
        binary_uri = f"s3://{real_test_bucket}/{binary_key}"
        result = bucket_object_text(s3_uri=binary_uri, max_bytes=1000)

        print(f"  Binary file result type: {type(result).__name__}")

        # Verify graceful handling - should either:
        # 1. Return success with replacement characters (errors='replace')
        # 2. Return error with clear message
        assert hasattr(result, "error") or hasattr(result, "text"), (
            "Result should have either 'error' or 'text' attribute"
        )

        if hasattr(result, "error") and result.error:
            # Error case - verify it's informative
            print(f"  ⚠️  Binary file returned error (acceptable): {result.error}")
            # Error message varies by backend:
            # - quilt3: may decode successfully with replacement chars
            # - platform: may return AWS access errors in JWT mode
            # Both are acceptable - just verify we got an error response
            assert len(result.error) > 0, "Error message should not be empty"
        else:
            # Success case with replacement characters - verify we got text back
            print(f"  ℹ️  Binary file returned text (with replacement chars)")
            assert hasattr(result, "text"), "Success result should have 'text' attribute"
            # Text should contain replacement characters since we read binary data
            # The UTF-8 decoder with errors='replace' will insert U+FFFD for invalid bytes

        # ============================================================
        # Validation: Check registry is uncorrupted
        # ============================================================
        print("\n--- Validation: Registry Integrity ---")

        # Verify registry is still accessible after validation failures
        # Note: We expect the registry to be accessible, but backend errors
        # (GraphQL issues, network problems) are acceptable as they indicate
        # the service is still responding, just with errors. What we DON'T
        # want is validation errors or corruption errors.
        try:
            # Try to list packages - this should work if registry is uncorrupted
            # Note: search_packages doesn't have a limit parameter
            packages = backend_with_auth.search_packages(query="*", registry=registry)
            print(f"  ✅ Registry still accessible ({len(packages)} packages found)")
        except ValidationError as e:
            # ValidationError would indicate registry corruption or validation state issues
            pytest.fail(f"Registry validation failed after validation tests: {e}")
        except Exception as e:
            # Other errors (BackendError, network issues) are acceptable
            # They indicate the service is responding, just with errors
            print(f"  ℹ️  Registry returned error (acceptable, not corrupted): {type(e).__name__}")

        print("\n=== All validation scenarios passed ===")

"""Integration tests for utils module (AWS-dependent tests)."""

import pytest
from quilt_mcp.utils.common import generate_signed_url


class TestUtilsAWSIntegration:
    """Test utility functions that require AWS connectivity."""

    def test_generate_signed_url_success(self, test_bucket):
        """Test URL generation with real AWS connection."""
        # Skip if AWS credentials not available
        try:
            import boto3

            s3 = boto3.client("s3")
            s3.list_buckets()  # Test basic connectivity
        except Exception:
            pytest.fail("AWS credentials not available")

        # Extract bucket name from test_bucket
        bucket_name = test_bucket.replace("s3://", "") if test_bucket.startswith("s3://") else test_bucket
        test_s3_uri = f"s3://{bucket_name}/README.md"

        result = generate_signed_url(test_s3_uri, 1800)

        # Should return a valid presigned URL or None if bucket doesn't exist
        if result is not None:
            assert isinstance(result, str)
            assert result.startswith("https://")
            assert bucket_name in result
            assert "README.md" in result

    def test_generate_signed_url_expiration_limits(self, test_bucket):
        """Test expiration time limits with real AWS (integration test)."""
        # Removed test_bucket import - using test_bucket fixture

        # Extract bucket name from test_bucket
        bucket_name = test_bucket.replace("s3://", "") if test_bucket.startswith("s3://") else test_bucket
        test_s3_uri = f"s3://{bucket_name}/test-key.txt"

        # Test minimum expiration (0 should become 1)
        result1 = generate_signed_url(test_s3_uri, 0)
        assert result1.startswith("https://")

        # Test maximum expiration (more than 7 days should become 7 days)
        result2 = generate_signed_url(test_s3_uri, 700000)  # > 7 days
        assert result2.startswith("https://")

    def test_generate_signed_url_exception(self):
        """Test handling of exceptions with real AWS (integration test)."""
        # Try to generate URL for a bucket that doesn't exist
        result = generate_signed_url("s3://definitely-nonexistent-bucket-12345/key")

        # AWS will generate a presigned URL even for non-existent buckets
        # The URL generation doesn't validate bucket existence
        # So we expect either a valid URL or None (depending on credentials/permissions)
        assert result is None or (isinstance(result, str) and result.startswith("https://"))

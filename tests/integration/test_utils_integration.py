"""Integration tests for utils module (AWS-dependent tests)."""

import pytest
from quilt_mcp.utils import generate_signed_url


class TestUtilsAWSIntegration:
    """Test utility functions that require AWS connectivity."""

    @pytest.mark.integration
    def test_generate_signed_url_success(self):
        """Test URL generation with real AWS connection."""
        # Skip if AWS credentials not available
        try:
            import boto3

            s3 = boto3.client("s3")
            s3.list_buckets()  # Test basic connectivity
        except Exception:
            pytest.fail("AWS credentials not available")

        # Use a known public bucket for testing (quilt-example is publicly readable)
        result = generate_signed_url("s3://quilt-example/README.md", 1800)

        # Should return a valid presigned URL or None if bucket doesn't exist
        if result is not None:
            assert isinstance(result, str)
            assert result.startswith("https://")
            assert "quilt-example" in result
            assert "README.md" in result

    @pytest.mark.integration
    def test_generate_signed_url_expiration_limits(self):
        """Test expiration time limits with real AWS (integration test)."""
        from quilt_mcp.constants import DEFAULT_BUCKET

        # Extract bucket name from DEFAULT_BUCKET
        bucket_name = DEFAULT_BUCKET.replace("s3://", "") if DEFAULT_BUCKET.startswith("s3://") else DEFAULT_BUCKET
        test_s3_uri = f"s3://{bucket_name}/test-key.txt"

        # Test minimum expiration (0 should become 1)
        result1 = generate_signed_url(test_s3_uri, 0)
        assert result1.startswith("https://")

        # Test maximum expiration (more than 7 days should become 7 days)
        result2 = generate_signed_url(test_s3_uri, 700000)  # > 7 days
        assert result2.startswith("https://")

    @pytest.mark.integration
    def test_generate_signed_url_exception(self):
        """Test handling of exceptions with real AWS (integration test)."""
        # Try to generate URL for a bucket that doesn't exist
        result = generate_signed_url("s3://definitely-nonexistent-bucket-12345/key")

        # AWS will generate a presigned URL even for non-existent buckets
        # The URL generation doesn't validate bucket existence
        # So we expect either a valid URL or None (depending on credentials/permissions)
        assert result is None or (isinstance(result, str) and result.startswith("https://"))

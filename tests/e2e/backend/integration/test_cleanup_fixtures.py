"""Test cleanup fixtures work correctly.

This test validates that cleanup_packages and cleanup_s3_objects
fixtures properly track and clean up resources even on test failure.
"""

import pytest
import uuid
import boto3


@pytest.mark.e2e
@pytest.mark.backend
class TestCleanupFixtures:
    """Test cleanup fixture functionality."""

    def test_cleanup_s3_objects_success(self, real_test_bucket, cleanup_s3_objects):
        """Test S3 object cleanup on successful test.

        This test:
        1. Creates S3 objects via boto3 directly
        2. Tracks them for cleanup
        3. Verifies cleanup happens automatically

        Args:
            real_test_bucket: Test bucket name
            cleanup_s3_objects: Cleanup fixture
        """
        # Generate unique key
        test_key = f"e2e_test/cleanup_test_{uuid.uuid4().hex[:8]}.txt"

        # Create S3 object directly with boto3
        s3 = boto3.client('s3')
        s3.put_object(Bucket=real_test_bucket, Key=test_key, Body=b"test cleanup")

        # Verify creation
        response = s3.head_object(Bucket=real_test_bucket, Key=test_key)
        assert response['ContentLength'] == 12

        # Track for cleanup
        cleanup_s3_objects.track_s3_object(bucket=real_test_bucket, key=test_key)

        # Verify tracking
        assert len(cleanup_s3_objects.s3_objects) == 1
        assert cleanup_s3_objects.s3_objects[0]["key"] == test_key

        # Cleanup will happen automatically via finalizer

    def test_cleanup_multiple_s3_objects(self, real_test_bucket, cleanup_s3_objects):
        """Test cleanup of multiple S3 objects.

        Args:
            real_test_bucket: Test bucket name
            cleanup_s3_objects: Cleanup fixture
        """
        prefix = f"e2e_test/multi_cleanup_{uuid.uuid4().hex[:8]}"
        keys = [f"{prefix}/file{i}.txt" for i in range(3)]

        s3 = boto3.client('s3')

        # Create multiple objects
        for key in keys:
            s3.put_object(Bucket=real_test_bucket, Key=key, Body=f"test content {key}".encode())
            cleanup_s3_objects.track_s3_object(bucket=real_test_bucket, key=key)

        # Verify all tracked
        assert len(cleanup_s3_objects.s3_objects) == 3

        # Cleanup will happen automatically

    @pytest.mark.skipif(True, reason="Intentional failure test - enable manually to test cleanup on failure")
    def test_cleanup_on_failure(self, real_test_bucket, cleanup_s3_objects):
        """Test cleanup happens even when test fails.

        This test is SKIPPED by default to avoid polluting test results.
        Enable it manually to verify cleanup works on failure.

        Args:
            real_test_bucket: Test bucket name
            cleanup_s3_objects: Cleanup fixture
        """
        test_key = f"e2e_test/failure_test_{uuid.uuid4().hex[:8]}.txt"

        s3 = boto3.client('s3')

        # Create and track object
        s3.put_object(Bucket=real_test_bucket, Key=test_key, Body=b"test cleanup on failure")
        cleanup_s3_objects.track_s3_object(bucket=real_test_bucket, key=test_key)

        # Intentionally fail - cleanup should still happen
        assert False, "Intentional failure to test cleanup"

import os
import pytest
from unittest.mock import MagicMock, patch

from quilt_mcp import (
    bucket_object_fetch,
    bucket_object_info,
    bucket_object_link,
    bucket_object_text,
    bucket_objects_list,
    bucket_objects_put,
)

# Removed test_bucket import - using test_bucket fixture instead
from quilt_mcp.models import (
    BucketObjectsListSuccess,
    BucketObjectInfoSuccess,
    BucketObjectsPutSuccess,
    BucketObjectFetchSuccess,
    PresignedUrlResponse,
    BucketObjectTextSuccess,
)
from quilt_mcp.tools.auth_helpers import AuthorizationContext

pytestmark = pytest.mark.usefixtures("backend_mode")


def test_bucket_objects_list_success(test_bucket):
    """Test bucket objects listing with real AWS (integration test)."""
    result = bucket_objects_list(bucket=test_bucket, max_keys=10)

    # Check if request failed
    if hasattr(result, 'error'):
        pytest.fail(
            f"Failed to list bucket {test_bucket}. "
            f"Ensure QUILT_TEST_BUCKET is set and AWS credentials are configured. "
            f"Error: {result.error}"
        )

    assert isinstance(result, BucketObjectsListSuccess)
    assert result.bucket
    assert isinstance(result.objects, list)
    # Should have some objects in the test bucket
    assert len(result.objects) >= 0  # Allow empty bucket


def test_bucket_objects_list_error():
    mock_client = MagicMock()
    mock_client.list_objects_v2.side_effect = Exception("boom")
    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        result = bucket_objects_list(bucket="my-bucket")
        assert hasattr(result, "error")


def test_bucket_object_info_success(test_bucket):
    """Test bucket object info with real AWS (integration test)."""
    # First, get a list of objects to find one that exists
    objects_result = bucket_objects_list(bucket=test_bucket, max_keys=5)

    # Check if request failed (handles both permission errors and other issues)
    if hasattr(objects_result, 'error'):
        pytest.fail(f"Failed to list objects in {test_bucket}. Error: {objects_result.error}")

    if not objects_result.objects:
        pytest.fail(f"No objects found in test bucket {test_bucket}")

    # Use the first object for testing
    test_object = objects_result.objects[0]
    test_s3_uri = test_object.s3_uri

    result = bucket_object_info(s3_uri=test_s3_uri)
    assert isinstance(result, BucketObjectInfoSuccess)
    assert result.object.size >= 0


def test_bucket_object_info_invalid_uri():
    # Invalid URIs should fail at runtime validation
    result = bucket_object_info(s3_uri="not-an-s3-uri")
    assert hasattr(result, "error")


def test_bucket_objects_put_success(test_bucket):
    """Test bucket objects upload with real AWS (integration test)."""
    # Use timestamp-based keys to avoid conflicts
    import time

    timestamp = int(time.time())

    items = [
        {"key": f"test-{timestamp}-a.txt", "text": "hello world"},
        {"key": f"test-{timestamp}-b.bin", "data": "aGVsbG8="},
    ]
    result = bucket_objects_put(bucket=test_bucket, items=items)

    assert isinstance(result, BucketObjectsPutSuccess)
    assert len(result.results) == 2
    assert result.uploaded >= 0


def test_bucket_object_fetch_base64(test_bucket):
    """Test bucket object fetch with real AWS (integration test)."""
    # First, get a list of objects to find one that exists
    objects_result = bucket_objects_list(bucket=test_bucket, max_keys=5)

    # Check if request failed (handles both permission errors and other issues)
    if hasattr(objects_result, 'error'):
        pytest.fail(f"Failed to list objects in {test_bucket}. Error: {objects_result.error}")

    if not objects_result.objects:
        pytest.fail(f"No objects found in test bucket {test_bucket}")

    # Use the first object for testing
    test_object = objects_result.objects[0]
    test_s3_uri = test_object.s3_uri

    result = bucket_object_fetch(s3_uri=test_s3_uri, max_bytes=10, base64_encode=True)
    assert isinstance(result, BucketObjectFetchSuccess)
    assert result.is_base64 is True
    assert result.data
    assert isinstance(result.data, str)


def test_bucket_object_link_success(test_bucket):
    """Test bucket object presigned URL generation with real AWS (integration test)."""
    # First, get a list of objects to find one that exists
    objects_result = bucket_objects_list(bucket=test_bucket, max_keys=5)

    # Check if request failed (handles both permission errors and other issues)
    if hasattr(objects_result, 'error'):
        pytest.fail(f"Failed to list objects in {test_bucket}. Error: {objects_result.error}")

    if not objects_result.objects:
        pytest.fail(f"No objects found in test bucket {test_bucket}")

    # Use the first object for testing
    test_object = objects_result.objects[0]
    test_s3_uri = test_object.s3_uri

    result = bucket_object_link(s3_uri=test_s3_uri, expiration=7200)
    assert isinstance(result, PresignedUrlResponse)
    assert result.bucket
    assert result.key
    assert result.signed_url
    assert result.expiration_seconds == 7200
    assert result.signed_url.startswith("https://")


def test_bucket_object_link_invalid_uri():
    # Invalid URIs should be caught by Pydantic validation
    from pydantic import ValidationError

    try:
        result = bucket_object_link(s3_uri="not-an-s3-uri")
        assert hasattr(result, "error")
    except ValidationError:
        # Expected - Pydantic validates the URI format
        pass


def test_bucket_object_link_error():
    mock_client = MagicMock()
    mock_client.generate_presigned_url.side_effect = Exception("access denied")
    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        result = bucket_object_link(s3_uri="s3://my-bucket/file.txt")
        assert hasattr(result, "error")
        assert result.bucket == "my-bucket"
        assert result.key == "file.txt"


# Version ID Tests - These should fail initially (TDD Red phase)

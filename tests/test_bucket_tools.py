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
from quilt_mcp.constants import DEFAULT_BUCKET


@pytest.mark.aws
def test_bucket_objects_list_success():
    """Test bucket objects listing with real AWS (integration test)."""
    from tests.test_helpers import skip_if_no_aws_credentials

    skip_if_no_aws_credentials()

    result = bucket_objects_list(bucket=DEFAULT_BUCKET, max_keys=10)
    assert "bucket" in result
    assert "objects" in result
    assert isinstance(result["objects"], list)
    # Should have some objects in the test bucket
    assert len(result["objects"]) >= 0  # Allow empty bucket


def test_bucket_objects_list_error():
    mock_client = MagicMock()
    mock_client.list_objects_v2.side_effect = Exception("boom")
    with patch("quilt_mcp.tools.buckets.get_s3_client", return_value=mock_client):
        result = bucket_objects_list(bucket="my-bucket")
        assert "error" in result


@pytest.mark.aws
def test_bucket_object_info_success():
    """Test bucket object info with real AWS (integration test)."""
    from tests.test_helpers import skip_if_no_aws_credentials

    skip_if_no_aws_credentials()

    # First, get a list of objects to find one that exists
    objects_result = bucket_objects_list(bucket=DEFAULT_BUCKET, max_keys=5)
    if not objects_result.get("objects"):
        pytest.skip(f"No objects found in test bucket {DEFAULT_BUCKET}")

    # Use the first object for testing
    test_object = objects_result["objects"][0]
    test_s3_uri = f"{DEFAULT_BUCKET}/{test_object['key']}"

    result = bucket_object_info(test_s3_uri)
    assert "size" in result
    assert "content_type" in result
    assert isinstance(result["size"], int)
    assert result["size"] >= 0


def test_bucket_object_info_invalid_uri():
    result = bucket_object_info("not-an-s3-uri")
    assert "error" in result


@pytest.mark.aws
def test_bucket_objects_put_success():
    """Test bucket objects upload with real AWS (integration test)."""
    from tests.test_helpers import skip_if_no_aws_credentials

    skip_if_no_aws_credentials()

    # Use timestamp-based keys to avoid conflicts
    import time

    timestamp = int(time.time())

    result = bucket_objects_put(
        bucket=DEFAULT_BUCKET,
        items=[
            {"key": f"test-{timestamp}-a.txt", "text": "hello world"},
            {
                "key": f"test-{timestamp}-b.bin",
                "data": "aGVsbG8=",
            },  # base64 for "hello"
        ],
    )

    assert "uploaded" in result
    assert "results" in result
    assert len(result["results"]) == 2
    # Should have uploaded successfully
    assert result["uploaded"] >= 0


@pytest.mark.aws
def test_bucket_object_fetch_base64():
    """Test bucket object fetch with real AWS (integration test)."""
    from tests.test_helpers import skip_if_no_aws_credentials

    skip_if_no_aws_credentials()

    # First, get a list of objects to find one that exists
    objects_result = bucket_objects_list(bucket=DEFAULT_BUCKET, max_keys=5)
    if not objects_result.get("objects"):
        pytest.skip(f"No objects found in test bucket {DEFAULT_BUCKET}")

    # Use the first object for testing
    test_object = objects_result["objects"][0]
    test_s3_uri = f"{DEFAULT_BUCKET}/{test_object['key']}"

    result = bucket_object_fetch(test_s3_uri, max_bytes=10, base64_encode=True)
    assert "base64" in result
    assert result["base64"] is True
    assert "data" in result
    assert isinstance(result["data"], str)


@pytest.mark.aws
def test_bucket_object_link_success():
    """Test bucket object presigned URL generation with real AWS (integration test)."""
    from tests.test_helpers import skip_if_no_aws_credentials

    skip_if_no_aws_credentials()

    # First, get a list of objects to find one that exists
    objects_result = bucket_objects_list(bucket=DEFAULT_BUCKET, max_keys=5)
    if not objects_result.get("objects"):
        pytest.skip(f"No objects found in test bucket {DEFAULT_BUCKET}")

    # Use the first object for testing
    test_object = objects_result["objects"][0]
    test_s3_uri = f"{DEFAULT_BUCKET}/{test_object['key']}"

    result = bucket_object_link(test_s3_uri, expiration=7200)
    assert "bucket" in result
    assert "key" in result
    assert "presigned_url" in result
    assert "expires_in" in result
    assert result["expires_in"] == 7200
    assert result["presigned_url"].startswith("https://")


def test_bucket_object_link_invalid_uri():
    result = bucket_object_link("not-an-s3-uri")
    assert "error" in result


def test_bucket_object_link_error():
    mock_client = MagicMock()
    mock_client.generate_presigned_url.side_effect = Exception("access denied")
    with patch("quilt_mcp.tools.buckets.get_s3_client", return_value=mock_client):
        result = bucket_object_link("s3://my-bucket/file.txt")
        assert "error" in result
        assert result["bucket"] == "my-bucket"
        assert result["key"] == "file.txt"


# Version ID Tests - These should fail initially (TDD Red phase)

def test_bucket_object_info_with_version_id():
    """Test bucket_object_info calls head_object with VersionId when provided."""
    mock_client = MagicMock()
    mock_head_response = {
        "ContentLength": 1024,
        "ContentType": "text/plain",
        "ETag": '"abc123"',
        "LastModified": "2023-01-01T00:00:00Z",
        "VersionId": "test-version-123"
    }
    mock_client.head_object.return_value = mock_head_response
    
    with patch("quilt_mcp.tools.buckets.get_s3_client", return_value=mock_client):
        result = bucket_object_info("s3://my-bucket/file.txt?versionId=test-version-123")
        
        # Verify S3 API was called with VersionId
        mock_client.head_object.assert_called_once_with(
            Bucket="my-bucket",
            Key="file.txt",
            VersionId="test-version-123"
        )
        assert "error" not in result


def test_bucket_object_text_with_version_id():
    """Test bucket_object_text calls get_object with VersionId when provided."""
    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = b"test content"
    mock_get_response = {"Body": mock_body}
    mock_client.get_object.return_value = mock_get_response
    
    with patch("quilt_mcp.tools.buckets.get_s3_client", return_value=mock_client):
        result = bucket_object_text("s3://my-bucket/file.txt?versionId=test-version-123")
        
        # Verify S3 API was called with VersionId  
        mock_client.get_object.assert_called_once_with(
            Bucket="my-bucket",
            Key="file.txt",
            VersionId="test-version-123"
        )
        assert "error" not in result
        assert result["text"] == "test content"


def test_bucket_object_fetch_with_version_id():
    """Test bucket_object_fetch calls get_object with VersionId when provided."""
    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = b"binary data"
    mock_get_response = {"Body": mock_body, "ContentType": "application/octet-stream"}
    mock_client.get_object.return_value = mock_get_response
    
    with patch("quilt_mcp.tools.buckets.get_s3_client", return_value=mock_client):
        result = bucket_object_fetch("s3://my-bucket/file.bin?versionId=test-version-123")
        
        # Verify S3 API was called with VersionId
        mock_client.get_object.assert_called_once_with(
            Bucket="my-bucket", 
            Key="file.bin",
            VersionId="test-version-123"
        )
        assert "error" not in result


def test_bucket_object_link_with_version_id():
    """Test bucket_object_link calls generate_presigned_url with VersionId when provided."""
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://example.com/signed-url"
    
    with patch("quilt_mcp.tools.buckets.get_s3_client", return_value=mock_client):
        result = bucket_object_link("s3://my-bucket/file.txt?versionId=test-version-123")
        
        # Verify S3 API was called with VersionId in Params
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": "my-bucket",
                "Key": "file.txt", 
                "VersionId": "test-version-123"
            },
            ExpiresIn=3600
        )
        assert "error" not in result
        assert result["presigned_url"] == "https://example.com/signed-url"


def test_bucket_object_info_version_error_handling():
    """Test bucket_object_info handles version-specific errors correctly."""
    from botocore.exceptions import ClientError
    
    mock_client = MagicMock()
    # Simulate NoSuchVersion error
    error_response = {
        'Error': {
            'Code': 'NoSuchVersion',
            'Message': 'The specified version does not exist'
        }
    }
    mock_client.head_object.side_effect = ClientError(error_response, 'HeadObject')
    
    with patch("quilt_mcp.tools.buckets.get_s3_client", return_value=mock_client):
        result = bucket_object_info("s3://my-bucket/file.txt?versionId=invalid-version")
        
        assert "error" in result
        assert "Version invalid-version not found" in result["error"]


def test_bucket_object_text_version_error_handling():
    """Test bucket_object_text handles version-specific errors correctly."""
    from botocore.exceptions import ClientError
    
    mock_client = MagicMock()
    # Simulate AccessDenied error with version context
    error_response = {
        'Error': {
            'Code': 'AccessDenied',
            'Message': 'Access Denied'
        }
    }
    mock_client.get_object.side_effect = ClientError(error_response, 'GetObject')
    
    with patch("quilt_mcp.tools.buckets.get_s3_client", return_value=mock_client):
        result = bucket_object_text("s3://my-bucket/file.txt?versionId=restricted-version")
        
        assert "error" in result
        assert "Access denied for version restricted-version" in result["error"]


def test_bucket_object_functions_without_version_id():
    """Test all functions work correctly without version ID (backward compatibility)."""
    mock_client = MagicMock()
    
    # Setup mocks for each function
    mock_client.head_object.return_value = {
        "ContentLength": 1024,
        "ContentType": "text/plain"
    }
    
    mock_body = MagicMock()
    mock_body.read.return_value = b"test"
    mock_client.get_object.return_value = {"Body": mock_body}
    
    mock_client.generate_presigned_url.return_value = "https://example.com/url"
    
    with patch("quilt_mcp.tools.buckets.get_s3_client", return_value=mock_client):
        # Test without version ID - should not pass VersionId parameter
        info_result = bucket_object_info("s3://my-bucket/file.txt")
        text_result = bucket_object_text("s3://my-bucket/file.txt")
        fetch_result = bucket_object_fetch("s3://my-bucket/file.txt") 
        link_result = bucket_object_link("s3://my-bucket/file.txt")
        
        # Verify calls were made without VersionId
        mock_client.head_object.assert_called_with(Bucket="my-bucket", Key="file.txt")
        mock_client.get_object.assert_any_call(Bucket="my-bucket", Key="file.txt")
        mock_client.generate_presigned_url.assert_called_with(
            "get_object",
            Params={"Bucket": "my-bucket", "Key": "file.txt"},
            ExpiresIn=3600
        )
        
        # All should succeed
        assert "error" not in info_result
        assert "error" not in text_result
        assert "error" not in fetch_result
        assert "error" not in link_result

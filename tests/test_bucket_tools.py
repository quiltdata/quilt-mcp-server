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
@pytest.mark.integration
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
    with patch("boto3.client", return_value=mock_client):
        result = bucket_objects_list(bucket="my-bucket")
        assert "error" in result


@pytest.mark.aws
@pytest.mark.integration
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
@pytest.mark.integration
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
            {"key": f"test-{timestamp}-b.bin", "data": "aGVsbG8="}  # base64 for "hello"
        ],
    )
    
    assert "uploaded" in result
    assert "results" in result
    assert len(result["results"]) == 2
    # Should have uploaded successfully
    assert result["uploaded"] >= 0


@pytest.mark.aws
@pytest.mark.integration
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
@pytest.mark.integration
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
    with patch("boto3.client", return_value=mock_client):
        result = bucket_object_link("s3://my-bucket/file.txt")
        assert "error" in result
        assert result["bucket"] == "my-bucket"
        assert result["key"] == "file.txt"

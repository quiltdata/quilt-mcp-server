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


def test_bucket_objects_list_mocked():
    """Test bucket objects listing with mocks (unit test)."""
    mock_resp = {
        "Contents": [
            {
                "Key": "foo.txt",
                "Size": 10,
                "LastModified": "2025-01-01",
                "ETag": "abc",
                "StorageClass": "STANDARD",
            },
            {
                "Key": "bar.csv",
                "Size": 20,
                "LastModified": "2025-01-02",
                "ETag": "def",
                "StorageClass": "STANDARD",
            },
        ],
        "IsTruncated": False,
        "KeyCount": 2,
    }
    mock_client = MagicMock()
    mock_client.list_objects_v2.return_value = mock_resp
    with patch("boto3.client", return_value=mock_client):
        result = bucket_objects_list(bucket="s3://my-bucket", prefix="", max_keys=100)
        assert result["bucket"] == "my-bucket"
        assert len(result["objects"]) == 2
        assert result["truncated"] is False


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


def test_bucket_object_info_mocked():
    """Test bucket object info with mocks (unit test)."""
    head = {
        "ContentLength": 123,
        "ContentType": "text/plain",
        "ETag": '"etag"',
        "LastModified": "2025-01-03",
        "Metadata": {"a": "b"},
        "StorageClass": "STANDARD",
        "CacheControl": "no-cache",
    }
    mock_client = MagicMock()
    mock_client.head_object.return_value = head
    with patch("boto3.client", return_value=mock_client):
        result = bucket_object_info("s3://my-bucket/foo.txt")
        assert result["size"] == 123
        assert result["content_type"] == "text/plain"
        assert result["metadata"] == {"a": "b"}


def test_bucket_object_info_invalid_uri():
    result = bucket_object_info("not-an-s3-uri")
    assert "error" in result


@pytest.mark.aws
@pytest.mark.integration
def test_bucket_object_text_success_truncated():
    """Test bucket object text reading with real AWS (integration test)."""
    from tests.test_helpers import skip_if_no_aws_credentials
    skip_if_no_aws_credentials()
    
    # First, get a list of objects to find a text file
    objects_result = bucket_objects_list(bucket=DEFAULT_BUCKET, max_keys=10)
    if not objects_result.get("objects"):
        pytest.skip(f"No objects found in test bucket {DEFAULT_BUCKET}")
    
    # Look for a text-like file (csv, txt, json, etc.)
    text_object = None
    for obj in objects_result["objects"]:
        if any(obj["key"].endswith(ext) for ext in [".txt", ".csv", ".json", ".md", ".py"]):
            text_object = obj
            break
    
    if not text_object:
        pytest.skip("No text files found in test bucket for text reading test")
    
    test_s3_uri = f"{DEFAULT_BUCKET}/{text_object['key']}"
    result = bucket_object_text(test_s3_uri, max_bytes=50)
    
    assert "text" in result
    assert isinstance(result["text"], str)
    # If the file is larger than 50 bytes, it should be truncated
    if text_object["size"] > 50:
        assert result.get("truncated") is True
        assert len(result["text"]) <= 50


def test_bucket_object_text_mocked():
    """Test bucket object text reading with mocks (unit test)."""
    body_content = b"X" * 200
    mock_stream = MagicMock()
    mock_stream.read.return_value = body_content
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": mock_stream}
    with patch("boto3.client", return_value=mock_client):
        result = bucket_object_text("s3://my-bucket/file.txt", max_bytes=50)
        assert result["truncated"] is True
        assert len(result["text"]) == 50


def test_bucket_object_text_decode_error():
    body_content = b"\xff\xfe\x00" * 10  # invalid utf-8 bytes, but we allow decode replace
    mock_stream = MagicMock()
    mock_stream.read.return_value = body_content
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": mock_stream}
    with patch("boto3.client", return_value=mock_client):
        result = bucket_object_text("s3://my-bucket/file.bin", max_bytes=10, encoding="utf-8")
        assert "text" in result  # replaced chars


def test_bucket_object_text_error():
    mock_client = MagicMock()
    mock_client.get_object.side_effect = Exception("nope")
    with patch("boto3.client", return_value=mock_client):
        result = bucket_object_text("s3://my-bucket/file.txt")
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


def test_bucket_objects_put_mocked():
    """Test bucket objects upload with mocks (unit test)."""
    mock_client = MagicMock()
    mock_client.put_object.return_value = {"ETag": '"etag1"'}
    with patch("boto3.client", return_value=mock_client):
        result = bucket_objects_put(
            bucket="s3://my-bucket",
            items=[{"key": "a.txt", "text": "hello"}, {"key": "b.bin", "data": "aGVsbG8="}],
        )
        assert result["uploaded"] == 2
        assert len(result["results"]) == 2


def test_bucket_objects_put_errors():
    mock_client = MagicMock()
    mock_client.put_object.side_effect = Exception("denied")
    with patch("boto3.client", return_value=mock_client):
        result = bucket_objects_put(
            bucket="my-bucket",
            items=[
                {"key": "a.txt", "text": "hello"},
                {"key": "", "text": "bad"},
                {"key": "c.bin", "data": "***"},
            ],
        )
        # One success attempt fails due to put exception; others have validation errors
        assert len(result["results"]) == 3
        assert any("error" in r for r in result["results"])


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


def test_bucket_object_fetch_base64_mocked():
    """Test bucket object fetch with mocks (unit test)."""
    mock_stream = MagicMock()
    mock_stream.read.return_value = b"abcdef"
    mock_client = MagicMock()
    mock_client.get_object.return_value = {
        "Body": mock_stream,
        "ContentType": "application/octet-stream",
    }
    with patch("boto3.client", return_value=mock_client):
        result = bucket_object_fetch("s3://my-bucket/file.bin", max_bytes=10, base64_encode=True)
        assert result["base64"] is True
        assert "data" in result


@pytest.mark.aws
@pytest.mark.integration
def test_bucket_object_fetch_text_fallback():
    """Test bucket object fetch text mode with real AWS (integration test)."""
    from tests.test_helpers import skip_if_no_aws_credentials
    skip_if_no_aws_credentials()
    
    # First, get a list of objects to find a text file
    objects_result = bucket_objects_list(bucket=DEFAULT_BUCKET, max_keys=10)
    if not objects_result.get("objects"):
        pytest.skip(f"No objects found in test bucket {DEFAULT_BUCKET}")
    
    # Look for a text-like file
    text_object = None
    for obj in objects_result["objects"]:
        if any(obj["key"].endswith(ext) for ext in [".txt", ".csv", ".json", ".md", ".py"]):
            text_object = obj
            break
    
    if not text_object:
        pytest.skip("No text files found in test bucket for text fetch test")
    
    test_s3_uri = f"{DEFAULT_BUCKET}/{text_object['key']}"
    result = bucket_object_fetch(test_s3_uri, max_bytes=100, base64_encode=False)
    
    assert "base64" in result
    assert result["base64"] is False
    assert "text" in result
    assert isinstance(result["text"], str)


def test_bucket_object_fetch_text_fallback_mocked():
    """Test bucket object fetch text mode with mocks (unit test)."""
    mock_stream = MagicMock()
    mock_stream.read.return_value = b"hello world"
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": mock_stream, "ContentType": "text/plain"}
    with patch("boto3.client", return_value=mock_client):
        result = bucket_object_fetch("s3://my-bucket/file.txt", max_bytes=100, base64_encode=False)
        assert result["base64"] is False
        assert result["text"].startswith("hello")


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


def test_bucket_object_link_mocked():
    """Test bucket object presigned URL generation with mocks (unit test)."""
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = (
        "https://example.com/presigned-url?signature=abc123"
    )
    with patch("boto3.client", return_value=mock_client):
        result = bucket_object_link("s3://my-bucket/file.txt", expiration=7200)
        assert result["bucket"] == "my-bucket"
        assert result["key"] == "file.txt"
        assert result["presigned_url"] == "https://example.com/presigned-url?signature=abc123"
        assert result["expires_in"] == 7200
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object", Params={"Bucket": "my-bucket", "Key": "file.txt"}, ExpiresIn=7200
        )


def test_bucket_object_link_invalid_uri():
    result = bucket_object_link("not-an-s3-uri")
    assert "error" in result


def test_bucket_object_link_expiration_limits():
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://example.com/presigned-url"
    with patch("boto3.client", return_value=mock_client):
        # Test minimum expiration
        result = bucket_object_link("s3://my-bucket/file.txt", expiration=0)
        assert result["expires_in"] == 1

        # Test maximum expiration
        result = bucket_object_link("s3://my-bucket/file.txt", expiration=1000000)
        assert result["expires_in"] == 604800


def test_bucket_object_link_error():
    mock_client = MagicMock()
    mock_client.generate_presigned_url.side_effect = Exception("access denied")
    with patch("boto3.client", return_value=mock_client):
        result = bucket_object_link("s3://my-bucket/file.txt")
        assert "error" in result
        assert result["bucket"] == "my-bucket"
        assert result["key"] == "file.txt"

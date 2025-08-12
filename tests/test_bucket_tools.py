import pytest
from unittest.mock import patch, MagicMock

from quilt_mcp import (
    bucket_objects_list,
    bucket_object_info,
    bucket_object_text,
    bucket_objects_put,
    bucket_object_fetch,
)


def test_bucket_objects_list_success():
    mock_resp = {
        "Contents": [
            {"Key": "foo.txt", "Size": 10, "LastModified": "2025-01-01", "ETag": "abc", "StorageClass": "STANDARD"},
            {"Key": "bar.csv", "Size": 20, "LastModified": "2025-01-02", "ETag": "def", "StorageClass": "STANDARD"},
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


def test_bucket_object_info_success():
    head = {
        "ContentLength": 123,
        "ContentType": "text/plain",
        "ETag": "\"etag\"",
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


def test_bucket_object_text_success_truncated():
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


def test_bucket_objects_put_success():
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
            items=[{"key": "a.txt", "text": "hello"}, {"key": "", "text": "bad"}, {"key": "c.bin", "data": "***"}],
        )
        # One success attempt fails due to put exception; others have validation errors
        assert len(result["results"]) == 3
        assert any("error" in r for r in result["results"])


def test_bucket_object_fetch_base64():
    mock_stream = MagicMock()
    mock_stream.read.return_value = b"abcdef"
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": mock_stream, "ContentType": "application/octet-stream"}
    with patch("boto3.client", return_value=mock_client):
        result = bucket_object_fetch("s3://my-bucket/file.bin", max_bytes=10, base64_encode=True)
        assert result["base64"] is True
        assert "data" in result


def test_bucket_object_fetch_text_fallback():
    mock_stream = MagicMock()
    mock_stream.read.return_value = b"hello world"
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": mock_stream, "ContentType": "text/plain"}
    with patch("boto3.client", return_value=mock_client):
        result = bucket_object_fetch("s3://my-bucket/file.txt", max_bytes=100, base64_encode=False)
        assert result["base64"] is False
        assert result["text"].startswith("hello")

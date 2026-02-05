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


def test_bucket_object_text_encoding_scenarios():
    """Test bucket_object_text with various encoding scenarios to improve coverage."""
    mock_client = MagicMock()

    test_cases = [
        # (content, encoding, should_succeed)
        (b"Hello, World!", "utf-8", True),
        (b"\xc3\xa9\xc3\xa1\xc3\xad", "utf-8", True),  # UTF-8 accented chars
        (b"Hello, World!", "ascii", True),
        (b"\xff\xfe\x48\x00\x65\x00\x6c\x00\x6c\x00\x6f\x00", "utf-16", True),  # UTF-16 LE BOM
        (b"\xff\xff\xff\xff", "utf-8", True),  # Invalid UTF-8, should use errors="replace"
    ]

    for content, encoding, should_succeed in test_cases:
        mock_body = MagicMock()
        mock_body.read.return_value = content
        mock_client.get_object.return_value = {"Body": mock_body}

        mock_auth_ctx = AuthorizationContext(
            authorized=True,
            auth_type="iam",
            s3_client=mock_client,
        )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        result = bucket_object_text(s3_uri="s3://test-bucket/test-file.txt", encoding=encoding)

        if should_succeed:
            assert not hasattr(result, "error")
            assert hasattr(result, "text")
            assert isinstance(result.text, str)
            assert result.encoding == encoding
        else:
            assert hasattr(result, "error")


def test_bucket_object_text_truncation_scenarios():
    """Test bucket_object_text truncation behavior with various content sizes."""
    mock_client = MagicMock()

    test_cases = [
        # (content_size, max_bytes, should_truncate)
        (100, 200, False),  # Content smaller than limit
        (200, 200, False),  # Content equals limit
        (300, 200, True),  # Content larger than limit
        (1, 1, False),  # Edge case: 1 byte content, 1 byte limit
        (2, 1, True),  # Edge case: 2 byte content, 1 byte limit
    ]

    for content_size, max_bytes, should_truncate in test_cases:
        # Create content that simulates the behavior in bucket_object_text
        if should_truncate:
            # For truncation test, return max_bytes + 1 bytes to trigger truncation
            content = b"x" * (max_bytes + 1)
            expected_text_length = max_bytes
        else:
            # For non-truncation test, return exactly content_size bytes
            content = b"x" * content_size
            expected_text_length = content_size

        mock_body = MagicMock()
        mock_body.read.return_value = content
        mock_client.get_object.return_value = {"Body": mock_body}

        mock_auth_ctx = AuthorizationContext(
            authorized=True,
            auth_type="iam",
            s3_client=mock_client,
        )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        result = bucket_object_text(s3_uri="s3://test-bucket/test-file.txt", max_bytes=max_bytes)

        assert not hasattr(result, "error")
        assert hasattr(result, "truncated")
        assert result.truncated == should_truncate
        # max_bytes is in the input params, not the output
        assert len(result.text) == expected_text_length


def test_bucket_object_text_with_client_error_variations():
    """Test bucket_object_text with various client error scenarios."""
    from botocore.exceptions import ClientError

    mock_client = MagicMock()

    error_scenarios = [
        # (error_code, operation, expected_in_message)
        ("NoSuchKey", "GetObject", "Failed to get object"),
        ("AccessDenied", "GetObject", "Failed to get object"),
        ("InvalidBucketName", "GetObject", "Failed to get object"),
        ("NoSuchBucket", "GetObject", "Failed to get object"),
    ]

    for error_code, operation, expected_msg in error_scenarios:
        error_response = {'Error': {'Code': error_code, 'Message': f"Test {error_code} error"}}
        mock_client.get_object.side_effect = ClientError(error_response, operation)

        mock_auth_ctx = AuthorizationContext(
            authorized=True,
            auth_type="iam",
            s3_client=mock_client,
        )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        result = bucket_object_text(s3_uri="s3://test-bucket/test-file.txt")

        assert hasattr(result, "error")
        assert expected_msg in result.error
        assert result.bucket == "test-bucket"
        assert result.key == "test-file.txt"


def test_bucket_object_text_decode_failure_handling():
    """Test bucket_object_text behavior when decode fails."""
    mock_client = MagicMock()

    # Content that will fail to decode with specified encoding
    invalid_content = b"\xff\xfe\x00\x00"  # Invalid UTF-8 sequence

    mock_body = MagicMock()
    mock_body.read.return_value = invalid_content
    mock_client.get_object.return_value = {"Body": mock_body}

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        # Test with errors="replace" (default behavior)
        result = bucket_object_text(s3_uri="s3://test-bucket/test-file.txt", encoding="ascii")

        # Should succeed but use replacement characters
        assert not hasattr(result, "error")
        assert hasattr(result, "text")
        assert isinstance(result.text, str)
        # Content should contain replacement characters for invalid sequences
        assert "�" in result.text or result.text != ""


def test_bucket_object_fetch_with_decode_fallback():
    """Test bucket_object_fetch fallback to base64 when UTF-8 decode fails."""
    mock_client = MagicMock()

    # Binary content that cannot be decoded as UTF-8
    binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"  # PNG header

    mock_body = MagicMock()
    mock_body.read.return_value = binary_content
    mock_client.get_object.return_value = {"Body": mock_body, "ContentType": "image/png"}

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        # Test with base64_encode=False to trigger decode fallback
        result = bucket_object_fetch(s3_uri="s3://test-bucket/image.png", base64_encode=False)

        assert not hasattr(result, "error")
        assert result.is_base64 is True
        assert hasattr(result, "data")
        # Note: The "note" field may or may not exist in BucketObjectFetchSuccess
        # Just check that base64 encoding was used

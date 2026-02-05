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


def test_invalid_s3_uri_consistency():
    """Test that invalid S3 URI formats are handled consistently across all functions."""
    from pydantic import ValidationError

    invalid_uris = [
        "not-an-s3-uri",
        "http://example.com/file.txt",
        "s3://",
        "s3://bucket",  # No key
        "",
    ]

    for uri in invalid_uris:
        # All functions should return errors for invalid URIs
        for func_name, func in [
            ("bucket_object_info", bucket_object_info),
            ("bucket_object_text", bucket_object_text),
            ("bucket_object_fetch", bucket_object_fetch),
            ("bucket_object_link", bucket_object_link),
        ]:
            # Functions should return an error for invalid URIs
            result = func(s3_uri=uri)
            assert hasattr(result, "error"), f"Expected error for URI: {uri} with {func_name}"


def test_malformed_version_id_handling(test_bucket):
    """Test handling of malformed version IDs in S3 URIs."""
    malformed_uris = [
        "s3://bucket/file.txt?versionId=",
        "s3://bucket/file.txt?versionId=invalid spaces",
        "s3://bucket/file.txt?versionId=null",
        "s3://bucket/file.txt?versionId=undefined",
    ]

    mock_client = MagicMock()

    # Mock successful responses to focus on URI parsing
    mock_client.head_object.return_value = {"ContentLength": 1024, "ContentType": "text/plain"}

    mock_body = MagicMock()
    mock_body.read.return_value = b"test content"
    mock_client.get_object.return_value = {"Body": mock_body}

    mock_client.generate_presigned_url.return_value = "https://example.com/url"

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        for uri in malformed_uris:
            # Functions should either parse and handle the version ID or fail consistently
            info_result = bucket_object_info(s3_uri=uri)
            text_result = bucket_object_text(s3_uri=uri)
            fetch_result = bucket_object_fetch(s3_uri=uri)
            link_result = bucket_object_link(s3_uri=uri)

            # All should have the same error/success status
            all_have_error = all(
                hasattr(result, "error") for result in [info_result, text_result, fetch_result, link_result]
            )
            all_succeed = all(
                not hasattr(result, "error") for result in [info_result, text_result, fetch_result, link_result]
            )

            assert all_have_error or all_succeed, f"Inconsistent results for URI: {uri}"


# Phase 5: Enhanced Test Coverage for bucket_object_text

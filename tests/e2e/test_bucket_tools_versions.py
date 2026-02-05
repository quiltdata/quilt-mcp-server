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


def test_bucket_object_info_with_version_id():
    """Test bucket_object_info calls head_object with VersionId when provided."""
    mock_client = MagicMock()
    mock_head_response = {
        "ContentLength": 1024,
        "ContentType": "text/plain",
        "ETag": '"abc123"',
        "LastModified": "2023-01-01T00:00:00Z",
        "VersionId": "test-version-123",
    }
    mock_client.head_object.return_value = mock_head_response

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        result = bucket_object_info(s3_uri="s3://my-bucket/file.txt?versionId=test-version-123")

        # Verify S3 API was called with VersionId
        mock_client.head_object.assert_called_once_with(
            Bucket="my-bucket", Key="file.txt", VersionId="test-version-123"
        )
        assert not hasattr(result, "error")


def test_bucket_object_text_with_version_id():
    """Test bucket_object_text calls get_object with VersionId when provided."""
    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = b"test content"
    mock_get_response = {"Body": mock_body}
    mock_client.get_object.return_value = mock_get_response

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        result = bucket_object_text(s3_uri="s3://my-bucket/file.txt?versionId=test-version-123")

        # Verify S3 API was called with VersionId
        mock_client.get_object.assert_called_once_with(
            Bucket="my-bucket", Key="file.txt", VersionId="test-version-123"
        )
        assert not hasattr(result, "error")
        assert result.text == "test content"


def test_bucket_object_fetch_with_version_id():
    """Test bucket_object_fetch calls get_object with VersionId when provided."""
    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = b"binary data"
    mock_get_response = {"Body": mock_body, "ContentType": "application/octet-stream"}
    mock_client.get_object.return_value = mock_get_response

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        result = bucket_object_fetch(s3_uri="s3://my-bucket/file.bin?versionId=test-version-123")

        # Verify S3 API was called with VersionId
        mock_client.get_object.assert_called_once_with(
            Bucket="my-bucket", Key="file.bin", VersionId="test-version-123"
        )
        assert not hasattr(result, "error")


def test_bucket_object_link_with_version_id():
    """Test bucket_object_link calls generate_presigned_url with VersionId when provided."""
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://example.com/signed-url"

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        result = bucket_object_link(s3_uri="s3://my-bucket/file.txt?versionId=test-version-123")

        # Verify S3 API was called with VersionId in Params
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "my-bucket", "Key": "file.txt", "VersionId": "test-version-123"},
            ExpiresIn=3600,
        )
        assert not hasattr(result, "error")
        assert result.signed_url == "https://example.com/signed-url"


def test_bucket_object_info_version_error_handling():
    """Test bucket_object_info handles version-specific errors correctly."""
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    # Simulate NoSuchVersion error
    error_response = {'Error': {'Code': 'NoSuchVersion', 'Message': 'The specified version does not exist'}}
    mock_client.head_object.side_effect = ClientError(error_response, 'HeadObject')

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        result = bucket_object_info(s3_uri="s3://my-bucket/file.txt?versionId=invalid-version")

        assert hasattr(result, "error")
        assert "Version invalid-version not found" in result.error


def test_bucket_object_text_version_error_handling():
    """Test bucket_object_text handles version-specific errors correctly."""
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    # Simulate AccessDenied error with version context
    error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}}
    mock_client.get_object.side_effect = ClientError(error_response, 'GetObject')

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        result = bucket_object_text(s3_uri="s3://my-bucket/file.txt?versionId=restricted-version")

        assert hasattr(result, "error")
        assert "Access denied for version restricted-version" in result.error


def test_bucket_object_functions_without_version_id():
    """Test all functions work correctly without version ID (backward compatibility)."""
    mock_client = MagicMock()

    # Setup mocks for each function
    mock_client.head_object.return_value = {"ContentLength": 1024, "ContentType": "text/plain"}

    mock_body = MagicMock()
    mock_body.read.return_value = b"test"
    mock_client.get_object.return_value = {"Body": mock_body}

    mock_client.generate_presigned_url.return_value = "https://example.com/url"

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        # Test without version ID - should not pass VersionId parameter
        info_result = bucket_object_info(s3_uri="s3://my-bucket/file.txt")
        text_result = bucket_object_text(s3_uri="s3://my-bucket/file.txt")
        fetch_result = bucket_object_fetch(s3_uri="s3://my-bucket/file.txt")
        link_result = bucket_object_link(s3_uri="s3://my-bucket/file.txt")

        # Verify calls were made without VersionId
        mock_client.head_object.assert_called_with(Bucket="my-bucket", Key="file.txt")
        mock_client.get_object.assert_any_call(Bucket="my-bucket", Key="file.txt")
        mock_client.generate_presigned_url.assert_called_with(
            "get_object", Params={"Bucket": "my-bucket", "Key": "file.txt"}, ExpiresIn=3600
        )

        # All should succeed
        assert not hasattr(info_result, "error")
        assert not hasattr(text_result, "error")
        assert not hasattr(fetch_result, "error")
        assert not hasattr(link_result, "error")


# Phase 5: Cross-Function Consistency Tests


def test_version_consistency_across_all_functions(test_bucket):
    """Test that the same versionId returns consistent object metadata across all four functions."""
    mock_client = MagicMock()

    # Mock responses for each function
    test_version_id = "test-version-456"
    test_bucket = "my-bucket"
    test_key = "file.txt"
    test_s3_uri = f"s3://{test_bucket}/{test_key}?versionId={test_version_id}"

    # Setup consistent metadata across all functions
    mock_head_response = {
        "ContentLength": 2048,
        "ContentType": "text/plain",
        "ETag": '"def456"',
        "LastModified": "2023-06-01T12:00:00Z",
        "VersionId": test_version_id,
    }
    mock_client.head_object.return_value = mock_head_response

    mock_body = MagicMock()
    mock_body.read.return_value = b"consistent test content"
    mock_get_response = {"Body": mock_body, "ContentType": "text/plain", "VersionId": test_version_id}
    mock_client.get_object.return_value = mock_get_response

    mock_client.generate_presigned_url.return_value = "https://example.com/versioned-url"

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        # Call all four functions with the same versioned URI
        info_result = bucket_object_info(s3_uri=test_s3_uri)
        text_result = bucket_object_text(s3_uri=test_s3_uri)
        fetch_result = bucket_object_fetch(s3_uri=test_s3_uri)
        link_result = bucket_object_link(s3_uri=test_s3_uri)

        # Verify all functions called with the same VersionId
        mock_client.head_object.assert_called_with(Bucket=test_bucket, Key=test_key, VersionId=test_version_id)
        mock_client.get_object.assert_any_call(Bucket=test_bucket, Key=test_key, VersionId=test_version_id)
        mock_client.generate_presigned_url.assert_called_with(
            "get_object", Params={"Bucket": test_bucket, "Key": test_key, "VersionId": test_version_id}, ExpiresIn=3600
        )

        # Verify consistent bucket/key in all results
        assert info_result.object.bucket == test_bucket
        assert text_result.bucket == test_bucket
        assert fetch_result.bucket == test_bucket
        assert link_result.bucket == test_bucket

        assert info_result.object.key == test_key
        assert text_result.key == test_key
        assert fetch_result.key == test_key
        assert link_result.key == test_key

        # All functions should succeed with same version
        assert not hasattr(info_result, "error")
        assert not hasattr(text_result, "error")
        assert not hasattr(fetch_result, "error")
        assert not hasattr(link_result, "error")


@pytest.mark.parametrize(
    "version_id,should_fail",
    [
        ("valid-version-123", False),
        ("another-valid-version-456", False),
        (None, False),  # No version ID should work
    ],
)
def test_version_parameter_consistency_across_functions(version_id, should_fail):
    """Test that versionId parameter handling is consistent across all functions."""
    mock_client = MagicMock()

    test_bucket = "test-bucket"
    test_key = "test-file.txt"

    if version_id:
        test_s3_uri = f"s3://{test_bucket}/{test_key}?versionId={version_id}"
    else:
        test_s3_uri = f"s3://{test_bucket}/{test_key}"

    # Setup mock responses
    mock_client.head_object.return_value = {"ContentLength": 1024, "ContentType": "application/json"}

    mock_body = MagicMock()
    mock_body.read.return_value = b'{"test": "data"}'
    mock_client.get_object.return_value = {"Body": mock_body}

    mock_client.generate_presigned_url.return_value = "https://example.com/url"

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        # Call all functions
        info_result = bucket_object_info(s3_uri=test_s3_uri)
        text_result = bucket_object_text(s3_uri=test_s3_uri)
        fetch_result = bucket_object_fetch(s3_uri=test_s3_uri)
        link_result = bucket_object_link(s3_uri=test_s3_uri)

        # Build expected call parameters
        expected_params = {"Bucket": test_bucket, "Key": test_key}
        if version_id:
            expected_params["VersionId"] = version_id

        # Verify consistent parameter passing
        mock_client.head_object.assert_called_with(**expected_params)
        mock_client.get_object.assert_any_call(**expected_params)

        # For generate_presigned_url, the Params are nested
        mock_client.generate_presigned_url.assert_called_with("get_object", Params=expected_params, ExpiresIn=3600)

        # All should have consistent error/success status
        if should_fail:
            assert hasattr(info_result, "error")
            assert hasattr(text_result, "error")
            assert hasattr(fetch_result, "error")
            assert hasattr(link_result, "error")
        else:
            assert not hasattr(info_result, "error")
            assert not hasattr(text_result, "error")
            assert not hasattr(fetch_result, "error")
            assert not hasattr(link_result, "error")


def test_error_handling_consistency_across_functions(test_bucket):
    """Test that version-specific errors are handled consistently across all functions."""
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    test_s3_uri = "s3://my-bucket/file.txt?versionId=nonexistent-version"

    # Create consistent error response
    error_response = {'Error': {'Code': 'NoSuchVersion', 'Message': 'The specified version does not exist'}}
    client_error = ClientError(error_response, 'Operation')

    # All operations should fail with the same error
    mock_client.head_object.side_effect = client_error
    mock_client.get_object.side_effect = client_error
    mock_client.generate_presigned_url.side_effect = client_error

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        info_result = bucket_object_info(s3_uri=test_s3_uri)
        text_result = bucket_object_text(s3_uri=test_s3_uri)
        fetch_result = bucket_object_fetch(s3_uri=test_s3_uri)
        link_result = bucket_object_link(s3_uri=test_s3_uri)

        # All should have error
        assert hasattr(info_result, "error")
        assert hasattr(text_result, "error")
        assert hasattr(fetch_result, "error")
        assert hasattr(link_result, "error")

        # Error messages should contain version information consistently
        for result in [info_result, text_result, fetch_result, link_result]:
            assert "nonexistent-version" in result.error
            assert "not found" in result.error.lower()
            assert result.bucket == "my-bucket"
            assert result.key == "file.txt"


# Phase 5: Comprehensive Error Scenario Tests


@pytest.mark.parametrize(
    "error_code,error_message,expected_in_error",
    [
        ("NoSuchVersion", "The specified version does not exist", "Version test-version not found"),
        ("InvalidVersionId", "Invalid version id specified", "Version test-version not found"),
        ("AccessDenied", "Access Denied", "Access denied for version test-version"),
    ],
)
def test_version_error_scenarios_across_functions(error_code, error_message, expected_in_error):
    """Test that different version-related errors are handled consistently across all functions."""
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    test_version_id = "test-version"
    test_s3_uri = f"s3://error-bucket/error-file.txt?versionId={test_version_id}"

    error_response = {'Error': {'Code': error_code, 'Message': error_message}}
    client_error = ClientError(error_response, 'Operation')

    mock_client.head_object.side_effect = client_error
    mock_client.get_object.side_effect = client_error
    mock_client.generate_presigned_url.side_effect = client_error

    mock_auth_ctx = AuthorizationContext(
        authorized=True,
        auth_type="iam",
        s3_client=mock_client,
    )
    with patch("quilt_mcp.tools.buckets.check_s3_authorization", return_value=mock_auth_ctx):
        results = [
            bucket_object_info(s3_uri=test_s3_uri),
            bucket_object_text(s3_uri=test_s3_uri),
            bucket_object_fetch(s3_uri=test_s3_uri),
            bucket_object_link(s3_uri=test_s3_uri),
        ]

        # All should have error with consistent messaging
        for result in results:
            assert hasattr(result, "error")
            if error_code == "NoSuchVersion":
                assert f"Version {test_version_id} not found" in result.error
            elif error_code == "InvalidVersionId":
                # InvalidVersionId gets generic error handling, not version-specific
                assert "Failed to" in result.error or "Invalid version" in result.error
            elif error_code == "AccessDenied":
                assert f"Access denied for version {test_version_id}" in result.error

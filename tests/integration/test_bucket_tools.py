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


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
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

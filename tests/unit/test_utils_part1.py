"""Unit tests for utils module (mocked, no external dependencies)."""

import inspect
import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from fastmcp import FastMCP
from quilt_mcp.tools import buckets, catalog, packages
from quilt_mcp.utils import (
    create_configured_server,
    create_mcp_server,
    fix_url,
    generate_signed_url,
    get_tool_modules,
    normalize_url,
    parse_s3_uri,
    register_tools,
    run_server,
)


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def test_generate_signed_url_invalid_uri(self):
        """Test generate_signed_url with invalid URI."""
        # Not S3 URI
        self.assertIsNone(generate_signed_url("https://example.com/file"))

        # No path
        self.assertIsNone(generate_signed_url("s3://bucket"))

        # Empty string
        self.assertIsNone(generate_signed_url(""))

    @patch("quilt_mcp.utils.get_s3_client")
    def test_generate_signed_url_mocked(self, mock_s3_client):
        """Test successful URL generation with mocks (unit test)."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://signed.url"
        mock_s3_client.return_value = mock_client

        result = generate_signed_url("s3://my-bucket/my-key.txt", 1800)

        self.assertEqual(result, "https://signed.url")
        mock_s3_client.assert_called_once()
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "my-bucket", "Key": "my-key.txt"},
            ExpiresIn=1800,
        )

    @patch("quilt_mcp.utils.get_s3_client")
    def test_generate_signed_url_expiration_limits_mocked(self, mock_s3_client):
        """Test expiration time limits with mocks (unit test)."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://signed.url"
        mock_s3_client.return_value = mock_client

        # Test minimum (0 should become 1)
        generate_signed_url("s3://bucket/key", 0)
        mock_client.generate_presigned_url.assert_called_with(
            "get_object", Params={"Bucket": "bucket", "Key": "key"}, ExpiresIn=1
        )

        # Test maximum (more than 7 days should become 7 days)
        generate_signed_url("s3://bucket/key", 700000)  # > 7 days
        mock_client.generate_presigned_url.assert_called_with(
            "get_object",
            Params={"Bucket": "bucket", "Key": "key"},
            ExpiresIn=604800,  # 7 days
        )

    @patch("quilt_mcp.utils.get_s3_client")
    def test_generate_signed_url_exception_mocked(self, mock_s3_client):
        """Test handling of exceptions during URL generation with mocks (unit test)."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.side_effect = Exception("AWS Error")
        mock_s3_client.return_value = mock_client

        result = generate_signed_url("s3://bucket/key")

        assert result is None

    def test_generate_signed_url_complex_key(self):
        """Test with complex S3 key containing slashes."""
        with patch("quilt_mcp.utils.get_s3_client") as mock_s3_client:
            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = "https://signed.url"
            mock_s3_client.return_value = mock_client

            result = generate_signed_url("s3://bucket/path/to/my-file.txt")

            self.assertEqual(result, "https://signed.url")
            mock_client.generate_presigned_url.assert_called_once_with(
                "get_object",
                Params={"Bucket": "bucket", "Key": "path/to/my-file.txt"},
                ExpiresIn=3600,  # default
            )

    def test_parse_s3_uri_valid_basic_uri(self):
        """Test parse_s3_uri with valid basic S3 URI."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/my-key.txt")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "my-key.txt")
        self.assertIsNone(version_id)  # Phase 2: always returns None

    def test_parse_s3_uri_valid_complex_key(self):
        """Test parse_s3_uri with complex S3 key containing slashes."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/path/to/my-file.txt")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "path/to/my-file.txt")
        self.assertIsNone(version_id)  # Phase 2: always returns None

    def test_parse_s3_uri_with_versionid_parsed(self):
        """Test parse_s3_uri with versionId parameter (parsed in Phase 3)."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/my-key.txt?versionId=abc123")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "my-key.txt")  # Phase 3: query parameters extracted from key
        self.assertEqual(version_id, "abc123")  # Phase 3: returns parsed version_id

    def test_parse_s3_uri_with_versionid_extracted(self):
        """Test parse_s3_uri with versionId parameter (extracted in Phase 3)."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/my-key.txt?versionId=abc123")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "my-key.txt")  # Phase 3: query parameters extracted from key
        self.assertEqual(version_id, "abc123")  # Phase 3: returns parsed version_id

    def test_parse_s3_uri_invalid_not_s3_scheme(self):
        """Test parse_s3_uri with non-s3:// URI."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("https://bucket/key")

        self.assertIn("Invalid S3 URI scheme", str(context.exception))

    def test_parse_s3_uri_invalid_empty_string(self):
        """Test parse_s3_uri with empty string."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("")

        self.assertIn("Invalid S3 URI scheme", str(context.exception))

    def test_parse_s3_uri_invalid_no_key(self):
        """Test parse_s3_uri with URI missing key."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("s3://bucket")

        # This should raise ValueError when trying to split without a slash
        # The exact error message will depend on the implementation

    def test_parse_s3_uri_invalid_only_scheme(self):
        """Test parse_s3_uri with only s3:// scheme."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("s3://")

        # This should raise ValueError when trying to split an empty string

    def test_parse_s3_uri_bucket_with_special_chars(self):
        """Test parse_s3_uri with bucket containing allowed special characters."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket-123/key.txt")

        self.assertEqual(bucket, "my-bucket-123")
        self.assertEqual(key, "key.txt")
        self.assertIsNone(version_id)

    def test_parse_s3_uri_key_with_special_chars(self):
        """Test parse_s3_uri with key containing special characters."""
        bucket, key, version_id = parse_s3_uri("s3://bucket/path/with spaces and-symbols_123.txt")

        self.assertEqual(bucket, "bucket")
        self.assertEqual(key, "path/with spaces and-symbols_123.txt")
        self.assertIsNone(version_id)

    # Phase 3 Tests: versionId query parameter support

    def test_parse_s3_uri_with_valid_versionid(self):
        """Test parse_s3_uri with valid versionId query parameter."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/my-key.txt?versionId=abc123")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "my-key.txt")
        self.assertEqual(version_id, "abc123")

    def test_parse_s3_uri_with_versionid_complex_key(self):
        """Test parse_s3_uri with versionId and complex key path."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/path/to/file.txt?versionId=def456")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "path/to/file.txt")
        self.assertEqual(version_id, "def456")

    def test_parse_s3_uri_with_url_encoded_key_and_versionid(self):
        """Test parse_s3_uri with URL encoded key and versionId."""
        bucket, key, version_id = parse_s3_uri("s3://bucket/key%20with%20spaces?versionId=abc123")

        self.assertEqual(bucket, "bucket")
        self.assertEqual(key, "key with spaces")  # Should be URL decoded
        self.assertEqual(version_id, "abc123")

    def test_parse_s3_uri_with_url_encoded_path_and_versionid(self):
        """Test parse_s3_uri with URL encoded path separators and versionId."""
        bucket, key, version_id = parse_s3_uri("s3://bucket/path%2Fto%2Ffile?versionId=def456")

        self.assertEqual(bucket, "bucket")
        self.assertEqual(key, "path/to/file")  # Should be URL decoded
        self.assertEqual(version_id, "def456")

    def test_parse_s3_uri_with_invalid_query_parameter(self):
        """Test parse_s3_uri with invalid query parameter."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("s3://bucket/key?other=value")

        self.assertIn("Unexpected S3 query string", str(context.exception))

    def test_parse_s3_uri_with_multiple_query_parameters(self):
        """Test parse_s3_uri with multiple query parameters (versionId + other)."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("s3://bucket/key?versionId=abc&other=value")

        self.assertIn("Unexpected S3 query string", str(context.exception))

    def test_parse_s3_uri_with_prefix_query_parameter(self):
        """Test parse_s3_uri with prefix query parameter (should fail)."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("s3://bucket/key?prefix=test")

        self.assertIn("Unexpected S3 query string", str(context.exception))

    def test_parse_s3_uri_invalid_scheme_with_query(self):
        """Test parse_s3_uri with invalid scheme but valid query format."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("https://bucket/key?versionId=abc123")

        self.assertIn("Invalid S3 URI scheme", str(context.exception))

    # fix_url tests

    def test_fix_url_preserves_existing_url_schemes(self):
        """Test fix_url preserves URLs with existing schemes."""
        # S3 URL
        self.assertEqual(fix_url("s3://bucket/key"), "s3://bucket/key")

        # HTTPS URL
        self.assertEqual(fix_url("https://example.com/path"), "https://example.com/path")

        # HTTP URL
        self.assertEqual(fix_url("http://example.com"), "http://example.com")

    def test_fix_url_converts_relative_path_to_file_url(self):
        """Test fix_url converts relative paths to file:// URLs."""
        result = fix_url("./test.txt")
        self.assertTrue(result.startswith("file:///"))
        self.assertTrue(result.endswith("/test.txt"))

    def test_fix_url_converts_absolute_path_to_file_url(self):
        """Test fix_url converts absolute paths to file:// URLs."""
        result = fix_url("/tmp/test.txt")  # noqa: S108
        # On macOS, /tmp is a symlink to /private/tmp, so resolve() expands it
        self.assertTrue(result.startswith("file:///"))
        self.assertTrue(result.endswith("/tmp/test.txt"))  # noqa: S108

    def test_fix_url_expands_tilde_in_paths(self):
        """Test fix_url expands ~ to user's home directory."""
        result = fix_url("~/test.txt")
        self.assertTrue(result.startswith("file:///"))
        self.assertNotIn("~", result)
        self.assertTrue(result.endswith("/test.txt"))

    def test_fix_url_preserves_trailing_slash_for_directories(self):
        """Test fix_url preserves trailing slashes."""
        result = fix_url("/tmp/dir/")  # noqa: S108
        self.assertTrue(result.endswith("/"))

    def test_fix_url_raises_on_empty_string(self):
        """Test fix_url raises ValueError on empty string."""
        with self.assertRaises(ValueError) as context:
            fix_url("")
        self.assertIn("Empty URL", str(context.exception))

    def test_fix_url_raises_on_none(self):
        """Test fix_url raises ValueError on None."""
        with self.assertRaises(ValueError) as context:
            fix_url(None)
        self.assertIn("Empty URL", str(context.exception))

    # normalize_url tests

    def test_normalize_url_strips_trailing_slash_by_default(self):
        """Test normalize_url strips trailing slashes by default."""
        self.assertEqual(normalize_url("https://example.com/"), "https://example.com")
        self.assertEqual(normalize_url("s3://bucket/"), "s3://bucket")
        self.assertEqual(normalize_url("https://api.example.com/v1/"), "https://api.example.com/v1")

    def test_normalize_url_preserves_url_without_trailing_slash(self):
        """Test normalize_url preserves URLs without trailing slashes."""
        self.assertEqual(normalize_url("https://example.com"), "https://example.com")
        self.assertEqual(normalize_url("s3://bucket"), "s3://bucket")

    def test_normalize_url_with_strip_false_preserves_trailing_slash(self):
        """Test normalize_url can preserve trailing slashes when requested."""
        self.assertEqual(normalize_url("https://example.com/", strip_trailing_slash=False), "https://example.com/")
        self.assertEqual(normalize_url("s3://bucket/", strip_trailing_slash=False), "s3://bucket/")

    def test_normalize_url_handles_empty_string(self):
        """Test normalize_url handles empty strings gracefully."""
        self.assertEqual(normalize_url(""), "")
        self.assertEqual(normalize_url(None), None)

    def test_normalize_url_handles_multiple_trailing_slashes(self):
        """Test normalize_url removes multiple trailing slashes."""
        self.assertEqual(normalize_url("https://example.com///"), "https://example.com")
        self.assertEqual(normalize_url("s3://bucket//"), "s3://bucket")

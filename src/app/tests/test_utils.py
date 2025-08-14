"""Tests for utils module."""

import unittest
from unittest.mock import patch, MagicMock

from quilt_mcp.utils import generate_signed_url


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

    @patch('quilt_mcp.utils.boto3.client')
    def test_generate_signed_url_success(self, mock_boto_client):
        """Test successful URL generation."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://signed.url"
        mock_boto_client.return_value = mock_client
        
        result = generate_signed_url("s3://my-bucket/my-key.txt", 1800)
        
        self.assertEqual(result, "https://signed.url")
        mock_boto_client.assert_called_once_with("s3")
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "my-bucket", "Key": "my-key.txt"},
            ExpiresIn=1800
        )

    @patch('quilt_mcp.utils.boto3.client')
    def test_generate_signed_url_expiration_limits(self, mock_boto_client):
        """Test expiration time limits."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://signed.url"
        mock_boto_client.return_value = mock_client
        
        # Test minimum (0 should become 1)
        generate_signed_url("s3://bucket/key", 0)
        mock_client.generate_presigned_url.assert_called_with(
            "get_object",
            Params={"Bucket": "bucket", "Key": "key"},
            ExpiresIn=1
        )
        
        # Test maximum (more than 7 days should become 7 days)
        generate_signed_url("s3://bucket/key", 700000)  # > 7 days
        mock_client.generate_presigned_url.assert_called_with(
            "get_object",
            Params={"Bucket": "bucket", "Key": "key"},
            ExpiresIn=604800  # 7 days
        )

    @patch('quilt_mcp.utils.boto3.client')
    def test_generate_signed_url_exception(self, mock_boto_client):
        """Test handling of exceptions during URL generation."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.side_effect = Exception("AWS Error")
        mock_boto_client.return_value = mock_client
        
        result = generate_signed_url("s3://bucket/key")
        
        self.assertIsNone(result)

    def test_generate_signed_url_complex_key(self):
        """Test with complex S3 key containing slashes."""
        with patch('quilt_mcp.utils.boto3.client') as mock_boto_client:
            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = "https://signed.url"
            mock_boto_client.return_value = mock_client
            
            result = generate_signed_url("s3://bucket/path/to/my-file.txt")
            
            self.assertEqual(result, "https://signed.url")
            mock_client.generate_presigned_url.assert_called_once_with(
                "get_object",
                Params={"Bucket": "bucket", "Key": "path/to/my-file.txt"},
                ExpiresIn=3600  # default
            )
"""Tests for S3-to-package creation functionality."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from quilt_mcp.tools.s3_package import (
    package_create_from_s3,
    _validate_bucket_access,
    _discover_s3_objects,
    _should_include_object,
)
from quilt_mcp.utils import validate_package_name, format_error_response


class TestPackageCreateFromS3:
    """Test cases for the package_create_from_s3 function."""

    @pytest.mark.asyncio
    async def test_invalid_package_name(self):
        """Test that invalid package names are rejected."""
        result = await package_create_from_s3(
            source_bucket="test-bucket",
            package_name="invalid-name",  # Missing namespace
            target_registry="s3://test-registry",
        )
        
        assert result["success"] is False
        assert "Invalid package name format" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_required_params(self):
        """Test that missing required parameters are handled."""
        result = await package_create_from_s3(
            source_bucket="",  # Empty bucket
            package_name="test/package",
            target_registry="s3://test-registry",
        )
        
        assert result["success"] is False
        assert "source_bucket and target_registry are required" in result["error"]

    @pytest.mark.asyncio
    @patch('quilt_mcp.tools.s3_package.get_s3_client')
    @patch('quilt_mcp.tools.s3_package._validate_bucket_access')
    @patch('quilt_mcp.tools.s3_package._discover_s3_objects')
    async def test_no_objects_found(self, mock_discover, mock_validate, mock_s3_client):
        """Test handling when no objects are found."""
        # Setup mocks
        mock_s3_client.return_value = Mock()
        mock_validate.return_value = None
        mock_discover.return_value = []  # No objects found
        
        result = await package_create_from_s3(
            source_bucket="test-bucket",
            package_name="test/package",
            target_registry="s3://test-registry",
        )
        
        assert result["success"] is False
        assert "No objects found" in result["error"]

    @pytest.mark.asyncio
    @patch('quilt_mcp.tools.s3_package.get_s3_client')
    @patch('quilt_mcp.tools.s3_package._validate_bucket_access')
    @patch('quilt_mcp.tools.s3_package._discover_s3_objects')
    @patch('quilt_mcp.tools.s3_package._create_package_from_objects')
    async def test_successful_package_creation(self, mock_create, mock_discover, mock_validate, mock_s3_client):
        """Test successful package creation."""
        # Setup mocks
        mock_s3_client.return_value = Mock()
        mock_validate.return_value = None
        mock_discover.return_value = [
            {"Key": "file1.txt", "Size": 100},
            {"Key": "file2.txt", "Size": 200},
        ]
        mock_create.return_value = {"top_hash": "test_hash_123"}
        
        result = await package_create_from_s3(
            source_bucket="test-bucket",
            package_name="test/package",
            target_registry="s3://test-registry",
            description="Test package",
        )
        
        assert result["success"] is True
        assert result["package_name"] == "test/package"
        assert result["objects_count"] == 2
        assert result["total_size"] == 300
        assert result["package_hash"] == "test_hash_123"
        assert result["description"] == "Test package"


class TestUtilityFunctions:
    """Test cases for utility functions."""

    def test_should_include_object_no_patterns(self):
        """Test object inclusion with no patterns."""
        assert _should_include_object("test.txt", None, None) is True

    def test_should_include_object_include_patterns(self):
        """Test object inclusion with include patterns."""
        assert _should_include_object("test.txt", ["*.txt"], None) is True
        assert _should_include_object("test.pdf", ["*.txt"], None) is False

    def test_should_include_object_exclude_patterns(self):
        """Test object inclusion with exclude patterns."""
        assert _should_include_object("test.txt", None, ["*.tmp"]) is True
        assert _should_include_object("test.tmp", None, ["*.tmp"]) is False

    def test_should_include_object_both_patterns(self):
        """Test object inclusion with both include and exclude patterns."""
        # Should exclude even if it matches include pattern
        assert _should_include_object("test.tmp", ["*.txt", "*.tmp"], ["*.tmp"]) is False
        # Should include if matches include and doesn't match exclude
        assert _should_include_object("test.txt", ["*.txt"], ["*.tmp"]) is True


class TestValidation:
    """Test cases for validation functions."""

    def test_validate_package_name_valid(self):
        """Test valid package names."""
        assert validate_package_name("namespace/package") is True
        assert validate_package_name("my-ns/my-pkg") is True
        assert validate_package_name("ns123/pkg456") is True

    def test_validate_package_name_invalid(self):
        """Test invalid package names."""
        assert validate_package_name("invalid") is False  # No slash
        assert validate_package_name("ns/pkg/extra") is False  # Too many parts
        assert validate_package_name("/package") is False  # Empty namespace
        assert validate_package_name("namespace/") is False  # Empty package name
        assert validate_package_name("") is False  # Empty string

    def test_format_error_response(self):
        """Test error response formatting."""
        result = format_error_response("Test error message")
        
        assert result["success"] is False
        assert result["error"] == "Test error message"
        assert "timestamp" in result

"""Tests for unified package creation and user experience tools."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from quilt_mcp.tools.unified_package import (
    create_package,
    quick_start,
    list_available_resources,
    _analyze_file_sources,
    _format_validation_error,
    _find_common_prefix,
)
from quilt_mcp.tools.auth import (
    configure_catalog,
    switch_catalog,
)


class TestCreatePackage:
    """Test cases for the unified create_package function."""

    def test_invalid_package_name(self):
        """Test validation error for invalid package name."""
        result = create_package(
            name="invalid-name",  # Missing namespace
            files=["s3://bucket/file.csv"],
        )

        assert result["status"] == "error"
        assert "Invalid name format" in result["error"]
        assert "examples" in result
        assert "tip" in result

    def test_empty_files_list(self):
        """Test validation error for empty files list."""
        result = create_package(name="test/package", files=[])

        assert result["status"] == "error"
        assert "Invalid files format" in result["error"]
        assert "examples" in result

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_s3_only_package_creation(self, mock_s3_create):
        """Test package creation with S3-only sources."""
        mock_s3_create.return_value = {
            "success": True,
            "package_name": "test/package",
            "registry": "s3://test-bucket",
        }

        result = create_package(
            name="test/package",
            files=["s3://source-bucket/data.csv", "s3://source-bucket/readme.md"],
        )

        assert result["success"] is True
        assert result["creation_method"] == "s3_sources"
        assert "user_guidance" in result

    def test_local_files_not_implemented(self):
        """Test handling of local files (not yet implemented)."""
        result = create_package(name="test/package", files=["/path/to/local/file.csv"])

        assert result["status"] == "not_implemented"
        assert "Upload files to S3 first" in result["alternative"]


class TestQuickStart:
    """Test cases for the quick_start onboarding tool."""

    @patch("quilt_mcp.tools.auth.auth_status")
    def test_quick_start_authenticated(self, mock_auth_status):
        """Test quick start for authenticated user."""
        mock_auth_status.return_value = {
            "status": "authenticated",
            "catalog_name": "demo.quiltdata.com",
        }

        result = quick_start()

        assert result["status"] == "ready"
        assert result["current_step"] == "package_creation"
        assert "next_actions" in result
        assert len(result["next_actions"]) > 0

    @patch("quilt_mcp.tools.auth.auth_status")
    def test_quick_start_not_authenticated(self, mock_auth_status):
        """Test quick start for non-authenticated user."""
        mock_auth_status.return_value = {"status": "not_authenticated"}

        result = quick_start()

        assert result["status"] == "setup_needed"
        assert result["current_step"] == "authentication"
        assert "setup_flow" in result
        assert len(result["setup_flow"]) >= 4

    @patch("quilt_mcp.tools.auth.auth_status")
    def test_quick_start_error_state(self, mock_auth_status):
        """Test quick start for error state."""
        mock_auth_status.return_value = {
            "status": "error",
            "error": "AWS credentials not found",
        }

        result = quick_start()

        assert result["status"] == "error"
        assert result["current_step"] == "troubleshooting"
        assert "troubleshooting_steps" in result


class TestCatalogConfiguration:
    """Test cases for catalog configuration tools."""

    @patch("quilt3.config")
    def test_configure_catalog_success(self, mock_config):
        """Test successful catalog configuration."""
        mock_config.return_value = {"navigator_url": "https://demo.quiltdata.com"}

        result = configure_catalog("https://demo.quiltdata.com")

        assert result["status"] == "success"
        assert result["catalog_url"] == "https://demo.quiltdata.com"
        assert "next_steps" in result

    def test_configure_catalog_invalid_url(self):
        """Test catalog configuration with invalid URL."""
        result = configure_catalog("invalid-url")

        assert result["status"] == "error"
        assert "Invalid catalog URL format" in result["error"]
        assert "expected" in result
        assert "example" in result

    @patch("quilt_mcp.tools.auth.configure_catalog")
    def test_switch_catalog_by_name(self, mock_configure):
        """Test switching catalog by friendly name."""
        mock_configure.return_value = {"status": "success"}

        result = switch_catalog("demo")

        assert result["status"] == "success"
        assert result["action"] == "switched"
        mock_configure.assert_called_with("https://demo.quiltdata.com")

    @patch("quilt_mcp.tools.auth.configure_catalog")
    def test_switch_catalog_invalid_name(self, mock_configure):
        """Test switching to invalid catalog name."""
        # Mock the configure_catalog call to fail but still return available catalogs
        mock_configure.return_value = {
            "status": "error",
            "error": "Failed to configure catalog",
            "available_catalogs": ["demo", "production", "staging"],
        }

        result = switch_catalog("nonexistent-catalog")

        # Should return error with available catalogs
        assert result["status"] == "error"
        # The function should still return available_catalogs even on error
        assert "available_catalogs" in result
        assert "demo" in result["available_catalogs"]


class TestUtilityFunctions:
    """Test cases for utility functions."""

    def test_analyze_file_sources_s3_only(self):
        """Test file source analysis for S3-only files."""
        files = ["s3://bucket/file1.csv", "s3://bucket/file2.json"]

        result = _analyze_file_sources(files)

        assert result["source_type"] == "s3_only"
        assert len(result["s3_files"]) == 2
        assert len(result["local_files"]) == 0
        assert result["has_errors"] is False

    def test_analyze_file_sources_invalid_s3(self):
        """Test file source analysis with invalid S3 URIs."""
        files = ["s3://bucket-only", "s3://bucket/"]

        result = _analyze_file_sources(files)

        assert result["has_errors"] is True
        assert len(result["errors"]) == 2

    def test_find_common_prefix(self):
        """Test common prefix finding."""
        keys = ["data/processed/file1.csv", "data/processed/file2.csv"]
        prefix = _find_common_prefix(keys)
        assert prefix == "data/processed/"

        # Single file
        single_prefix = _find_common_prefix(["data/file.csv"])
        assert single_prefix == "data/"

        # No common prefix
        no_prefix = _find_common_prefix(["file1.csv", "other/file2.csv"])
        assert no_prefix == ""

    def test_format_validation_error(self):
        """Test validation error formatting."""
        result = _format_validation_error(
            field="test_field",
            provided="invalid_value",
            expected="valid format",
            examples=["example1", "example2"],
            tip="Use proper format",
        )

        assert result["status"] == "error"
        assert "Invalid test_field format" in result["error"]
        assert result["provided"] == "invalid_value"
        assert "examples" in result
        assert "tip" in result

    def test_readme_content_extraction_from_metadata(self):
        """Test that README content is automatically extracted from metadata."""
        # Test metadata with README content
        test_metadata = {
            "description": "Test dataset",
            "readme_content": "# Test Dataset\n\nThis is a test dataset with README content.",
            "tags": ["test", "example"],
        }

        # Mock the file analysis to return S3 sources
        with patch(
            "quilt_mcp.tools.unified_package._analyze_file_sources"
        ) as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            # Mock the S3 package creation
            with patch(
                "quilt_mcp.tools.unified_package._create_package_from_s3_sources"
            ) as mock_s3_create:
                mock_s3_create.return_value = {
                    "status": "success",
                    "package_name": "test/dataset",
                }

                result = create_package(
                    name="test/dataset",
                    files=["s3://bucket/file.csv"],
                    metadata=test_metadata,
                )

                # Verify success
                assert result["status"] == "success"

                # Verify that the S3 creation function was called with cleaned metadata
                mock_s3_create.assert_called_once()
                call_args = mock_s3_create.call_args
                passed_metadata = call_args[1]["metadata"]

                # Verify README content was removed from metadata
                assert "readme_content" not in passed_metadata
                assert "readme" not in passed_metadata

                # Verify other metadata was preserved
                assert "description" in passed_metadata
                assert "tags" in passed_metadata

    def test_both_readme_fields_extraction(self):
        """Test that both 'readme_content' and 'readme' fields are extracted."""
        # Test metadata with both README fields
        test_metadata = {
            "description": "Test dataset",
            "readme_content": "# Priority README",
            "readme": "This should be ignored",
            "version": "1.0.0",
        }

        # Mock the file analysis to return S3 sources
        with patch(
            "quilt_mcp.tools.unified_package._analyze_file_sources"
        ) as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            # Mock the S3 package creation
            with patch(
                "quilt_mcp.tools.unified_package._create_package_from_s3_sources"
            ) as mock_s3_create:
                mock_s3_create.return_value = {
                    "status": "success",
                    "package_name": "test/dataset",
                }

                result = create_package(
                    name="test/dataset",
                    files=["s3://bucket/file.csv"],
                    metadata=test_metadata,
                )

                # Verify success
                assert result["status"] == "success"

                # Verify that the S3 creation function was called with cleaned metadata
                mock_s3_create.assert_called_once()
                call_args = mock_s3_create.call_args
                passed_metadata = call_args[1]["metadata"]

                # Verify both README fields were removed
                assert "readme_content" not in passed_metadata
                assert "readme" not in passed_metadata

                # Verify other metadata was preserved
                assert "description" in passed_metadata
                assert "version" in passed_metadata

    def test_no_readme_content_in_metadata(self):
        """Test that packages without README content work normally."""
        # Test metadata without README content
        test_metadata = {
            "description": "Test dataset",
            "tags": ["test", "example"],
            "version": "1.0.0",
        }

        # Mock the file analysis to return S3 sources
        with patch(
            "quilt_mcp.tools.unified_package._analyze_file_sources"
        ) as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            # Mock the S3 package creation
            with patch(
                "quilt_mcp.tools.unified_package._create_package_from_s3_sources"
            ) as mock_s3_create:
                mock_s3_create.return_value = {
                    "status": "success",
                    "package_name": "test/dataset",
                }

                result = create_package(
                    name="test/dataset",
                    files=["s3://bucket/file.csv"],
                    metadata=test_metadata,
                )

                # Verify success
                assert result["status"] == "success"

                # Verify that the S3 creation function was called with unchanged metadata
                mock_s3_create.assert_called_once()
                call_args = mock_s3_create.call_args
                passed_metadata = call_args[1]["metadata"]

                # Verify metadata was passed unchanged
                assert passed_metadata == test_metadata

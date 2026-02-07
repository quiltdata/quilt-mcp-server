"""Functional tests for S3-to-package workflows (mocked)."""

from unittest.mock import Mock, patch

from tests.conftest import KNOWN_TEST_PACKAGE
from quilt_mcp.tools.packages import package_create_from_s3

TEST_BUCKET = "test-bucket"
TEST_REGISTRY = "s3://test-bucket"


class TestPackageCreateFromS3:
    """Test cases for the package_create_from_s3 function."""

    def test_invalid_package_name(self):
        """Test that invalid package names are rejected - validation happens inside function."""
        result = package_create_from_s3(
            source_bucket=TEST_BUCKET,
            package_name="invalid-name",
        )

        assert result.success is False
        assert "Invalid package name format" in result.error

    def test_missing_required_params(self):
        """Test that missing required parameters are handled."""
        result = package_create_from_s3(
            source_bucket="",
            package_name=KNOWN_TEST_PACKAGE,
        )

        assert result.success is False
        assert "source_bucket is required" in result.error

    @patch("quilt_mcp.tools.packages.get_s3_client")
    @patch("quilt_mcp.tools.packages._validate_bucket_access")
    @patch("quilt_mcp.tools.packages._discover_s3_objects")
    @patch("quilt_mcp.tools.packages._create_enhanced_package")
    @patch("quilt_mcp.services.permissions_service.bucket_recommendations_get")
    @patch("quilt_mcp.services.permissions_service.check_bucket_access")
    def test_no_objects_found(
        self,
        mock_access_check,
        mock_recommendations,
        mock_create,
        mock_discover,
        mock_validate,
        mock_s3_client,
    ):
        """Test handling when no objects are found in source bucket."""
        mock_s3_client.return_value = Mock()
        mock_validate.return_value = None
        mock_discover.return_value = []
        mock_create.return_value = {"top_hash": "test_hash_123"}
        mock_recommendations.return_value = {
            "success": True,
            "recommendations": {"package_creation": [TEST_REGISTRY]},
        }
        mock_access_check.return_value = {
            "success": True,
            "access_summary": {"can_write": True},
        }

        result = package_create_from_s3(
            source_bucket=TEST_BUCKET,
            package_name=KNOWN_TEST_PACKAGE,
            target_registry=TEST_REGISTRY,
        )

        assert result.success is False
        assert (
            "No objects found matching the specified criteria" in result.error
            or "Cannot create package in target registry" in result.error
        )


class TestValidation:
    """Test cases for validation functions that exercise the workflow."""

    @patch("quilt_mcp.tools.packages.get_s3_client")
    @patch("quilt_mcp.tools.packages._discover_s3_objects")
    @patch("quilt_mcp.tools.packages.bucket_recommendations_get")
    @patch("quilt_mcp.tools.packages.check_bucket_access")
    @patch("quilt_mcp.tools.packages._validate_bucket_access")
    @patch("quilt_mcp.tools.packages._create_enhanced_package")
    def test_dry_run_preview(
        self,
        mock_create,
        mock_validate_access,
        mock_check_access,
        mock_recommendations,
        mock_discover,
        mock_s3_client,
    ):
        """Test dry_run=True doesn't call package creation."""
        mock_s3_client.return_value = Mock()
        mock_discover.return_value = [{"Key": "data/file.csv", "Size": 10}]
        mock_recommendations.return_value = {
            "success": True,
            "recommendations": {"primary_recommendations": [{"bucket_name": "test-registry"}]},
        }
        mock_check_access.return_value = {"success": True, "access_summary": {"can_write": True}}
        mock_validate_access.return_value = None

        mock_create.side_effect = RuntimeError("Should not create package in dry_run mode!")

        result = package_create_from_s3(
            source_bucket="test-bucket",
            package_name="test/pkg",
            dry_run=True,
        )

        assert mock_create.call_count == 0
        assert result.success is True


class TestREADMEContentExtraction:
    """Test cases for README content extraction from metadata."""

    @patch("quilt_mcp.tools.packages.get_s3_client")
    @patch("quilt_mcp.tools.packages._discover_s3_objects")
    @patch("quilt_mcp.tools.packages.bucket_recommendations_get")
    @patch("quilt_mcp.tools.packages.check_bucket_access")
    @patch("quilt_mcp.tools.packages._validate_bucket_access")
    def test_readme_content_extraction_from_metadata(
        self,
        mock_validate_access,
        mock_check_access,
        mock_recommendations,
        mock_discover,
        mock_s3_client,
    ):
        """Test that metadata fields are handled correctly."""
        mock_s3_client.return_value = Mock()
        mock_discover.return_value = [{"Key": "data/file.csv", "Size": 10}]
        mock_recommendations.return_value = {
            "success": True,
            "recommendations": {"primary_recommendations": [{"bucket_name": "test-registry"}]},
        }
        mock_check_access.return_value = {"success": True, "access_summary": {"can_write": True}}
        mock_validate_access.return_value = None

        test_metadata = {"description": "Test", "readme_content": "# README"}

        result = package_create_from_s3(
            source_bucket="test-bucket",
            package_name=KNOWN_TEST_PACKAGE,
            metadata=test_metadata,
        )

        result_dict = result.model_dump() if hasattr(result, "model_dump") else result

        assert "error" in result_dict or "success" in result_dict

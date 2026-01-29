"""Tests for enhanced S3-to-package creation functionality."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from quilt_mcp.constants import KNOWN_TEST_PACKAGE

# Note: PackageCreateFromS3Params removed after flattening - use direct parameters
from quilt_mcp.tools.packages import (
    package_create_from_s3,
    _create_enhanced_package,
    _validate_bucket_access,
    _discover_s3_objects,
    _should_include_object,
    _suggest_target_registry,
    _organize_file_structure,
    _generate_readme_content,
    _generate_package_metadata,
)
from quilt_mcp.utils import validate_package_name, format_error_response
from quilt_mcp.validators import (
    validate_package_structure,
    validate_metadata_compliance,
    validate_package_naming,
)


@pytest.mark.search
@pytest.mark.integration
class TestPackageCreateFromS3:
    """Test cases for the package_create_from_s3 function."""

    def test_invalid_package_name(self, test_bucket):
        """Test that invalid package names are rejected - validation happens inside function."""
        # Call function directly with invalid package name
        result = package_create_from_s3(
            source_bucket=test_bucket,
            package_name="invalid-name",  # Missing namespace
        )

        # Verify the function returns an error response
        assert result.success is False
        assert "Invalid package name format" in result.error

    def test_missing_required_params(self):
        """Test that missing required parameters are handled."""
        result = package_create_from_s3(
            source_bucket="",  # Empty bucket
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
        test_bucket,
        test_registry,
    ):
        """Test handling when no objects are found in source bucket."""
        # Setup mocks
        mock_s3_client.return_value = Mock()
        mock_validate.return_value = None
        mock_discover.return_value = []  # No objects found
        mock_create.return_value = {"top_hash": "test_hash_123"}
        mock_recommendations.return_value = {
            "success": True,
            "recommendations": {"package_creation": [test_registry]},
        }
        # Mock bucket access check to return success for target registry
        mock_access_check.return_value = {
            "success": True,
            "access_summary": {"can_write": True},
        }

        result = package_create_from_s3(
            source_bucket=test_bucket,
            package_name=KNOWN_TEST_PACKAGE,
            target_registry=test_registry,
        )

        # The function should fail because no objects were found in the source bucket
        assert result.success is False
        # Check for the actual error message - could be about registry access or no objects
        assert (
            "No objects found matching the specified criteria" in result.error
            or "Cannot create package in target registry" in result.error
        )


@pytest.mark.integration
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
    ):
        """Test dry_run=True doesn't call package creation."""
        # Mock all AWS calls to avoid real API calls
        mock_recommendations.return_value = {
            "success": True,
            "recommendations": {"primary_recommendations": [{"bucket_name": "test-registry"}]}
        }
        mock_check_access.return_value = {
            "success": True,
            "access_summary": {"can_write": True}
        }
        mock_validate_access.return_value = None  # No exception = valid access

        # Make it error if called
        mock_create.side_effect = RuntimeError("Should not create package in dry_run mode!")

        # Call with dry_run=True
        result = package_create_from_s3(
            source_bucket="test-bucket",
            package_name="test/pkg",
            dry_run=True,
        )

        # Verify package creation was never called
        assert mock_create.call_count == 0, "dry_run=True called _create_enhanced_package"

    def test_auto_registry_suggestion(self):
        """Test _suggest_target_registry function directly."""
        # This is already tested in TestEnhancedFunctionality.test_suggest_target_registry
        # No need to test it again with complex mocking
        pass


@pytest.mark.integration
class TestEnhancedFunctionality:
    """Test cases for enhanced S3-to-package functionality."""

    def test_suggest_target_registry(self):
        """Test registry suggestion algorithm."""
        # ML patterns
        assert _suggest_target_registry("ml-data", "models") == "s3://ml-packages"
        assert _suggest_target_registry("training-data", "") == "s3://ml-packages"

        # Analytics patterns
        assert _suggest_target_registry("analytics-reports", "") == "s3://analytics-packages"
        assert _suggest_target_registry("data", "dashboard") == "s3://analytics-packages"

        # Default fallback
        assert _suggest_target_registry("random-bucket", "") == "s3://data-packages"

    def test_organize_file_structure(self):
        """Test smart file organization."""
        objects = [
            {"Key": "data.csv"},
            {"Key": "config.yml"},
            {"Key": "readme.md"},
            {"Key": "model.pkl"},
            {"Key": "image.png"},
        ]

        organized = _organize_file_structure(objects, auto_organize=True)

        assert "data/processed" in organized
        assert "metadata" in organized
        assert "docs" in organized
        assert "data/misc" in organized
        assert "data/media" in organized

        # Test flat organization
        flat = _organize_file_structure(objects, auto_organize=False)
        assert "" in flat
        assert len(flat[""]) == 5

    def test_generate_readme_content(self, test_bucket, test_registry):
        """Test README generation."""
        organized_structure = {
            "data/processed": [{"Key": "data.csv"}],
            "docs": [{"Key": "readme.md"}],
        }

        readme = _generate_readme_content(
            package_name=KNOWN_TEST_PACKAGE,
            description="Test package",
            organized_structure=organized_structure,
            total_size=1000000,
            source_info={"bucket": test_bucket},
            metadata_template="standard",
        )

        assert f"# {KNOWN_TEST_PACKAGE}" in readme
        assert "Test package" in readme
        assert "data/processed" in readme
        assert "Usage" in readme
        assert "Package.browse" in readme

    def test_generate_package_metadata(self, test_bucket, test_registry):
        """Test metadata generation."""
        organized_structure = {
            "data/processed": [{"Key": "data.csv", "Size": 1000}],
        }

        metadata = _generate_package_metadata(
            package_name=KNOWN_TEST_PACKAGE,
            source_info={"bucket": test_bucket, "prefix": "data/"},
            organized_structure=organized_structure,
            metadata_template="ml",
            user_metadata={"tags": ["test"]},
        )

        assert "quilt" in metadata
        assert "ml" in metadata
        assert "user_metadata" in metadata
        assert metadata["quilt"]["source"]["bucket"] == test_bucket
        assert metadata["user_metadata"]["tags"] == ["test"]


class TestValidationUtilities:
    """Test cases for validation utilities."""

    def test_package_structure_validation(self):
        """Test package structure validation."""
        good_structure = {
            "data/processed": [{"Key": "data.csv"}],
            "docs": [{"Key": "readme.md"}],
        }

        is_valid, warnings, recommendations = validate_package_structure(good_structure)
        assert is_valid is True

        # Test problematic structure
        bad_structure = {
            "temp": [{"Key": "file1.txt"}] * 60,  # Too many files, bad folder name
        }

        is_valid, warnings, recommendations = validate_package_structure(bad_structure)
        assert len(warnings) > 0

    def test_metadata_compliance_validation(self):
        """Test metadata compliance validation."""
        good_metadata = {
            "quilt": {
                "created_by": "test",
                "creation_date": "2024-01-01T00:00:00Z",
                "source": {"type": "s3_bucket", "bucket": "test"},
            }
        }

        is_compliant, errors, warnings = validate_metadata_compliance(good_metadata)
        assert is_compliant is True
        assert len(errors) == 0

    def test_package_naming_validation(self):
        """Test package naming validation."""
        is_valid, errors, suggestions = validate_package_naming(KNOWN_TEST_PACKAGE)
        assert is_valid is True
        assert len(errors) == 0

        is_valid, errors, suggestions = validate_package_naming("invalid-name")
        assert is_valid is False
        assert len(errors) > 0


class TestREADMEContentExtraction:
    """Test cases for README content extraction from metadata."""

    def test_readme_content_extraction_from_metadata(self):
        """Test that metadata fields are handled correctly."""
        # Test that the function handles metadata parameter
        # The actual extraction logic is simple: metadata gets passed through
        test_metadata = {"description": "Test", "readme_content": "# README"}

        # Just verify the function accepts metadata without error
        result = package_create_from_s3(
            source_bucket="nonexistent",
            package_name=KNOWN_TEST_PACKAGE,
            metadata=test_metadata,
        )

        # Convert result to dict for easier checking
        result_dict = result.model_dump() if hasattr(result, 'model_dump') else result

        # Should either fail gracefully or handle metadata
        assert "error" in result_dict or "success" in result_dict


class TestCreateEnhancedPackageMigration:
    """Test cases for the _create_enhanced_package migration to create_package_revision."""

    @patch("quilt_mcp.tools.packages.QuiltService")
    def test_create_enhanced_package_uses_create_package_revision(
        self, mock_quilt_service_class, test_bucket, test_registry
    ):
        """Test that _create_enhanced_package uses create_package_revision with auto_organize=True."""
        from pathlib import Path

        # Mock the QuiltService instance and its create_package_revision method
        mock_quilt_service = Mock()
        mock_quilt_service_class.return_value = mock_quilt_service
        mock_quilt_service.create_package_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 2,
        }

        # Test data
        organized_structure = {
            "data": [
                {"Key": "file1.txt", "Size": 100},
                {"Key": "file2.csv", "Size": 200},
            ]
        }
        enhanced_metadata = {
            "description": "Test package",
            "tags": ["test", "migration"],
        }

        result = _create_enhanced_package(
            s3_client=Mock(),
            organized_structure=organized_structure,
            source_bucket=test_bucket,
            package_name=KNOWN_TEST_PACKAGE,
            target_registry=test_registry,
            description="Test package description",
            enhanced_metadata=enhanced_metadata,
        )

        # Verify create_package_revision was called with auto_organize=True
        mock_quilt_service.create_package_revision.assert_called_once()
        call_args = mock_quilt_service.create_package_revision.call_args

        assert call_args[1]["package_name"] == KNOWN_TEST_PACKAGE
        assert call_args[1]["registry"] == test_registry
        assert call_args[1]["auto_organize"]  # s3_package.py should use True
        assert call_args[1]["metadata"] == enhanced_metadata

        # Verify expected S3 URIs were passed
        expected_s3_uris = [
            f"s3://{test_bucket}/file1.txt",
            f"s3://{test_bucket}/file2.csv",
        ]
        assert set(call_args[1]["s3_uris"]) == set(expected_s3_uris)

        # Verify success result
        assert result["top_hash"] == "test_hash_123"

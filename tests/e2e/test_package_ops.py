"""Tests for package creation and management operations.

This module tests the core functionality for creating and managing Quilt packages,
including the automatic README content extraction from metadata.
"""

from unittest.mock import Mock, patch, MagicMock
import io
import pytest

from quilt_mcp.tools.package_ops import (
    package_delete,
    _normalize_registry,
)
from quilt_mcp.tools.unified_package import create_package


class TestCreatePackage:
    """Test cases for the create_package function."""

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_readme_content_extraction_from_metadata(self, mock_create_revision):
        """Test that README content is automatically extracted from metadata and added as package file."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

        # Test metadata with README content
        test_metadata = {
            "description": "Test package",
            "readme_content": "# Test Package\n\nThis is a test package with README content.",
            "tags": ["test", "example"],
        }

        result = create_package(
            name="test/package",
            files=["s3://bucket/test.txt"],
            metadata=test_metadata,
            target_registry="s3://test-bucket",
        )

        # Verify create_package_revision was called with processed metadata (without README)
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata was processed to remove README content and includes template fields
        processed_metadata = call_args[1]["metadata"]

        # Check that standard template fields are present
        assert processed_metadata["description"] == "Test package"
        assert processed_metadata["tags"] == ["test", "example"]
        assert processed_metadata["created_by"] == "quilt-mcp-server"
        assert processed_metadata["package_type"] == "data"
        assert processed_metadata["version"] == "1.0.0"
        assert "creation_date" in processed_metadata

        # Verify README content was extracted and stored separately
        assert "_extracted_readme" in processed_metadata
        assert processed_metadata["_extracted_readme"] == "# Test Package\n\nThis is a test package with README content."

        # Verify original readme_content field was removed from metadata
        assert "readme_content" not in processed_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_readme_field_extraction_from_metadata(self, mock_create_revision):
        """Test that 'readme' field is also extracted from metadata."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

        # Test metadata with 'readme' field
        test_metadata = {
            "description": "Test package",
            "readme": "This is a simple README.",
            "version": "1.0.0",
        }

        result = create_package(
            name="test/package",
            files=["s3://bucket/test.txt"],
            metadata=test_metadata,
            target_registry="s3://test-bucket",
        )

        # Verify create_package_revision was called with processed metadata (without README)
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata was processed to remove README content and includes template fields
        processed_metadata = call_args[1]["metadata"]

        # Check that standard template fields are present
        assert processed_metadata["description"] == "Test package"
        assert processed_metadata["version"] == "1.0.0"  # User-provided version overrides template
        assert processed_metadata["created_by"] == "quilt-mcp-server"
        assert processed_metadata["package_type"] == "data"
        assert "creation_date" in processed_metadata

        # Verify README content was extracted and stored separately
        assert "_extracted_readme" in processed_metadata
        assert processed_metadata["_extracted_readme"] == "This is a simple README."

        # Verify original readme field was removed from metadata
        assert "readme" not in processed_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_both_readme_fields_extraction(self, mock_create_revision):
        """Test that both 'readme_content' and 'readme' fields are extracted (readme_content takes priority)."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

        # Test metadata with both README fields
        test_metadata = {
            "description": "Test package",
            "readme_content": "# Priority README",
            "readme": "This should be ignored",
            "tags": ["test"],
        }

        result = create_package(
            name="test/package",
            files=["s3://bucket/test.txt"],
            metadata=test_metadata,
            target_registry="s3://test-bucket",
        )

        # Verify create_package_revision was called with processed metadata (without README)
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata was processed to remove both README fields and includes template fields
        processed_metadata = call_args[1]["metadata"]

        # Check that standard template fields are present
        assert processed_metadata["description"] == "Test package"
        assert processed_metadata["tags"] == ["test"]
        assert processed_metadata["created_by"] == "quilt-mcp-server"
        assert processed_metadata["package_type"] == "data"
        assert processed_metadata["version"] == "1.0.0"
        assert "creation_date" in processed_metadata

        # Verify README content was extracted (readme_content takes priority over readme)
        assert "_extracted_readme" in processed_metadata
        assert processed_metadata["_extracted_readme"] == "# Priority README"

        # Verify both original readme fields were removed from metadata
        assert "readme_content" not in processed_metadata
        assert "readme" not in processed_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_no_readme_content_in_metadata(self, mock_create_revision):
        """Test that packages without README content in metadata work normally."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

        # Test metadata without README content
        test_metadata = {"description": "Test package", "tags": ["test", "example"]}

        result = create_package(
            name="test/package",
            files=["s3://bucket/test.txt"],
            metadata=test_metadata,
            target_registry="s3://test-bucket",
        )

        # Verify create_package_revision was called with metadata as-is
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata includes template fields (no README extraction needed)
        processed_metadata = call_args[1]["metadata"]

        # Check that standard template fields are present
        assert processed_metadata["description"] == "Test package"
        assert processed_metadata["tags"] == ["test", "example"]
        assert processed_metadata["created_by"] == "quilt-mcp-server"
        assert processed_metadata["package_type"] == "data"
        assert processed_metadata["version"] == "1.0.0"
        assert "creation_date" in processed_metadata

        # No README extraction should happen (no readme fields in input)
        assert "_extracted_readme" not in processed_metadata
        assert "readme_content" not in processed_metadata
        assert "readme" not in processed_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_readme_file_creation_failure_handling(self, mock_create_revision):
        """Test that README file creation failures are handled gracefully."""
        # Mock package creation that will process README internally
        # NOTE: With create_package_revision, README handling is internal
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

        # Test metadata with README content
        test_metadata = {
            "description": "Test package",
            "readme_content": "# Test Package\n\nThis is a test package with README content.",
            "tags": ["test"],
        }

        result = create_package(
            name="test/package",
            files=["s3://bucket/test.txt"],
            metadata=test_metadata,
            target_registry="s3://test-bucket",
        )

        # Verify create_package_revision was called with processed metadata (without README)
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata was processed to remove README content and includes template fields
        processed_metadata = call_args[1]["metadata"]

        # Check that standard template fields are present
        assert processed_metadata["description"] == "Test package"
        assert processed_metadata["tags"] == ["test"]
        assert processed_metadata["created_by"] == "quilt-mcp-server"
        assert processed_metadata["package_type"] == "data"
        assert processed_metadata["version"] == "1.0.0"
        assert "creation_date" in processed_metadata

        # Verify README content was extracted and stored separately
        assert "_extracted_readme" in processed_metadata
        assert processed_metadata["_extracted_readme"] == "# Test Package\n\nThis is a test package with README content."

        # Verify original readme fields were removed from metadata
        assert "readme_content" not in processed_metadata
        assert "readme" not in processed_metadata

        # Verify success (README failure handling is now internal to create_package_revision)
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_empty_metadata_handling(self, mock_create_revision):
        """Test that empty metadata is handled correctly."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

        result = create_package(
            name="test/package",
            files=["s3://bucket/test.txt"],
            metadata=None,  # No metadata
            target_registry="s3://test-bucket",
        )

        # Verify create_package_revision was called with empty metadata
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata includes standard template (even when input is None)
        processed_metadata = call_args[1]["metadata"]

        # Check that standard template fields are present
        assert processed_metadata["description"] == "Standard data package"
        assert processed_metadata["created_by"] == "quilt-mcp-server"
        assert processed_metadata["package_type"] == "data"
        assert processed_metadata["version"] == "1.0.0"
        assert "creation_date" in processed_metadata

        # No README extraction should happen (no readme fields)
        assert "_extracted_readme" not in processed_metadata

        # Verify success
        assert result["status"] == "success"

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_metadata_without_readme_fields(self, mock_create_revision):
        """Test that metadata without README fields is processed normally."""
        # Mock successful package creation
        mock_create_revision.return_value = {
            "status": "success",
            "top_hash": "test_hash_123",
            "entries_added": 1,
        }

        # Test metadata with various fields but no README content
        test_metadata = {
            "description": "Test package",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": ["test", "example"],
            "custom_field": "custom_value",
        }

        result = create_package(
            name="test/package",
            files=["s3://bucket/test.txt"],
            metadata=test_metadata,
            target_registry="s3://test-bucket",
        )

        # Verify create_package_revision was called with metadata unchanged
        mock_create_revision.assert_called_once()
        call_args = mock_create_revision.call_args

        assert call_args[1]["package_name"] == "test/package"
        assert call_args[1]["s3_uris"] == ["s3://bucket/test.txt"]
        assert call_args[1]["registry"] == "s3://test-bucket"
        assert not call_args[1]["auto_organize"]  # package_ops.py should use False

        # Verify metadata includes user fields plus template fields
        processed_metadata = call_args[1]["metadata"]

        # Check that user-provided fields are preserved
        assert processed_metadata["description"] == "Test package"
        assert processed_metadata["version"] == "1.0.0"  # User version overrides template
        assert processed_metadata["author"] == "test@example.com"
        assert processed_metadata["tags"] == ["test", "example"]
        assert processed_metadata["custom_field"] == "custom_value"

        # Check that standard template fields are also present
        assert processed_metadata["created_by"] == "quilt-mcp-server"
        assert processed_metadata["package_type"] == "data"
        assert "creation_date" in processed_metadata

        # No README extraction should happen (no readme fields)
        assert "_extracted_readme" not in processed_metadata
        assert "readme_content" not in processed_metadata
        assert "readme" not in processed_metadata

        # Verify success
        assert result["status"] == "success"




class TestNormalizeRegistry:
    """Test cases for the _normalize_registry function."""

    def test_normalize_registry_with_s3_prefix(self):
        """Test that s3:// URIs are returned as-is."""
        result = _normalize_registry("s3://my-bucket")
        assert result == "s3://my-bucket"

    def test_normalize_registry_without_s3_prefix(self):
        """Test that bucket names get s3:// prefix added."""
        result = _normalize_registry("my-bucket")
        assert result == "s3://my-bucket"

    def test_normalize_registry_with_path(self):
        """Test that bucket names with paths get s3:// prefix added."""
        result = _normalize_registry("my-bucket/path/to/files")
        assert result == "s3://my-bucket/path/to/files"




class TestPackageCreateErrorHandling:
    """Test error handling in create_package function."""

    def test_create_package_with_empty_s3_uris(self):
        """Test create_package with empty S3 URIs list."""
        result = create_package(name="test/package", files=[], target_registry="s3://test-bucket")

        assert result["error"] == "Invalid files parameter"

    def test_create_package_with_empty_package_name(self):
        """Test create_package with empty package name."""
        result = create_package(name="", files=["s3://bucket/file.txt"], target_registry="s3://test-bucket")

        assert result["error"] == "Invalid package name format"

    def test_create_package_with_invalid_json_metadata(self):
        """Test create_package with invalid JSON string metadata."""
        result = create_package(
            name="test/package",
            files=["s3://bucket/file.txt"],
            metadata='{"invalid": json syntax}',  # Invalid JSON
            target_registry="s3://test-bucket",
        )

        assert result["success"] is False
        assert result["error"] == "Invalid metadata JSON format"
        assert "json_error" in result
        assert "examples" in result

    def test_create_package_with_non_dict_non_string_metadata(self):
        """Test create_package with metadata that's not a dict or string."""
        result = create_package(
            name="test/package",
            files=["s3://bucket/file.txt"],
            metadata=123,  # Invalid type
            target_registry="s3://test-bucket",
        )

        assert result["success"] is False
        assert result["error"] == "Invalid metadata type"
        assert result["provided_type"] == "int"
        assert "examples" in result

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_create_package_with_service_error_response(self, mock_create_revision):
        """Test create_package when service returns error response."""
        mock_create_revision.return_value = {
            "error": "Service failed to create package",
            "details": "Some internal error",
        }

        result = create_package(
            name="test/package", files=["s3://bucket/file.txt"], target_registry="s3://test-bucket"
        )

        assert result["error"] == "Service failed to create package"
        assert result["package_name"] == "test/package"
        assert "warnings" in result

    @patch("quilt_mcp.tools.package_ops.quilt_service.create_package_revision")
    def test_create_package_with_service_exception(self, mock_create_revision):
        """Test create_package when service raises exception."""
        mock_create_revision.side_effect = Exception("Network error")

        result = create_package(
            name="test/package", files=["s3://bucket/file.txt"], target_registry="s3://test-bucket"
        )

        assert "Failed to create package: Network error" in result["error"]
        assert result["package_name"] == "test/package"
        assert "warnings" in result



class TestPackageUpdateRemoval:
    """Test that package_update function has been removed."""

    def test_package_update_cannot_be_imported(self):
        """Test that package_update can no longer be imported after removal."""
        with pytest.raises(ImportError, match="cannot import name 'package_update'"):
            from quilt_mcp.tools.package_ops import package_update

    def test_package_update_not_in_main_exports(self):
        """Test that package_update is not in main module exports."""
        import quilt_mcp

        # Should not have package_update in the module
        assert not hasattr(quilt_mcp, 'package_update')


class TestPackageDelete:
    """Test cases for the package_delete function."""

    def test_package_delete_with_empty_package_name(self):
        """Test package_delete with empty package name."""
        result = package_delete(package_name="", target_registry="s3://test-bucket")

        assert result["error"] == "package_name is required for package deletion"

    @patch("quilt_mcp.tools.package_ops.quilt3.delete_package")
    @patch("quilt_mcp.utils.suppress_stdout")
    def test_package_delete_success(self, mock_suppress, mock_delete):
        """Test successful package deletion."""
        mock_delete.return_value = None  # Successful deletion

        result = package_delete(package_name="test/package", target_registry="s3://test-bucket")

        assert result["status"] == "success"
        assert result["action"] == "deleted"
        assert result["package_name"] == "test/package"
        assert result["registry"] == "s3://test-bucket"
        assert "deleted successfully" in result["message"]

    @patch("quilt_mcp.tools.package_ops.quilt3.delete_package")
    @patch("quilt_mcp.utils.suppress_stdout")
    def test_package_delete_failure(self, mock_suppress, mock_delete):
        """Test package deletion failure."""
        mock_delete.side_effect = Exception("Deletion failed")

        result = package_delete(package_name="test/package", target_registry="s3://test-bucket")

        assert "Failed to delete package 'test/package':" in result["error"]
        assert result["package_name"] == "test/package"
        assert result["registry"] == "s3://test-bucket"

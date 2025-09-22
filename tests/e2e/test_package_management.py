"""Tests for enhanced package management functionality."""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.tools.package_management import (
    package_create,
    package_validate,
    package_tools_list,
)
from quilt_mcp.tools.metadata_templates import (
    metadata_template_get,
    list_metadata_templates,
    validate_metadata_structure,
)
from quilt_mcp.tools.packages import package_browse


class TestPackageCreate:
    """Test cases for enhanced package creation."""

    def test_invalid_package_name(self):
        """Test validation of invalid package names."""
        result = package_create(
            name="invalid-name",  # Missing namespace
            files=["s3://bucket/file.csv"],
        )

        assert result["success"] is False
        assert "Invalid package name format" in result["error"]
        assert "examples" in result
        assert "tip" in result

    def test_invalid_files_parameter(self):
        """Test validation of invalid files parameter."""
        result = package_create(
            name="team/dataset",
            files=[],  # Empty list
        )

        assert result["success"] is False
        assert "Invalid files parameter" in result["error"]
        assert "examples" in result

    def test_invalid_s3_uris(self):
        """Test validation of invalid S3 URIs."""
        result = package_create(
            name="team/dataset",
            files=["invalid-uri", "s3://bucket-only"],  # Invalid URIs
        )

        assert result["success"] is False
        assert "Invalid S3 URIs detected" in result["error"]
        assert "invalid_uris" in result
        assert len(result["invalid_uris"]) == 2

    def test_dry_run_preview(self):
        """Test dry run functionality."""
        result = package_create(
            name="team/dataset",
            files=["s3://bucket/file.csv"],
            description="Test dataset",
            metadata_template="genomics",
            dry_run=True,
        )

        assert result["success"] is True
        assert result["action"] == "preview"
        assert "metadata_preview" in result
        assert "next_steps" in result
        assert result["metadata_template"] == "genomics"

    def test_json_string_metadata_handling(self):
        """Test handling of metadata as JSON string."""
        # This would test the JSON parsing logic
        # In a full test, we'd mock the base package creation
        result = package_create(
            name="team/dataset",
            files=["s3://bucket/file.csv"],
            metadata='{"custom": "value"}',  # JSON string
            dry_run=True,
        )

        assert result["success"] is True
        assert "custom" in result["metadata_preview"]

    def test_readme_content_extraction_from_metadata(self):
        """Test that README content is automatically extracted from metadata."""
        # Mock the base package creation function
        with patch("quilt_mcp.tools.package_management._base_package_create") as mock_base_create:
            mock_base_create.return_value = {
                "status": "success",
                "entries_added": 1,
                "package_name": "team/dataset",
            }

            # Test metadata with README content
            test_metadata = {
                "description": "Test dataset",
                "readme_content": "# Test Dataset\n\nThis is a test dataset with README content.",
                "tags": ["test", "example"],
            }

            result = package_create(
                name="team/dataset",
                files=["s3://bucket/file.csv"],
                metadata=test_metadata,
                dry_run=True,
            )

            # Verify success
            assert result["success"] is True

            # Verify that README content was extracted and stored in metadata
            # In dry_run mode, the function returns early and doesn't call _base_package_create
            # but we can verify the metadata processing worked correctly
            assert "metadata_preview" in result

            # Verify README content was removed from the processed metadata
            processed_metadata = result["metadata_preview"]
            assert "readme_content" not in processed_metadata
            assert "readme" not in processed_metadata

            # Verify other metadata was preserved
            assert "description" in processed_metadata
            assert "tags" in processed_metadata

            # Verify that README content was extracted and stored
            assert "_extracted_readme" in processed_metadata
            assert (
                processed_metadata["_extracted_readme"]
                == "# Test Dataset\n\nThis is a test dataset with README content."
            )

    def test_both_readme_fields_extraction(self):
        """Test that both 'readme_content' and 'readme' fields are extracted."""
        # Mock the base package creation function
        with patch("quilt_mcp.tools.package_management._base_package_create") as mock_base_create:
            mock_base_create.return_value = {
                "status": "success",
                "entries_added": 1,
                "package_name": "team/dataset",
            }

            # Test metadata with both README fields
            test_metadata = {
                "description": "Test dataset",
                "readme_content": "# Priority README",
                "readme": "This should be ignored",
                "version": "1.0.0",
            }

            result = package_create(
                name="team/dataset",
                files=["s3://bucket/file.csv"],
                metadata=test_metadata,
                dry_run=True,
            )

            # Verify success
            assert result["success"] is True

            # Verify that README content was extracted and stored in metadata
            # In dry_run mode, the function returns early and doesn't call _base_package_create
            # but we can verify the metadata processing worked correctly
            assert "metadata_preview" in result

            # Verify that README content was extracted and stored (priority to readme_content)
            processed_metadata = result["metadata_preview"]
            assert "readme_content" not in processed_metadata  # This should be removed
            assert "readme" in processed_metadata  # This remains since we only extract one field
            assert "_extracted_readme" in processed_metadata

            # Verify that readme_content took priority
            assert processed_metadata["_extracted_readme"] == "# Priority README"

            # Verify other metadata was preserved
            assert "description" in processed_metadata
            assert "version" in processed_metadata

    def test_no_readme_content_in_metadata(self):
        """Test that packages without README content work normally."""
        # Mock the base package creation function
        with patch("quilt_mcp.tools.package_management._base_package_create") as mock_base_create:
            mock_base_create.return_value = {
                "status": "success",
                "entries_added": 1,
                "package_name": "team/dataset",
            }

            # Test metadata without README content
            test_metadata = {
                "description": "Test dataset",
                "tags": ["test", "example"],
                "version": "1.0.0",
            }

            result = package_create(
                name="team/dataset",
                files=["s3://bucket/file.csv"],
                metadata=test_metadata,
                dry_run=True,
            )

            # Verify success
            assert result["success"] is True

            # Verify that no README fields are in the processed metadata
            # In dry_run mode, the function returns early and doesn't call _base_package_create
            # but we can verify the metadata processing worked correctly
            assert "metadata_preview" in result

            # Verify no README fields in the processed metadata
            processed_metadata = result["metadata_preview"]
            assert "readme_content" not in processed_metadata
            assert "readme" not in processed_metadata
            assert "_extracted_readme" not in processed_metadata

            # Verify other metadata was preserved
            assert "description" in processed_metadata
            assert "tags" in processed_metadata
            assert "version" in processed_metadata


class TestMetadataTemplates:
    """Test cases for metadata templates."""

    def test_get_standard_template(self):
        """Test getting standard metadata template."""
        metadata = metadata_template_get("standard")

        assert "description" in metadata
        assert "created_by" in metadata
        assert "creation_date" in metadata
        assert "package_type" in metadata

    def test_get_genomics_template(self):
        """Test getting genomics metadata template."""
        metadata = metadata_template_get("genomics", {"organism": "human"})

        assert metadata["package_type"] == "genomics"
        assert metadata["organism"] == "human"
        assert "genome_build" in metadata

    def test_list_metadata_templates(self):
        """Test listing available templates."""
        result = list_metadata_templates()

        assert "available_templates" in result
        assert "usage_examples" in result
        assert "genomics" in result["available_templates"]
        assert "ml" in result["available_templates"]

    def test_validate_metadata_structure(self):
        """Test metadata structure validation."""
        # Valid metadata
        valid_metadata = {"description": "Test dataset", "version": "1.0"}
        result = validate_metadata_structure(valid_metadata)

        assert result["valid"] is True

        # Invalid metadata (not a dict)
        invalid_result = validate_metadata_structure("not a dict")  # type: ignore
        assert invalid_result["valid"] is False


class TestEnhancedPackageBrowsing:
    """Test cases for enhanced package browsing."""

    @patch("quilt3.Package.browse")
    def test_package_browse_enhanced(self, mock_browse):
        """Test enhanced package browsing with file tree."""
        # Mock package with nested structure
        mock_pkg = Mock()
        mock_pkg.keys.return_value = [
            "data/file1.csv",
            "docs/readme.md",
            "analysis/script.py",
        ]

        # Mock individual entries
        mock_entry1 = Mock()
        mock_entry1.size = 1000
        mock_entry1.hash = "hash1"
        mock_entry1.physical_key = "s3://bucket/data/file1.csv"

        mock_entry2 = Mock()
        mock_entry2.size = 500
        mock_entry2.hash = "hash2"
        mock_entry2.physical_key = "s3://bucket/docs/readme.md"

        # Configure the mock to handle __getitem__ calls
        mock_pkg.__getitem__ = Mock(
            side_effect=lambda key: {
                "data/file1.csv": mock_entry1,
                "docs/readme.md": mock_entry2,
                "analysis/script.py": mock_entry1,
            }[key]
        )

        mock_browse.return_value = mock_pkg

        result = package_browse("test/package", recursive=True, include_file_info=True)

        assert result["success"] is True
        assert result["view_type"] == "recursive"
        assert "file_tree" in result
        assert "summary" in result
        assert result["summary"]["total_files"] > 0

    @patch("quilt3.Package.browse")
    def test_package_browse_error_handling(self, mock_browse):
        """Test package browsing error handling."""
        mock_browse.side_effect = Exception("Package not found")

        result = package_browse("nonexistent/package")

        assert result["success"] is False
        assert "Failed to browse package" in result["error"]
        assert "possible_fixes" in result
        assert "suggested_actions" in result


class TestPackageValidation:
    """Test cases for package validation."""

    @patch("quilt_mcp.tools.package_management.package_browse")
    def test_package_validate_success(self, mock_browse):
        """Test successful package validation."""
        mock_browse.return_value = {
            "success": True,
            "entries": [
                {"logical_key": "file1.csv", "physical_key": "s3://bucket/file1.csv"},
                {"logical_key": "file2.json", "physical_key": "s3://bucket/file2.json"},
            ],
            "summary": {"total_size": 1500},
        }

        result = package_validate("test/package")

        assert result["success"] is True
        assert "validation" in result
        assert result["validation"]["accessible_files"] == 2

    @patch("quilt_mcp.tools.package_management.package_browse")
    def test_package_validate_browse_failure(self, mock_browse):
        """Test package validation when browsing fails."""
        mock_browse.return_value = {"success": False, "error": "Package not found"}

        result = package_validate("nonexistent/package")

        assert result["success"] is False
        assert "Cannot validate package" in result["error"]


class TestToolDocumentation:
    """Test cases for tool documentation and guidance."""

    def test_list_package_tools(self):
        """Test package tools listing."""
        result = package_tools_list()

        assert "primary_tools" in result
        assert "specialized_tools" in result
        assert "workflow_guide" in result
        assert "tips" in result

        # Check that main tools are documented
        assert "package_create" in result["primary_tools"]
        assert "package_browse" in result["primary_tools"]
        assert "package_validate" in result["primary_tools"]


class TestFunctionRemoval:
    """Test cases for verifying removed functions cannot be imported."""

    def test_package_update_metadata_removed(self):
        """Test that package_update_metadata function has been removed and cannot be imported."""
        # Test that the function cannot be imported from the module
        with pytest.raises(ImportError, match="cannot import name 'package_update_metadata'"):
            from quilt_mcp.tools.package_management import package_update_metadata

        # Test that the function is not in the main package exports
        with pytest.raises(ImportError, match="cannot import name 'package_update_metadata'"):
            from quilt_mcp import package_update_metadata



"""Unit tests for unified package creation metadata template functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from quilt_mcp.tools.unified_package import (
    create_package,
    _create_package_from_s3_sources,
)


class TestMetadataTemplateSystem:
    """Unit tests for metadata template functionality in create_package."""

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_applies_standard_template_by_default(self, mock_s3_create):
        """Test that standard template is applied by default."""
        mock_s3_create.return_value = {
            "success": True,
            "package_name": "test/package",
            "registry": "s3://test-bucket",
        }

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            result = create_package(
                name="test/package",
                files=["s3://bucket/file.csv"],
                # No metadata_template specified, should default to "standard"
            )

            # Verify success
            assert result["success"] is True
            assert result["metadata_template_used"] == "standard"

            # Verify the S3 function was called with standard template metadata
            mock_s3_create.assert_called_once()
            call_args = mock_s3_create.call_args
            passed_metadata = call_args[1]["metadata"]

            # Verify standard template fields
            assert passed_metadata["package_type"] == "data"
            assert passed_metadata["created_by"] == "quilt-mcp-server"
            assert "creation_date" in passed_metadata

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_applies_genomics_template(self, mock_s3_create):
        """Test that genomics template is correctly applied."""
        mock_s3_create.return_value = {
            "success": True,
            "package_name": "genomics/study1",
            "registry": "s3://test-bucket",
        }

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/data.vcf"],
                "local_files": [],
                "has_errors": False,
            }

            result = create_package(
                name="genomics/study1",
                files=["s3://bucket/data.vcf"],
                metadata_template="genomics",
                metadata={"organism": "human", "genome_build": "GRCh38"},
            )

            # Verify success
            assert result["success"] is True
            assert result["metadata_template_used"] == "genomics"

            # Verify the S3 function was called with merged metadata
            mock_s3_create.assert_called_once()
            call_args = mock_s3_create.call_args
            passed_metadata = call_args[1]["metadata"]

            # Verify genomics template fields
            assert passed_metadata["package_type"] == "genomics"
            assert passed_metadata["data_type"] == "genomics"

            # Verify user-provided values override template defaults
            assert passed_metadata["organism"] == "human"
            assert passed_metadata["genome_build"] == "GRCh38"

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_applies_ml_template(self, mock_s3_create):
        """Test that ML template is correctly applied."""
        mock_s3_create.return_value = {
            "success": True,
            "package_name": "ml/dataset",
            "registry": "s3://test-bucket",
        }

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/training_data.csv"],
                "local_files": [],
                "has_errors": False,
            }

            result = create_package(
                name="ml/dataset",
                files=["s3://bucket/training_data.csv"],
                metadata_template="ml",
                metadata={"features_count": 150, "target_variable": "price"},
            )

            # Verify success
            assert result["success"] is True
            assert result["metadata_template_used"] == "ml"

            # Verify the S3 function was called with merged metadata
            mock_s3_create.assert_called_once()
            call_args = mock_s3_create.call_args
            passed_metadata = call_args[1]["metadata"]

            # Verify ML template fields
            assert passed_metadata["package_type"] == "ml_dataset"
            assert passed_metadata["data_type"] == "machine_learning"
            assert passed_metadata["model_ready"] is True

            # Verify user-provided values override template defaults
            assert passed_metadata["features_count"] == 150
            assert passed_metadata["target_variable"] == "price"

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_invalid_template_falls_back_to_standard(self, mock_s3_create):
        """Test that invalid template name falls back to standard."""
        mock_s3_create.return_value = {
            "success": True,
            "package_name": "test/package",
            "registry": "s3://test-bucket",
        }

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            result = create_package(
                name="test/package",
                files=["s3://bucket/file.csv"],
                metadata_template="invalid_template_name",
            )

            # Verify success
            assert result["success"] is True

            # Verify the S3 function was called with standard template (fallback)
            mock_s3_create.assert_called_once()
            call_args = mock_s3_create.call_args
            passed_metadata = call_args[1]["metadata"]

            # Should fallback to standard template
            assert passed_metadata["package_type"] == "data"

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_handles_json_string_metadata(self, mock_s3_create):
        """Test that JSON string metadata works with templates."""
        mock_s3_create.return_value = {
            "success": True,
            "package_name": "research/study",
            "registry": "s3://test-bucket",
        }

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/data.csv"],
                "local_files": [],
                "has_errors": False,
            }

            result = create_package(
                name="research/study",
                files=["s3://bucket/data.csv"],
                metadata_template="research",
                metadata='{"study_type": "clinical_trial", "research_domain": "medicine"}',
            )

            # Verify success
            assert result["success"] is True
            assert result["metadata_template_used"] == "research"

            # Verify the S3 function was called with parsed and merged metadata
            mock_s3_create.assert_called_once()
            call_args = mock_s3_create.call_args
            passed_metadata = call_args[1]["metadata"]

            # Verify research template fields
            assert passed_metadata["package_type"] == "research"
            assert passed_metadata["data_type"] == "research"

            # Verify parsed JSON values override template defaults
            assert passed_metadata["study_type"] == "clinical_trial"
            assert passed_metadata["research_domain"] == "medicine"

    def test_create_package_invalid_json_metadata_returns_error(self):
        """Test that invalid JSON metadata returns a helpful error."""
        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            result = create_package(
                name="test/package",
                files=["s3://bucket/file.csv"],
                metadata_template="standard",
                metadata='{"invalid": json}',  # Invalid JSON
            )

            # Verify error
            assert result["success"] is False
            assert "Invalid metadata JSON format" in result["error"]
            assert "json_error" in result
            assert "examples" in result

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_description_added_to_metadata(self, mock_s3_create):
        """Test that description parameter is added to template metadata."""
        mock_s3_create.return_value = {
            "success": True,
            "package_name": "test/package",
            "registry": "s3://test-bucket",
        }

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            result = create_package(
                name="test/package",
                files=["s3://bucket/file.csv"],
                description="Test dataset for analysis",
                metadata_template="standard",
            )

            # Verify success
            assert result["success"] is True

            # Verify the S3 function was called with description in metadata
            mock_s3_create.assert_called_once()
            call_args = mock_s3_create.call_args
            passed_metadata = call_args[1]["metadata"]

            # Verify description was added
            assert passed_metadata["description"] == "Test dataset for analysis"

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_readme_content_extracted_from_metadata(self, mock_s3_create):
        """Test that README content is extracted from metadata."""
        mock_s3_create.return_value = {
            "success": True,
            "package_name": "test/package",
            "registry": "s3://test-bucket",
        }

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            result = create_package(
                name="test/package",
                files=["s3://bucket/file.csv"],
                metadata_template="standard",
                metadata={
                    "readme_content": "# Test Dataset\n\nThis is a test README.",
                    "custom_field": "value",
                },
            )

            # Verify success
            assert result["success"] is True

            # Verify the S3 function was called with README content extracted
            mock_s3_create.assert_called_once()
            call_args = mock_s3_create.call_args
            passed_metadata = call_args[1]["metadata"]

            # Verify README content was removed from metadata but stored for processing
            assert "readme_content" not in passed_metadata
            assert "_extracted_readme" in passed_metadata
            assert passed_metadata["_extracted_readme"] == "# Test Dataset\n\nThis is a test README."

            # Verify other metadata was preserved
            assert passed_metadata["custom_field"] == "value"
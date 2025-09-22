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


class TestEnhancedDryRunCapabilities:
    """Unit tests for enhanced dry-run functionality in create_package."""

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_dry_run_returns_comprehensive_preview(self, mock_s3_create):
        """Test that dry-run returns comprehensive preview including quilt_summarize.json."""
        # Mock the enhanced dry-run response from package_create_from_s3
        mock_s3_create.return_value = {
            "success": True,
            "action": "preview",
            "package_name": "test/package",
            "registry": "s3://test-bucket",
            "structure_preview": {
                "organized_structure": {
                    "data/": [{"name": "file.csv", "size": 1024}],
                    "docs/": [{"name": "README.md", "size": 512}],
                },
                "total_files": 2,
                "total_size_mb": 0.0015,
                "organization_applied": True,
            },
            "readme_preview": "# Test Package\n\nThis is a test package...",
            "metadata_preview": {
                "package_type": "data",
                "created_by": "quilt-mcp-server",
                "description": "Test dataset",
            },
            "summary_files_preview": {
                "quilt_summarize.json": {
                    "version": "1.0",
                    "name": "test/package",
                    "structure": {"data/": 1, "docs/": 1},
                },
                "visualizations": {
                    "file_distribution": {"csv": 1},
                },
                "files_generated": {
                    "quilt_summarize.json": True,
                    "README.md": True,
                },
            },
            "message": "Preview generated. Set dry_run=False to create the package.",
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
                description="Test dataset",
                metadata_template="standard",
                dry_run=True,
            )

            # Verify comprehensive dry-run response
            assert result["success"] is True
            assert result["action"] == "preview"
            assert result["package_name"] == "test/package"
            assert result["registry"] == "s3://test-bucket"

            # Verify structure preview
            assert "structure_preview" in result
            structure = result["structure_preview"]
            assert "organized_structure" in structure
            assert "total_files" in structure
            assert "total_size_mb" in structure

            # Verify metadata preview
            assert "metadata_preview" in result
            metadata = result["metadata_preview"]
            assert metadata["package_type"] == "data"
            assert metadata["description"] == "Test dataset"

            # Verify README preview
            assert "readme_preview" in result
            assert result["readme_preview"].startswith("# Test Package")

            # Verify summary files preview
            assert "summary_files_preview" in result
            summary = result["summary_files_preview"]
            assert "quilt_summarize.json" in summary
            assert "visualizations" in summary
            assert "files_generated" in summary

            # Verify enhancement context
            assert result["metadata_template_used"] == "standard"
            assert result["creation_method"] == "s3_sources"

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_dry_run_with_genomics_template_shows_validation(self, mock_s3_create):
        """Test that dry-run with genomics template shows metadata validation results."""
        # Mock comprehensive genomics template dry-run response
        mock_s3_create.return_value = {
            "success": True,
            "action": "preview",
            "package_name": "genomics/study1",
            "registry": "s3://genomics-bucket",
            "structure_preview": {
                "organized_structure": {
                    "raw_data/": [{"name": "sample1.vcf", "size": 2048}],
                    "analysis/": [{"name": "variants.txt", "size": 1024}],
                },
                "total_files": 2,
                "total_size_mb": 0.003,
                "organization_applied": True,
            },
            "readme_preview": "# Genomics Study 1\n\nThis package contains genomic data...",
            "metadata_preview": {
                "package_type": "genomics",
                "data_type": "genomics",
                "organism": "human",
                "genome_build": "GRCh38",
                "description": "Human genome study",
                "created_by": "quilt-mcp-server",
            },
            "summary_files_preview": {
                "quilt_summarize.json": {
                    "version": "1.0",
                    "name": "genomics/study1",
                    "metadata_template": "genomics",
                    "organism": "human",
                    "genome_build": "GRCh38",
                },
                "visualizations": {
                    "file_distribution": {"vcf": 1, "txt": 1},
                },
                "files_generated": {
                    "quilt_summarize.json": True,
                    "README.md": True,
                    "genomics_metadata.json": True,
                },
            },
            "validation_results": {
                "metadata_valid": True,
                "template_compliance": True,
                "missing_fields": [],
                "warnings": ["Consider adding sample_count field"],
            },
            "message": "Preview generated. Set dry_run=False to create the package.",
        }

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/sample1.vcf", "s3://bucket/analysis/variants.txt"],
                "local_files": [],
                "has_errors": False,
            }

            result = create_package(
                name="genomics/study1",
                files=["s3://bucket/sample1.vcf", "s3://bucket/analysis/variants.txt"],
                description="Human genome study",
                metadata_template="genomics",
                metadata={"organism": "human", "genome_build": "GRCh38"},
                dry_run=True,
            )

            # Verify comprehensive genomics dry-run response
            assert result["success"] is True
            assert result["action"] == "preview"

            # Verify genomics-specific metadata preview
            metadata = result["metadata_preview"]
            assert metadata["package_type"] == "genomics"
            assert metadata["organism"] == "human"
            assert metadata["genome_build"] == "GRCh38"

            # Verify validation results if present
            if "validation_results" in result:
                validation = result["validation_results"]
                assert validation["metadata_valid"] is True
                assert validation["template_compliance"] is True

            # Verify template was used
            assert result["metadata_template_used"] == "genomics"

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_dry_run_shows_structure_warnings(self, mock_s3_create):
        """Test that dry-run shows structure warnings and suggestions."""
        # Mock dry-run response with warnings
        mock_s3_create.return_value = {
            "success": True,
            "action": "preview",
            "package_name": "test/messy-data",
            "registry": "s3://test-bucket",
            "structure_preview": {
                "organized_structure": {
                    "data/": [{"name": "file1.csv", "size": 1024}],
                    "unorganized/": [{"name": "random_file.tmp", "size": 256}],
                },
                "total_files": 2,
                "total_size_mb": 0.00125,
                "organization_applied": True,
                "warnings": [
                    "Found 1 file with unknown extension (.tmp)",
                    "Some files may not be in optimal structure",
                ],
                "suggestions": [
                    "Consider reviewing files in 'unorganized/' folder",
                    "Add file descriptions in metadata for better discoverability",
                ],
            },
            "readme_preview": "# Messy Data Package\n\nThis package contains mixed data types...",
            "metadata_preview": {
                "package_type": "data",
                "created_by": "quilt-mcp-server",
                "description": "Mixed data with various formats",
            },
            "summary_files_preview": {
                "quilt_summarize.json": {
                    "version": "1.0",
                    "name": "test/messy-data",
                    "structure": {"data/": 1, "unorganized/": 1},
                    "warnings": ["Mixed file types detected"],
                },
                "files_generated": {
                    "quilt_summarize.json": True,
                    "README.md": True,
                },
            },
            "message": "Preview generated. Set dry_run=False to create the package.",
        }

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file1.csv", "s3://bucket/random_file.tmp"],
                "local_files": [],
                "has_errors": False,
            }

            result = create_package(
                name="test/messy-data",
                files=["s3://bucket/file1.csv", "s3://bucket/random_file.tmp"],
                description="Mixed data with various formats",
                dry_run=True,
            )

            # Verify dry-run shows warnings and suggestions
            assert result["success"] is True

            # Check for warnings in structure preview
            structure = result["structure_preview"]
            if "warnings" in structure:
                assert len(structure["warnings"]) > 0
                assert any("unknown extension" in warning for warning in structure["warnings"])

            if "suggestions" in structure:
                assert len(structure["suggestions"]) > 0
                assert any("unorganized" in suggestion for suggestion in structure["suggestions"])

    def test_create_package_dry_run_with_metadata_validation_failure(self):
        """Test that dry-run handles metadata validation failures gracefully."""
        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze, \
             patch("quilt_mcp.tools.unified_package.validate_metadata_structure") as mock_validate:

            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            # Mock validation failure
            mock_validate.return_value = {
                "valid": False,
                "errors": ["Missing required field: organism"],
                "suggestions": ["Add organism field for genomics template"],
                "warnings": ["Incomplete metadata for genomics package"],
            }

            result = create_package(
                name="genomics/invalid",
                files=["s3://bucket/file.csv"],
                metadata_template="genomics",
                metadata={"incomplete": "data"},
                dry_run=True,
            )

            # Verify validation failure is returned
            assert result["success"] is False
            assert "Metadata validation failed" in result["error"]
            assert "validation_result" in result
            assert result["validation_result"]["valid"] is False
            assert "Missing required field: organism" in result["validation_result"]["errors"]

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_dry_run_preserves_readme_extraction(self, mock_s3_create):
        """Test that dry-run correctly shows README content extraction."""
        # Mock dry-run response with README extraction
        mock_s3_create.return_value = {
            "success": True,
            "action": "preview",
            "package_name": "test/with-readme",
            "registry": "s3://test-bucket",
            "structure_preview": {
                "organized_structure": {
                    "data/": [{"name": "file.csv", "size": 1024}],
                    "docs/": [{"name": "README.md", "size": 512}],
                },
                "total_files": 2,
                "total_size_mb": 0.0015,
                "organization_applied": True,
            },
            "readme_preview": "# Custom README\n\nThis is a custom README from metadata...",
            "metadata_preview": {
                "package_type": "data",
                "created_by": "quilt-mcp-server",
                "description": "Package with custom README",
                "_extracted_readme": "# Custom README\n\nThis is a custom README from metadata.",
            },
            "summary_files_preview": {
                "quilt_summarize.json": {
                    "version": "1.0",
                    "name": "test/with-readme",
                    "has_custom_readme": True,
                },
                "files_generated": {
                    "quilt_summarize.json": True,
                    "README.md": True,
                },
            },
            "message": "Preview generated. Set dry_run=False to create the package.",
        }

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            result = create_package(
                name="test/with-readme",
                files=["s3://bucket/file.csv"],
                description="Package with custom README",
                metadata={"readme_content": "# Custom README\n\nThis is a custom README from metadata."},
                dry_run=True,
            )

            # Verify dry-run shows extracted README
            assert result["success"] is True
            assert result["readme_preview"].startswith("# Custom README")

            # Verify metadata shows extraction occurred
            metadata = result["metadata_preview"]
            assert "_extracted_readme" in metadata
            assert metadata["_extracted_readme"] == "# Custom README\n\nThis is a custom README from metadata."

            # Verify README not in regular metadata fields
            assert "readme_content" not in metadata

    def test_create_package_dry_run_needs_comprehensive_structure_preview(self):
        """Test that dry-run should provide comprehensive structure preview - this should fail initially."""
        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze, \
             patch("quilt_mcp.tools.unified_package.package_create_from_s3") as mock_s3_create:

            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            # Mock a minimal dry-run response - missing comprehensive preview
            mock_s3_create.return_value = {
                "success": True,
                "action": "preview",
                "package_name": "test/package",
                "registry": "s3://test-bucket",
                # Missing: structure_preview, metadata_preview, summary_files_preview
            }

            result = create_package(
                name="test/package",
                files=["s3://bucket/file.csv"],
                metadata_template="standard",
                dry_run=True,
            )

            # These comprehensive preview fields should be present in enhanced dry-run
            # This test will FAIL if the comprehensive preview is not implemented
            assert result["success"] is True

            # The key missing features that should be enhanced
            assert "structure_preview" in result, "Dry-run should include comprehensive structure preview"
            assert "metadata_preview" in result, "Dry-run should include metadata preview with template"
            assert "summary_files_preview" in result, "Dry-run should include quilt_summarize.json preview"
            assert "readme_preview" in result, "Dry-run should include README preview"

            # Verify the structure preview has the expected detailed information
            structure = result["structure_preview"]
            assert "organized_structure" in structure, "Should show organized file structure"
            assert "total_files" in structure, "Should show total file count"
            assert "total_size_mb" in structure, "Should show total size"

            # Verify metadata preview includes template information
            metadata = result["metadata_preview"]
            assert "package_type" in metadata, "Should show package type from template"
            assert "created_by" in metadata, "Should show creator information"
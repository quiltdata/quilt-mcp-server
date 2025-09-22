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


class TestPackageCreateEquivalence:
    """Integration tests to verify create_package provides comprehensive package creation functionality."""

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_comprehensive_functionality_standard_template(self, mock_create_from_s3):
        """Test that create_package with standard template provides comprehensive functionality."""
        # Mock successful package creation response
        expected_result = {
            "success": True,
            "package_name": "test/dataset",
            "registry": "s3://test-bucket",
            "created_at": "2024-01-01T12:00:00Z",
            "files_processed": 2,
        }

        mock_create_from_s3.return_value = expected_result.copy()

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file1.csv", "s3://bucket/file2.csv"],
                "local_files": [],
                "has_errors": False,
            }

            # Call create_package with standard template
            result = create_package(
                name="test/dataset",
                files=["s3://bucket/file1.csv", "s3://bucket/file2.csv"],
                description="Test dataset",
                metadata_template="standard",
            )

            # Verify comprehensive functionality
            assert result["success"] is True
            assert result["package_name"] == "test/dataset"
            assert result["metadata_template_used"] == "standard"
            assert result["creation_method"] == "s3_sources"

            # Verify underlying function was called with proper metadata template
            mock_create_from_s3.assert_called_once()
            call_args = mock_create_from_s3.call_args
            passed_metadata = call_args[1]["metadata"]

            # Verify standard template fields were applied
            assert passed_metadata["package_type"] == "data"
            assert passed_metadata["created_by"] == "quilt-mcp-server"
            assert "creation_date" in passed_metadata
            assert passed_metadata["description"] == "Test dataset"

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_supports_all_metadata_templates(self, mock_create_from_s3):
        """Test that create_package works with all available metadata templates."""
        templates_to_test = ["standard", "genomics", "ml", "research", "analytics"]

        for template in templates_to_test:
            # Reset mock for each template
            mock_create_from_s3.reset_mock()

            expected_result = {
                "success": True,
                "package_name": f"{template}/dataset",
                "registry": "s3://test-bucket",
                "metadata_template": template,
            }

            mock_create_from_s3.return_value = expected_result.copy()

            with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
                mock_analyze.return_value = {
                    "source_type": "s3_only",
                    "s3_files": ["s3://bucket/data.csv"],
                    "local_files": [],
                    "has_errors": False,
                }

                # Call create_package with each template
                result = create_package(
                    name=f"{template}/dataset",
                    files=["s3://bucket/data.csv"],
                    metadata_template=template,
                )

                # Verify success for this template
                assert result["success"] is True, f"create_package failed for {template} template"
                assert result["metadata_template_used"] == template

                # Verify template-specific metadata was applied
                mock_create_from_s3.assert_called_once()
                call_args = mock_create_from_s3.call_args
                passed_metadata = call_args[1]["metadata"]

                # Verify appropriate package_type based on template
                if template == "genomics":
                    assert passed_metadata["package_type"] == "genomics"
                    assert passed_metadata["data_type"] == "genomics"
                elif template == "ml":
                    assert passed_metadata["package_type"] == "ml_dataset"
                    assert passed_metadata["data_type"] == "machine_learning"
                elif template == "research":
                    assert passed_metadata["package_type"] == "research"
                    assert passed_metadata["data_type"] == "research"
                elif template == "analytics":
                    assert passed_metadata["package_type"] == "analytics"
                    assert passed_metadata["data_type"] == "business_analytics"
                else:  # standard
                    assert passed_metadata["package_type"] == "data"

    def test_create_package_comprehensive_error_handling(self):
        """Test that create_package handles various error scenarios with high-quality error messages."""
        # Test specific error scenarios by directly calling with problematic inputs

        # Test 1: Invalid package name (no mocking needed - this is validation)
        result = create_package(
            name="invalid-package-name",  # Missing namespace/name format
            files=["s3://bucket/file.csv"],
        )

        # Should fail with validation error
        is_error = (result.get("success") is False) or (result.get("status") == "error")
        assert is_error, "Should fail for invalid package name format"
        assert "error" in result, "Should provide error message"

        # Test 2: Empty files list
        result = create_package(
            name="test/package",
            files=[],  # Empty files list
        )

        # Should fail with validation error
        is_error = (result.get("success") is False) or (result.get("status") == "error")
        assert is_error, "Should fail for empty files list"
        assert "error" in result, "Should provide error message"

        # Test 3: Test with proper mocking for file analysis errors
        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "error",
                "s3_files": [],
                "local_files": [],
                "has_errors": True,
                "errors": ["Invalid S3 URI format"],
            }

            result = create_package(
                name="test/package",
                files=["s3://bucket/file.csv"],
            )

            # Should fail with file analysis error
            is_error = (result.get("success") is False) or (result.get("status") == "error")
            assert is_error, "Should fail for file analysis errors"
            assert "error" in result, "Should provide error message"

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_comprehensive_dry_run_preview(self, mock_create_from_s3):
        """Test that create_package dry_run provides comprehensive preview capabilities."""
        # Mock comprehensive dry-run response
        enhanced_dry_run = {
            "success": True,
            "action": "preview",
            "package_name": "test/preview",
            "registry": "s3://test-bucket",
            "structure_preview": {
                "organized_structure": {"data/": [{"name": "file.csv", "size": 1024}]},
                "total_files": 1,
                "total_size_mb": 0.001,
                "organization_applied": True,
            },
            "metadata_preview": {
                "package_type": "data",
                "created_by": "quilt-mcp-server",
                "description": "Test preview",
            },
            "readme_preview": "# Test Preview\n\nThis is a preview package...",
            "summary_files_preview": {
                "quilt_summarize.json": {"version": "1.0", "name": "test/preview"},
                "files_generated": {"quilt_summarize.json": True, "README.md": True},
            },
            "message": "Preview generated",
        }

        mock_create_from_s3.return_value = enhanced_dry_run

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            # Call create_package with dry_run=True
            result = create_package(
                name="test/preview",
                files=["s3://bucket/file.csv"],
                description="Test preview",
                dry_run=True,
            )

            # Verify comprehensive dry-run preview
            assert result["success"] is True
            assert result["action"] == "preview"
            assert result["package_name"] == "test/preview"

            # Verify comprehensive preview features
            assert "structure_preview" in result, "create_package should provide enhanced structure preview"
            assert "metadata_preview" in result, "create_package should provide metadata preview"
            assert "summary_files_preview" in result, "create_package should provide summary files preview"
            assert "readme_preview" in result, "create_package should provide README preview"

            # Verify enhancement metadata
            assert result["metadata_template_used"] == "standard"
            assert result["creation_method"] == "s3_sources"

            # Verify structure preview details
            structure = result["structure_preview"]
            assert "organized_structure" in structure
            assert "total_files" in structure
            assert "total_size_mb" in structure

            # Verify metadata preview includes template fields
            metadata = result["metadata_preview"]
            assert metadata["package_type"] == "data"
            assert metadata["created_by"] == "quilt-mcp-server"

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_comprehensive_json_metadata_handling(self, mock_create_from_s3):
        """Test that create_package handles JSON string metadata comprehensively."""
        json_metadata = '{"custom_field": "value", "tags": ["tag1", "tag2"], "priority": 1}'

        expected_result = {
            "success": True,
            "package_name": "test/json-metadata",
            "registry": "s3://test-bucket",
        }

        mock_create_from_s3.return_value = expected_result.copy()

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            # Call create_package with JSON string metadata
            result = create_package(
                name="test/json-metadata",
                files=["s3://bucket/file.csv"],
                metadata=json_metadata,
            )

            # Verify successful JSON metadata handling
            assert result["success"] is True
            assert result["metadata_template_used"] == "standard"

            # Verify the underlying function was called with parsed metadata
            mock_create_from_s3.assert_called_once()
            call_args = mock_create_from_s3.call_args
            passed_metadata = call_args[1]["metadata"]

            # Verify JSON fields were parsed and merged with template
            assert "custom_field" in passed_metadata
            assert passed_metadata["custom_field"] == "value"
            assert "tags" in passed_metadata
            assert passed_metadata["tags"] == ["tag1", "tag2"]
            assert "priority" in passed_metadata
            assert passed_metadata["priority"] == 1

            # Verify template fields are also present
            assert passed_metadata["package_type"] == "data"
            assert passed_metadata["created_by"] == "quilt-mcp-server"

    def test_create_package_invalid_json_error_quality(self):
        """Test that create_package provides high-quality error messages for invalid JSON."""
        invalid_json_cases = [
            '{"invalid": json}',  # Invalid syntax
            '{"unclosed": "string}',  # Unclosed string
            '{invalid_key: "value"}',  # Unquoted key
            '{"trailing": "comma",}',  # Trailing comma
        ]

        for invalid_json in invalid_json_cases:
            with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
                mock_analyze.return_value = {
                    "source_type": "s3_only",
                    "s3_files": ["s3://bucket/file.csv"],
                    "local_files": [],
                    "has_errors": False,
                }

                result = create_package(
                    name="test/invalid-json",
                    files=["s3://bucket/file.csv"],
                    metadata=invalid_json,
                )

                # Verify error handling
                assert result["success"] is False
                assert "Invalid metadata JSON format" in result["error"]

                # Verify helpful error context is provided
                assert "json_error" in result, "Should provide specific JSON parsing error"
                assert "examples" in result, "Should provide JSON examples for guidance"

                # Verify error message quality
                error_msg = result["error"]
                assert any(word in error_msg.lower() for word in ["json", "format", "parse"]), \
                    "Error message should clearly indicate JSON parsing issue"

    @patch("quilt_mcp.tools.unified_package.package_create_from_s3")
    def test_create_package_performance_characteristics(self, mock_create_from_s3):
        """Test that create_package has reasonable performance characteristics."""
        # Mock fast response
        mock_create_from_s3.return_value = {
            "success": True,
            "package_name": "test/performance",
            "registry": "s3://test-bucket",
        }

        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze:
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/file.csv"],
                "local_files": [],
                "has_errors": False,
            }

            import time

            # Time the function call
            start_time = time.time()
            result = create_package(
                name="test/performance",
                files=["s3://bucket/file.csv"],
                metadata_template="standard",
            )
            execution_time = time.time() - start_time

            # Verify success
            assert result["success"] is True
            assert result["metadata_template_used"] == "standard"

            # Verify reasonable performance (should complete in under 1 second for mocked operations)
            assert execution_time < 1.0, f"create_package took {execution_time:.3f}s, which seems too slow for mocked operations"

            # Verify template processing doesn't add excessive overhead
            # Multiple calls should have consistent performance
            times = []
            for i in range(3):
                mock_create_from_s3.reset_mock()
                start = time.time()
                create_package(
                    name=f"test/perf-{i}",
                    files=["s3://bucket/file.csv"],
                    metadata_template="genomics",
                )
                times.append(time.time() - start)

            # Performance should be consistent (no significant degradation)
            avg_time = sum(times) / len(times)
            assert all(t < avg_time * 2 for t in times), "Performance should be consistent across calls"

    @patch("quilt_mcp.tools.unified_package.validate_metadata_structure")
    def test_create_package_metadata_validation_comprehensive(self, mock_validate):
        """Test that create_package provides comprehensive metadata validation."""
        validation_scenarios = [
            {
                "template": "genomics",
                "metadata": {"organism": "human"},
                "validation_result": {
                    "valid": True,
                    "errors": [],
                    "warnings": ["Consider adding genome_build field"],
                    "suggestions": ["Add sample_count for better documentation"],
                },
                "should_succeed": True,
            },
            {
                "template": "ml",
                "metadata": {"incomplete": "data"},
                "validation_result": {
                    "valid": False,
                    "errors": ["Missing required field: features_count"],
                    "warnings": ["Model metadata incomplete"],
                    "suggestions": ["Add target_variable and model_type fields"],
                },
                "should_succeed": False,
            },
        ]

        for scenario in validation_scenarios:
            mock_validate.return_value = scenario["validation_result"]

            with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze, \
                 patch("quilt_mcp.tools.unified_package.package_create_from_s3") as mock_create:

                # Mock successful file analysis
                mock_analyze.return_value = {
                    "source_type": "s3_only",
                    "s3_files": ["s3://test-bucket/file.csv"],
                    "local_files": [],
                    "has_errors": False,
                }

                # Mock package creation response for successful validation
                if scenario["should_succeed"]:
                    mock_create.return_value = {
                        "success": True,
                        "action": "preview",
                        "package_name": f"{scenario['template']}/validation-test",
                        "registry": "s3://test-bucket",
                        "validation_result": scenario["validation_result"],
                    }
                else:
                    # Don't call mock_create for failing validation
                    pass

                result = create_package(
                    name=f"{scenario['template']}/validation-test",
                    files=["s3://test-bucket/file.csv"],
                    metadata_template=scenario["template"],
                    metadata=scenario["metadata"],
                    dry_run=True,  # Use dry_run to test validation without creation
                )

                if scenario["should_succeed"]:
                    # Should succeed but may have validation warnings
                    assert result["success"] is True, f"Should succeed for valid {scenario['template']} metadata"
                    if "validation_result" in result:
                        validation = result["validation_result"]
                        assert validation["valid"] == scenario["validation_result"]["valid"]
                else:
                    # Should fail validation
                    assert result["success"] is False, f"Should fail for invalid {scenario['template']} metadata"
                    assert "validation" in result["error"].lower(), "Error should mention validation failure"
                    assert "validation_result" in result, "Should provide validation details"
                    validation = result["validation_result"]
                    assert validation["valid"] is False, "Validation result should indicate failure"
                    assert len(validation["errors"]) > 0, "Should provide specific validation errors"

    def test_create_package_comprehensive_parameter_support(self):
        """Test that create_package supports comprehensive parameter set for package creation."""
        import inspect

        # Get parameter names from create_package
        unified_params = set(inspect.signature(create_package).parameters.keys())

        # Verify create_package has all essential package creation parameters
        essential_params = {
            "name",           # Package name
            "files",          # Files to include
            "description",    # Package description
            "metadata",       # Custom metadata
            "dry_run",        # Preview mode
            "auto_organize",  # File organization
            "target_registry", # Target registry
        }

        missing_essential = essential_params - unified_params
        assert len(missing_essential) == 0, \
            f"create_package missing essential parameters: {missing_essential}"

        # Verify create_package has enhancement parameters
        enhancement_params = {"metadata_template"}  # Template system enhancement
        present_enhancements = enhancement_params & unified_params
        assert len(present_enhancements) > 0, \
            f"create_package should have enhancement parameters like: {enhancement_params}"

        # Verify the function signature is reasonable (not too many parameters)
        assert len(unified_params) < 15, \
            f"create_package has {len(unified_params)} parameters, which might be too many"

        # Verify key enhancement parameters exist
        assert "metadata_template" in unified_params, "Should support metadata template system"

    def test_create_package_integration_with_all_supported_features(self):
        """Integration test that create_package works with all its supported features together."""
        with patch("quilt_mcp.tools.unified_package._analyze_file_sources") as mock_analyze, \
             patch("quilt_mcp.tools.unified_package.package_create_from_s3") as mock_create, \
             patch("quilt_mcp.tools.unified_package.validate_metadata_structure") as mock_validate:

            # Mock successful analysis
            mock_analyze.return_value = {
                "source_type": "s3_only",
                "s3_files": ["s3://bucket/data.csv", "s3://bucket/readme.md"],
                "local_files": [],
                "has_errors": False,
            }

            # Mock successful validation
            mock_validate.return_value = {
                "valid": True,
                "errors": [],
                "warnings": ["Consider adding more metadata fields"],
                "suggestions": ["Add data_source field for better documentation"],
            }

            # Mock successful package creation
            mock_create.return_value = {
                "success": True,
                "package_name": "integration/full-test",
                "registry": "s3://test-bucket",
                "files_processed": 2,
                "created_at": "2024-01-01T12:00:00Z",
            }

            # Test create_package with all supported features
            result = create_package(
                name="integration/full-test",
                files=["s3://bucket/data.csv", "s3://bucket/readme.md"],
                description="Integration test with all features",
                metadata_template="research",
                metadata={
                    "study_type": "observational",
                    "data_source": "clinical_trial",
                    "readme_content": "# Custom README\n\nThis is a test.",
                },
                auto_organize=True,
                target_registry="s3://test-bucket",
                dry_run=False,
            )

            # Verify comprehensive integration
            assert result["success"] is True
            assert result["package_name"] == "integration/full-test"
            assert result["metadata_template_used"] == "research"
            assert result["creation_method"] == "s3_sources"

            # Verify all subsystems were called
            mock_analyze.assert_called_once()
            mock_validate.assert_called_once()
            mock_create.assert_called_once()

            # Verify metadata template integration
            call_args = mock_create.call_args
            passed_metadata = call_args[1]["metadata"]

            # Should have template fields
            assert passed_metadata["package_type"] == "research"
            assert passed_metadata["data_type"] == "research"

            # Should have user fields
            assert passed_metadata["study_type"] == "observational"
            assert passed_metadata["data_source"] == "clinical_trial"

            # Should have extracted README
            assert "_extracted_readme" in passed_metadata
            assert passed_metadata["_extracted_readme"] == "# Custom README\n\nThis is a test."
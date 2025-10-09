"""Tests for the quilt_summary module."""

import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from quilt_mcp.tools.quilt_summary import (
    generate_quilt_summarize_json,
    generate_package_visualizations,
    create_quilt_summary_files,
    quilt_summary,
)


class TestQuiltSummary:
    """Test cases for quilt summary generation."""

    def test_generate_quilt_summarize_json_basic(self):
        """Test basic quilt_summarize.json generation."""
        package_name = "test/package"
        package_metadata = {
            "quilt": {
                "created_by": "test-user",
                "creation_date": "2024-01-01T00:00:00Z",
                "package_version": "1.0.0",
            }
        }
        organized_structure = {
            "data": [
                {"Key": "data/file1.csv", "Size": 1024},
                {"Key": "data/file2.csv", "Size": 2048},
            ],
            "docs": [{"Key": "docs/readme.md", "Size": 512}],
        }
        readme_content = "# Test Package\n\nTest content"
        source_info = {
            "type": "s3_bucket",
            "bucket": "test-bucket",
            "prefix": "test-prefix",
        }

        result = generate_quilt_summarize_json(
            package_name=package_name,
            package_metadata=package_metadata,
            organized_structure=organized_structure,
            readme_content=readme_content,
            source_info=source_info,
            metadata_template="standard",
        )

        assert result["package_info"]["name"] == package_name
        assert result["package_info"]["namespace"] == "test"
        assert result["package_info"]["package_name"] == "package"
        assert result["data_summary"]["total_files"] == 3
        assert result["data_summary"]["total_size_bytes"] == 3584
        assert result["structure"]["folders"]["data"]["file_count"] == 2
        assert result["structure"]["folders"]["docs"]["file_count"] == 1
        assert result["source"]["bucket"] == "test-bucket"
        assert result["documentation"]["readme_generated"] is True
        assert result["documentation"]["visualizations_generated"] is True

    def test_generate_quilt_summarize_json_with_errors(self):
        """Test quilt_summarize.json generation with invalid data."""
        result = generate_quilt_summarize_json(
            package_name="invalid/package",
            package_metadata={},
            organized_structure={},
            readme_content="",
            source_info={},
            metadata_template="standard",
        )

        # Function handles invalid input gracefully, not as an error
        assert "package_info" in result
        assert result["package_info"]["name"] == "invalid/package"
        assert result["package_info"]["namespace"] == "invalid"
        assert result["package_info"]["package_name"] == "package"

    def test_generate_package_visualizations_handles_missing_matplotlib(self):
        """Legacy visualization path should surface a clear error without matplotlib."""
        package_name = "test/package"
        organized_structure = {
            "data": [
                {"Key": "data/file1.csv", "Size": 1024},
                {"Key": "data/file2.csv", "Size": 2048},
            ],
            "docs": [{"Key": "docs/readme.md", "Size": 512}],
        }
        file_types = {"csv": 2, "md": 1}

        with patch("quilt_mcp.tools.quilt_summary._ensure_matplotlib", side_effect=ImportError("Matplotlib missing")):
            result = generate_package_visualizations(
                package_name=package_name,
                organized_structure=organized_structure,
                file_types=file_types,
                metadata_template="standard",
            )

        assert result["success"] is False
        assert "Matplotlib" in result["error"]

    def test_create_quilt_summary_files(self):
        """Test complete quilt summary file creation."""
        package_name = "test/package"
        package_metadata = {
            "quilt": {
                "created_by": "test-user",
                "creation_date": "2024-01-01T00:00:00Z",
                "package_version": "1.0.0",
            }
        }
        organized_structure = {
            "data": [
                {"Key": "data/file1.csv", "Size": 1024},
                {"Key": "data/file2.csv", "Size": 2048},
            ]
        }
        readme_content = "# Test Package\n\nTest content"
        source_info = {"type": "s3_bucket", "bucket": "test-bucket"}

        with patch("quilt_mcp.tools.quilt_summary.generate_package_visualizations", return_value={"success": False, "count": 0, "types": []}):
            result = create_quilt_summary_files(
                package_name=package_name,
                package_metadata=package_metadata,
                organized_structure=organized_structure,
                readme_content=readme_content,
                source_info=source_info,
                metadata_template="standard",
            )

        assert result["success"] is True
        assert result["files_generated"]["quilt_summarize.json"] is True
        assert result["files_generated"]["README.md"] is True
        assert result["files_generated"]["visualizations"] is True
        assert result["visualization_count"] > 0
        assert "quilt_summarize.json" in result["summary_package"]
        assert "README.md" in result["summary_package"]
        assert "visualizations" in result["summary_package"]
        visualizations = result["summary_package"]["visualizations"]
        assert visualizations["multi_format"]["success"] is True
        assert "legacy" in visualizations
        assert result["summary_package"]["quilt_summarize_entries"]
        assert result["summary_package"]["visualization_files"]

    def test_create_quilt_summary_files_with_errors(self):
        """Test quilt summary creation with invalid data."""
        with patch("quilt_mcp.tools.quilt_summary.generate_package_visualizations", return_value={"success": False, "count": 0, "types": []}):
            result = create_quilt_summary_files(
                package_name="",
                package_metadata={},
                organized_structure={},
                readme_content="",
                source_info={},
                metadata_template="invalid",
            )

        # Function handles invalid input gracefully, not as an error
        assert result["success"] is True
        assert "summary_package" in result

    def test_quilt_summary_discovery_includes_multi_viz(self):
        """The module should advertise the new multi-format action."""
        result = quilt_summary()
        assert "generate_multi_viz" in result["actions"]

    def test_generate_multi_viz_action_returns_multi_format_visualizations(self):
        """generate_multi_viz should surface multi-format outputs."""
        organized_structure = {
            "data": [
                {"Key": "data/customers.csv", "Size": 4096},
                {"Key": "data/metrics.json", "Size": 2048},
            ],
            "genomics": [{"Key": "genomics/sample.vcf", "Size": 102400}],
        }

        params = {
            "package_name": "team/example",
            "organized_structure": organized_structure,
            "file_types": {"csv": 1, "json": 1, "vcf": 1},
        }

        result = quilt_summary(action="generate_multi_viz", params=params)

        assert result["success"] is True
        assert result["count"] == len(result["visualizations"])
        formats = {viz["format"] for viz in result["visualizations"].values()}
        assert "echarts" in formats
        assert "perspective" in formats
        assert "igv" in formats
        assert len(result["quilt_summarize_entries"]) == result["count"]
        assert all(entry["path"] in result["files"] for entry in result["quilt_summarize_entries"])


if __name__ == "__main__":
    pytest.main([__file__])

"""Tests for the quilt_summary module."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from quilt_mcp.tools.quilt_summary import (
    generate_quilt_summarize_json,
    generate_package_visualizations,
    create_quilt_summary_files
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
                "package_version": "1.0.0"
            }
        }
        organized_structure = {
            "data": [
                {"Key": "data/file1.csv", "Size": 1024},
                {"Key": "data/file2.csv", "Size": 2048}
            ],
            "docs": [
                {"Key": "docs/readme.md", "Size": 512}
            ]
        }
        readme_content = "# Test Package\n\nTest content"
        source_info = {
            "type": "s3_bucket",
            "bucket": "test-bucket",
            "prefix": "test-prefix"
        }
        
        result = generate_quilt_summarize_json(
            package_name=package_name,
            package_metadata=package_metadata,
            organized_structure=organized_structure,
            readme_content=readme_content,
            source_info=source_info,
            metadata_template="standard"
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
            metadata_template="standard"
        )
        
        assert "error" in result
        assert result["package_name"] == "invalid/package"
    
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    def test_generate_package_visualizations(self, mock_close, mock_savefig):
        """Test package visualization generation."""
        package_name = "test/package"
        organized_structure = {
            "data": [
                {"Key": "data/file1.csv", "Size": 1024},
                {"Key": "data/file2.csv", "Size": 2048}
            ],
            "docs": [
                {"Key": "docs/readme.md", "Size": 512}
            ]
        }
        file_types = {"csv": 2, "md": 1}
        
        result = generate_package_visualizations(
            package_name=package_name,
            organized_structure=organized_structure,
            file_types=file_types,
            metadata_template="standard"
        )
        
        assert result["success"] is True
        assert result["count"] > 0
        assert "file_type_distribution" in result["types"]
        assert "folder_structure" in result["types"]
        assert "package_dashboard" in result["types"]
    
    def test_create_quilt_summary_files(self):
        """Test complete quilt summary file creation."""
        package_name = "test/package"
        package_metadata = {
            "quilt": {
                "created_by": "test-user",
                "creation_date": "2024-01-01T00:00:00Z",
                "package_version": "1.0.0"
            }
        }
        organized_structure = {
            "data": [
                {"Key": "data/file1.csv", "Size": 1024},
                {"Key": "data/file2.csv", "Size": 2048}
            ]
        }
        readme_content = "# Test Package\n\nTest content"
        source_info = {
            "type": "s3_bucket",
            "bucket": "test-bucket"
        }
        
        result = create_quilt_summary_files(
            package_name=package_name,
            package_metadata=package_metadata,
            organized_structure=organized_structure,
            readme_content=readme_content,
            source_info=source_info,
            metadata_template="standard"
        )
        
        assert result["success"] is True
        assert result["files_generated"]["quilt_summarize.json"] is True
        assert result["files_generated"]["README.md"] is True
        assert result["files_generated"]["visualizations"] is True
        assert result["visualization_count"] > 0
        assert "quilt_summarize.json" in result["summary_package"]
        assert "README.md" in result["summary_package"]
        assert "visualizations" in result["summary_package"]
    
    def test_create_quilt_summary_files_with_errors(self):
        """Test quilt summary creation with invalid data."""
        result = create_quilt_summary_files(
            package_name="",
            package_metadata={},
            organized_structure={},
            readme_content="",
            source_info={},
            metadata_template="invalid"
        )
        
        # Should handle errors gracefully
        assert result["success"] is False
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__])

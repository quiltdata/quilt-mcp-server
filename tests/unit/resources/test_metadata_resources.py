"""Unit tests for metadata resources."""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.resources.metadata import (
    MetadataTemplatesResource,
    MetadataExamplesResource,
    MetadataTroubleshootingResource,
    MetadataTemplateResource,
)


class TestMetadataTemplatesResource:
    """Test MetadataTemplatesResource."""

    @pytest.fixture
    def resource(self):
        return MetadataTemplatesResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful templates list retrieval."""
        mock_result = {
            "status": "success",
            "templates": {
                "standard": {"description": "Standard template"},
                "genomics": {"description": "Genomics template"},
            },
        }

        with patch("quilt_mcp.resources.metadata.list_metadata_templates") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("metadata://templates")

            assert response.uri == "metadata://templates"
            assert response.content == mock_result


class TestMetadataExamplesResource:
    """Test MetadataExamplesResource."""

    @pytest.fixture
    def resource(self):
        return MetadataExamplesResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful examples retrieval."""
        mock_result = {
            "status": "success",
            "examples": [
                {"name": "basic", "code": "..."},
                {"name": "advanced", "code": "..."},
            ],
        }

        with patch("quilt_mcp.resources.metadata.show_metadata_examples") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("metadata://examples")

            assert response.uri == "metadata://examples"
            assert response.content == mock_result

    @pytest.mark.anyio
    async def test_read_structure_validation(self, resource):
        """Test that examples response has expected structure."""
        mock_result = {
            "metadata_usage_guide": {
                "working_examples": [],
                "common_patterns": [],
                "recommended_approach": "...",
            },
            "troubleshooting": {},
            "best_practices": [],
            "quick_reference": {
                "available_templates": ["standard", "genomics", "ml", "research", "analytics"],
            },
        }

        with patch("quilt_mcp.resources.metadata.show_metadata_examples") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("metadata://examples")

            content = response.content
            assert "metadata_usage_guide" in content
            assert "troubleshooting" in content
            assert "best_practices" in content
            assert "quick_reference" in content

            # Verify nested structure
            muc = content["metadata_usage_guide"]
            assert "working_examples" in muc
            assert "common_patterns" in muc
            assert "recommended_approach" in muc

            # Verify template list
            quick = content["quick_reference"]
            assert "available_templates" in quick
            templates = set(quick["available_templates"])
            assert {"standard", "genomics", "ml", "research", "analytics"}.issubset(templates)


class TestMetadataTroubleshootingResource:
    """Test MetadataTroubleshootingResource."""

    @pytest.fixture
    def resource(self):
        return MetadataTroubleshootingResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful troubleshooting guide retrieval."""
        mock_result = {
            "status": "success",
            "guide": "Troubleshooting steps...",
        }

        with patch("quilt_mcp.resources.metadata.fix_metadata_validation_issues") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("metadata://troubleshooting")

            assert response.uri == "metadata://troubleshooting"
            assert response.content == mock_result

    @pytest.mark.anyio
    async def test_read_structure_validation(self, resource):
        """Test that troubleshooting response has expected structure."""
        mock_result = {
            "common_issues_and_fixes": {
                "schema_validation_error": "...",
                "json_format_error": "...",
                "type_validation_error": "...",
            },
            "step_by_step_fix": [
                "1. Check your metadata",
                "Choose your approach",
                "2. Validate the structure",
            ],
        }

        with patch("quilt_mcp.resources.metadata.fix_metadata_validation_issues") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("metadata://troubleshooting")

            content = response.content
            assert "common_issues_and_fixes" in content
            issues = content["common_issues_and_fixes"]
            assert "schema_validation_error" in issues
            assert "json_format_error" in issues
            assert "type_validation_error" in issues

            assert "step_by_step_fix" in content
            steps = content["step_by_step_fix"]
            assert any("Choose your approach" in step or step.startswith("1.") for step in steps)


class TestMetadataTemplateResource:
    """Test MetadataTemplateResource (parameterized)."""

    @pytest.fixture
    def resource(self):
        return MetadataTemplateResource()

    @pytest.mark.anyio
    async def test_read_with_params(self, resource):
        """Test reading specific template with parameters."""
        mock_result = {
            "status": "success",
            "template": {
                "name": "genomics",
                "fields": ["organism", "genome_build"],
            },
        }

        with patch("quilt_mcp.resources.metadata.get_metadata_template") as mock_tool:
            mock_tool.return_value = mock_result

            params = {"name": "genomics"}
            response = await resource.read("metadata://templates/genomics", params)

            assert response.uri == "metadata://templates/genomics"
            assert response.content == mock_result
            mock_tool.assert_called_once_with(template_name="genomics")

    @pytest.mark.anyio
    async def test_read_missing_param(self, resource):
        """Test reading without required parameters raises error."""
        with pytest.raises(ValueError, match="Template name required"):
            await resource.read("metadata://templates/genomics", params=None)

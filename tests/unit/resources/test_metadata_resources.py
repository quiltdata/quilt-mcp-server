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

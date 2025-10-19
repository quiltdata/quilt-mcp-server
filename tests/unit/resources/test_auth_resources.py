"""Unit tests for auth resources."""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.resources.auth import (
    AuthStatusResource,
    CatalogInfoResource,
    CatalogNameResource,
    FilesystemStatusResource,
)


class TestAuthStatusResource:
    """Test AuthStatusResource."""

    @pytest.fixture
    def resource(self):
        return AuthStatusResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful auth status retrieval."""
        mock_result = {
            "status": "authenticated",
            "catalog_name": "my-catalog",
            "user": "alice",
        }

        with patch("quilt_mcp.resources.auth.auth_status") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("auth://status")

            assert response.uri == "auth://status"
            assert response.content == mock_result


class TestCatalogInfoResource:
    """Test CatalogInfoResource."""

    @pytest.fixture
    def resource(self):
        return CatalogInfoResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful catalog info retrieval."""
        mock_result = {
            "status": "success",
            "catalog_name": "my-catalog",
            "navigator_url": "https://catalog.example.com",
        }

        with patch("quilt_mcp.resources.auth.catalog_info") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("auth://catalog/info")

            assert response.uri == "auth://catalog/info"
            assert response.content == mock_result


class TestCatalogNameResource:
    """Test CatalogNameResource."""

    @pytest.fixture
    def resource(self):
        return CatalogNameResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful catalog name retrieval."""
        mock_result = {
            "status": "success",
            "catalog_name": "my-catalog",
        }

        with patch("quilt_mcp.resources.auth.catalog_name") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("auth://catalog/name")

            assert response.uri == "auth://catalog/name"
            assert response.content == mock_result


class TestFilesystemStatusResource:
    """Test FilesystemStatusResource."""

    @pytest.fixture
    def resource(self):
        return FilesystemStatusResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful filesystem status retrieval."""
        mock_result = {
            "home_writable": True,
            "temp_writable": True,
            "status": "full_access",
        }

        with patch("quilt_mcp.resources.auth.filesystem_status") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("auth://filesystem/status")

            assert response.uri == "auth://filesystem/status"
            assert response.content == mock_result

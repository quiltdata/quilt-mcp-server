"""Unit tests for tabulator resources."""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.resources.tabulator import (
    TabulatorBucketsResource,
    TabulatorTablesResource,
)


class TestTabulatorBucketsResource:
    """Test TabulatorBucketsResource."""

    @pytest.fixture
    def resource(self):
        return TabulatorBucketsResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful buckets list retrieval."""
        mock_result = {
            "success": True,
            "buckets": ["bucket1", "bucket2", "bucket3"],
            "count": 3,
        }

        with patch("quilt_mcp.resources.tabulator.list_tabulator_buckets") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("tabulator://buckets")

            assert response.uri == "tabulator://buckets"
            assert response.content["items"] == mock_result["buckets"]
            assert response.content["metadata"]["total_count"] == 3

    @pytest.mark.anyio
    async def test_read_failure(self, resource):
        """Test buckets list retrieval failure."""
        mock_result = {"success": False, "error": "Service unavailable"}

        with patch("quilt_mcp.resources.tabulator.list_tabulator_buckets") as mock_tool:
            mock_tool.return_value = mock_result

            with pytest.raises(Exception, match="Failed to list buckets"):
                await resource.read("tabulator://buckets")

    @pytest.mark.anyio
    async def test_read_catalog_not_configured(self, resource):
        """Test buckets list when catalog not configured."""
        mock_result = {
            "success": False,
            "error": "tabulator_data_catalog not configured in catalog"
        }

        with patch("quilt_mcp.resources.tabulator.list_tabulator_buckets") as mock_tool:
            mock_tool.return_value = mock_result

            with pytest.raises(Exception, match="catalog not configured"):
                await resource.read("tabulator://buckets")


class TestTabulatorTablesResource:
    """Test TabulatorTablesResource (parameterized)."""

    @pytest.fixture
    def resource(self):
        return TabulatorTablesResource()

    @pytest.mark.anyio
    async def test_read_with_params(self, resource):
        """Test reading tables with parameters."""
        mock_result = {
            "success": True,
            "tables": [
                {"name": "table1", "schema": []},
                {"name": "table2", "schema": []},
            ],
            "count": 2,
        }

        with patch("quilt_mcp.resources.tabulator.list_tabulator_tables") as mock_tool:
            mock_tool.return_value = mock_result

            params = {"bucket": "my-bucket"}
            response = await resource.read("tabulator://buckets/my-bucket/tables", params)

            assert response.uri == "tabulator://buckets/my-bucket/tables"
            assert response.content["items"] == mock_result["tables"]
            assert response.content["metadata"]["total_count"] == 2
            mock_tool.assert_called_once_with("my-bucket")

    @pytest.mark.anyio
    async def test_read_missing_param(self, resource):
        """Test reading without required parameters raises error."""
        with pytest.raises(ValueError, match="Bucket name required"):
            await resource.read("tabulator://buckets/my-bucket/tables", params=None)

    @pytest.mark.anyio
    async def test_read_failure(self, resource):
        """Test tables list retrieval failure."""
        mock_result = {"success": False, "error": "Bucket not found"}

        with patch("quilt_mcp.resources.tabulator.list_tabulator_tables") as mock_tool:
            mock_tool.return_value = mock_result

            params = {"bucket": "nonexistent"}
            with pytest.raises(Exception, match="Failed to list tables"):
                await resource.read("tabulator://buckets/nonexistent/tables", params)

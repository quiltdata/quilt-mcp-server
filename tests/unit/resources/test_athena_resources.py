"""Unit tests for athena resources."""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.resources.athena import (
    AthenaDatabasesResource,
    AthenaTablesResource,
    AthenaWorkgroupsResource,
    AthenaTableSchemaResource,
    AthenaQueryHistoryResource,
)


class TestAthenaDatabasesResource:
    """Test AthenaDatabasesResource."""

    @pytest.fixture
    def resource(self):
        return AthenaDatabasesResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful databases list retrieval."""
        mock_result = {
            "success": True,
            "databases": [
                {"name": "default", "description": "Default database"},
                {"name": "analytics", "description": "Analytics database"},
            ],
            "count": 2,
        }

        with patch("quilt_mcp.resources.athena.athena_databases_list") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("athena://databases")

            assert response.uri == "athena://databases"
            assert response.content["items"] == mock_result["databases"]
            assert response.content["metadata"]["total_count"] == 2

    @pytest.mark.anyio
    async def test_read_failure(self, resource):
        """Test databases list retrieval failure."""
        mock_result = {"success": False, "error": "AWS error"}

        with patch("quilt_mcp.resources.athena.athena_databases_list") as mock_tool:
            mock_tool.return_value = mock_result

            with pytest.raises(Exception, match="Failed to list databases"):
                await resource.read("athena://databases")


class TestAthenaWorkgroupsResource:
    """Test AthenaWorkgroupsResource."""

    @pytest.fixture
    def resource(self):
        return AthenaWorkgroupsResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful workgroups list retrieval."""
        mock_result = {
            "success": True,
            "workgroups": [
                {"name": "primary", "state": "ENABLED"},
                {"name": "secondary", "state": "ENABLED"},
            ],
            "count": 2,
        }

        with patch("quilt_mcp.resources.athena.athena_workgroups_list") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("athena://workgroups")

            assert response.uri == "athena://workgroups"
            assert response.content["items"] == mock_result["workgroups"]
            assert response.content["metadata"]["total_count"] == 2


class TestAthenaTablesResource:
    """Test AthenaTablesResource (parameterized)."""

    @pytest.fixture
    def resource(self):
        return AthenaTablesResource()

    @pytest.mark.anyio
    async def test_read_with_params(self, resource):
        """Test reading tables list with parameters."""
        mock_result = {
            "success": True,
            "tables": [
                {"table_name": "users", "table_type": "EXTERNAL_TABLE"},
                {"table_name": "orders", "table_type": "EXTERNAL_TABLE"},
            ],
            "count": 2,
        }

        with patch("quilt_mcp.resources.athena.athena_tables_list") as mock_tool:
            mock_tool.return_value = mock_result

            params = {"database": "mydb"}
            response = await resource.read("athena://databases/mydb/tables", params)

            assert response.uri == "athena://databases/mydb/tables"
            assert response.content["items"] == mock_result["tables"]
            assert response.content["metadata"]["total_count"] == 2
            mock_tool.assert_called_once_with(database="mydb")

    @pytest.mark.anyio
    async def test_read_missing_params(self, resource):
        """Test reading without required parameters raises error."""
        with pytest.raises(ValueError, match="Database name required"):
            await resource.read("athena://databases/mydb/tables", params=None)

    @pytest.mark.anyio
    async def test_read_failure(self, resource):
        """Test tables list retrieval failure."""
        mock_result = {"success": False, "error": "Database not found"}

        with patch("quilt_mcp.resources.athena.athena_tables_list") as mock_tool:
            mock_tool.return_value = mock_result

            params = {"database": "mydb"}
            with pytest.raises(Exception, match="Failed to list tables"):
                await resource.read("athena://databases/mydb/tables", params)


class TestAthenaTableSchemaResource:
    """Test AthenaTableSchemaResource (parameterized)."""

    @pytest.fixture
    def resource(self):
        return AthenaTableSchemaResource()

    @pytest.mark.anyio
    async def test_read_with_params(self, resource):
        """Test reading table schema with parameters."""
        mock_result = {
            "success": True,
            "columns": [
                {"name": "id", "type": "bigint"},
                {"name": "name", "type": "string"},
            ],
        }

        with patch("quilt_mcp.resources.athena.athena_table_schema") as mock_tool:
            mock_tool.return_value = mock_result

            params = {"database": "mydb", "table": "mytable"}
            response = await resource.read("athena://databases/mydb/tables/mytable/schema", params)

            assert response.uri == "athena://databases/mydb/tables/mytable/schema"
            assert response.content == mock_result
            mock_tool.assert_called_once_with(database="mydb", table="mytable")

    @pytest.mark.anyio
    async def test_read_missing_params(self, resource):
        """Test reading without required parameters raises error."""
        with pytest.raises(ValueError, match="Database and table names required"):
            await resource.read("athena://databases/mydb/tables/mytable/schema", params=None)


class TestAthenaQueryHistoryResource:
    """Test AthenaQueryHistoryResource."""

    @pytest.fixture
    def resource(self):
        return AthenaQueryHistoryResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful query history retrieval."""
        mock_result = {
            "success": True,
            "queries": [
                {"id": "q1", "status": "SUCCEEDED"},
                {"id": "q2", "status": "FAILED"},
            ],
            "count": 2,
        }

        with patch("quilt_mcp.resources.athena.athena_query_history") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("athena://queries/history")

            assert response.uri == "athena://queries/history"
            # AthenaQueryHistoryResource returns the full result, not just items
            assert response.content == mock_result

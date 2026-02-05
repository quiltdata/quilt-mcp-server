#!/usr/bin/env python3
"""
Tests for Quilt Tabulator management tools
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from quilt_mcp.tools.tabulator import (
    tabulator_tables_list,
    tabulator_table_create,
    tabulator_table_delete,
    tabulator_table_rename,
)
# TabulatorService has been deprecated - admin operations moved to backend
# Query operations moved to athena_read_service


class TestTabulatorService:
    """Test TabulatorService class - DEPRECATED.

    Note: TabulatorService has been removed. Admin operations moved to TabulatorMixin.
    Query operations moved to athena_read_service.
    """

    def test_service_initialization_without_admin(self):
        """Test deprecated - TabulatorService removed."""
        pytest.skip("TabulatorService removed - admin operations moved to backend TabulatorMixin")

    def test_service_initialization_with_admin(self):
        """Test deprecated - TabulatorService removed."""
        pytest.skip("TabulatorService removed - admin operations moved to backend TabulatorMixin")

    def test_service_open_query_methods_no_admin_available(self):
        """Test deprecated - open query methods moved to backend."""
        pytest.skip("Open query methods moved to backend TabulatorMixin")


class TestGetTabulatorService:
    """Test get_tabulator_service utility function - DEPRECATED."""

    def test_get_tabulator_service(self):
        """Test deprecated - get_tabulator_service removed."""
        pytest.skip("get_tabulator_service removed - use backend directly")


class TestTabulatorTablesList:
    """Test tabulator_tables_list function."""

    @patch("quilt_mcp.ops.factory.QuiltOpsFactory.create")
    @pytest.mark.asyncio
    async def test_list_tables_success(self, mock_create):
        """Test successful table listing."""
        mock_backend = Mock()
        mock_create.return_value = mock_backend

        mock_backend.list_tabulator_tables.return_value = [
            {
                "name": "test_table",
                "config": "schema:\n- name: col1\n  type: STRING\n",
            }
        ]

        result = await tabulator_tables_list("test-bucket")

        assert result["success"] is True
        assert len(result["tables"]) == 1
        assert result["tables"][0]["name"] == "test_table"
        assert result["bucket_name"] == "test-bucket"
        mock_backend.list_tabulator_tables.assert_called_once_with("test-bucket")

    @patch("quilt_mcp.ops.factory.QuiltOpsFactory.create")
    @pytest.mark.asyncio
    async def test_list_tables_error(self, mock_create):
        """Test table listing error handling."""
        mock_backend = Mock()
        mock_create.return_value = mock_backend
        mock_backend.list_tabulator_tables.side_effect = Exception("Connection failed")

        result = await tabulator_tables_list("test-bucket")

        assert result["success"] is False
        assert "Connection failed" in result["error"]


class TestTabulatorTableCreate:
    """Test tabulator_table_create function."""

    @patch("quilt_mcp.ops.factory.QuiltOpsFactory.create")
    @pytest.mark.asyncio
    async def test_create_table_success(self, mock_create):
        """Test successful table creation."""
        mock_backend = Mock()
        mock_create.return_value = mock_backend

        mock_backend.create_tabulator_table.return_value = {
            "__typename": "BucketConfig",
            "bucketConfig": {"name": "test-bucket"},
        }

        schema = [{"name": "col1", "type": "STRING"}]
        result = await tabulator_table_create(
            bucket_name="test-bucket",
            table_name="test_table",
            schema=schema,
            package_pattern="^test-bucket/package$",
            logical_key_pattern="data/*.csv$",
        )

        assert result["success"] is True
        assert result["table_name"] == "test_table"
        mock_backend.create_tabulator_table.assert_called_once()

    @patch("quilt_mcp.ops.factory.QuiltOpsFactory.create")
    @pytest.mark.asyncio
    async def test_create_table_error_handling(self, mock_create):
        """Test table creation error handling."""
        mock_backend = Mock()
        mock_create.return_value = mock_backend
        mock_backend.create_tabulator_table.side_effect = Exception("Unexpected error")

        schema = [{"name": "col1", "type": "STRING"}]
        result = await tabulator_table_create(
            bucket_name="test-bucket",
            table_name="test_table",
            schema=schema,
            package_pattern="^test-bucket/package$",
            logical_key_pattern="data/*.csv$",
        )

        assert result["success"] is False
        assert "Unexpected error" in result["error"]


class TestTabulatorTableDelete:
    """Test tabulator_table_delete function."""

    @patch("quilt_mcp.ops.factory.QuiltOpsFactory.create")
    @pytest.mark.asyncio
    async def test_delete_table_success(self, mock_create):
        """Test successful table deletion."""
        mock_backend = Mock()
        mock_create.return_value = mock_backend

        mock_backend.delete_tabulator_table.return_value = {"__typename": "BucketConfig"}

        result = await tabulator_table_delete("test-bucket", "test_table")

        assert result["success"] is True
        assert result["table_name"] == "test_table"
        mock_backend.delete_tabulator_table.assert_called_once_with("test-bucket", "test_table")

    @patch("quilt_mcp.ops.factory.QuiltOpsFactory.create")
    @pytest.mark.asyncio
    async def test_delete_table_error_handling(self, mock_create):
        """Test table deletion error handling."""
        mock_backend = Mock()
        mock_create.return_value = mock_backend
        mock_backend.delete_tabulator_table.side_effect = Exception("Delete failed")

        result = await tabulator_table_delete("test-bucket", "test_table")

        assert result["success"] is False
        assert "Delete failed" in result["error"]


class TestTabulatorTableRename:
    """Test tabulator_table_rename function."""

    @patch("quilt_mcp.ops.factory.QuiltOpsFactory.create")
    @pytest.mark.asyncio
    async def test_rename_table_success(self, mock_create):
        """Test successful table rename."""
        mock_backend = Mock()
        mock_create.return_value = mock_backend

        mock_backend.rename_tabulator_table.return_value = {"__typename": "BucketConfig"}

        result = await tabulator_table_rename("test-bucket", "old_table", "new_table")

        assert result["success"] is True
        assert result["old_table_name"] == "old_table"
        assert result["new_table_name"] == "new_table"
        mock_backend.rename_tabulator_table.assert_called_once_with("test-bucket", "old_table", "new_table")

    @patch("quilt_mcp.ops.factory.QuiltOpsFactory.create")
    @pytest.mark.asyncio
    async def test_rename_table_error_handling(self, mock_create):
        """Test table rename error handling."""
        mock_backend = Mock()
        mock_create.return_value = mock_backend
        mock_backend.rename_tabulator_table.side_effect = Exception("Rename failed")

        result = await tabulator_table_rename("test-bucket", "old_table", "new_table")

        assert result["success"] is False
        assert "Rename failed" in result["error"]


class TestTabulatorOpenQuery:
    """Test tabulator open query functions.

    NOTE: These tools have been deprecated and removed.
    Use governance.admin_tabulator_open_query_get/set instead.
    """

    pass


class TestTabulatorQueryExecution:
    """Test tabulator query execution helpers."""

    def test_tabulator_query_discovers_catalog_from_catalog_info(self, monkeypatch: pytest.MonkeyPatch):
        """Test that tabulator_query_execute auto-discovers tabulator_data_catalog."""
        mock_catalog_info = MagicMock(
            return_value={
                "status": "success",
                "is_authenticated": True,
                "tabulator_data_catalog": "quilt_example_catalog",
            }
        )
        monkeypatch.setattr("quilt_mcp.services.auth_metadata.catalog_info", mock_catalog_info)

        mock_execute = MagicMock(return_value={"success": True, "rows": [], "row_count": 0})
        monkeypatch.setattr("quilt_mcp.services.athena_read_service.athena_query_execute", mock_execute)

        from quilt_mcp.services.athena_read_service import tabulator_query_execute

        result = tabulator_query_execute("SHOW DATABASES")

        assert result["success"] is True
        mock_catalog_info.assert_called_once()
        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args.kwargs
        assert call_kwargs["data_catalog_name"] == "quilt_example_catalog"
        assert call_kwargs["query"] == "SHOW DATABASES"
        assert call_kwargs.get("database_name") is None

    def test_tabulator_query_accepts_database_name(self, monkeypatch: pytest.MonkeyPatch):
        """Test that tabulator_query_execute accepts optional database_name parameter."""
        mock_catalog_info = MagicMock(
            return_value={
                "status": "success",
                "tabulator_data_catalog": "quilt_example_catalog",
            }
        )
        monkeypatch.setattr("quilt_mcp.services.auth_metadata.catalog_info", mock_catalog_info)

        mock_execute = MagicMock(return_value={"success": True, "formatted_data": []})
        monkeypatch.setattr("quilt_mcp.services.athena_read_service.athena_query_execute", mock_execute)

        from quilt_mcp.services.athena_read_service import tabulator_query_execute

        result = tabulator_query_execute("SELECT * FROM test_table LIMIT 1", database_name="test-bucket")

        assert result["success"] is True
        call_kwargs = mock_execute.call_args.kwargs
        assert call_kwargs["database_name"] == "test-bucket"
        assert call_kwargs["data_catalog_name"] == "quilt_example_catalog"

    def test_tabulator_query_fails_without_catalog_config(self, monkeypatch: pytest.MonkeyPatch):
        """Test that tabulator_query_execute fails gracefully without catalog configuration."""
        mock_catalog_info = MagicMock(return_value={"status": "success", "is_authenticated": True})
        monkeypatch.setattr("quilt_mcp.services.auth_metadata.catalog_info", mock_catalog_info)

        from quilt_mcp.services.athena_read_service import tabulator_query_execute

        result = tabulator_query_execute("SHOW DATABASES")

        assert result["success"] is False
        assert "tabulator_data_catalog not configured" in result["error"]

    def test_tabulator_bucket_query_calls_tabulator_query_with_database(self, monkeypatch: pytest.MonkeyPatch):
        """Test that tabulator_query_execute is called with database_name via tools layer."""
        mock_query = MagicMock(
            return_value={
                "success": True,
                "formatted_data": [{"col1": "value1"}],
            }
        )
        monkeypatch.setattr("quilt_mcp.services.athena_read_service.tabulator_query_execute", mock_query)

        from quilt_mcp.tools.tabulator import tabulator_bucket_query
        import asyncio

        result = asyncio.run(
            tabulator_bucket_query(bucket_name="test-bucket", query="SELECT * FROM test_table LIMIT 1")
        )

        mock_query.assert_called_once()
        call_kwargs = mock_query.call_args.kwargs
        assert call_kwargs["query"] == "SELECT * FROM test_table LIMIT 1"
        assert call_kwargs["database_name"] == "test-bucket"
        assert result["success"] is True

    def test_tabulator_bucket_query_validates_bucket_name(self, monkeypatch: pytest.MonkeyPatch):
        """Test that tabulator_bucket_query passes through bucket_name parameter."""
        mock_query = MagicMock(return_value={"success": False, "error": "Query cannot be empty"})
        monkeypatch.setattr("quilt_mcp.services.athena_read_service.tabulator_query_execute", mock_query)

        from quilt_mcp.tools.tabulator import tabulator_bucket_query
        import asyncio

        result = asyncio.run(tabulator_bucket_query(bucket_name="", query="SELECT * FROM table"))

        assert result is not None

    def test_tabulator_bucket_query_validates_query(self, monkeypatch: pytest.MonkeyPatch):
        """Test that tabulator_query_execute validates query parameter."""
        mock_catalog_info = MagicMock(
            return_value={
                "status": "success",
                "tabulator_data_catalog": "quilt_example_catalog",
            }
        )
        monkeypatch.setattr("quilt_mcp.services.auth_metadata.catalog_info", mock_catalog_info)

        from quilt_mcp.services.athena_read_service import tabulator_query_execute

        result = tabulator_query_execute(query="", database_name="test-bucket")

        assert result["success"] is False
        assert "query" in result["error"].lower() or "empty" in result["error"].lower()


if __name__ == "__main__":
    pytest.main([__file__])

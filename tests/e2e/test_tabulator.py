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


if __name__ == "__main__":
    pytest.main([__file__])

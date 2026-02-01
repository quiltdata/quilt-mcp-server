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
    tabulator_open_query_status,
    tabulator_open_query_toggle,
)
from quilt_mcp.services.tabulator_service import (
    TabulatorService,
    get_tabulator_service,
)


class TestTabulatorService:
    """Test TabulatorService class - DEPRECATED.

    Note: Most table management tests have been deprecated and removed.
    Table operations are now handled by TabulatorMixin in the backend layer.
    Only admin operations (open query) remain in the service.
    """

    def test_service_initialization_without_admin(self):
        """Test service initialization when admin client is not available."""
        with patch("quilt_mcp.services.tabulator_service.ADMIN_AVAILABLE", False):
            service = TabulatorService(use_quilt_auth=True)
            assert service.admin_available is False
            assert service.use_quilt_auth is True

    @patch("quilt_mcp.services.tabulator_service.ADMIN_AVAILABLE", True)
    def test_service_initialization_with_admin(self):
        """Test service initialization with admin client."""
        service = TabulatorService(use_quilt_auth=True)
        assert service.admin_available is True
        assert service.use_quilt_auth is True

    def test_service_open_query_methods_no_admin_available(self):
        """Test open query methods when admin not available."""
        service = TabulatorService(use_quilt_auth=False)

        result = service.get_open_query_status()
        assert result["success"] is False
        assert "Admin functionality not available" in result["error"]

        result = service.set_open_query(True)
        assert result["success"] is False
        assert "Admin functionality not available" in result["error"]


class TestGetTabulatorService:
    """Test get_tabulator_service utility function."""

    def test_get_tabulator_service(self):
        """Test get_tabulator_service returns TabulatorService instance."""
        service = get_tabulator_service()
        assert isinstance(service, TabulatorService)
        assert service.use_quilt_auth is True


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
            "__typename": "BucketSetTabulatorTableSuccess",
            "bucketConfig": {"name": "test-bucket"}
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

        mock_backend.delete_tabulator_table.return_value = {
            "__typename": "BucketSetTabulatorTableSuccess"
        }

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

        mock_backend.rename_tabulator_table.return_value = {
            "__typename": "BucketSetTabulatorTableSuccess"
        }

        result = await tabulator_table_rename("test-bucket", "old_table", "new_table")

        assert result["success"] is True
        assert result["old_table_name"] == "old_table"
        assert result["new_table_name"] == "new_table"
        mock_backend.rename_tabulator_table.assert_called_once_with(
            "test-bucket", "old_table", "new_table"
        )

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
    """Test tabulator open query functions."""

    @patch("quilt_mcp.services.tabulator_service.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_open_query_status(self, mock_get_service):
        """Test getting open query status."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        mock_service.get_open_query_status.return_value = {
            "success": True,
            "open_query_enabled": True,
        }

        result = await tabulator_open_query_status()

        assert result["success"] is True
        assert result["open_query_enabled"] is True
        mock_service.get_open_query_status.assert_called_once()

    @patch("quilt_mcp.services.tabulator_service.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_open_query_toggle(self, mock_get_service):
        """Test toggling open query status."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        mock_service.set_open_query.return_value = {
            "success": True,
            "open_query_enabled": False,
            "message": "Open query disabled",
        }

        result = await tabulator_open_query_toggle(False)

        assert result["success"] is True
        assert result["open_query_enabled"] is False
        assert "disabled" in result["message"]
        mock_service.set_open_query.assert_called_once_with(False)

    @patch("quilt_mcp.services.tabulator_service.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_open_query_status_error_handling(self, mock_get_service):
        """Test open query status error handling."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.get_open_query_status.side_effect = Exception("Status check failed")

        result = await tabulator_open_query_status()

        assert result["success"] is False
        assert "Status check failed" in result["error"]

    @patch("quilt_mcp.services.tabulator_service.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_open_query_toggle_error_handling(self, mock_get_service):
        """Test open query toggle error handling."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.set_open_query.side_effect = Exception("Toggle failed")

        result = await tabulator_open_query_toggle(True)

        assert result["success"] is False
        assert "Toggle failed" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__])

"""Tests for QuiltService tabulator administration methods.

This module tests the tabulator administration methods in QuiltService,
following Phase 3.3 of the orchestration plan.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Any

from quilt_mcp.services.quilt_service import QuiltService
from quilt_mcp.services.exceptions import BucketNotFoundError


class TestTabulatorAccessMethods:
    """Test tabulator access management methods."""

    def test_get_tabulator_access_returns_bool(self):
        """Test get_tabulator_access returns boolean value."""
        service = QuiltService()

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            mock_admin.return_value.get_open_query.return_value = True

            result = service.get_tabulator_access()

            assert isinstance(result, bool)
            assert result is True
            mock_admin.return_value.get_open_query.assert_called_once()

    def test_get_tabulator_access_returns_false(self):
        """Test get_tabulator_access can return False."""
        service = QuiltService()

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            mock_admin.return_value.get_open_query.return_value = False

            result = service.get_tabulator_access()

            assert isinstance(result, bool)
            assert result is False

    def test_set_tabulator_access_enables(self):
        """Test set_tabulator_access enables tabulator access."""
        service = QuiltService()

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            mock_admin.return_value.set_open_query.return_value = None

            result = service.set_tabulator_access(True)

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert result["enabled"] is True
            mock_admin.return_value.set_open_query.assert_called_once_with(True)

    def test_set_tabulator_access_disables(self):
        """Test set_tabulator_access disables tabulator access."""
        service = QuiltService()

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            mock_admin.return_value.set_open_query.return_value = None

            result = service.set_tabulator_access(False)

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert result["enabled"] is False
            mock_admin.return_value.set_open_query.assert_called_once_with(False)


class TestTabulatorTableListing:
    """Test tabulator table listing methods."""

    def test_list_tabulator_tables_returns_list(self):
        """Test list_tabulator_tables returns typed list of dicts."""
        service = QuiltService()

        mock_table = Mock()
        mock_table.name = "test_table"
        mock_table.config = "schema:\n  - name: col1\n    type: STRING"

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            mock_admin.return_value.list_tables.return_value = [mock_table]

            result = service.list_tabulator_tables("test-bucket")

            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], dict)
            assert result[0]["name"] == "test_table"
            assert "config" in result[0]
            mock_admin.return_value.list_tables.assert_called_once_with("test-bucket")

    def test_list_tabulator_tables_empty_bucket(self):
        """Test list_tabulator_tables returns empty list for bucket with no tables."""
        service = QuiltService()

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            mock_admin.return_value.list_tables.return_value = []

            result = service.list_tabulator_tables("empty-bucket")

            assert isinstance(result, list)
            assert len(result) == 0

    def test_list_tabulator_tables_raises_bucket_not_found(self):
        """Test list_tabulator_tables raises BucketNotFoundError when bucket doesn't exist."""
        service = QuiltService()

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            # Create a mock exception that looks like quilt3.admin.exceptions.BucketNotFoundError
            class MockBucketNotFoundError(Exception):
                pass

            # Mock the _get_admin_exceptions to return our mock class
            with patch.object(service, '_get_admin_exceptions') as mock_exceptions:
                mock_exceptions.return_value = {
                    'Quilt3AdminError': Exception,
                    'UserNotFoundError': Exception,
                    'BucketNotFoundError': MockBucketNotFoundError,
                }

                mock_admin.return_value.list_tables.side_effect = MockBucketNotFoundError("Bucket not found")

                with pytest.raises(BucketNotFoundError, match="Bucket 'nonexistent-bucket' not found"):
                    service.list_tabulator_tables("nonexistent-bucket")


class TestTabulatorTableCreation:
    """Test tabulator table creation methods."""

    def test_create_tabulator_table_success(self):
        """Test create_tabulator_table creates a table successfully."""
        service = QuiltService()

        config = {
            "schema": [{"name": "col1", "type": "STRING"}],
            "source": {"package_pattern": ".*", "logical_key_pattern": ".*\\.csv$"},
            "parser": {"format": "csv"},
        }

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            mock_admin.return_value.set_table.return_value = Mock(__typename="OK")

            result = service.create_tabulator_table("test-bucket", "new_table", config)

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert result["table_name"] == "new_table"
            assert result["bucket_name"] == "test-bucket"
            mock_admin.return_value.set_table.assert_called_once()

    def test_create_tabulator_table_with_yaml_config(self):
        """Test create_tabulator_table accepts YAML string config."""
        service = QuiltService()

        yaml_config = """
schema:
  - name: col1
    type: STRING
source:
  package_pattern: ".*"
  logical_key_pattern: ".*\\.csv$"
parser:
  format: csv
"""

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            mock_admin.return_value.set_table.return_value = Mock(__typename="OK")

            result = service.create_tabulator_table("test-bucket", "new_table", yaml_config)

            assert result["status"] == "success"
            assert result["table_name"] == "new_table"

    def test_create_tabulator_table_raises_bucket_not_found(self):
        """Test create_tabulator_table raises BucketNotFoundError when bucket doesn't exist."""
        service = QuiltService()

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            # Create a mock exception that looks like quilt3.admin.exceptions.BucketNotFoundError
            class MockBucketNotFoundError(Exception):
                pass

            # Mock the _get_admin_exceptions to return our mock class
            with patch.object(service, '_get_admin_exceptions') as mock_exceptions:
                mock_exceptions.return_value = {
                    'Quilt3AdminError': Exception,
                    'UserNotFoundError': Exception,
                    'BucketNotFoundError': MockBucketNotFoundError,
                }

                mock_admin.return_value.set_table.side_effect = MockBucketNotFoundError("Bucket not found")

                with pytest.raises(BucketNotFoundError, match="Bucket 'nonexistent-bucket' not found"):
                    service.create_tabulator_table("nonexistent-bucket", "table", {})


class TestTabulatorTableDeletion:
    """Test tabulator table deletion methods."""

    def test_delete_tabulator_table_success(self):
        """Test delete_tabulator_table deletes a table successfully."""
        service = QuiltService()

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            mock_admin.return_value.set_table.return_value = Mock(__typename="OK")

            service.delete_tabulator_table("test-bucket", "old_table")

            # Should call set_table with config=None to delete
            mock_admin.return_value.set_table.assert_called_once_with(
                bucket_name="test-bucket", table_name="old_table", config=None
            )

    def test_delete_tabulator_table_raises_bucket_not_found(self):
        """Test delete_tabulator_table raises BucketNotFoundError when bucket doesn't exist."""
        service = QuiltService()

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            # Create a mock exception that looks like quilt3.admin.exceptions.BucketNotFoundError
            class MockBucketNotFoundError(Exception):
                pass

            # Mock the _get_admin_exceptions to return our mock class
            with patch.object(service, '_get_admin_exceptions') as mock_exceptions:
                mock_exceptions.return_value = {
                    'Quilt3AdminError': Exception,
                    'UserNotFoundError': Exception,
                    'BucketNotFoundError': MockBucketNotFoundError,
                }

                mock_admin.return_value.set_table.side_effect = MockBucketNotFoundError("Bucket not found")

                with pytest.raises(BucketNotFoundError, match="Bucket 'nonexistent-bucket' not found"):
                    service.delete_tabulator_table("nonexistent-bucket", "table")


class TestTabulatorTableRename:
    """Test tabulator table rename methods."""

    def test_rename_tabulator_table_success(self):
        """Test rename_tabulator_table renames a table successfully."""
        service = QuiltService()

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            mock_admin.return_value.rename_table.return_value = Mock(__typename="OK")

            result = service.rename_tabulator_table("test-bucket", "old_name", "new_name")

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert result["old_name"] == "old_name"
            assert result["new_name"] == "new_name"
            assert result["bucket_name"] == "test-bucket"
            mock_admin.return_value.rename_table.assert_called_once_with(
                bucket_name="test-bucket", table_name="old_name", new_table_name="new_name"
            )

    def test_rename_tabulator_table_raises_bucket_not_found(self):
        """Test rename_tabulator_table raises BucketNotFoundError when bucket doesn't exist."""
        service = QuiltService()

        with patch.object(service, '_get_tabulator_admin_module') as mock_admin:
            # Create a mock exception that looks like quilt3.admin.exceptions.BucketNotFoundError
            class MockBucketNotFoundError(Exception):
                pass

            # Mock the _get_admin_exceptions to return our mock class
            with patch.object(service, '_get_admin_exceptions') as mock_exceptions:
                mock_exceptions.return_value = {
                    'Quilt3AdminError': Exception,
                    'UserNotFoundError': Exception,
                    'BucketNotFoundError': MockBucketNotFoundError,
                }

                mock_admin.return_value.rename_table.side_effect = MockBucketNotFoundError("Bucket not found")

                with pytest.raises(BucketNotFoundError, match="Bucket 'nonexistent-bucket' not found"):
                    service.rename_tabulator_table("nonexistent-bucket", "old", "new")


class TestTabulatorAdminModule:
    """Test _get_tabulator_admin_module helper."""

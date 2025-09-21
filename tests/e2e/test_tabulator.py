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
    TabulatorService,
    get_tabulator_service,
)


class TestTabulatorService:
    """Test TabulatorService class."""

    def test_service_initialization_without_admin(self):
        """Test service initialization when admin client is not available."""
        with patch("quilt_mcp.tools.tabulator.ADMIN_AVAILABLE", False):
            service = TabulatorService(use_quilt_auth=True)
            assert service.admin_available is False
            assert service.use_quilt_auth is True

    @patch("quilt_mcp.tools.tabulator.ADMIN_AVAILABLE", True)
    def test_service_initialization_with_admin(self):
        """Test service initialization with admin client."""
        service = TabulatorService(use_quilt_auth=True)
        assert service.admin_available is True
        assert service.use_quilt_auth is True

    def test_validate_schema_valid(self):
        """Test schema validation with valid schema."""
        service = TabulatorService(use_quilt_auth=False)
        schema = [
            {"name": "col1", "type": "STRING"},
            {"name": "col2", "type": "INT"},
            {"name": "col3", "type": "FLOAT"},
        ]

        errors = service._validate_schema(schema)
        assert errors == []

    def test_validate_schema_invalid(self):
        """Test schema validation with invalid schema."""
        service = TabulatorService(use_quilt_auth=False)

        # Empty schema
        errors = service._validate_schema([])
        assert len(errors) == 1
        assert "Schema cannot be empty" in errors[0]

        # Missing fields
        schema = [
            {"name": "col1"},  # Missing type
            {"type": "INT"},  # Missing name
            {"name": "col3", "type": "INVALID_TYPE"},  # Invalid type
        ]

        errors = service._validate_schema(schema)
        assert len(errors) == 3
        assert any("missing 'type' field" in error for error in errors)
        assert any("missing 'name' field" in error for error in errors)
        assert any("Invalid type 'INVALID_TYPE'" in error for error in errors)

    def test_validate_patterns_valid(self):
        """Test pattern validation with valid patterns."""
        service = TabulatorService(use_quilt_auth=False)

        package_pattern = r"^bucket/(?P<date>\d{4}-\d{2}-\d{2})/package$"
        logical_key_pattern = r"data/(?P<sample>[^/]+)\.csv$"

        errors = service._validate_patterns(package_pattern, logical_key_pattern)
        assert errors == []

    def test_validate_patterns_invalid(self):
        """Test pattern validation with invalid patterns."""
        service = TabulatorService(use_quilt_auth=False)

        # Invalid regex patterns
        package_pattern = r"^bucket/(?P<date>\d{4-\d{2-\d{2})/package$[unclosed"  # Invalid regex - unclosed bracket
        logical_key_pattern = ""  # Empty pattern

        errors = service._validate_patterns(package_pattern, logical_key_pattern)
        assert len(errors) == 2
        assert any("Invalid package pattern" in error for error in errors)
        assert any("Logical key pattern cannot be empty" in error for error in errors)

    def test_validate_parser_config_valid(self):
        """Test parser config validation with valid config."""
        service = TabulatorService(use_quilt_auth=False)

        # CSV config
        csv_config = {"format": "csv", "delimiter": ",", "header": True}
        errors = service._validate_parser_config(csv_config)
        assert errors == []

        # Parquet config
        parquet_config = {"format": "parquet"}
        errors = service._validate_parser_config(parquet_config)
        assert errors == []

    def test_validate_parser_config_invalid(self):
        """Test parser config validation with invalid config."""
        service = TabulatorService(use_quilt_auth=False)

        # Empty config
        errors = service._validate_parser_config({})
        assert len(errors) == 1
        assert "Parser configuration cannot be empty" in errors[0]

        # Invalid format
        invalid_config = {"format": "xml"}
        errors = service._validate_parser_config(invalid_config)
        assert len(errors) == 1
        assert "Invalid format 'xml'" in errors[0]

    def test_validate_parser_config_edge_cases(self):
        """Test parser config validation edge cases."""
        service = TabulatorService(use_quilt_auth=False)

        # Test Parquet format (should be valid)
        parquet_config = {"format": "parquet"}
        errors = service._validate_parser_config(parquet_config)
        assert errors == []

        # Test TSV format (should be valid)
        tsv_config = {"format": "tsv", "delimiter": "\t"}
        errors = service._validate_parser_config(tsv_config)
        assert errors == []

        # Test JSON format (should be invalid)
        json_config = {"format": "json"}
        errors = service._validate_parser_config(json_config)
        assert len(errors) == 1
        assert "Invalid format 'json'" in errors[0]

    def test_validate_schema_edge_cases(self):
        """Test schema validation edge cases."""
        service = TabulatorService(use_quilt_auth=False)

        # Test all valid column types
        valid_types = ["STRING", "INT", "FLOAT", "BOOLEAN", "TIMESTAMP"]
        for col_type in valid_types:
            schema = [{"name": "test_col", "type": col_type}]
            errors = service._validate_schema(schema)
            assert errors == [], f"Type {col_type} should be valid"

        # Test invalid type
        invalid_schema = [{"name": "test_col", "type": "DATE"}]
        errors = service._validate_schema(invalid_schema)
        assert len(errors) == 1
        assert "Invalid type 'DATE'" in errors[0]

        # Test schema with multiple columns
        large_schema = [{"name": f"col_{i}", "type": "STRING"} for i in range(10)]
        errors = service._validate_schema(large_schema)
        assert errors == []

    def test_validate_patterns_edge_cases(self):
        """Test pattern validation edge cases."""
        service = TabulatorService(use_quilt_auth=False)

        # Test complex but valid patterns
        complex_package = r"^bucket/(?P<year>\d{4})/(?P<month>\d{2})/package$"
        complex_key = r"data/(?P<category>[^/]+)/(?P<file>[^/]+\.(csv|tsv|json))$"

        errors = service._validate_patterns(complex_package, complex_key)
        assert errors == []

        # Test escaped patterns
        escaped_pattern = r"^bucket/package\[test\]$"
        errors = service._validate_patterns(escaped_pattern, "data/.*.csv$")
        assert errors == []

    def test_build_tabulator_config(self):
        """Test YAML configuration building."""
        service = TabulatorService(use_quilt_auth=False)

        schema = [{"name": "col1", "type": "STRING"}]
        package_pattern = "^bucket/package$"
        logical_key_pattern = "data/*.csv$"
        parser_config = {"format": "csv", "delimiter": ",", "header": True}

        config_yaml = service._build_tabulator_config(schema, package_pattern, logical_key_pattern, parser_config)

        # Basic checks that YAML is generated
        assert "schema:" in config_yaml
        assert "source:" in config_yaml
        assert "parser:" in config_yaml
        assert "quilt-packages" in config_yaml

    # Add tests for service methods without mocking AWS responses
    def test_service_methods_no_admin_available(self):
        """Test all service methods when admin not available."""
        service = TabulatorService(use_quilt_auth=False)

        # Test all methods return appropriate error when admin not available
        result = service.list_tables("test-bucket")
        assert result["success"] is False
        assert "Admin functionality not available" in result["error"]

        result = service.create_table("bucket", "table", [], "pattern", "pattern", {})
        assert result["success"] is False
        assert "Admin functionality not available" in result["error"]

        result = service.delete_table("bucket", "table")
        assert result["success"] is False
        assert "Admin functionality not available" in result["error"]

        result = service.rename_table("bucket", "old", "new")
        assert result["success"] is False
        assert "Admin functionality not available" in result["error"]

        result = service.get_open_query_status()
        assert result["success"] is False
        assert "Admin functionality not available" in result["error"]

        result = service.set_open_query(True)
        assert result["success"] is False
        assert "Admin functionality not available" in result["error"]

    @patch("quilt_mcp.tools.tabulator.ADMIN_AVAILABLE", True)
    def test_create_table_validation_errors(self):
        """Test TabulatorService.create_table with validation errors."""
        service = TabulatorService(use_quilt_auth=True)

        # Empty inputs should trigger validation errors
        result = service.create_table("", "", [], "", "", {})

        assert result["success"] is False
        assert "Validation errors" in result["error"]


class TestGetTabulatorService:
    """Test get_tabulator_service utility function."""

    def test_get_tabulator_service(self):
        """Test get_tabulator_service returns TabulatorService instance."""
        service = get_tabulator_service()
        assert isinstance(service, TabulatorService)
        assert service.use_quilt_auth is True


class TestTabulatorTablesList:
    """Test tabulator_tables_list function."""

    @patch("quilt_mcp.tools.tabulator.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_list_tables_success(self, mock_get_service):
        """Test successful table listing."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        mock_service.list_tables.return_value = {
            "success": True,
            "tables": [
                {
                    "name": "test_table",
                    "config_yaml": "schema:\n- name: col1\n  type: STRING\n",
                    "schema": [{"name": "col1", "type": "STRING"}],
                    "column_count": 1,
                }
            ],
            "bucket_name": "test-bucket",
            "count": 1,
        }

        result = await tabulator_tables_list("test-bucket")

        assert result["success"] is True
        assert len(result["tables"]) == 1
        assert result["tables"][0]["name"] == "test_table"
        assert result["bucket_name"] == "test-bucket"
        mock_service.list_tables.assert_called_once_with("test-bucket")

    @patch("quilt_mcp.tools.tabulator.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_list_tables_error(self, mock_get_service):
        """Test table listing error handling."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.list_tables.side_effect = Exception("Connection failed")

        result = await tabulator_tables_list("test-bucket")

        assert result["success"] is False
        assert "Connection failed" in result["error"]


class TestTabulatorTableCreate:
    """Test tabulator_table_create function."""

    @patch("quilt_mcp.tools.tabulator.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_create_table_success(self, mock_get_service):
        """Test successful table creation."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        mock_service.create_table.return_value = {
            "success": True,
            "table_name": "test_table",
            "bucket_name": "test-bucket",
            "message": "Tabulator table 'test_table' created successfully",
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
        mock_service.create_table.assert_called_once()

    @patch("quilt_mcp.tools.tabulator.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_create_table_with_parser_options(self, mock_get_service):
        """Test table creation with custom parser options."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.create_table.return_value = {"success": True}

        schema = [{"name": "col1", "type": "STRING"}]
        await tabulator_table_create(
            bucket_name="test-bucket",
            table_name="test_table",
            schema=schema,
            package_pattern="^test-bucket/package$",
            logical_key_pattern="data/*.tsv$",
            parser_format="tsv",
            parser_delimiter="\t",
            parser_header=False,
            parser_skip_rows=1,
        )

        # Verify parser config was built correctly
        call_args = mock_service.create_table.call_args
        parser_config = call_args.kwargs["parser_config"]
        assert parser_config["format"] == "tsv"
        assert parser_config["delimiter"] == "\t"
        assert parser_config["header"] is False
        assert parser_config["skip_rows"] == 1

    @patch("quilt_mcp.tools.tabulator.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_create_table_error_handling(self, mock_get_service):
        """Test table creation error handling."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.create_table.side_effect = Exception("Unexpected error")

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

    @patch("quilt_mcp.tools.tabulator.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_delete_table_success(self, mock_get_service):
        """Test successful table deletion."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        mock_service.delete_table.return_value = {
            "success": True,
            "table_name": "test_table",
            "bucket_name": "test-bucket",
            "message": "Tabulator table 'test_table' deleted successfully",
        }

        result = await tabulator_table_delete("test-bucket", "test_table")

        assert result["success"] is True
        assert result["table_name"] == "test_table"
        mock_service.delete_table.assert_called_once_with("test-bucket", "test_table")

    @patch("quilt_mcp.tools.tabulator.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_delete_table_error_handling(self, mock_get_service):
        """Test table deletion error handling."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.delete_table.side_effect = Exception("Delete failed")

        result = await tabulator_table_delete("test-bucket", "test_table")

        assert result["success"] is False
        assert "Delete failed" in result["error"]


class TestTabulatorTableRename:
    """Test tabulator_table_rename function."""

    @patch("quilt_mcp.tools.tabulator.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_rename_table_success(self, mock_get_service):
        """Test successful table rename."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        mock_service.rename_table.return_value = {
            "success": True,
            "old_table_name": "old_table",
            "new_table_name": "new_table",
            "bucket_name": "test-bucket",
        }

        result = await tabulator_table_rename("test-bucket", "old_table", "new_table")

        assert result["success"] is True
        assert result["old_table_name"] == "old_table"
        assert result["new_table_name"] == "new_table"
        mock_service.rename_table.assert_called_once_with("test-bucket", "old_table", "new_table")

    @patch("quilt_mcp.tools.tabulator.get_tabulator_service")
    @pytest.mark.asyncio
    async def test_rename_table_error_handling(self, mock_get_service):
        """Test table rename error handling."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.rename_table.side_effect = Exception("Rename failed")

        result = await tabulator_table_rename("test-bucket", "old_table", "new_table")

        assert result["success"] is False
        assert "Rename failed" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__])

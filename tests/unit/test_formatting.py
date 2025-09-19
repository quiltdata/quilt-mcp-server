"""Tests for the formatting module."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch

from quilt_mcp.formatting import (
    format_as_table,
    should_use_table_format,
    enhance_result_with_table_format,
    format_athena_results_as_table,
    format_tabulator_results_as_table,
)


class TestFormatAsTable:
    """Test cases for the format_as_table function."""

    def test_format_dataframe(self):
        """Test formatting a pandas DataFrame."""
        df = pd.DataFrame(
            [
                {"package": "test/package1", "size_mb": 10.5, "files": 25},
                {"package": "test/package2", "size_mb": 5.2, "files": 12},
            ]
        )

        result = format_as_table(df)

        assert isinstance(result, str)
        assert "package" in result
        assert "size_mb" in result
        assert "files" in result
        assert "test/package1" in result
        assert "10.5" in result
        assert "25" in result

    def test_format_list_of_dicts(self):
        """Test formatting a list of dictionaries."""
        data = [
            {"name": "workgroup1", "state": "ENABLED", "accessible": True},
            {"name": "workgroup2", "state": "DISABLED", "accessible": False},
        ]

        result = format_as_table(data)

        assert isinstance(result, str)
        assert "name" in result
        assert "state" in result
        assert "accessible" in result
        assert "workgroup1" in result
        assert "ENABLED" in result

    def test_format_single_dict(self):
        """Test formatting a single dictionary."""
        data = {"database": "test_db", "tables": 5, "accessible": True}

        result = format_as_table(data)

        assert isinstance(result, str)
        assert "database" in result
        assert "test_db" in result

    def test_format_empty_data(self):
        """Test formatting empty data."""
        result = format_as_table([])
        # Empty list gets converted to string representation
        assert result == "[]"

        result = format_as_table(pd.DataFrame())
        assert result == "No data to display"

    def test_format_with_max_rows(self):
        """Test formatting with row limit."""
        data = [{"id": i, "value": f"value_{i}"} for i in range(10)]

        result = format_as_table(data, max_rows=3)

        assert isinstance(result, str)
        assert "value_0" in result
        assert "value_1" in result
        assert "value_2" in result
        assert "(7 more rows)" in result

    def test_format_invalid_data(self):
        """Test formatting invalid data types."""
        result = format_as_table("not a table")
        assert result == "not a table"

        result = format_as_table(123)
        assert result == "123"

    def test_format_error_handling(self):
        """Test error handling in table formatting."""
        # Mock pandas to raise an exception
        with patch("quilt_mcp.formatting.pd.DataFrame") as mock_df:
            mock_df.side_effect = Exception("Test error")

            result = format_as_table([{"test": "data"}])
            assert "Error formatting table" in result


class TestShouldUseTableFormat:
    """Test cases for the should_use_table_format function."""

    def test_explicit_table_format(self):
        """Test explicit table format request."""
        data = [{"a": 1}]
        assert should_use_table_format(data, output_format="table") is True

    def test_explicit_non_table_format(self):
        """Test explicit non-table format request."""
        data = [{"a": 1}, {"a": 2}]
        assert should_use_table_format(data, output_format="json") is False

    def test_auto_detection_dataframe(self):
        """Test auto-detection with DataFrame."""
        df = pd.DataFrame([{"col1": "a", "col2": "b"}, {"col1": "c", "col2": "d"}])
        assert should_use_table_format(df, output_format="auto") is True

    def test_auto_detection_list_of_dicts(self):
        """Test auto-detection with list of dictionaries."""
        # Good case: multiple rows, consistent structure
        data = [{"name": "item1", "value": 10}, {"name": "item2", "value": 20}]
        assert should_use_table_format(data, output_format="auto") is True

    def test_auto_detection_insufficient_rows(self):
        """Test auto-detection with insufficient rows."""
        data = [{"name": "item1", "value": 10}]  # Only 1 row
        assert should_use_table_format(data, output_format="auto", min_rows=2) is False

    def test_auto_detection_too_many_columns(self):
        """Test auto-detection with too many columns."""
        data = [{f"col_{i}": f"value_{i}" for i in range(25)}] * 3  # 25 columns
        assert should_use_table_format(data, output_format="auto", max_cols=20) is False

    def test_auto_detection_inconsistent_structure(self):
        """Test auto-detection with inconsistent dictionary structure."""
        data = [
            {"name": "item1", "value": 10},
            {"name": "item2", "different_key": 20},  # Different keys
        ]
        assert should_use_table_format(data, output_format="auto") is False

    def test_auto_detection_non_tabular_data(self):
        """Test auto-detection with non-tabular data."""
        assert should_use_table_format("string", output_format="auto") is False
        assert should_use_table_format(123, output_format="auto") is False
        assert should_use_table_format([], output_format="auto") is False


class TestEnhanceResultWithTableFormat:
    """Test cases for the enhance_result_with_table_format function."""

    def test_enhance_successful_result(self):
        """Test enhancing a successful result with tabular data."""
        result = {
            "success": True,
            "formatted_data": [
                {"name": "item1", "value": 10},
                {"name": "item2", "value": 20},
            ],
        }

        enhanced = enhance_result_with_table_format(result)

        assert enhanced["success"] is True
        assert "formatted_data_table" in enhanced
        assert "display_format" in enhanced
        assert enhanced["display_format"] == "table"

    def test_enhance_failed_result(self):
        """Test enhancing a failed result."""
        result = {"success": False, "error": "Test error"}

        enhanced = enhance_result_with_table_format(result)

        assert enhanced == result  # Should be unchanged

    def test_enhance_result_with_csv_data(self):
        """Test enhancing result with CSV data (should skip)."""
        result = {"success": True, "formatted_data": "name,value\nitem1,10\nitem2,20"}

        enhanced = enhance_result_with_table_format(result)

        # Should not add table format for CSV strings
        assert "formatted_data_table" not in enhanced

    def test_enhance_multiple_fields(self):
        """Test enhancing result with multiple tabular fields."""
        result = {
            "success": True,
            "results": [{"a": 1}, {"a": 2}],
            "tables": [{"name": "table1"}, {"name": "table2"}],
        }

        enhanced = enhance_result_with_table_format(result)

        assert "results_table" in enhanced
        assert "tables_table" in enhanced


class TestFormatAthenaResultsAsTable:
    """Test cases for the format_athena_results_as_table function."""

    def test_format_athena_csv_results(self):
        """Test formatting Athena CSV results as table."""
        result = {
            "success": True,
            "formatted_data": "package,size_mb,files\ntest/pkg1,10.5,25\ntest/pkg2,5.2,12",
            "format": "csv",
        }

        enhanced = format_athena_results_as_table(result)

        assert enhanced["success"] is True
        assert "formatted_data_table" in enhanced
        assert "display_format" in enhanced
        assert enhanced["display_format"] == "table"
        assert "test/pkg1" in enhanced["formatted_data_table"]

    def test_format_athena_json_results(self):
        """Test formatting Athena JSON results as table."""
        result = {
            "success": True,
            "formatted_data": [
                {"package": "test/pkg1", "size_mb": 10.5},
                {"package": "test/pkg2", "size_mb": 5.2},
            ],
            "format": "json",
        }

        enhanced = format_athena_results_as_table(result)

        assert enhanced["success"] is True
        assert "formatted_data_table" in enhanced
        assert "display_format" in enhanced

    def test_format_athena_failed_result(self):
        """Test formatting failed Athena result."""
        result = {"success": False, "error": "Query failed"}

        enhanced = format_athena_results_as_table(result)

        assert enhanced == result  # Should be unchanged

    def test_format_athena_csv_parse_error(self):
        """Test handling CSV parse errors."""
        result = {
            "success": True,
            "formatted_data": "invalid,csv\ndata",  # Malformed CSV
            "format": "csv",
        }

        with patch("quilt_mcp.formatting.pd.read_csv") as mock_read_csv:
            mock_read_csv.side_effect = Exception("Parse error")

            enhanced = format_athena_results_as_table(result)

            # Should not crash, just not add table format
            assert enhanced["success"] is True
            assert "formatted_data_table" not in enhanced


class TestFormatTabulatorResultsAsTable:
    """Test cases for the format_tabulator_results_as_table function."""

    def test_format_tabulator_tables_list(self):
        """Test formatting tabulator tables list as table."""
        result = {
            "success": True,
            "tables": [
                {"name": "table1", "column_count": 5, "bucket_name": "test-bucket"},
                {"name": "table2", "column_count": 3, "bucket_name": "test-bucket"},
            ],
        }

        enhanced = format_tabulator_results_as_table(result)

        assert enhanced["success"] is True
        assert "tables_table" in enhanced
        assert "display_format" in enhanced
        assert enhanced["display_format"] == "table"

    def test_format_tabulator_failed_result(self):
        """Test formatting failed tabulator result."""
        result = {"success": False, "error": "Tabulator error"}

        enhanced = format_tabulator_results_as_table(result)

        assert enhanced == result  # Should be unchanged

    def test_format_tabulator_empty_tables(self):
        """Test formatting empty tabulator tables list."""
        result = {"success": True, "tables": []}

        enhanced = format_tabulator_results_as_table(result)

        # Should not add table format for empty list
        assert "tables_table" not in enhanced

    def test_format_tabulator_non_tabular_tables(self):
        """Test formatting non-tabular tables data."""
        result = {"success": True, "tables": "not a list"}

        enhanced = format_tabulator_results_as_table(result)

        # Should not add table format for non-list data
        assert "tables_table" not in enhanced


class TestIntegrationWithAthenaService:
    """Integration tests with AthenaQueryService."""

    @patch("quilt_mcp.formatting.logger")
    def test_athena_service_table_format_integration(self, mock_logger):
        """Test integration with AthenaQueryService format_results method."""
        from quilt_mcp.aws.athena_service import AthenaQueryService

        service = AthenaQueryService()

        # Create test DataFrame
        df = pd.DataFrame(
            [
                {"query_id": "123", "status": "SUCCEEDED", "duration_ms": 1500},
                {"query_id": "456", "status": "FAILED", "duration_ms": 500},
            ]
        )

        result_data = {"success": True, "data": df}

        # Test table format
        formatted = service.format_results(result_data, "table")

        assert formatted["success"] is True
        assert formatted["format"] == "table"
        assert isinstance(formatted["formatted_data"], str)
        assert "query_id" in formatted["formatted_data"]
        assert "SUCCEEDED" in formatted["formatted_data"]

    def test_athena_service_auto_table_detection(self):
        """Test auto table detection in AthenaQueryService."""
        from quilt_mcp.aws.athena_service import AthenaQueryService

        service = AthenaQueryService()

        # Create test DataFrame that should trigger table formatting
        df = pd.DataFrame(
            [
                {"database": "db1", "table_count": 5},
                {"database": "db2", "table_count": 3},
            ]
        )

        result_data = {"success": True, "data": df}

        # Test JSON format with auto table detection
        formatted = service.format_results(result_data, "json")

        assert formatted["success"] is True
        assert formatted["format"] == "json"
        assert "formatted_data_table" in formatted
        assert formatted["display_format"] == "table"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_format_table_with_none_values(self):
        """Test formatting table with None values."""
        data = [{"name": "item1", "value": None}, {"name": None, "value": 20}]

        result = format_as_table(data)

        assert isinstance(result, str)
        assert "item1" in result

    def test_format_table_with_mixed_types(self):
        """Test formatting table with mixed data types."""
        data = [
            {"name": "item1", "value": 10, "active": True},
            {"name": "item2", "value": 20.5, "active": False},
        ]

        result = format_as_table(data)

        assert isinstance(result, str)
        assert "True" in result
        assert "False" in result

    def test_format_table_with_long_strings(self):
        """Test formatting table with very long strings."""
        data = [
            {"name": "item1", "description": "A" * 100},
            {"name": "item2", "description": "B" * 100},
        ]

        result = format_as_table(data)

        assert isinstance(result, str)
        # Should handle long strings gracefully
        assert len(result) > 0

    def test_should_use_table_format_error_handling(self):
        """Test error handling in should_use_table_format."""
        # Create data that might cause errors
        problematic_data = Mock()
        problematic_data.__len__ = Mock(side_effect=Exception("Test error"))

        result = should_use_table_format(problematic_data, output_format="auto")

        # Should return False on error, not crash
        assert result is False
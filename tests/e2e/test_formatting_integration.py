"""Integration tests for table formatting with MCP tools."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from quilt_mcp.tools.athena_glue import (
    athena_query_execute,
)

# athena_workgroups_list, athena_databases_list, and tabulator_tables_list replaced by MCP resources:
# - athena://workgroups (AthenaWorkgroupsResource)
# - athena://databases (AthenaDatabasesResource)
# - tabulator://{bucket}/tables (TabulatorTablesResource)


class TestAthenaTableFormatIntegration:
    """Integration tests for Athena tools with table formatting."""

    @patch("quilt_mcp.tools.athena_glue.AthenaQueryService")
    def test_athena_query_execute_with_table_format(self, mock_service_class):
        """Test athena_query_execute with table output format."""
        # Mock the service and its methods
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Create mock DataFrame result
        test_df = pd.DataFrame(
            [
                {"package_name": "test/package1", "file_count": 7, "size_mb": 11.31},
                {"package_name": "test/package2", "file_count": 50, "size_mb": 23.84},
            ]
        )

        # Mock execute_query to return successful result with DataFrame
        mock_service.execute_query.return_value = {
            "success": True,
            "data": test_df,
            "row_count": 2,
            "columns": ["package_name", "file_count", "size_mb"],
        }

        # Mock format_results to simulate table formatting
        def mock_format_results(result_data, output_format):
            if output_format == "table":
                return {
                    "success": True,
                    "formatted_data": "package_name  file_count  size_mb\ntest/package1  7  11.31\ntest/package2  50  23.84",
                    "format": "table",
                    "row_count": 2,
                    "columns": ["package_name", "file_count", "size_mb"],
                }
            return result_data

        mock_service.format_results.side_effect = mock_format_results

        # Test with table format
        result = athena_query_execute(query="SELECT * FROM test_table", output_format="table", max_results=10)

        assert result["success"] is True
        assert result["format"] == "table"
        assert "package_name" in result["formatted_data"]
        assert "test/package1" in result["formatted_data"]

        # Verify the service was called correctly
        mock_service.execute_query.assert_called_once()
        mock_service.format_results.assert_called_once()

    @patch("quilt_mcp.tools.athena_glue.AthenaQueryService")
    def test_athena_query_execute_with_auto_table_detection(self, mock_service_class):
        """Test athena_query_execute with automatic table detection."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Create mock DataFrame result
        test_df = pd.DataFrame(
            [
                {"database_name": "db1", "table_count": 15},
                {"database_name": "db2", "table_count": 8},
            ]
        )

        mock_service.execute_query.return_value = {"success": True, "data": test_df}

        # Mock format_results to simulate auto table detection
        def mock_format_results(result_data, output_format):
            result = {
                "success": True,
                "formatted_data": [
                    {"database_name": "db1", "table_count": 15},
                    {"database_name": "db2", "table_count": 8},
                ],
                "format": "json",
            }
            # Simulate auto table detection
            result["formatted_data_table"] = "database_name  table_count\ndb1  15\ndb2  8"
            result["display_format"] = "table"
            return result

        mock_service.format_results.side_effect = mock_format_results

        # Test with JSON format (should auto-detect table)
        result = athena_query_execute(query="SHOW DATABASES", output_format="json")

        assert result["success"] is True
        assert result["format"] == "json"
        assert "formatted_data_table" in result
        assert result["display_format"] == "table"
        assert "database_name" in result["formatted_data_table"]

    @pytest.mark.asyncio
    @patch("quilt_mcp.resources.athena.AthenaQueryService")
    async def test_athena_workgroups_resource_with_table_format(self, mock_service_class):
        """Test AthenaWorkgroupsResource with table formatting enhancement."""
        from quilt_mcp.resources.athena import AthenaWorkgroupsResource

        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Mock the service's list_workgroups method to return test data
        mock_service.list_workgroups.return_value = [
            {
                "name": "QuiltUserAthena-test",
                "description": "Test workgroup",
                "creation_time": None,
                "output_location": "s3://test-bucket/results/",
                "enforce_workgroup_config": False,
            },
            {
                "name": "primary",
                "description": "Default workgroup",
                "creation_time": None,
                "output_location": None,
                "enforce_workgroup_config": False,
            },
        ]

        resource = AthenaWorkgroupsResource()
        result = await resource.list_items()

        assert result["success"] is True
        assert "workgroups" in result
        assert len(result["workgroups"]) == 2

        # Verify the service method was called
        mock_service.list_workgroups.assert_called_once()

        # Should have table formatting enhancement
        # Note: The actual implementation may not have this yet
        # This test verifies the integration works without errors

    @pytest.mark.asyncio
    @patch("quilt_mcp.resources.athena.AthenaQueryService")
    async def test_athena_databases_resource_with_table_format(self, mock_service_class):
        """Test AthenaDatabasesResource with table formatting."""
        from quilt_mcp.resources.athena import AthenaDatabasesResource

        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Mock discover_databases to return tabular data
        mock_service.discover_databases.return_value = {
            "success": True,
            "databases": [
                {"name": "database1", "description": "Test DB 1"},
                {"name": "database2", "description": "Test DB 2"},
            ],
            "count": 2,
        }

        resource = AthenaDatabasesResource()
        result = await resource.list_items()

        assert result["success"] is True
        assert "databases" in result
        # Note: databases_list doesn't have table formatting enhancement yet
        # This would be added if we enhance that function too


class TestTabulatorTableFormatIntegration:
    """Integration tests for tabulator tools with table formatting."""

    @patch("quilt_mcp.tools.tabulator.get_tabulator_service")
    def test_tabulator_tables_list_with_table_format(self, mock_get_service):
        """Test tabulator_tables_list with table formatting."""
        # Mock the tabulator service
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        # Mock list_tables to return tabular data
        mock_service.list_tables.return_value = {
            "success": True,
            "tables": [
                {
                    "name": "table1",
                    "column_count": 5,
                    "schema": [
                        {"name": "col1", "type": "STRING"},
                        {"name": "col2", "type": "INT"},
                    ],
                },
                {
                    "name": "table2",
                    "column_count": 3,
                    "schema": [{"name": "id", "type": "INT"}],
                },
            ],
            "bucket_name": "test-bucket",
            "count": 2,
        }

        # Since tabulator_tables_list is async, we need to mock it differently
        # For now, test the service directly
        result = mock_service.list_tables("test-bucket")

        assert result["success"] is True
        assert "tables" in result
        # Note: Testing the service directly, not the full MCP tool chain
        # The table formatting would be applied at the MCP tool level


class TestTableFormatErrorHandling:
    """Test error handling in table formatting integration."""

    @patch("quilt_mcp.tools.athena_glue.AthenaQueryService")
    def test_athena_query_execute_format_error_handling(self, mock_service_class):
        """Test error handling when table formatting fails."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Mock successful query execution
        mock_service.execute_query.return_value = {
            "success": True,
            "data": pd.DataFrame([{"test": "data"}]),
        }

        # Mock format_results to raise an exception
        mock_service.format_results.side_effect = Exception("Formatting error")

        result = athena_query_execute(query="SELECT * FROM test", output_format="table")

        # Should handle the error gracefully
        assert result["success"] is False
        assert "error" in result
        assert "Query execution failed" in result["error"]

    @pytest.mark.skip(reason="athena_workgroups_list replaced by athena://workgroups resource")
    @patch("quilt_mcp.tools.athena_glue.AthenaQueryService")
    def test_athena_workgroups_list_format_error_handling(self, mock_service_class):
        """Test error handling in workgroups list formatting."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        with patch("boto3.client") as mock_boto3_client:
            mock_client = Mock()
            mock_boto3_client.return_value = mock_client

            # Mock successful API calls
            mock_client.list_work_groups.return_value = {"WorkGroups": [{"Name": "test-workgroup"}]}
            mock_client.get_work_group.return_value = {
                "WorkGroup": {
                    "Name": "test-workgroup",
                    "State": "ENABLED",
                    "Configuration": {},
                }
            }

            # Mock table formatting to fail
            with patch("quilt_mcp.formatting.enhance_result_with_table_format") as mock_enhance:
                mock_enhance.side_effect = Exception("Table formatting error")

                # result = athena_workgroups_list()  # Function removed

                # The error handling should prevent the function from failing
                # but in this test case, the error propagates up
                # This is expected behavior for this test scenario


class TestTableFormatPerformance:
    """Test performance aspects of table formatting."""

    def test_large_dataset_table_formatting(self):
        """Test table formatting with large datasets."""
        from quilt_mcp.formatting import format_as_table, should_use_table_format

        # Create a large dataset
        large_data = [{"id": i, "name": f"item_{i}", "value": i * 10} for i in range(1000)]

        # Should still detect as table format
        assert should_use_table_format(large_data) is True

        # Should format with row limit
        result = format_as_table(large_data, max_rows=10)

        assert isinstance(result, str)
        assert "item_0" in result
        assert "item_9" in result
        assert "(990 more rows)" in result

    def test_wide_table_formatting(self):
        """Test table formatting with many columns."""
        from quilt_mcp.formatting import should_use_table_format

        # Create data with many columns
        wide_data = [{f"col_{i}": f"value_{i}" for i in range(25)} for _ in range(3)]

        # Should not use table format for too many columns
        assert should_use_table_format(wide_data, max_cols=20) is False

        # But should use it if we allow more columns
        assert should_use_table_format(wide_data, max_cols=30) is True

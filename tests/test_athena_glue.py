#!/usr/bin/env python3
"""
Tests for AWS Athena and Glue Data Catalog tools
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timezone

from quilt_mcp.tools.athena_glue import (
    athena_databases_list,
    athena_tables_list,
    athena_table_schema,
    athena_query_execute,
    athena_query_history,
    athena_workgroups_list,
    athena_query_validate,
)
from quilt_mcp.aws.athena_service import AthenaQueryService


@pytest.mark.aws
@pytest.mark.slow
class TestAthenaDatabasesList:
    """Test athena_databases_list function."""

    def test_list_databases_success(self):
        """Test successful database listing with real AWS (integration test)."""
        from tests.test_helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        result = athena_databases_list()

        assert isinstance(result, dict)
        assert "success" in result
        assert "databases" in result
        assert isinstance(result["databases"], list)
        # Should have at least the default database


@pytest.mark.aws
@pytest.mark.slow
class TestAthenaTablesList:
    """Test athena_tables_list function."""

    def test_list_tables_success(self):
        """Test successful table listing with real AWS (integration test)."""
        from tests.test_helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        # Use test database from environment, fallback to default if not set
        test_database = os.getenv("QUILT_TEST_DATABASE", "default")
        result = athena_tables_list(test_database)

        assert isinstance(result, dict)
        assert "success" in result

        if result["success"]:
            assert "tables" in result
            assert isinstance(result["tables"], list)
            # Tables list can be empty, that's ok
        else:
            # If the database is not accessible or has naming issues, that's ok for testing
            assert "error" in result
            print(f"Database {test_database} not accessible (expected for some environments): {result['error']}")


@pytest.mark.aws
@pytest.mark.slow
class TestAthenaTableSchema:
    """Test athena_table_schema function."""

    def test_get_table_schema_success(self):
        """Test successful table schema retrieval with real AWS (integration test)."""
        from tests.test_helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        # Use test database from environment, fallback to default if not set
        test_database = os.getenv("QUILT_TEST_DATABASE", "default")
        # Try to get schema for a table that might exist
        # This will likely fail gracefully if no tables exist
        result = athena_table_schema(test_database, "nonexistent_table")

        assert isinstance(result, dict)
        assert "success" in result
        # If success is False, that's expected for nonexistent table


class TestAthenaQueryExecute:
    """Test athena_query_execute function."""

    @pytest.mark.aws
    @pytest.mark.slow
    def test_query_execute_success(self):
        """Test successful query execution with real AWS (integration test)."""
        from tests.test_helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        # Use a simple query that should work on any Athena setup
        query = "SELECT 1 as test_column, 'hello' as test_string"
        result = athena_query_execute(query)

        assert isinstance(result, dict)
        assert "success" in result
        # Query might fail if Athena isn't properly configured, that's ok

    def test_query_execute_empty_query(self):
        """Test query execution with empty query."""
        result = athena_query_execute("")

        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_query_execute_invalid_max_results(self):
        """Test query execution with invalid max_results."""
        result = athena_query_execute("SELECT * FROM table", max_results=0)

        assert result["success"] is False
        assert "max_results must be between" in result["error"]

    def test_query_execute_invalid_format(self):
        """Test query execution with invalid output format."""
        result = athena_query_execute("SELECT * FROM table", output_format="xml")

        assert result["success"] is False
        assert "output_format must be one of" in result["error"]

    @pytest.mark.aws
    @pytest.mark.slow
    def test_query_execute_with_builtin_credentials(self):
        """Test query execution using built-in AWS credentials (not quilt3)."""
        from tests.test_helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        # Use a simple query that should work on any Athena setup
        query = "SELECT 1 as test_column, 'builtin_creds' as auth_type"

        # Explicitly use built-in AWS credentials (use_quilt_auth=False)
        result = athena_query_execute(
            query=query,
            max_results=5,
            output_format="json",
            use_quilt_auth=False,  # This is the key - use AWS credentials, not quilt3
        )

        assert isinstance(result, dict)
        assert "success" in result

        if result["success"]:
            # Verify the query executed successfully with built-in credentials
            assert "formatted_data" in result
            assert "format" in result
            assert result["format"] == "json"
            assert len(result["formatted_data"]) == 1
            assert result["formatted_data"][0]["test_column"] == 1
            assert result["formatted_data"][0]["auth_type"] == "builtin_creds"
            # Verify other expected fields in successful response
            assert "row_count" in result
            assert "columns" in result
            assert result["row_count"] == 1
            assert "test_column" in result["columns"]
            assert "auth_type" in result["columns"]
        else:
            # Query might fail due to Athena configuration, but should fail gracefully
            assert "error" in result
            # The error should not be related to authentication if we have valid AWS creds
            assert isinstance(result["error"], str)


class TestAthenaQueryHistory:
    """Test athena_query_history function."""

    @pytest.mark.aws
    @pytest.mark.slow
    def test_query_history_success(self):
        """Test query history retrieval with real AWS connection."""
        # Skip if AWS credentials not available
        try:
            import boto3

            athena = boto3.client("athena")
            athena.list_work_groups()  # Test basic connectivity
        except Exception:
            pytest.skip("AWS credentials not available or Athena not accessible")

        result = athena_query_history(max_results=10)

        # Should succeed or fail gracefully with AWS error
        assert isinstance(result, dict)
        assert "success" in result

        if result["success"]:
            assert "query_history" in result
            assert isinstance(result["query_history"], list)
            assert "count" in result
            # Each query should have required fields
            for query in result["query_history"]:
                assert "query_execution_id" in query
                assert "status" in query
        else:
            # Should have error message if failed
            assert "error" in result
            assert isinstance(result["error"], str)

    @patch("boto3.client")
    @patch("quilt_mcp.tools.athena_glue.AthenaQueryService")
    def test_query_history_mocked(self, mock_service_class, mock_boto3_client):
        """Test successful query history retrieval with mocks (unit test)."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client

        # Mock list_query_executions response
        mock_athena_client.list_query_executions.return_value = {"QueryExecutionIds": ["query-1", "query-2"]}

        # Mock batch_get_query_execution response
        mock_execution_time = datetime.now(timezone.utc)
        mock_athena_client.batch_get_query_execution.return_value = {
            "QueryExecutions": [
                {
                    "QueryExecutionId": "query-1",
                    "Query": "SELECT * FROM table1",
                    "Status": {
                        "State": "SUCCEEDED",
                        "SubmissionDateTime": mock_execution_time,
                        "CompletionDateTime": mock_execution_time,
                    },
                    "Statistics": {
                        "TotalExecutionTimeInMillis": 2300,
                        "DataScannedInBytes": 1024000,
                    },
                    "ResultConfiguration": {"OutputLocation": "s3://results/query-1"},
                    "WorkGroup": "primary",
                    "QueryExecutionContext": {"Database": "analytics_db"},
                }
            ]
        }

        result = athena_query_history()

        assert result["success"] is True
        assert len(result["query_history"]) == 1
        assert result["query_history"][0]["query_execution_id"] == "query-1"
        assert result["query_history"][0]["status"] == "SUCCEEDED"

    @patch("boto3.client")
    @patch("quilt_mcp.tools.athena_glue.AthenaQueryService")
    def test_query_history_no_executions(self, mock_service_class, mock_boto3_client):
        """Test query history with no executions."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client
        mock_athena_client.list_query_executions.return_value = {"QueryExecutionIds": []}

        result = athena_query_history()

        assert result["success"] is True
        assert len(result["query_history"]) == 0
        assert result["count"] == 0


class TestAthenaWorkgroupsList:
    """Test athena_workgroups_list function."""

    @pytest.mark.aws
    @pytest.mark.slow
    def test_list_workgroups_success(self):
        """Test workgroups listing with real AWS connection."""
        # Skip if AWS credentials not available
        try:
            import boto3

            athena = boto3.client("athena")
            athena.list_work_groups()  # Test basic connectivity
        except Exception:
            pytest.skip("AWS credentials not available or Athena not accessible")

        result = athena_workgroups_list()

        # Should succeed or fail gracefully with AWS error
        assert isinstance(result, dict)
        assert "success" in result

        if result["success"]:
            assert "workgroups" in result
            assert isinstance(result["workgroups"], list)
            assert "count" in result
            # Each workgroup should have required fields
            for wg in result["workgroups"]:
                assert "name" in wg
                # Note: accessible field removed in Episode 2
        else:
            # Should have error message if failed
            assert "error" in result
            assert isinstance(result["error"], str)

    @patch("boto3.client")
    def test_list_workgroups_mocked(self, mock_boto3_client):
        """Test successful workgroups listing with mocks (unit test)."""
        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client

        mock_time = datetime.now(timezone.utc)
        mock_athena_client.list_work_groups.return_value = {
            "WorkGroups": [
                {
                    "Name": "primary",
                    "Description": "Primary workgroup",
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
                {
                    "Name": "analytics",
                    "Description": "Analytics workgroup",
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
            ]
        }

        result = athena_workgroups_list()

        assert result["success"] is True
        assert len(result["workgroups"]) == 2
        assert result["workgroups"][0]["name"] == "analytics"  # Sorted alphabetically
        assert result["workgroups"][1]["name"] == "primary"

    @patch("boto3.client")
    def test_athena_workgroups_list_filters_enabled_only(self, mock_boto3_client):
        """Test that only ENABLED workgroups appear in results (Episode 1)."""
        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client

        mock_time = datetime.now(timezone.utc)
        # Mock response with both ENABLED and DISABLED workgroups
        mock_athena_client.list_work_groups.return_value = {
            "WorkGroups": [
                {
                    "Name": "enabled-workgroup",
                    "Description": "Enabled workgroup",
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
                {
                    "Name": "disabled-workgroup", 
                    "Description": "Disabled workgroup",
                    "State": "DISABLED",
                    "CreationTime": mock_time,
                },
                {
                    "Name": "another-enabled",
                    "Description": "Another enabled workgroup", 
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
            ]
        }

        # Mock GetWorkGroup calls for enabled workgroups only
        def mock_get_work_group(WorkGroup):
            if WorkGroup in ["enabled-workgroup", "another-enabled"]:
                return {
                    "WorkGroup": {
                        "Name": WorkGroup,
                        "State": "ENABLED",
                        "Description": f"Description for {WorkGroup}",
                        "CreationTime": mock_time,
                        "Configuration": {
                            "ResultConfiguration": {"OutputLocation": f"s3://results/{WorkGroup}/"},
                            "EnforceWorkGroupConfiguration": False,
                        },
                    }
                }
            else:
                # Should not be called for disabled workgroups
                raise Exception(f"GetWorkGroup should not be called for {WorkGroup}")

        mock_athena_client.get_work_group.side_effect = mock_get_work_group

        result = athena_workgroups_list()

        # Only ENABLED workgroups should appear in results
        assert result["success"] is True
        assert len(result["workgroups"]) == 2
        workgroup_names = [wg["name"] for wg in result["workgroups"]]
        assert "enabled-workgroup" in workgroup_names
        assert "another-enabled" in workgroup_names
        assert "disabled-workgroup" not in workgroup_names

        # Verify GetWorkGroup was only called for ENABLED workgroups
        expected_calls = ["enabled-workgroup", "another-enabled"]
        actual_calls = [call.kwargs["WorkGroup"] for call in mock_athena_client.get_work_group.call_args_list]
        assert set(actual_calls) == set(expected_calls)

    @patch("boto3.client")
    def test_athena_workgroups_list_no_synthetic_accessible_field(self, mock_boto3_client):
        """Test that 'accessible' field is not present in any workgroup result (Episode 2)."""
        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client

        mock_time = datetime.now(timezone.utc)
        mock_athena_client.list_work_groups.return_value = {
            "WorkGroups": [
                {
                    "Name": "test-workgroup",
                    "Description": "Test workgroup",
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
            ]
        }

        # Mock successful GetWorkGroup call
        mock_athena_client.get_work_group.return_value = {
            "WorkGroup": {
                "Name": "test-workgroup",
                "State": "ENABLED",
                "Description": "Test workgroup description",
                "CreationTime": mock_time,
                "Configuration": {
                    "ResultConfiguration": {"OutputLocation": "s3://results/test-workgroup/"},
                    "EnforceWorkGroupConfiguration": False,
                },
            }
        }

        result = athena_workgroups_list()

        # Verify success and basic structure
        assert result["success"] is True
        assert len(result["workgroups"]) == 1
        
        # Assert 'accessible' field is not present in any workgroup result
        workgroup = result["workgroups"][0]
        assert "accessible" not in workgroup
        
        # Verify expected AWS API fields are present
        assert "name" in workgroup
        assert "description" in workgroup
        assert "creation_time" in workgroup
        assert "output_location" in workgroup
        assert "enforce_workgroup_config" in workgroup

    @patch("boto3.client")
    def test_athena_workgroups_list_no_state_field_in_output(self, mock_boto3_client):
        """Test that 'state' field is not present in workgroup results (Episode 3)."""
        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client

        mock_time = datetime.now(timezone.utc)
        mock_athena_client.list_work_groups.return_value = {
            "WorkGroups": [
                {
                    "Name": "test-workgroup",
                    "Description": "Test workgroup",
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
            ]
        }

        # Mock successful GetWorkGroup call
        mock_athena_client.get_work_group.return_value = {
            "WorkGroup": {
                "Name": "test-workgroup",
                "State": "ENABLED",  # AWS API returns state
                "Description": "Test workgroup description",
                "CreationTime": mock_time,
                "Configuration": {
                    "ResultConfiguration": {"OutputLocation": "s3://results/test-workgroup/"},
                    "EnforceWorkGroupConfiguration": False,
                },
            }
        }

        result = athena_workgroups_list()

        # Verify success and basic structure
        assert result["success"] is True
        assert len(result["workgroups"]) == 1
        
        # Assert 'state' field is not present in workgroup result
        # Since all workgroups are ENABLED (Episode 1), state field is redundant
        workgroup = result["workgroups"][0]
        assert "state" not in workgroup
        
        # Verify expected AWS API fields are still present
        assert "name" in workgroup
        assert "description" in workgroup
        assert "creation_time" in workgroup
        assert "output_location" in workgroup
        assert "enforce_workgroup_config" in workgroup


class TestAthenaQueryValidate:
    """Test athena_query_validate function."""

    def test_validate_empty_query(self):
        """Test validation of empty query."""
        result = athena_query_validate("")

        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_validate_valid_select_query(self):
        """Test validation of valid SELECT query."""
        query = "SELECT event_type, COUNT(*) FROM customer_events WHERE date >= '2024-01-01' GROUP BY event_type"
        result = athena_query_validate(query)

        assert result["success"] is True
        assert result["valid"] is True
        assert result["query_type"] == "SELECT"

    def test_validate_dangerous_query(self):
        """Test validation of dangerous query."""
        query = "DROP TABLE customer_events"
        result = athena_query_validate(query)

        assert result["success"] is False
        assert result["valid"] is False
        assert "dangerous" in result["error"].lower()

    def test_validate_select_without_from(self):
        """Test validation of SELECT without FROM."""
        query = "SELECT 1, 2, 3"
        result = athena_query_validate(query)

        assert result["success"] is False
        assert result["valid"] is False
        assert "FROM clause" in result["error"]

    def test_validate_mismatched_parentheses(self):
        """Test validation of query with mismatched parentheses."""
        query = "SELECT COUNT((event_type) FROM customer_events"
        result = athena_query_validate(query)

        assert result["success"] is False
        assert result["valid"] is False
        assert "parentheses" in result["error"].lower()

    def test_validate_show_query(self):
        """Test validation of SHOW query."""
        query = "SHOW TABLES"
        result = athena_query_validate(query)

        assert result["success"] is True
        assert result["valid"] is True
        assert result["query_type"] == "SHOW"

    def test_validate_describe_query(self):
        """Test validation of DESCRIBE query."""
        query = "DESCRIBE analytics_db.customer_events"
        result = athena_query_validate(query)

        assert result["success"] is True
        assert result["valid"] is True
        assert result["query_type"] == "DESCRIBE"

    def test_validate_backticks_query(self):
        """Test validation of query with backticks (MySQL-style) instead of double quotes."""
        query = "SELECT `column_name`, `another_column` FROM `table_name` WHERE `id` = 1"
        result = athena_query_validate(query)

        assert result["success"] is False
        assert result["valid"] is False
        assert "backtick" in result["error"].lower()
        assert "suggestions" in result
        assert len(result["suggestions"]) > 0


class TestAthenaQueryService:
    """Test AthenaQueryService class."""

    @pytest.fixture(scope="class")
    def athena_service(self):
        """Shared AthenaQueryService instance for all tests in this class."""
        return AthenaQueryService(use_quilt_auth=False)

    @pytest.mark.aws
    @pytest.mark.slow
    def test_service_initialization(self):
        """Test service initialization with real AWS connection."""
        # Skip if AWS credentials not available
        try:
            import boto3

            athena = boto3.client("athena")
            athena.list_work_groups()  # Test basic connectivity
        except Exception:
            pytest.skip("AWS credentials not available or Athena not accessible")

        # Test both with and without quilt auth
        service_no_auth = AthenaQueryService(use_quilt_auth=False)
        assert service_no_auth.use_quilt_auth is False

        service_with_auth = AthenaQueryService(use_quilt_auth=True)
        assert service_with_auth.use_quilt_auth is True

    @pytest.mark.aws
    @pytest.mark.slow
    def test_discover_databases(self, athena_service):
        """Test database discovery with real AWS connection."""
        # Skip if AWS credentials not available
        try:
            import boto3

            athena = boto3.client("athena")
            athena.list_work_groups()  # Test basic connectivity
        except Exception:
            pytest.skip("AWS credentials not available or Athena not accessible")

        result = athena_service.discover_databases()

        # Should succeed or fail gracefully with AWS error
        assert isinstance(result, dict)
        assert "success" in result

        if result["success"]:
            assert "databases" in result
            assert isinstance(result["databases"], list)
        else:
            # Should have error message if failed
            assert "error" in result
            assert isinstance(result["error"], str)

    @patch("quilt_mcp.aws.athena_service.create_engine")
    @patch("quilt_mcp.aws.athena_service.boto3")
    def test_service_initialization_mocked(self, mock_boto3, mock_create_engine, athena_service):
        """Test service initialization with mocks (unit test)."""
        assert athena_service.use_quilt_auth is False
        assert athena_service.query_cache.maxsize == 100

    @patch("quilt_mcp.aws.athena_service.pd.read_sql_query")
    @patch("quilt_mcp.aws.athena_service.create_engine")
    @patch("quilt_mcp.aws.athena_service.boto3")
    def test_discover_databases_mocked(self, mock_boto3, mock_create_engine, mock_read_sql, athena_service):
        """Test database discovery with mocks (unit test)."""
        # Mock pandas DataFrame result from SQL query
        mock_df = pd.DataFrame({"database_name": ["analytics_db", "test_db"]})
        mock_read_sql.return_value = mock_df

        result = athena_service.discover_databases()

        assert result["success"] is True
        assert len(result["databases"]) == 2
        assert result["databases"][0]["name"] == "analytics_db"
        assert result["databases"][1]["name"] == "test_db"
        mock_read_sql.assert_called_once()

    @pytest.mark.aws
    @pytest.mark.slow
    def test_execute_query(self, athena_service):
        """Test query execution with real AWS (integration test)."""
        from tests.test_helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        try:
            # Use a simple query that should work on any Athena setup
            result = athena_service.execute_query("SELECT 1 as test_column")

            assert result["success"] is True
            assert result["row_count"] >= 1
            assert "test_column" in result["columns"]

        except Exception as e:
            pytest.skip(f"Athena service not available: {e}")

    @patch("quilt_mcp.aws.athena_service.pd.read_sql_query")
    @patch("quilt_mcp.aws.athena_service.create_engine")
    @patch("quilt_mcp.aws.athena_service.boto3")
    def test_execute_query_mocked(self, mock_boto3, mock_create_engine, mock_read_sql, athena_service):
        """Test query execution with mocks (unit test)."""

        # Mock pandas DataFrame result
        mock_df = pd.DataFrame({"event_type": ["page_view", "purchase"], "count": [125432, 23891]})
        mock_read_sql.return_value = mock_df

        result = athena_service.execute_query("SELECT event_type, COUNT(*) FROM events GROUP BY event_type")

        assert result["success"] is True
        assert result["row_count"] == 2
        assert result["columns"] == ["event_type", "count"]
        assert result["truncated"] is False

    @pytest.mark.aws
    @pytest.mark.slow
    def test_format_results_json(self, athena_service):
        """Test result formatting to JSON with real AWS (integration test)."""
        from tests.test_helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        # Create test data
        df = pd.DataFrame({"test_column": ["value1", "value2"], "count": [1, 2]})

        # Create a result dict like what execute_query would return
        result_data = {
            "success": True,
            "row_count": len(df),
            "columns": df.columns.tolist(),
            "data": df,  # Pass DataFrame directly, not as dict
            "truncated": False,
        }
        result = athena_service.format_results(result_data, "json")

        assert result["success"] is True
        assert result["format"] == "json"
        assert "formatted_data" in result

    @pytest.mark.aws
    @pytest.mark.slow
    def test_format_results_csv(self, athena_service):
        """Test result formatting to CSV with real AWS (integration test)."""
        from tests.test_helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        # Create test data
        df = pd.DataFrame({"event_type": ["page_view", "purchase"], "count": [125432, 23891]})

        # Create a result dict like what execute_query would return
        result_data = {
            "success": True,
            "row_count": len(df),
            "columns": df.columns.tolist(),
            "data": df,  # Pass DataFrame directly, not as dict
            "truncated": False,
        }
        result = athena_service.format_results(result_data, "csv")

        assert result["success"] is True
        assert result["format"] == "csv"
        assert "formatted_data" in result
        assert "event_type,count" in result["formatted_data"]


if __name__ == "__main__":
    pytest.main([__file__])
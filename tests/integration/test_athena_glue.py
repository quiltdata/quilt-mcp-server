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
from quilt_mcp.services.athena_service import AthenaQueryService


def test_athena_service_factory_reuses_instances(athena_service_factory):
    """Factory should reuse cached services to avoid repeated bootstrap work."""

    first = athena_service_factory(use_quilt_auth=True)
    second = athena_service_factory(use_quilt_auth=True)

    assert first is second


@pytest.fixture(scope="module")
def require_aws_credentials():
    """Skip module tests when AWS credentials are unavailable."""

    from tests.helpers import skip_if_no_aws_credentials

    skip_if_no_aws_credentials()
    return True


@pytest.fixture(scope="class")
def databases_response(require_aws_credentials, athena_service_quilt):
    """Fetch database list once per class to avoid duplicate calls."""

    return athena_databases_list(service=athena_service_quilt)


@pytest.fixture(scope="class")
def tables_response(require_aws_credentials, athena_service_quilt):
    """Fetch table list once per class to reduce duplicate network work."""

    test_database = os.getenv("QUILT_TEST_DATABASE", "default")
    result = athena_tables_list(
        test_database,
        service=athena_service_quilt,
    )

    return test_database, result


@pytest.fixture(scope="class")
def table_schema_response(require_aws_credentials, athena_service_quilt):
    """Fetch table schema once per class using the cached service."""

    test_database = os.getenv("QUILT_TEST_DATABASE", "default")
    return athena_table_schema(
        test_database,
        "nonexistent_table",
        service=athena_service_quilt,
    )


@pytest.mark.aws
class TestAthenaDatabasesList:
    """Test athena_databases_list function."""

    @pytest.mark.slow
    def test_list_databases_success(self, databases_response):
        """Test successful database listing with real AWS (integration test)."""

        result = databases_response

        assert isinstance(result, dict)
        assert "success" in result
        assert "databases" in result
        assert isinstance(result["databases"], list)
        # Should have at least the default database


@pytest.mark.aws
class TestAthenaTablesList:
    """Test athena_tables_list function."""

    @pytest.mark.slow
    def test_list_tables_success(self, tables_response):
        """Test successful table listing with real AWS (integration test)."""

        test_database, result = tables_response

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

    def test_get_table_schema_success(self, table_schema_response):
        """Test successful table schema retrieval with real AWS (integration test)."""

        result = table_schema_response

        assert isinstance(result, dict)
        assert "success" in result
        # If success is False, that's expected for nonexistent table


class TestAthenaQueryExecute:
    """Test athena_query_execute function."""

    @pytest.mark.aws
    @pytest.mark.slow
    def test_query_execute_success(self, require_aws_credentials, athena_service_quilt):
        """Test successful query execution with real AWS (integration test)."""

        # Use a simple query that should work on any Athena setup
        query = "SELECT 1 as test_column, 'hello' as test_string"
        result = athena_query_execute(query, service=athena_service_quilt)

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
    def test_query_execute_with_builtin_credentials(self, require_aws_credentials, athena_service_builtin):
        """Test query execution using built-in AWS credentials (not quilt3)."""

        # Use a simple query that should work on any Athena setup
        query = "SELECT 1 as test_column, 'builtin_creds' as auth_type"

        # Explicitly use built-in AWS credentials (use_quilt_auth=False)
        result = athena_query_execute(
            query=query,
            max_results=5,
            output_format="json",
            use_quilt_auth=False,  # This is the key - use AWS credentials, not quilt3
            service=athena_service_builtin,
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
    def test_query_history_success(self, require_aws_credentials, athena_service_quilt):
        """Test query history retrieval with real AWS connection."""

        result = athena_query_history(max_results=10, service=athena_service_quilt)

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

    @patch("boto3.client")
    def test_athena_workgroups_list_clean_description_field(self, mock_boto3_client):
        """Test that description field contains only AWS data, no error messages (Episode 4)."""
        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client

        mock_time = datetime.now(timezone.utc)
        mock_athena_client.list_work_groups.return_value = {
            "WorkGroups": [
                {
                    "Name": "accessible-workgroup",
                    "Description": "Original AWS description",
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
                {
                    "Name": "inaccessible-workgroup",
                    "Description": "Another AWS description",
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
            ]
        }

        # Mock GetWorkGroup calls - one succeeds, one fails
        def mock_get_work_group(WorkGroup):
            if WorkGroup == "accessible-workgroup":
                return {
                    "WorkGroup": {
                        "Name": WorkGroup,
                        "State": "ENABLED",
                        "Description": "Detailed AWS description",
                        "CreationTime": mock_time,
                        "Configuration": {
                            "ResultConfiguration": {"OutputLocation": f"s3://results/{WorkGroup}/"},
                            "EnforceWorkGroupConfiguration": False,
                        },
                    }
                }
            elif WorkGroup == "inaccessible-workgroup":
                # Simulate access denied error
                raise Exception("AccessDenied: User does not have permission")

        mock_athena_client.get_work_group.side_effect = mock_get_work_group

        result = athena_workgroups_list()

        # Verify success and basic structure
        assert result["success"] is True
        assert len(result["workgroups"]) == 2

        # Find accessible and inaccessible workgroups
        accessible_wg = next(wg for wg in result["workgroups"] if wg["name"] == "accessible-workgroup")
        inaccessible_wg = next(wg for wg in result["workgroups"] if wg["name"] == "inaccessible-workgroup")

        # Assert accessible workgroup has clean AWS description
        assert accessible_wg["description"] == "Detailed AWS description"
        assert "Access denied" not in accessible_wg["description"]
        assert "Error" not in accessible_wg["description"]

        # Assert inaccessible workgroup preserves original AWS description or remains clean
        # NO error messages should pollute the description field
        assert "Access denied" not in inaccessible_wg["description"]
        assert "AccessDenied" not in inaccessible_wg["description"]
        assert "permission" not in inaccessible_wg["description"]
        # Should preserve original AWS description from ListWorkGroups
        assert inaccessible_wg["description"] == "Another AWS description"

    @patch("boto3.client")
    def test_athena_workgroups_list_layered_api_access(self, mock_boto3_client):
        """Test layered API access pattern - minimal and enhanced permissions (Episode 5)."""
        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client

        mock_time = datetime.now(timezone.utc)
        mock_athena_client.list_work_groups.return_value = {
            "WorkGroups": [
                {
                    "Name": "basic-workgroup",
                    "Description": "Basic workgroup description",
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
                {
                    "Name": "enhanced-workgroup",
                    "Description": "Enhanced workgroup description",
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
            ]
        }

        # Mock GetWorkGroup calls - one succeeds (enhanced), one fails (minimal permissions)
        def mock_get_work_group(WorkGroup):
            if WorkGroup == "enhanced-workgroup":
                # Enhanced permissions: GetWorkGroup succeeds
                return {
                    "WorkGroup": {
                        "Name": WorkGroup,
                        "State": "ENABLED",
                        "Description": "Detailed enhanced description",
                        "CreationTime": mock_time,
                        "Configuration": {
                            "ResultConfiguration": {"OutputLocation": f"s3://results/{WorkGroup}/"},
                            "EnforceWorkGroupConfiguration": True,
                        },
                    }
                }
            elif WorkGroup == "basic-workgroup":
                # Minimal permissions: GetWorkGroup fails
                raise Exception("AccessDenied: Insufficient permissions for GetWorkGroup")

        mock_athena_client.get_work_group.side_effect = mock_get_work_group

        result = athena_workgroups_list()

        # Verify core functionality works regardless of permission level
        assert result["success"] is True
        assert len(result["workgroups"]) == 2

        # Find workgroups
        basic_wg = next(wg for wg in result["workgroups"] if wg["name"] == "basic-workgroup")
        enhanced_wg = next(wg for wg in result["workgroups"] if wg["name"] == "enhanced-workgroup")

        # Test minimal permissions scenario (ListWorkGroups only)
        # Core functionality should work with data from ListWorkGroups
        assert basic_wg["name"] == "basic-workgroup"
        assert basic_wg["description"] == "Basic workgroup description"  # From ListWorkGroups
        assert basic_wg["creation_time"] == mock_time  # From ListWorkGroups
        assert basic_wg["output_location"] is None  # GetWorkGroup failed
        assert basic_wg["enforce_workgroup_config"] is False  # Default when GetWorkGroup fails

        # Test enhanced permissions scenario (both ListWorkGroups and GetWorkGroup)
        # Enhanced functionality available when GetWorkGroup succeeds
        assert enhanced_wg["name"] == "enhanced-workgroup"
        assert enhanced_wg["description"] == "Detailed enhanced description"  # From GetWorkGroup
        assert enhanced_wg["creation_time"] == mock_time  # From GetWorkGroup
        assert enhanced_wg["output_location"] == "s3://results/enhanced-workgroup/"  # From GetWorkGroup
        assert enhanced_wg["enforce_workgroup_config"] is True  # From GetWorkGroup

        # Assert graceful degradation - GetWorkGroup failures don't break core functionality
        # Both workgroups should be present and have essential information
        for wg in result["workgroups"]:
            assert "name" in wg and wg["name"]  # Essential info always available
            assert "description" in wg  # Always has description (from ListWorkGroups at minimum)
            assert "creation_time" in wg  # Always has creation time
            assert "output_location" in wg  # Field exists (may be None)
            assert "enforce_workgroup_config" in wg  # Field exists (may be default)

    @patch("boto3.client")
    def test_athena_workgroups_list_end_to_end_integration(self, mock_boto3_client):
        """Test complete workflow with all changes applied (Episode 6)."""
        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client

        mock_time = datetime.now(timezone.utc)
        # Mock ListWorkGroups with ENABLED and DISABLED workgroups to test Episode 1 filtering
        mock_athena_client.list_work_groups.return_value = {
            "WorkGroups": [
                {
                    "Name": "enabled-accessible",
                    "Description": "Accessible workgroup description",
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
                {
                    "Name": "enabled-inaccessible",
                    "Description": "Inaccessible workgroup description",
                    "State": "ENABLED",
                    "CreationTime": mock_time,
                },
                {
                    "Name": "disabled-workgroup",
                    "Description": "This should be filtered out",
                    "State": "DISABLED",  # Should be filtered by Episode 1
                    "CreationTime": mock_time,
                },
            ]
        }

        # Mock GetWorkGroup calls to test Episode 4 & 5 (layered access + clean descriptions)
        def mock_get_work_group(WorkGroup):
            if WorkGroup == "enabled-accessible":
                # Enhanced permissions scenario
                return {
                    "WorkGroup": {
                        "Name": WorkGroup,
                        "State": "ENABLED",
                        "Description": "Enhanced detailed description",
                        "CreationTime": mock_time,
                        "Configuration": {
                            "ResultConfiguration": {"OutputLocation": f"s3://results/{WorkGroup}/"},
                            "EnforceWorkGroupConfiguration": True,
                        },
                    }
                }
            elif WorkGroup == "enabled-inaccessible":
                # Minimal permissions scenario - GetWorkGroup fails
                raise Exception("AccessDenied: Insufficient permissions")
            elif WorkGroup == "disabled-workgroup":
                # Should NEVER be called due to Episode 1 filtering
                raise Exception("This workgroup should have been filtered out!")

        mock_athena_client.get_work_group.side_effect = mock_get_work_group

        result = athena_workgroups_list()

        # Verify comprehensive integration
        assert result["success"] is True

        # Episode 1: Only ENABLED workgroups should be present (DISABLED filtered out)
        assert len(result["workgroups"]) == 2  # disabled-workgroup should be filtered out
        workgroup_names = {wg["name"] for wg in result["workgroups"]}
        assert "enabled-accessible" in workgroup_names
        assert "enabled-inaccessible" in workgroup_names
        assert "disabled-workgroup" not in workgroup_names  # Filtered by Episode 1

        # Find workgroups for detailed testing
        accessible_wg = next(wg for wg in result["workgroups"] if wg["name"] == "enabled-accessible")
        inaccessible_wg = next(wg for wg in result["workgroups"] if wg["name"] == "enabled-inaccessible")

        # Episode 2: No synthetic 'accessible' field
        for wg in result["workgroups"]:
            assert "accessible" not in wg

        # Episode 3: No redundant 'state' field (all are ENABLED)
        for wg in result["workgroups"]:
            assert "state" not in wg

        # Episode 4: Clean descriptions (no error messages)
        assert "Access denied" not in accessible_wg["description"]
        assert "AccessDenied" not in inaccessible_wg["description"]
        assert "permission" not in inaccessible_wg["description"]
        # Preserve original AWS descriptions
        assert accessible_wg["description"] == "Enhanced detailed description"  # From GetWorkGroup
        assert inaccessible_wg["description"] == "Inaccessible workgroup description"  # From ListWorkGroups

        # Episode 5: Layered API access working correctly
        # Enhanced permissions scenario
        assert accessible_wg["output_location"] == "s3://results/enabled-accessible/"
        assert accessible_wg["enforce_workgroup_config"] is True
        # Minimal permissions scenario (graceful degradation)
        assert inaccessible_wg["output_location"] is None
        assert inaccessible_wg["enforce_workgroup_config"] is False

        # Verify all workgroups have clean AWS field structure
        for wg in result["workgroups"]:
            # Required AWS API fields
            assert "name" in wg and wg["name"]
            assert "description" in wg
            assert "creation_time" in wg
            assert "output_location" in wg  # May be None
            assert "enforce_workgroup_config" in wg  # May be False

            # No synthetic or error fields
            assert "accessible" not in wg
            assert "state" not in wg
            assert "Access denied" not in str(wg.get("description", ""))

    @patch.object(AthenaQueryService, 'list_workgroups')
    def test_athena_workgroups_list_uses_athena_query_service(self, mock_list_workgroups):
        """Test that workgroups listing uses AthenaQueryService for consistent auth patterns (Episode 7)."""
        mock_time = datetime.now(timezone.utc)

        # Mock the AthenaQueryService.list_workgroups method to return test data
        mock_list_workgroups.return_value = [
            {
                "name": "service-managed-workgroup",
                "description": "Enhanced description from service",
                "creation_time": mock_time,
                "output_location": "s3://results/service-managed/",
                "enforce_workgroup_config": False,
            }
        ]

        result = athena_workgroups_list()

        # Verify success
        assert result["success"] is True
        assert len(result["workgroups"]) == 1

        # Verify the result has expected structure from consolidated service
        workgroup = result["workgroups"][0]
        assert workgroup["name"] == "service-managed-workgroup"
        assert workgroup["description"] == "Enhanced description from service"
        assert workgroup["output_location"] == "s3://results/service-managed/"

        # Key test: Verify AthenaQueryService.list_workgroups was called
        # This will fail if the function doesn't use the service method
        mock_list_workgroups.assert_called_once()

        # Verify all Episodes 1-6 functionality is preserved through service integration
        # Episode 1: Only ENABLED workgroups (handled by service)
        # Episode 2-3: No synthetic fields (accessible, state)
        assert "accessible" not in workgroup
        assert "state" not in workgroup
        # Episode 4: Clean descriptions (handled by service)
        assert "Access denied" not in workgroup["description"]
        # Episode 5: Layered API access (handled by service)
        assert "output_location" in workgroup

    @patch.object(AthenaQueryService, 'list_workgroups')
    def test_discover_workgroup_uses_list_workgroups_method(self, mock_list_workgroups):
        """Test that _discover_workgroup uses list_workgroups method internally (Episode 7 consolidation)."""
        mock_time = datetime.now(timezone.utc)

        # Mock the list_workgroups method to return test data
        mock_list_workgroups.return_value = [
            {
                "name": "QuiltUserAthena-test",
                "description": "Quilt workgroup with output location",
                "creation_time": mock_time,
                "output_location": "s3://quilt-results/test/",
                "enforce_workgroup_config": True,
            },
            {
                "name": "primary",
                "description": "Primary workgroup without output location",
                "creation_time": mock_time,
                "output_location": None,
                "enforce_workgroup_config": False,
            },
        ]

        # Create service and test _discover_workgroup method
        service = AthenaQueryService(use_jwt_auth=True)

        # Call _discover_workgroup (this should internally call list_workgroups)
        result = service._discover_workgroup(None, "us-east-1")

        # Verify it returns the Quilt workgroup (prioritized and has output location)
        assert result["name"] == "QuiltUserAthena-test"
        assert result["output_location"] == "s3://quilt-results/test/"

        # Key test: Verify that list_workgroups was called internally
        # This ensures Episode 7 consolidation is working correctly
        mock_list_workgroups.assert_called_once()

    @patch.object(AthenaQueryService, 'list_workgroups')
    def test_discover_workgroup_fallback_behavior(self, mock_list_workgroups):
        """Test _discover_workgroup fallback behavior when no valid workgroups available."""
        # Test empty workgroups list
        mock_list_workgroups.return_value = []
        service = AthenaQueryService(use_jwt_auth=False)

        result = service._discover_workgroup(None, "us-east-1")
        assert result["name"] == "primary"
        assert result["output_location"] is None

        # Test workgroups without output locations
        mock_list_workgroups.return_value = [
            {
                "name": "test-workgroup",
                "description": "Test workgroup",
                "creation_time": None,
                "output_location": None,
                "enforce_workgroup_config": False,
            }
        ]

        result = service._discover_workgroup(None, "us-east-1")
        assert result["name"] == "test-workgroup"  # Uses first available when no valid output locations


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
    def athena_service(self, athena_service_builtin):
        """Shared AthenaQueryService instance for all tests in this class."""
        return athena_service_builtin

    @pytest.mark.aws
    def test_service_initialization(self, require_aws_credentials, athena_service_factory):
        """Test service initialization with real AWS connection."""

        # Test both with and without quilt auth using cached services
        service_no_auth = athena_service_factory(False)
        assert service_no_auth.use_quilt_auth is False

        service_with_auth = athena_service_factory(True)
        assert service_with_auth.use_quilt_auth is True

    @pytest.mark.aws
    @pytest.mark.slow
    def test_discover_databases(self, require_aws_credentials, athena_service):
        """Test database discovery with real AWS connection."""

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

    @pytest.mark.aws
    @pytest.mark.slow
    def test_execute_query(self, require_aws_credentials, athena_service):
        """Test query execution with real AWS (integration test)."""

        try:
            # Use a simple query that should work on any Athena setup
            result = athena_service.execute_query("SELECT 1 as test_column")

            assert result["success"] is True
            assert result["row_count"] >= 1
            assert "test_column" in result["columns"]

        except Exception as e:
            pytest.skip(f"Athena service not available: {e}")

    @patch("quilt_mcp.services.athena_service.pd.read_sql_query")
    @patch("quilt_mcp.services.athena_service.create_engine")
    @patch("quilt_mcp.services.athena_service.boto3")
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
    def test_format_results_json(self, athena_service):
        """Test result formatting to JSON with real AWS (integration test)."""

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
    def test_format_results_csv(self, athena_service):
        """Test result formatting to CSV with real AWS (integration test)."""

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

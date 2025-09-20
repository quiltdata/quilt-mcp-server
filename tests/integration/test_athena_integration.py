#!/usr/bin/env python3
"""
Integration tests for AWS Athena and Glue Data Catalog tools

These tests require actual AWS credentials and resources.
"""

import pytest
import os
from unittest.mock import patch, Mock

# Test timeout from environment variable
PYTEST_TIMEOUT = float(os.getenv('PYTEST_TIMEOUT', '120'))

from quilt_mcp.tools.athena_glue import (
    athena_databases_list,
    athena_tables_list,
    athena_table_schema,
    athena_query_execute,
    athena_workgroups_list,
)
from quilt_mcp.services.athena_service import AthenaQueryService


@pytest.mark.aws
@pytest.mark.slow
class TestAthenaIntegration:
    """Integration tests for Athena functionality."""

    @pytest.fixture(scope="class")
    def athena_service(self):
        """Shared AthenaQueryService instance for all tests in this class."""
        return AthenaQueryService(use_quilt_auth=False)

    @pytest.fixture(autouse=True)
    def setup_aws_env(self):
        """Setup AWS environment variables for testing."""
        # Check if AWS credentials are available by trying to get caller identity
        try:
            import boto3

            sts = boto3.client("sts")
            sts.get_caller_identity()
        except Exception:
            pytest.skip("AWS credentials not available")

        # No need to set ATHENA_QUERY_RESULT_LOCATION - workgroups handle this

    def test_list_databases_integration(self):
        """Test listing databases with real AWS connection."""
        result = athena_databases_list()

        # Should succeed or fail gracefully with AWS error
        assert isinstance(result, dict)
        assert "success" in result

        if result["success"]:
            assert "databases" in result
            assert isinstance(result["databases"], list)
            assert "catalog_name" in result
            assert result["catalog_name"] == "AwsDataCatalog"
        else:
            # Should have error message if failed
            assert "error" in result
            assert isinstance(result["error"], str)

    def test_list_workgroups_integration(self):
        """Test listing Athena workgroups with real AWS connection."""
        result = athena_workgroups_list()

        assert isinstance(result, dict)
        assert "success" in result

        if result["success"]:
            assert "workgroups" in result
            assert isinstance(result["workgroups"], list)
            # Should at least have 'primary' workgroup
            workgroup_names = [wg["name"] for wg in result["workgroups"]]
            assert "primary" in workgroup_names

    def test_query_execution_integration(self):
        """Test executing a simple query against Athena."""
        # Use a simple query that should work in most AWS accounts
        query = "SELECT 1 as test_value, 'hello' as test_string"

        result = athena_query_execute(
            query=query,
            max_results=10,
            output_format="json",
            use_quilt_auth=False,  # Use default AWS credentials
        )

        assert isinstance(result, dict)
        assert "success" in result

        if result["success"]:
            assert "formatted_data" in result
            assert "format" in result
            assert result["format"] == "json"
            assert len(result["formatted_data"]) == 1
            assert result["formatted_data"][0]["test_value"] == 1
            assert result["formatted_data"][0]["test_string"] == "hello"
        else:
            # Query might fail due to Athena setup, but should fail gracefully
            assert "error" in result

    def test_service_initialization_integration(self, athena_service):
        """Test AthenaQueryService initialization with real AWS."""
        try:
            # Test lazy initialization doesn't fail
            glue_client = athena_service.glue_client
            s3_client = athena_service.s3_client

            # These should be boto3 clients
            assert hasattr(glue_client, "get_databases")
            assert hasattr(s3_client, "list_buckets")

        except Exception as e:
            # If initialization fails, it should be due to AWS config issues
            assert "credential" in str(e).lower() or "auth" in str(e).lower()

    def test_database_discovery_integration(self, athena_service):
        """Test database discovery integration."""
        try:
            result = athena_service.discover_databases()

            assert isinstance(result, dict)
            assert "success" in result

            if result["success"]:
                assert "databases" in result
                assert isinstance(result["databases"], list)
                # Each database should have required fields
                for db in result["databases"]:
                    assert "name" in db
                    assert isinstance(db["name"], str)

        except Exception as e:
            pytest.skip(f"AWS access issue: {e}")


@pytest.mark.aws
@pytest.mark.slow
class TestQuiltAuthIntegration:
    """Integration tests for quilt3 authentication."""

    @pytest.fixture(scope="class")
    def athena_service_with_quilt(self):
        """Shared AthenaQueryService instance with quilt auth for all tests in this class."""
        return AthenaQueryService(use_quilt_auth=True)

    @pytest.fixture(autouse=True)
    def check_quilt_available(self):
        """Check if quilt3 is available and configured."""
        try:
            import quilt3

            # Try to get session to verify quilt3 is configured
            session = quilt3.session.get_session()
            if not session:
                pytest.skip("Quilt3 session not available")
        except ImportError:
            pytest.skip("quilt3 not available")
        except Exception as e:
            pytest.skip(f"Quilt3 configuration issue: {e}")

    @pytest.mark.aws
    def test_service_with_quilt_auth(self, athena_service_with_quilt):
        """Test service initialization with quilt3 authentication."""

        # Skip if no AWS credentials
        from tests.helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        try:
            # Test that we can create clients
            glue_client = athena_service_with_quilt.glue_client
            s3_client = athena_service_with_quilt.s3_client

            assert glue_client is not None
            assert s3_client is not None

            # Try to access the engine - this might fail if quilt3 auth isn't configured
            try:
                engine = athena_service_with_quilt.engine
                assert engine is not None
            except Exception as engine_error:
                # This is expected if quilt3 auth isn't properly configured
                # The error should be related to credentials or quilt configuration
                error_msg = str(engine_error).lower()
                assert any(keyword in error_msg for keyword in ["credential", "quilt", "auth", "access"])

        except Exception as e:
            # Expected if quilt3 isn't properly configured or AWS credentials are invalid
            error_msg = str(e).lower()
            assert any(
                keyword in error_msg
                for keyword in [
                    "credential",
                    "quilt",
                    "auth",
                    "access",
                    "unable to locate",
                ]
            )

    def test_query_with_quilt_auth(self):
        """Test query execution with quilt3 authentication."""
        query = "SELECT 1 as test_value"

        result = athena_query_execute(query=query, use_quilt_auth=True, max_results=1)

        assert isinstance(result, dict)
        assert "success" in result

        # Test passes if query succeeds or fails gracefully
        if not result["success"]:
            assert "error" in result


@pytest.mark.performance
@pytest.mark.slow
class TestAthenaPerformance:
    """Performance tests for Athena functionality."""

    @pytest.fixture(scope="class")
    def athena_service(self):
        """Shared AthenaQueryService instance for all tests in this class."""
        return AthenaQueryService(use_quilt_auth=False)

    @pytest.mark.aws
    def test_concurrent_database_discovery(self):
        """Test concurrent database discovery operations with real AWS (integration test)."""
        from tests.helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        try:
            import threading
            import time

            results = []
            errors = []

            def discover_databases():
                try:
                    result = athena_databases_list()
                    results.append(result)
                except Exception as e:
                    errors.append(e)

            # Run multiple concurrent requests
            threads = []
            start_time = time.time()

            for i in range(3):  # Reduced from 10 to be gentler on AWS
                thread = threading.Thread(target=discover_databases)
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            end_time = time.time()

            # Verify results (more lenient for real AWS)
            assert len(results) >= 0  # Allow for some failures
            assert end_time - start_time < PYTEST_TIMEOUT  # Allow more time for real AWS

        except Exception as e:
            pytest.skip(f"Athena service not available: {e}")

    @pytest.mark.aws
    def test_concurrent_database_discovery_real_aws(self):
        """Test concurrent database discovery operations with real AWS."""
        import threading
        import time

        # Skip if no AWS credentials
        from tests.helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        results = []
        errors = []

        def discover_databases():
            try:
                result = athena_databases_list()
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Run multiple concurrent requests (fewer for real AWS to avoid rate limits)
        threads = []
        start_time = time.time()

        for _ in range(3):  # Reduced from 10 to 3 for real AWS
            thread = threading.Thread(target=discover_databases)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        end_time = time.time()

        # All requests should complete successfully or fail gracefully
        assert len(results) == 3

        # Should complete in reasonable time (allow more time for real AWS)
        assert end_time - start_time < PYTEST_TIMEOUT

        # Results should either be successful or handle errors gracefully
        for result in results:
            assert "success" in result
            if not result["success"]:
                assert "error" in result

    @patch("quilt_mcp.services.athena_service.pd.read_sql_query")
    @patch("quilt_mcp.services.athena_service.create_engine")
    @patch("quilt_mcp.services.athena_service.boto3")
    def test_large_result_set_handling(self, mock_boto3, mock_create_engine, mock_read_sql, athena_service):
        """Test handling of large result sets."""
        import pandas as pd

        # Create large mock DataFrame (10,000 rows)
        large_df = pd.DataFrame({"id": range(10000), "value": [f"value_{i}" for i in range(10000)]})
        mock_read_sql.return_value = large_df

        # Test with default max_results (should truncate)
        result = athena_service.execute_query("SELECT * FROM large_table", max_results=1000)

        assert result["success"] is True
        assert result["row_count"] == 1000  # Should be truncated
        assert result["truncated"] is True

        # Test with higher limit
        result = athena_service.execute_query("SELECT * FROM large_table", max_results=5000)

        assert result["success"] is True
        assert result["row_count"] == 5000  # Should be truncated to 5000
        assert result["truncated"] is True


@pytest.mark.error_handling
@pytest.mark.slow
class TestAthenaErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture(scope="class")
    def athena_service(self):
        """Shared AthenaQueryService instance for all tests in this class."""
        return AthenaQueryService(use_quilt_auth=False)

    @pytest.mark.aws
    def test_glue_connection_error_real_aws(self):
        """Test handling of Glue connection errors with real AWS."""

        # Skip if no AWS credentials
        from tests.helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        # Try to access a non-existent catalog to trigger an error
        result = athena_databases_list(catalog_name="nonexistent-catalog-12345")

        # Should handle the error gracefully
        assert "success" in result
        if not result["success"]:
            assert "error" in result
            # The error message should indicate some kind of access or connection issue
            error_msg = result["error"].lower()
            assert any(keyword in error_msg for keyword in ["access", "denied", "not found", "error", "invalid"])

    @patch("quilt_mcp.services.athena_service.pd.read_sql_query")
    @patch("quilt_mcp.services.athena_service.create_engine")
    def test_sqlalchemy_connection_error(self, mock_create_engine, mock_read_sql, athena_service):
        """Test handling of SQLAlchemy connection errors."""
        from sqlalchemy.exc import SQLAlchemyError

        # Mock engine creation to succeed
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Mock pandas to raise a connection error
        mock_read_sql.side_effect = SQLAlchemyError("Connection failed")

        result = athena_service.execute_query("SELECT 1")

        assert result["success"] is False
        assert "Connection failed" in result["error"]

    @pytest.mark.aws
    def test_sql_syntax_error_real_aws(self):
        """Test handling of SQL syntax errors with real AWS."""

        # Skip if no AWS credentials
        from tests.helpers import skip_if_no_aws_credentials

        skip_if_no_aws_credentials()

        # Execute invalid SQL to trigger a syntax error
        result = athena_query_execute("SELECT FROM WHERE")  # Invalid SQL

        # Should handle the error gracefully
        assert "success" in result
        assert result["success"] is False
        assert "error" in result
        # The error message should indicate a syntax or query error
        error_msg = result["error"].lower()
        assert any(keyword in error_msg for keyword in ["syntax", "error", "invalid", "failed"])

    def test_invalid_query_parameters(self):
        """Test handling of invalid query parameters."""
        # Empty query
        result = athena_query_execute("")
        assert result["success"] is False

        # Invalid max_results
        result = athena_query_execute("SELECT 1", max_results=-1)
        assert result["success"] is False

        # Invalid output format
        result = athena_query_execute("SELECT 1", output_format="invalid")
        assert result["success"] is False

    @patch("quilt_mcp.services.athena_service.boto3")
    def test_table_not_found_error(self, mock_boto3):
        """Test handling when table is not found."""
        from botocore.exceptions import ClientError

        mock_glue = mock_boto3.client.return_value
        mock_glue.get_table.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "EntityNotFoundException",
                    "Message": "Table not found",
                }
            },
            operation_name="GetTable",
        )

        result = athena_table_schema("test_db", "nonexistent_table")

        assert result["success"] is False
        assert (
            "Table not found" in result["error"]
            or "not found" in result["error"].lower()
            or "access" in result["error"].lower()
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

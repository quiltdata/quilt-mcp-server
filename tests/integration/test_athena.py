#!/usr/bin/env python3
"""
Real-world Athena integration tests - full user workflows.

Tests the complete user journey with actual data:
1. Discover databases
2. List tables in a database
3. Query data from a table

NO MOCKING - tests full stack with real AWS.
"""

import os
import pytest


@pytest.fixture(scope="module")
def skip_if_no_aws():
    """Skip tests if AWS credentials are not available."""
    from tests.helpers import skip_if_no_aws_credentials

    skip_if_no_aws_credentials()


@pytest.mark.aws
@pytest.mark.slow
class TestTabulatorWorkflow:
    """Test complete Tabulator workflow with real bucket and data."""

    def test_tabulator_complete_workflow(self, skip_if_no_aws):  # noqa: ARG002
        """
        Complete Tabulator workflow:
        0. Get configured bucket from environment
        1. List tables in the bucket (SHOW TABLES)
        2. Extract first table name from results
        3. Query a row from that table (SELECT)

        This exercises:
        - Tabulator catalog configuration
        - Database context with hyphenated bucket names
        - SHOW TABLES query
        - SELECT query with actual data
        - Full stack: auth → catalog → query → results
        """
        from quilt_mcp.tools.athena_glue import tabulator_table_query

        # 0. Get bucket from environment (real bucket with hyphens)
        bucket = os.getenv("QUILT_DEFAULT_BUCKET")
        if not bucket:
            pytest.skip("QUILT_DEFAULT_BUCKET not set")
            return  # For type checker
        bucket_name = bucket.replace("s3://", "")

        # 1. List tables in the bucket
        tables_result = tabulator_table_query(
            bucket_name=bucket_name,
            query="SHOW TABLES",
            output_format="json",
        )

        assert tables_result["success"] is True, f"SHOW TABLES failed: {tables_result.get('error')}"
        assert "formatted_data" in tables_result
        assert isinstance(tables_result["formatted_data"], list)
        assert len(tables_result["formatted_data"]) > 0, "No tables found in bucket"

        # 2. Extract first table name
        first_table = tables_result["formatted_data"][0]
        table_name = first_table.get("tab_name") or first_table.get("table_name")
        assert table_name, f"Could not find table name in result: {first_table}"

        print(f"\nFound table: {table_name}")

        # 3. Query a row from the table
        query_result = tabulator_table_query(
            bucket_name=bucket_name,
            query=f'SELECT * FROM "{table_name}" LIMIT 1',
            output_format="json",
        )

        assert query_result["success"] is True, f"SELECT query failed: {query_result.get('error')}"
        assert "formatted_data" in query_result
        assert isinstance(query_result["formatted_data"], list)
        assert len(query_result["formatted_data"]) > 0, "No data returned from table"

        print(f"Successfully queried {len(query_result['formatted_data'])} rows from {table_name}")
        print(f"Columns: {query_result.get('columns', [])}")


@pytest.mark.aws
@pytest.mark.slow
class TestAthenaWorkflow:
    """Test complete Athena workflow with real databases."""

    def test_athena_complete_workflow(self, skip_if_no_aws):  # noqa: ARG002
        """
        Complete Athena workflow:
        0. List all databases (athena_databases_list)
        1. Find a database with tables
        2. List tables in that database (athena_tables_list)
        3. Query a row from a table (athena_query_execute)

        This exercises:
        - Database discovery via Glue API
        - Table listing via Glue API
        - SELECT query with actual data
        - Full stack without Tabulator catalog
        """
        from quilt_mcp.tools.athena_glue import (
            athena_databases_list,
            athena_query_execute,
            athena_tables_list,
        )

        # 0. List all databases using Glue API
        databases_result = athena_databases_list()

        # Validate databases_result structure
        if not databases_result.get("success"):
            error_msg = databases_result.get("error", "Unknown error")
            pytest.fail(f"athena_databases_list() failed\nError: {error_msg}\nFull response: {databases_result}")

        # Extract databases from response
        databases = databases_result.get("databases", [])
        if not databases:
            pytest.fail(
                f"athena_databases_list() returned no databases\n"
                f"Response structure: {list(databases_result.keys())}\n"
                f"Full response: {databases_result}"
            )

        print(f"\nFound {len(databases)} databases")

        # 1. Try to find a database with tables
        database_name = None
        tables = None
        tables_result = None

        for db_info in databases:
            # Handle both dict and string responses
            # Response format: {"name": "db_name", "description": "", ...}
            db_name = db_info.get("name") if isinstance(db_info, dict) else db_info
            if not db_name or db_name in ["information_schema", "default"]:
                continue

            print(f"Checking database: {db_name}")

            # 2. List tables using Glue API
            tables_result = athena_tables_list(database_name=db_name)

            if not tables_result.get("success"):
                error_msg = tables_result.get("error", "Unknown error")
                print(f"  athena_tables_list({db_name}) failed: {error_msg}")
                continue

            # Extract tables from response
            tables = tables_result.get("tables", [])
            if tables:
                database_name = db_name
                print(f"Found {len(tables)} tables in {db_name}")
                break

        if not database_name or not tables or not tables_result:
            pytest.skip(
                "Could not find a database with tables to query\nDatabases checked but no tables found in any of them"
            )

        # 3. Query a row from the first table
        # At this point, tables is guaranteed to be non-empty due to the check above
        assert tables, f"athena_tables_list({database_name}) returned success but no tables\nResponse: {tables_result}"

        first_table = tables[0]
        # Handle both dict and string responses
        # Response format: {"name": "table_name", "database_name": "db_name", ...}
        table_name = first_table.get("name") if isinstance(first_table, dict) else first_table
        if not table_name:
            pytest.fail(
                f"Could not extract table name from athena_tables_list response\n"
                f"First table structure: {first_table}\n"
                f"Expected 'name' key or string value"
            )

        print(f"Querying table: {database_name}.{table_name}")

        # Use athena_query_execute for actual data query
        query_result = athena_query_execute(
            query=f'SELECT * FROM "{database_name}"."{table_name}" LIMIT 1',
            output_format="json",
        )

        if not query_result.get("success"):
            error_msg = query_result.get("error", "Unknown error")
            pytest.fail(
                f"athena_query_execute() failed for SELECT query\n"
                f"Query: SELECT * FROM \"{database_name}\".\"{table_name}\" LIMIT 1\n"
                f"Error: {error_msg}\n"
                f"Full response: {query_result}"
            )

        formatted_data = query_result.get("formatted_data", [])
        if not formatted_data:
            pytest.fail(
                f"athena_query_execute() returned no data\n"
                f"Query: SELECT * FROM \"{database_name}\".\"{table_name}\" LIMIT 1\n"
                f"Response keys: {list(query_result.keys())}\n"
                f"Full response: {query_result}"
            )

        print(f"Successfully queried {len(formatted_data)} rows")
        print(f"Columns: {query_result.get('columns', [])}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

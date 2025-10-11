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
        0. List all databases (SHOW DATABASES)
        1. Find a database with tables
        2. List tables in that database (SHOW TABLES)
        3. Query a row from a table (SELECT)

        This exercises:
        - Database discovery
        - SHOW DATABASES query
        - SHOW TABLES with database context
        - SELECT query with actual data
        - Full stack without Tabulator catalog
        """
        from quilt_mcp.tools.athena_glue import athena_query_execute

        # 0. List all databases
        databases_result = athena_query_execute(
            query="SHOW DATABASES",
            output_format="json",
        )

        assert databases_result["success"] is True, f"SHOW DATABASES failed: {databases_result.get('error')}"
        assert "formatted_data" in databases_result
        databases = databases_result["formatted_data"]
        assert len(databases) > 0, "No databases found"

        print(f"\nFound {len(databases)} databases")

        # 1. Try to find a database with tables
        database_name = None
        tables_result = None

        for db_row in databases:
            db_name = db_row.get("database_name") or db_row.get("namespace_name")
            if not db_name or db_name in ["information_schema", "default"]:
                continue

            print(f"Checking database: {db_name}")

            # 2. List tables in this database
            tables_result = athena_query_execute(
                query=f'SHOW TABLES IN "{db_name}"',
                output_format="json",
            )

            if tables_result["success"] and tables_result.get("formatted_data"):
                database_name = db_name
                print(f"Found {len(tables_result['formatted_data'])} tables in {db_name}")
                break

        if not database_name or not tables_result:
            pytest.skip("Could not find a database with tables to query")

        # 3. Query a row from the first table
        tables = tables_result["formatted_data"]
        assert len(tables) > 0, "No tables found in database"

        first_table = tables[0]
        table_name = first_table.get("tab_name") or first_table.get("table_name")
        assert table_name, f"Could not find table name in result: {first_table}"

        print(f"Querying table: {database_name}.{table_name}")

        query_result = athena_query_execute(
            query=f'SELECT * FROM "{database_name}"."{table_name}" LIMIT 1',
            output_format="json",
        )

        assert query_result["success"] is True, f"SELECT query failed: {query_result.get('error')}"
        assert "formatted_data" in query_result
        assert len(query_result["formatted_data"]) > 0, "No data returned from table"

        print(f"Successfully queried {len(query_result['formatted_data'])} rows")
        print(f"Columns: {query_result.get('columns', [])}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

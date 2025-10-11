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
        Complete Tabulator workflow with dynamic discovery:
        0. List all buckets in Tabulator catalog (tabulator_buckets_list)
        1. Find a bucket with tables
        2. List tables in that bucket (SHOW TABLES via tabulator_bucket_query)
        3. Query a row from a table (SELECT via tabulator_bucket_query)

        This exercises:
        - Tabulator catalog discovery
        - Dynamic bucket selection
        - Database context with hyphenated bucket names
        - SHOW TABLES query
        - SELECT query with actual data
        - Full stack: auth → catalog → query → results
        """
        import asyncio
        from quilt_mcp.tools.tabulator import tabulator_buckets_list, tabulator_bucket_query

        # 0. List all buckets in Tabulator catalog
        buckets_result = asyncio.run(tabulator_buckets_list())

        assert buckets_result["success"] is True, f"tabulator_buckets_list failed: {buckets_result.get('error')}"
        assert "buckets" in buckets_result
        assert isinstance(buckets_result["buckets"], list)
        assert len(buckets_result["buckets"]) > 0, "No buckets found in Tabulator catalog"

        print(f"\nFound {len(buckets_result['buckets'])} bucket(s) in Tabulator catalog")

        # 1. Find a bucket with tables
        bucket_name = None
        table_name = None
        query_result = None

        for current_bucket in buckets_result["buckets"]:
            print(f"Checking bucket: {current_bucket}")

            # 2. List tables in this bucket
            tables_result = asyncio.run(
                tabulator_bucket_query(
                    bucket_name=current_bucket,
                    query="SHOW TABLES",
                    output_format="json",
                )
            )

            if not tables_result.get("success"):
                error_msg = tables_result.get("error", "Unknown error")
                print(f"  SHOW TABLES failed: {error_msg}")
                continue

            formatted_data = tables_result.get("formatted_data", [])
            if not formatted_data or len(formatted_data) == 0:
                print(f"  No tables found in {current_bucket}")
                continue

            # Extract first table name
            first_table = formatted_data[0]
            current_table_name = first_table.get("tab_name") or first_table.get("table_name")
            if not current_table_name:
                print(f"  Could not extract table name from: {first_table}")
                continue

            print(f"Found table: {current_table_name}")

            # 3. Try to query a row from the table
            current_query_result = asyncio.run(
                tabulator_bucket_query(
                    bucket_name=current_bucket,
                    query=f'SELECT * FROM "{current_table_name}" LIMIT 1',
                    output_format="json",
                )
            )

            if not current_query_result.get("success"):
                error_msg = current_query_result.get("error", "Unknown error")
                print(f"  SELECT query failed: {error_msg}")
                continue

            query_data = current_query_result.get("formatted_data", [])
            if not query_data or len(query_data) == 0:
                print(f"  No data returned from {current_table_name}")
                continue

            # Success! Found a working bucket and table
            bucket_name = current_bucket
            table_name = current_table_name
            query_result = current_query_result
            break

        # Verify we found a working bucket/table combination
        if not query_result or not bucket_name or not table_name:
            pytest.skip(
                "Could not find a bucket with queryable tables\n"
                "Tried all buckets but none had tables with accessible data"
            )

        print(
            f"Successfully queried {len(query_result.get('formatted_data', []))} rows from {bucket_name}.{table_name}"
        )
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

        # 1. Try to find a database with a queryable table
        # Try multiple databases and tables until we find one that works
        query_result = None
        database_name = None
        table_name = None

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
            if not tables:
                print(f"  No tables found in {db_name}")
                continue

            print(f"Found {len(tables)} tables in {db_name}")

            # 3. Try to query the first table from this database
            first_table = tables[0]
            # Handle both dict and string responses
            # Response format: {"name": "table_name", "database_name": "db_name", ...}
            current_table_name = first_table.get("name") if isinstance(first_table, dict) else first_table
            if not current_table_name:
                print(f"  Could not extract table name from: {first_table}")
                continue

            print(f"Trying to query table: {db_name}.{current_table_name}")

            # Use athena_query_execute for actual data query
            current_query_result = athena_query_execute(
                query=f'SELECT * FROM "{db_name}"."{current_table_name}" LIMIT 1',
                output_format="json",
            )

            if not current_query_result.get("success"):
                error_msg = current_query_result.get("error", "Unknown error")
                print(f"  Query failed: {error_msg}")
                continue

            formatted_data = current_query_result.get("formatted_data", [])
            if not formatted_data:
                print("  Query returned no data")
                continue

            # Success! Found a working database and table
            database_name = db_name
            table_name = current_table_name
            query_result = current_query_result
            break

        # Check if we found a working database/table combination
        if not query_result or not database_name or not table_name:
            pytest.skip(
                "Could not find a database with queryable tables\n"
                "Tried all databases but none had tables with accessible data"
            )

        print(
            f"Successfully queried {len(query_result.get('formatted_data', []))} rows from {database_name}.{table_name}"
        )
        print(f"Columns: {query_result.get('columns', [])}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

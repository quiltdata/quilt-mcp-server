#!/usr/bin/env python3
"""
Real-world Athena integration tests using actual data and queries.

These tests use real AWS infrastructure with real bucket names and queries
that users actually run. NO MOCKING of Athena calls - we test the full stack.

Test data:
- Uses QUILT_DEFAULT_BUCKET from environment (typically has hyphens)
- Uses real Tabulator catalog configuration
- Tests actual user workflows
"""

import os
import pytest


@pytest.fixture(scope="module")
def real_bucket_name():
    """Get real bucket name from environment."""
    bucket = os.getenv("QUILT_DEFAULT_BUCKET")
    if not bucket:
        pytest.skip("QUILT_DEFAULT_BUCKET not set")
    # Remove s3:// prefix if present
    return bucket.replace("s3://", "")


@pytest.fixture(scope="module")
def skip_if_no_aws():
    """Skip tests if AWS credentials are not available."""
    from tests.helpers import skip_if_no_aws_credentials

    skip_if_no_aws_credentials()


@pytest.mark.aws
@pytest.mark.slow
class TestTabulatorRealWorld:
    """Real-world tests for tabulator_table_query with actual buckets."""

    def test_show_tables_with_hyphenated_bucket(self, skip_if_no_aws, real_bucket_name):
        """
        Test SHOW TABLES with real hyphenated bucket name.

        This is the most common user query and currently FAILS due to USE statement bug.
        Real-world scenario: bucket_name='quilt-ernest-staging', query='SHOW TABLES'
        """
        from quilt_mcp.tools.athena_glue import tabulator_table_query

        # Skip if bucket name doesn't have hyphens
        if "-" not in real_bucket_name:
            pytest.skip("Bucket name doesn't contain hyphens, test not applicable")

        result = tabulator_table_query(
            bucket_name=real_bucket_name,
            query="SHOW TABLES",
            output_format="json",
            use_quilt_auth=True,
        )

        # This should succeed but currently fails with:
        # "SQL execution error: ... USE "bucket-name" ..."
        assert isinstance(result, dict)
        assert "success" in result

        if not result["success"]:
            # Document the actual error
            error = result.get("error", "")
            # Check if it's the old USE statement bug (should be fixed)
            if "USE" in error and "mismatched input" in error:
                pytest.fail(
                    f"USE statement bug still present with bucket '{real_bucket_name}':\n"
                    f"Error: {error[:500]}"
                )
            # Permission errors are expected in real environments - document but don't fail
            elif "AccessDenied" in error or "not authorized" in error or "glue:GetDatabase" in error:
                pytest.skip(
                    f"Skipping due to expected AWS permission error for '{real_bucket_name}': {error[:200]}"
                )
            else:
                # Unexpected error - fail the test
                pytest.fail(
                    f"Unexpected error with hyphenated bucket '{real_bucket_name}':\n"
                    f"Error: {error[:500]}"
                )

        # Verify successful response structure
        assert "formatted_data" in result
        assert "format" in result
        assert result["format"] == "json"
        assert isinstance(result["formatted_data"], list)
        assert "row_count" in result
        assert result["row_count"] >= 0

    def test_select_query_with_hyphenated_bucket(self, skip_if_no_aws, real_bucket_name):
        """
        Test SELECT query with real hyphenated bucket name.

        Real-world scenario: querying information_schema or actual tables.
        This requires database context and will fail with USE statement bug.
        """
        from quilt_mcp.tools.athena_glue import tabulator_table_query

        # Skip if bucket name doesn't have hyphens
        if "-" not in real_bucket_name:
            pytest.skip("Bucket name doesn't contain hyphens, test not applicable")

        result = tabulator_table_query(
            bucket_name=real_bucket_name,
            query="SELECT table_name FROM information_schema.tables LIMIT 5",
            output_format="json",
            use_quilt_auth=True,
        )

        # This should succeed but currently fails with USE statement bug
        assert isinstance(result, dict)
        assert "success" in result

        if not result["success"]:
            error = result.get("error", "")
            # Check if it's the old USE statement bug (should be fixed)
            if "USE" in error and "mismatched input" in error:
                pytest.fail(
                    f"USE statement bug still present with bucket '{real_bucket_name}':\n"
                    f"Error: {error[:500]}"
                )
            # Permission errors are expected in real environments
            elif "AccessDenied" in error or "not authorized" in error or "glue:GetDatabase" in error:
                pytest.skip(
                    f"Skipping due to expected AWS permission error for '{real_bucket_name}': {error[:200]}"
                )
            else:
                pytest.fail(
                    f"Unexpected error with hyphenated bucket '{real_bucket_name}':\n"
                    f"Error: {error[:500]}"
                )

        # Verify successful response structure
        assert "formatted_data" in result
        assert isinstance(result["formatted_data"], list)
        assert len(result["formatted_data"]) <= 5
        assert "row_count" in result

    def test_show_tables_without_hyphens(self, skip_if_no_aws):
        """
        Test SHOW TABLES with bucket name without hyphens (control test).

        This should work to verify our test infrastructure is correct.
        Only runs if we have a non-hyphenated bucket available.
        """
        from quilt_mcp.tools.athena_glue import tabulator_table_query

        # For this test, we need a bucket without hyphens
        # Most production buckets have hyphens, so this might skip
        bucket = os.getenv("QUILT_DEFAULT_BUCKET", "").replace("s3://", "")
        if not bucket or "-" in bucket:
            pytest.skip("No non-hyphenated bucket available for control test")

        result = tabulator_table_query(
            bucket_name=bucket,
            query="SHOW TABLES",
            output_format="json",
            use_quilt_auth=True,
        )

        # This should always succeed (no hyphens = no USE statement escaping issues)
        assert result["success"] is True
        assert "formatted_data" in result
        assert isinstance(result["formatted_data"], list)


@pytest.mark.aws
@pytest.mark.slow
class TestAthenaQueryExecuteRealWorld:
    """Real-world tests for athena_query_execute."""

    def test_simple_select_without_database(self, skip_if_no_aws):
        """
        Test simple SELECT query without database context.

        This should always work as it doesn't require USE statement.
        """
        from quilt_mcp.tools.athena_glue import athena_query_execute

        result = athena_query_execute(
            query="SELECT 1 as test_value, 'hello' as test_string",
            output_format="json",
            use_quilt_auth=True,
        )

        assert result["success"] is True
        assert "formatted_data" in result
        assert len(result["formatted_data"]) == 1
        assert result["formatted_data"][0]["test_value"] == 1
        assert result["formatted_data"][0]["test_string"] == "hello"

    def test_show_databases(self, skip_if_no_aws):
        """
        Test SHOW DATABASES query.

        Real-world scenario: discovering available databases/catalogs.
        """
        from quilt_mcp.tools.athena_glue import athena_query_execute

        result = athena_query_execute(
            query="SHOW DATABASES",
            output_format="json",
            use_quilt_auth=True,
        )

        # Should succeed and return list of databases
        assert result["success"] is True
        assert "formatted_data" in result
        assert isinstance(result["formatted_data"], list)
        assert result["row_count"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

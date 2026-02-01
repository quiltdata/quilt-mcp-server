#!/usr/bin/env python3
"""Real integration tests for Tabulator operations.

These tests hit the ACTUAL backend through QuiltOpsFactory.
NO MOCKING of backend methods or GraphQL execution.

Requirements:
- quilt3 catalog login (authenticated session)
- QUILT_TEST_BUCKET environment variable set
- Valid credentials with tabulator permissions

These tests will FAIL LOUDLY if credentials are not available.
"""

import os
import pytest
import time
from datetime import datetime

from quilt_mcp.ops.factory import QuiltOpsFactory


# Example config for testing
EXAMPLE_CONFIG_YAML = """schema:
- name: sample_id
  type: STRING
- name: collection_date
  type: TIMESTAMP
- name: concentration
  type: FLOAT
- name: quality_score
  type: INT
- name: passed_qc
  type: BOOLEAN
source:
  type: quilt-packages
  package_name: ^experiments/(?P<year>\\d{4})/(?P<experiment_id>[^/]+)$
  logical_key: samples/(?P<sample_type>[^/]+)\\.csv$
parser:
  format: csv
  delimiter: ","
  header: true"""


@pytest.fixture(scope="module")
def test_table_name():
    """Generate unique table name for this test run."""
    timestamp = int(time.time())
    return f"test_tabulator_{timestamp}"


@pytest.fixture(scope="module")
def backend():
    """Create real backend - NO MOCKING!

    This fixture creates a real backend instance using QuiltOpsFactory.
    It will fail loudly if credentials are not available.
    """
    try:
        backend = QuiltOpsFactory.create()

        # Verify backend has tabulator methods
        assert hasattr(backend, 'list_tabulator_tables'), (
            "Backend missing list_tabulator_tables - TabulatorMixin not loaded?"
        )
        assert hasattr(backend, 'create_tabulator_table'), (
            "Backend missing create_tabulator_table - TabulatorMixin not loaded?"
        )
        assert hasattr(backend, 'delete_tabulator_table'), (
            "Backend missing delete_tabulator_table - TabulatorMixin not loaded?"
        )
        assert hasattr(backend, 'rename_tabulator_table'), (
            "Backend missing rename_tabulator_table - TabulatorMixin not loaded?"
        )
        assert hasattr(backend, 'get_tabulator_table'), (
            "Backend missing get_tabulator_table - TabulatorMixin not loaded?"
        )

        return backend

    except Exception as e:
        pytest.fail(
            f"Failed to create backend. Ensure you have:\n"
            f"  1. Run 'quilt3 catalog login'\n"
            f"  2. Valid AWS credentials\n"
            f"  3. Permissions for tabulator operations\n"
            f"Error: {e}"
        )


@pytest.fixture(scope="module")
def test_bucket():
    """Get test bucket name - FAIL LOUDLY if not set."""
    bucket = os.getenv("QUILT_TEST_BUCKET", "").replace("s3://", "")

    if not bucket:
        pytest.fail(
            "QUILT_TEST_BUCKET environment variable not set!\n"
            "Set it to a bucket you have tabulator permissions on:\n"
            "  export QUILT_TEST_BUCKET=your-test-bucket"
        )

    return bucket


@pytest.fixture(scope="module")
def created_table(backend, test_bucket, test_table_name):
    """Create a test table and clean it up after all tests.

    This fixture creates a real table in the actual backend.
    It will be automatically deleted after all module tests complete.
    """
    table_name = test_table_name

    # Create the table
    try:
        result = backend.create_tabulator_table(bucket=test_bucket, table_name=table_name, config=EXAMPLE_CONFIG_YAML)

        # Verify creation succeeded
        assert result.get('__typename') == 'BucketSetTabulatorTableSuccess', f"Failed to create table: {result}"

        print(f"\n✅ Created test table: {table_name} in {test_bucket}")

    except Exception as e:
        pytest.fail(
            f"Failed to create test table '{table_name}' in bucket '{test_bucket}'.\n"
            f"Ensure you have:\n"
            f"  1. Tabulator permissions on bucket '{test_bucket}'\n"
            f"  2. Valid quilt3 authentication\n"
            f"Error: {e}"
        )

    yield table_name

    # Cleanup: Delete the table after tests
    try:
        backend.delete_tabulator_table(test_bucket, table_name)
        print(f"\n🧹 Cleaned up test table: {table_name}")
    except Exception as e:
        print(f"\n⚠️  Warning: Could not delete test table '{table_name}': {e}")


# ============================================================================
# REAL INTEGRATION TESTS - NO MOCKING!
# ============================================================================


@pytest.mark.integration
def test_backend_has_tabulator_methods(backend):
    """Verify backend was properly initialized with TabulatorMixin."""
    assert hasattr(backend, 'list_tabulator_tables')
    assert hasattr(backend, 'create_tabulator_table')
    assert hasattr(backend, 'delete_tabulator_table')
    assert hasattr(backend, 'rename_tabulator_table')
    assert hasattr(backend, 'get_tabulator_table')

    # Verify these are actual methods, not mocks
    assert callable(backend.list_tabulator_tables)
    assert not hasattr(backend.list_tabulator_tables, 'return_value'), (
        "list_tabulator_tables is a mock! This is an integration test!"
    )


@pytest.mark.integration
def test_list_tables_real(backend, test_bucket):
    """List tables in bucket - hits REAL GraphQL API."""
    try:
        tables = backend.list_tabulator_tables(test_bucket)

        # Should return a list (may be empty)
        assert isinstance(tables, list), f"Expected list, got {type(tables)}"

        print(f"\n📋 Found {len(tables)} table(s) in {test_bucket}")
        for table in tables[:3]:  # Show first 3
            print(f"  - {table.get('name')}")

    except Exception as e:
        pytest.fail(
            f"Failed to list tables in bucket '{test_bucket}'.\nThis is a REAL backend call, not a mock.\nError: {e}"
        )


@pytest.mark.integration
def test_create_table_real(backend, test_bucket, test_table_name):
    """Create a table - hits REAL GraphQL API.

    Note: This test creates and deletes its own table to avoid conflicts.
    """
    unique_table = f"{test_table_name}_create"

    try:
        # Create table
        result = backend.create_tabulator_table(
            bucket=test_bucket, table_name=unique_table, config=EXAMPLE_CONFIG_YAML
        )

        # Verify success
        assert result.get('__typename') == 'BucketSetTabulatorTableSuccess', f"Create failed: {result}"

        print(f"\n✅ Created table '{unique_table}' in {test_bucket}")

        # Verify table exists by listing
        tables = backend.list_tabulator_tables(test_bucket)
        table_names = [t.get('name') for t in tables]
        assert unique_table in table_names, f"Table '{unique_table}' not found in list after creation"

    except Exception as e:
        pytest.fail(f"Create table failed: {e}")

    finally:
        # Cleanup
        try:
            backend.delete_tabulator_table(test_bucket, unique_table)
            print(f"🧹 Cleaned up '{unique_table}'")
        except Exception as cleanup_error:
            print(f"⚠️  Cleanup warning: {cleanup_error}")


@pytest.mark.integration
def test_get_table_real(backend, test_bucket, created_table):
    """Get specific table - hits REAL GraphQL API."""
    try:
        table = backend.get_tabulator_table(test_bucket, created_table)

        # Verify table structure
        assert isinstance(table, dict), f"Expected dict, got {type(table)}"
        assert table.get('name') == created_table, f"Expected name '{created_table}', got '{table.get('name')}'"
        assert 'config' in table, "Table missing config field"

        # Verify config has expected schema fields
        config = table['config']
        assert 'sample_id' in config, "Schema missing 'sample_id' field"
        assert 'collection_date' in config, "Schema missing 'collection_date' field"

        print(f"\n✅ Retrieved table '{created_table}' from {test_bucket}")

    except Exception as e:
        pytest.fail(f"Failed to get table '{created_table}' from bucket '{test_bucket}'.\nError: {e}")


@pytest.mark.integration
def test_rename_table_real(backend, test_bucket, test_table_name):
    """Rename a table - hits REAL GraphQL API.

    Creates a table, renames it, verifies new name exists, cleans up.
    """
    original_name = f"{test_table_name}_rename_orig"
    new_name = f"{test_table_name}_rename_new"

    try:
        # Create table
        result = backend.create_tabulator_table(
            bucket=test_bucket, table_name=original_name, config=EXAMPLE_CONFIG_YAML
        )
        assert result.get('__typename') == 'BucketSetTabulatorTableSuccess'

        # Rename table
        rename_result = backend.rename_tabulator_table(test_bucket, original_name, new_name)
        assert rename_result.get('__typename') == 'BucketSetTabulatorTableSuccess', f"Rename failed: {rename_result}"

        print(f"\n✅ Renamed '{original_name}' → '{new_name}' in {test_bucket}")

        # Verify new name exists
        tables = backend.list_tabulator_tables(test_bucket)
        table_names = [t.get('name') for t in tables]
        assert new_name in table_names, f"New name '{new_name}' not found after rename"
        assert original_name not in table_names, f"Old name '{original_name}' still exists after rename"

    except Exception as e:
        pytest.fail(f"Rename table failed: {e}")

    finally:
        # Cleanup both possible names
        for name in [original_name, new_name]:
            try:
                backend.delete_tabulator_table(test_bucket, name)
                print(f"🧹 Cleaned up '{name}'")
            except:
                pass  # Table may not exist


@pytest.mark.integration
def test_delete_table_real(backend, test_bucket, test_table_name):
    """Delete a table - hits REAL GraphQL API."""
    unique_table = f"{test_table_name}_delete"

    try:
        # Create table
        create_result = backend.create_tabulator_table(
            bucket=test_bucket, table_name=unique_table, config=EXAMPLE_CONFIG_YAML
        )
        assert create_result.get('__typename') == 'BucketSetTabulatorTableSuccess'

        # Delete table
        delete_result = backend.delete_tabulator_table(test_bucket, unique_table)
        assert delete_result.get('__typename') == 'BucketSetTabulatorTableSuccess', f"Delete failed: {delete_result}"

        print(f"\n✅ Deleted table '{unique_table}' from {test_bucket}")

        # Verify table no longer exists
        tables = backend.list_tabulator_tables(test_bucket)
        table_names = [t.get('name') for t in tables]
        assert unique_table not in table_names, f"Table '{unique_table}' still exists after deletion"

    except Exception as e:
        pytest.fail(f"Delete table failed: {e}")


@pytest.mark.integration
def test_error_handling_bucket_not_found(backend):
    """Test error handling for nonexistent bucket - REAL API call."""
    nonexistent_bucket = "nonexistent-bucket-12345-test"

    try:
        # This should raise an exception or return error response
        with pytest.raises(Exception) as exc_info:
            backend.list_tabulator_tables(nonexistent_bucket)

        error_msg = str(exc_info.value)
        assert any(word in error_msg.lower() for word in ['bucket', 'not found', 'does not exist']), (
            f"Expected bucket-related error, got: {error_msg}"
        )

        print("\n✅ Correctly handled nonexistent bucket error")

    except Exception as e:
        # If it didn't raise, check if it returned an error response
        pytest.fail(f"Expected exception for nonexistent bucket, got: {e}")


@pytest.mark.integration
def test_error_handling_table_not_found(backend, test_bucket):
    """Test error handling for nonexistent table - REAL API call."""
    nonexistent_table = "nonexistent_table_12345"

    try:
        with pytest.raises(Exception) as exc_info:
            backend.get_tabulator_table(test_bucket, nonexistent_table)

        error_msg = str(exc_info.value)
        assert any(word in error_msg.lower() for word in ['table', 'not found']), (
            f"Expected table-related error, got: {error_msg}"
        )

        print("\n✅ Correctly handled nonexistent table error")

    except Exception as e:
        pytest.fail(f"Expected exception for nonexistent table, got: {e}")


@pytest.mark.integration
def test_full_lifecycle_real(backend, test_bucket, test_table_name):
    """Test complete table lifecycle - ALL REAL API calls.

    This test:
    1. Creates a table
    2. Lists tables (verifies it exists)
    3. Gets the specific table
    4. Renames the table
    5. Verifies new name
    6. Deletes the table
    7. Verifies deletion

    Every step hits the REAL backend - NO MOCKS!
    """
    original_name = f"{test_table_name}_lifecycle"
    renamed_name = f"{test_table_name}_lifecycle_renamed"

    try:
        # Step 1: Create
        print(f"\n[Step 1] Creating table '{original_name}'...")
        create_result = backend.create_tabulator_table(
            bucket=test_bucket, table_name=original_name, config=EXAMPLE_CONFIG_YAML
        )
        assert create_result.get('__typename') == 'BucketSetTabulatorTableSuccess'
        print("✅ Created")

        # Step 2: List (verify exists)
        print("[Step 2] Listing tables...")
        tables = backend.list_tabulator_tables(test_bucket)
        table_names = [t.get('name') for t in tables]
        assert original_name in table_names
        print(f"✅ Found '{original_name}' in list")

        # Step 3: Get specific table
        print("[Step 3] Getting table details...")
        table = backend.get_tabulator_table(test_bucket, original_name)
        assert table.get('name') == original_name
        assert 'config' in table
        print(f"✅ Retrieved details for '{original_name}'")

        # Step 4: Rename
        print(f"[Step 4] Renaming '{original_name}' → '{renamed_name}'...")
        rename_result = backend.rename_tabulator_table(test_bucket, original_name, renamed_name)
        assert rename_result.get('__typename') == 'BucketSetTabulatorTableSuccess'
        print("✅ Renamed")

        # Step 5: Verify new name
        print("[Step 5] Verifying new name exists...")
        tables = backend.list_tabulator_tables(test_bucket)
        table_names = [t.get('name') for t in tables]
        assert renamed_name in table_names
        assert original_name not in table_names
        print(f"✅ Verified '{renamed_name}' exists, '{original_name}' gone")

        # Step 6: Delete
        print(f"[Step 6] Deleting table '{renamed_name}'...")
        delete_result = backend.delete_tabulator_table(test_bucket, renamed_name)
        assert delete_result.get('__typename') == 'BucketSetTabulatorTableSuccess'
        print("✅ Deleted")

        # Step 7: Verify deletion
        print("[Step 7] Verifying deletion...")
        tables = backend.list_tabulator_tables(test_bucket)
        table_names = [t.get('name') for t in tables]
        assert renamed_name not in table_names
        print(f"✅ Verified '{renamed_name}' no longer exists")

        print("\n🎉 Full lifecycle test completed successfully!")

    except Exception as e:
        pytest.fail(f"Full lifecycle test failed: {e}")

    finally:
        # Cleanup both possible names
        for name in [original_name, renamed_name]:
            try:
                backend.delete_tabulator_table(test_bucket, name)
            except:
                pass  # Table may not exist


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

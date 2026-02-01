"""Unit tests for TabulatorMixin."""

import pytest
from unittest.mock import Mock
from quilt_mcp.ops.tabulator_mixin import TabulatorMixin
from quilt_mcp.ops.exceptions import BackendError, ValidationError


class MockBackend(TabulatorMixin):
    """Mock backend for testing mixin."""

    def __init__(self):
        self.execute_graphql_query = Mock()


def test_list_tabulator_tables_success():
    """Test listing tables successfully."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {
            'bucketConfig': {
                'tabulatorTables': [
                    {'name': 'table1', 'config': 'schema: ...'},
                    {'name': 'table2', 'config': 'schema: ...'},
                ]
            }
        }
    }

    tables = backend.list_tabulator_tables('test-bucket')

    assert len(tables) == 2
    assert tables[0]['name'] == 'table1'
    assert tables[1]['name'] == 'table2'
    backend.execute_graphql_query.assert_called_once()

    # Verify query structure
    call_args = backend.execute_graphql_query.call_args
    assert 'bucketConfig' in call_args[0][0]
    assert call_args[0][1] == {'name': 'test-bucket'}


def test_list_tabulator_tables_bucket_not_found():
    """Test error when bucket not found."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {'data': {'bucketConfig': None}}

    with pytest.raises(ValidationError, match="Bucket not found"):
        backend.list_tabulator_tables('nonexistent')


def test_list_tabulator_tables_empty():
    """Test listing tables when bucket has no tables."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {'data': {'bucketConfig': {'tabulatorTables': []}}}

    tables = backend.list_tabulator_tables('test-bucket')

    assert len(tables) == 0
    assert tables == []


def test_list_tabulator_tables_backend_error():
    """Test backend error handling."""
    backend = MockBackend()
    backend.execute_graphql_query.side_effect = Exception("Network error")

    with pytest.raises(BackendError, match="Failed to list tabulator tables"):
        backend.list_tabulator_tables('test-bucket')


def test_get_tabulator_table_success():
    """Test getting a specific table."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {
            'bucketConfig': {
                'tabulatorTables': [
                    {'name': 'table1', 'config': 'schema: ...'},
                    {'name': 'table2', 'config': 'config: ...'},
                ]
            }
        }
    }

    table = backend.get_tabulator_table('test-bucket', 'table2')

    assert table['name'] == 'table2'
    assert table['config'] == 'config: ...'


def test_get_tabulator_table_not_found():
    """Test error when table not found."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {'bucketConfig': {'tabulatorTables': [{'name': 'table1', 'config': 'schema: ...'}]}}
    }

    with pytest.raises(ValidationError, match="Table not found: nonexistent"):
        backend.get_tabulator_table('test-bucket', 'nonexistent')


def test_create_tabulator_table_success():
    """Test creating a table successfully."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {
            'bucketSetTabulatorTable': {
                '__typename': 'BucketConfig',
                'bucketConfig': {
                    'name': 'test-bucket',
                    'tabulatorTables': [{'name': 'my-table', 'config': 'schema: ...'}],
                },
            }
        }
    }

    result = backend.create_tabulator_table('test-bucket', 'my-table', 'schema: ...')

    assert result['__typename'] == 'BucketConfig'
    assert result['bucketConfig']['name'] == 'test-bucket'

    # Verify mutation call
    call_args = backend.execute_graphql_query.call_args
    assert 'bucketSetTabulatorTable' in call_args[0][0]
    assert call_args[0][1] == {'bucketName': 'test-bucket', 'tableName': 'my-table', 'config': 'schema: ...'}


def test_create_tabulator_table_invalid_config():
    """Test error handling for invalid config."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {'bucketSetTabulatorTable': {'__typename': 'InvalidInput', 'message': 'Invalid YAML syntax'}}
    }

    with pytest.raises(ValidationError, match="Invalid configuration"):
        backend.create_tabulator_table('test-bucket', 'my-table', 'bad yaml')


def test_create_tabulator_table_bucket_not_found():
    """Test error handling when bucket not found."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {'bucketSetTabulatorTable': {'__typename': 'BucketNotFound', 'message': 'Bucket does not exist'}}
    }

    with pytest.raises(ValidationError, match="Bucket not found"):
        backend.create_tabulator_table('nonexistent', 'my-table', 'schema: ...')


def test_create_tabulator_table_permission_denied():
    """Test error handling when user lacks permission."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {'bucketSetTabulatorTable': {'__typename': 'BucketNotAllowed', 'message': 'Permission denied'}}
    }

    with pytest.raises(PermissionError, match="Not authorized for bucket"):
        backend.create_tabulator_table('test-bucket', 'my-table', 'schema: ...')


def test_create_tabulator_table_backend_error():
    """Test backend error during table creation."""
    backend = MockBackend()
    backend.execute_graphql_query.side_effect = Exception("Connection timeout")

    with pytest.raises(BackendError, match="Failed to create/update tabulator table"):
        backend.create_tabulator_table('test-bucket', 'my-table', 'schema: ...')


def test_update_tabulator_table():
    """Test update is alias for create."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {
            'bucketSetTabulatorTable': {
                '__typename': 'BucketConfig',
                'bucketConfig': {'name': 'test-bucket'},
            }
        }
    }

    result = backend.update_tabulator_table('test-bucket', 'my-table', 'updated: config')

    assert result['__typename'] == 'BucketConfig'

    # Verify it used the create mutation
    call_args = backend.execute_graphql_query.call_args
    assert call_args[0][1]['config'] == 'updated: config'


def test_rename_tabulator_table_success():
    """Test renaming a table successfully."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {
            'bucketRenameTabulatorTable': {
                '__typename': 'BucketConfig',
                'bucketConfig': {
                    'name': 'test-bucket',
                    'tabulatorTables': [{'name': 'new-name', 'config': 'schema: ...'}],
                },
            }
        }
    }

    result = backend.rename_tabulator_table('test-bucket', 'old-name', 'new-name')

    assert result['__typename'] == 'BucketConfig'

    # Verify mutation call
    call_args = backend.execute_graphql_query.call_args
    assert 'bucketRenameTabulatorTable' in call_args[0][0]
    assert call_args[0][1] == {'bucketName': 'test-bucket', 'tableName': 'old-name', 'newTableName': 'new-name'}


def test_rename_tabulator_table_invalid():
    """Test error handling for invalid rename."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {'bucketRenameTabulatorTable': {'__typename': 'InvalidInput', 'message': 'Table not found'}}
    }

    with pytest.raises(ValidationError, match="Invalid rename"):
        backend.rename_tabulator_table('test-bucket', 'old', 'new')


def test_rename_tabulator_table_permission_denied():
    """Test error handling when rename permission denied."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {'bucketRenameTabulatorTable': {'__typename': 'BucketNotAllowed', 'message': 'No write access'}}
    }

    with pytest.raises(PermissionError, match="Not authorized"):
        backend.rename_tabulator_table('test-bucket', 'old', 'new')


def test_rename_tabulator_table_backend_error():
    """Test backend error during rename."""
    backend = MockBackend()
    backend.execute_graphql_query.side_effect = Exception("Server error")

    with pytest.raises(BackendError, match="Failed to rename tabulator table"):
        backend.rename_tabulator_table('test-bucket', 'old', 'new')


def test_delete_tabulator_table_success():
    """Test deleting a table (sets config to null)."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {
            'bucketSetTabulatorTable': {
                '__typename': 'BucketConfig',
                'bucketConfig': {'name': 'test-bucket'},
            }
        }
    }

    result = backend.delete_tabulator_table('test-bucket', 'my-table')

    assert result['__typename'] == 'BucketConfig'

    # Verify it called create with config=None
    call_args = backend.execute_graphql_query.call_args
    assert call_args[0][1]['config'] is None
    assert call_args[0][1]['tableName'] == 'my-table'


def test_delete_tabulator_table_backend_error():
    """Test backend error during deletion."""
    backend = MockBackend()
    backend.execute_graphql_query.side_effect = Exception("Delete failed")

    with pytest.raises(BackendError, match="Failed to create/update tabulator table"):
        backend.delete_tabulator_table('test-bucket', 'my-table')


def test_mixin_requires_execute_graphql_query():
    """Test that mixin requires execute_graphql_query method."""

    class IncompleteBackend(TabulatorMixin):
        pass

    backend = IncompleteBackend()

    # Should raise BackendError (wrapping AttributeError) when trying to call without execute_graphql_query
    with pytest.raises(BackendError, match="Failed to list tabulator tables"):
        backend.list_tabulator_tables('test-bucket')

# TabulatorMixin: Shared GraphQL Implementation

**Status:** Design Phase
**Created:** 2026-02-01
**Purpose:** Implement Tabulator operations as a shared mixin for both backends

## Overview

Tabulator operations are pure GraphQL with no backend-specific logic. By implementing them as a **mixin class**, both Quilt3_Backend and Platform_Backend can share the same implementation.

**Key Decision:** NO backward compatibility - fully migrate from standalone TabulatorService to backend mixin pattern.

## Architecture: TabulatorMixin Pattern

```python
# Shared mixin implementation
class TabulatorMixin:
    """Shared Tabulator operations using GraphQL."""

    def list_tabulator_tables(self, bucket: str) -> List[Dict]:
        # Calls self.execute_graphql_query() - implemented by backend
        ...

# Both backends inherit the mixin
class Quilt3_Backend(TabulatorMixin, ...): pass
class Platform_Backend(TabulatorMixin, QuiltOps): pass
```

**Benefits:**

- ✅ Write once, use in both backends
- ✅ Maintains architectural patterns (QuiltOps stays abstract)
- ✅ Template method pattern (mixin calls abstract execute_graphql_query)
- ✅ Easy to test and maintain

## Implementation

### File: `src/quilt_mcp/ops/tabulator_mixin.py`

```python
"""Shared Tabulator operations using GraphQL.

This mixin provides table management for Quilt tabulator functionality.
Works with any backend implementing execute_graphql_query().
"""

from typing import List, Dict, Any, Optional
from ..exceptions import BackendError, ValidationError


class TabulatorMixin:
    """Shared Tabulator operations using GraphQL.

    This mixin provides Tabulator table management operations that work
    with any backend implementing execute_graphql_query().

    Requires the including class to implement:
        - execute_graphql_query(query: str, variables: Optional[Dict]) -> Dict
    """

    def list_tabulator_tables(self, bucket: str) -> List[Dict[str, str]]:
        """List all tabulator tables in a bucket.

        Args:
            bucket: S3 bucket name

        Returns:
            List of dicts with 'name' and 'config' (YAML string) keys

        Raises:
            BackendError: If GraphQL query fails
            ValidationError: If bucket not found
        """
        query = """
        query ListTabulatorTables($name: String!) {
          bucketConfig(name: $name) {
            tabulatorTables {
              name
              config
            }
          }
        }
        """

        try:
            result = self.execute_graphql_query(query, {"name": bucket})
        except Exception as e:
            raise BackendError(
                f"Failed to list tabulator tables: {str(e)}",
                context={"bucket": bucket}
            ) from e

        # Extract tables from GraphQL response
        bucket_config = result.get('data', {}).get('bucketConfig')
        if not bucket_config:
            raise ValidationError(f"Bucket not found: {bucket}")

        tables = bucket_config.get('tabulatorTables', [])
        return tables

    def get_tabulator_table(self, bucket: str, table_name: str) -> Dict[str, str]:
        """Get a specific tabulator table configuration.

        Args:
            bucket: S3 bucket name
            table_name: Table name

        Returns:
            Dict with 'name' and 'config' (YAML string) keys

        Raises:
            BackendError: If GraphQL query fails
            ValidationError: If table not found
        """
        tables = self.list_tabulator_tables(bucket)

        for table in tables:
            if table['name'] == table_name:
                return table

        raise ValidationError(f"Table not found: {table_name}")

    def create_tabulator_table(
        self,
        bucket: str,
        table_name: str,
        config: str
    ) -> Dict[str, Any]:
        """Create or update a tabulator table.

        Args:
            bucket: S3 bucket name
            table_name: Table name
            config: YAML configuration string

        Returns:
            Dict with operation result

        Raises:
            BackendError: If GraphQL mutation fails
            ValidationError: If configuration is invalid
            PermissionError: If user lacks write access
        """
        mutation = """
        mutation SetTabulatorTable(
          $bucketName: String!
          $tableName: String!
          $config: String
        ) {
          bucketSetTabulatorTable(
            bucketName: $bucketName
            tableName: $tableName
            config: $config
          ) {
            ... on BucketSetTabulatorTableSuccess {
              bucketConfig {
                name
                tabulatorTables {
                  name
                  config
                }
              }
            }
            ... on InvalidInput {
              message
            }
            ... on BucketNotFound {
              message
            }
            ... on BucketNotAllowed {
              message
            }
          }
        }
        """

        try:
            result = self.execute_graphql_query(mutation, {
                "bucketName": bucket,
                "tableName": table_name,
                "config": config
            })
        except Exception as e:
            raise BackendError(
                f"Failed to create/update tabulator table: {str(e)}",
                context={"bucket": bucket, "table_name": table_name}
            ) from e

        # Check for GraphQL errors
        data = result.get('data', {}).get('bucketSetTabulatorTable', {})
        typename = data.get('__typename')

        if typename == 'InvalidInput':
            raise ValidationError(f"Invalid configuration: {data.get('message')}")
        elif typename == 'BucketNotFound':
            raise ValidationError(f"Bucket not found: {data.get('message')}")
        elif typename == 'BucketNotAllowed':
            raise PermissionError(f"Not authorized for bucket: {data.get('message')}")

        return data

    def update_tabulator_table(
        self,
        bucket: str,
        table_name: str,
        config: str
    ) -> Dict[str, Any]:
        """Update an existing tabulator table configuration.

        This is an alias for create_tabulator_table() since the GraphQL
        mutation handles both create and update.

        Args:
            bucket: S3 bucket name
            table_name: Table name
            config: YAML configuration string

        Returns:
            Dict with operation result
        """
        return self.create_tabulator_table(bucket, table_name, config)

    def rename_tabulator_table(
        self,
        bucket: str,
        old_name: str,
        new_name: str
    ) -> Dict[str, Any]:
        """Rename a tabulator table.

        Args:
            bucket: S3 bucket name
            old_name: Current table name
            new_name: New table name

        Returns:
            Dict with operation result

        Raises:
            BackendError: If GraphQL mutation fails
            ValidationError: If old table not found or new name invalid
        """
        mutation = """
        mutation RenameTabulatorTable(
          $bucketName: String!
          $tableName: String!
          $newTableName: String!
        ) {
          bucketRenameTabulatorTable(
            bucketName: $bucketName
            tableName: $tableName
            newTableName: $newTableName
          ) {
            ... on BucketSetTabulatorTableSuccess {
              bucketConfig {
                name
                tabulatorTables {
                  name
                  config
                }
              }
            }
            ... on InvalidInput {
              message
            }
            ... on BucketNotFound {
              message
            }
            ... on BucketNotAllowed {
              message
            }
          }
        }
        """

        try:
            result = self.execute_graphql_query(mutation, {
                "bucketName": bucket,
                "tableName": old_name,
                "newTableName": new_name
            })
        except Exception as e:
            raise BackendError(
                f"Failed to rename tabulator table: {str(e)}",
                context={"bucket": bucket, "old_name": old_name, "new_name": new_name}
            ) from e

        # Check for GraphQL errors
        data = result.get('data', {}).get('bucketRenameTabulatorTable', {})
        typename = data.get('__typename')

        if typename == 'InvalidInput':
            raise ValidationError(f"Invalid rename: {data.get('message')}")
        elif typename == 'BucketNotFound':
            raise ValidationError(f"Bucket not found: {data.get('message')}")
        elif typename == 'BucketNotAllowed':
            raise PermissionError(f"Not authorized: {data.get('message')}")

        return data

    def delete_tabulator_table(
        self,
        bucket: str,
        table_name: str
    ) -> Dict[str, Any]:
        """Delete a tabulator table.

        Deletion is implemented by setting config to null.

        Args:
            bucket: S3 bucket name
            table_name: Table name to delete

        Returns:
            Dict with operation result

        Raises:
            BackendError: If GraphQL mutation fails
        """
        return self.create_tabulator_table(bucket, table_name, None)
```

## Backend Integration

### Update: `src/quilt_mcp/backends/quilt3_backend.py`

```python
from ..ops.tabulator_mixin import TabulatorMixin

class Quilt3_Backend(
    TabulatorMixin,              # Add first for highest priority in MRO
    Quilt3_Backend_Session,
    Quilt3_Backend_Buckets,
    Quilt3_Backend_Content,
    Quilt3_Backend_Packages,
    Quilt3_Backend_Admin,
    Quilt3_Backend_Base,
    QuiltOps,
):
    """Backend implementation using quilt3 library."""

    @property
    def admin(self):
        """Access to admin operations."""
        return self
```

### Update: `src/quilt_mcp/backends/platform_backend.py`

```python
from ..ops.tabulator_mixin import TabulatorMixin

class Platform_Backend(TabulatorMixin, QuiltOps):
    """Platform GraphQL backend implementation."""

    def __init__(self):
        # ... existing JWT setup ...
        pass
```

## Tools Migration

### Current: `src/quilt_mcp/tools/tabulator.py`

**Old pattern** (calls TabulatorService):

```python
from ..services.tabulator_service import get_tabulator_service

def list_tabulator_tables(bucket: str):
    service = get_tabulator_service()
    return service.list_tables(bucket)
```

**New pattern** (calls backend directly):

```python
from ..ops.factory import QuiltOpsFactory

def list_tabulator_tables(bucket: str) -> List[Dict[str, str]]:
    """List tabulator tables in bucket.

    Args:
        bucket: S3 bucket name

    Returns:
        List of tables with name and config
    """
    backend = QuiltOpsFactory.create()
    return backend.list_tabulator_tables(bucket)

def create_tabulator_table(bucket: str, table_name: str, config: str) -> Dict[str, Any]:
    """Create or update tabulator table.

    Args:
        bucket: S3 bucket name
        table_name: Table name
        config: YAML configuration string

    Returns:
        Operation result
    """
    backend = QuiltOpsFactory.create()
    return backend.create_tabulator_table(bucket, table_name, config)

def rename_tabulator_table(bucket: str, old_name: str, new_name: str) -> Dict[str, Any]:
    """Rename tabulator table.

    Args:
        bucket: S3 bucket name
        old_name: Current table name
        new_name: New table name

    Returns:
        Operation result
    """
    backend = QuiltOpsFactory.create()
    return backend.rename_tabulator_table(bucket, old_name, new_name)

def delete_tabulator_table(bucket: str, table_name: str) -> Dict[str, Any]:
    """Delete tabulator table.

    Args:
        bucket: S3 bucket name
        table_name: Table name to delete

    Returns:
        Operation result
    """
    backend = QuiltOpsFactory.create()
    return backend.delete_tabulator_table(bucket, table_name)
```

## Files to Remove (NO backward compatibility)

### Delete: `src/quilt_mcp/services/tabulator_service.py`

586 lines - no longer needed, functionality moved to TabulatorMixin

### Update: `src/quilt_mcp/tools/__init__.py`

Remove TabulatorService registration:

```python
# OLD - DELETE THIS
"tabulator": "quilt_mcp.services.tabulator_service",

# Tools now use backend directly via QuiltOpsFactory
```

## Testing Strategy

### Unit Tests: `tests/unit/ops/test_tabulator_mixin.py`

```python
"""Unit tests for TabulatorMixin."""

import pytest
from unittest.mock import Mock
from quilt_mcp.ops.tabulator_mixin import TabulatorMixin
from quilt_mcp.exceptions import BackendError, ValidationError


class MockBackend(TabulatorMixin):
    """Mock backend for testing mixin."""

    def __init__(self):
        self.execute_graphql_query = Mock()


def test_list_tabulator_tables():
    """Test listing tables."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {
            'bucketConfig': {
                'tabulatorTables': [
                    {'name': 'table1', 'config': 'schema: ...'},
                    {'name': 'table2', 'config': 'schema: ...'}
                ]
            }
        }
    }

    tables = backend.list_tabulator_tables('test-bucket')

    assert len(tables) == 2
    assert tables[0]['name'] == 'table1'
    backend.execute_graphql_query.assert_called_once()


def test_list_tabulator_tables_bucket_not_found():
    """Test error when bucket not found."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {'bucketConfig': None}
    }

    with pytest.raises(ValidationError, match="Bucket not found"):
        backend.list_tabulator_tables('nonexistent')


def test_create_tabulator_table():
    """Test creating a table."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {
            'bucketSetTabulatorTable': {
                '__typename': 'BucketSetTabulatorTableSuccess',
                'bucketConfig': {'name': 'test-bucket'}
            }
        }
    }

    result = backend.create_tabulator_table(
        'test-bucket',
        'my-table',
        'schema: ...'
    )

    assert result['__typename'] == 'BucketSetTabulatorTableSuccess'


def test_create_tabulator_table_invalid_config():
    """Test error handling for invalid config."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {
            'bucketSetTabulatorTable': {
                '__typename': 'InvalidInput',
                'message': 'Invalid YAML'
            }
        }
    }

    with pytest.raises(ValidationError, match="Invalid configuration"):
        backend.create_tabulator_table('test-bucket', 'my-table', 'bad yaml')


def test_delete_tabulator_table():
    """Test deleting a table (sets config to null)."""
    backend = MockBackend()
    backend.execute_graphql_query.return_value = {
        'data': {
            'bucketSetTabulatorTable': {
                '__typename': 'BucketSetTabulatorTableSuccess'
            }
        }
    }

    backend.delete_tabulator_table('test-bucket', 'my-table')

    # Verify it called create with config=None
    call_args = backend.execute_graphql_query.call_args
    assert call_args[0][1]['config'] is None
```

### Integration Tests: `tests/integration/test_tabulator_backends.py`

```python
"""Integration tests for Tabulator with both backends."""

import pytest
from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
from quilt_mcp.backends.platform_backend import Platform_Backend


@pytest.mark.integration
def test_tabulator_quilt3_backend():
    """Test Tabulator operations with Quilt3_Backend."""
    backend = Quilt3_Backend()

    # List tables
    tables = backend.list_tabulator_tables('test-bucket')
    assert isinstance(tables, list)


@pytest.mark.integration
@pytest.mark.jwt
def test_tabulator_platform_backend(jwt_auth_context):
    """Test Tabulator operations with Platform_Backend."""
    backend = Platform_Backend()

    # List tables
    tables = backend.list_tabulator_tables('test-bucket')
    assert isinstance(tables, list)
```

### Update Existing Tests

**Migrate:** `tests/unit/test_tabulator.py` → `tests/unit/ops/test_tabulator_mixin.py`

**Migrate:** `tests/e2e/test_tabulator.py` → Update to use backend methods

## Migration Checklist

### Phase 1: Create Mixin

- [ ] Create `src/quilt_mcp/ops/tabulator_mixin.py`
- [ ] Add all GraphQL operations (list, create, rename, delete)
- [ ] Add error handling and transformations
- [ ] Write unit tests for mixin

### Phase 2: Integrate with Backends

- [ ] Add TabulatorMixin to Quilt3_Backend inheritance
- [ ] Add TabulatorMixin to Platform_Backend inheritance
- [ ] Verify MRO (Method Resolution Order) is correct
- [ ] Test that execute_graphql_query() is called correctly

### Phase 3: Migrate Tools

- [ ] Update `src/quilt_mcp/tools/tabulator.py` to call backend methods
- [ ] Remove TabulatorService import/usage
- [ ] Update tool docstrings and type hints
- [ ] Verify tools work with QuiltOpsFactory

### Phase 4: Remove Old Code

- [ ] Delete `src/quilt_mcp/services/tabulator_service.py`
- [ ] Remove TabulatorService from `src/quilt_mcp/tools/__init__.py`
- [ ] Update any imports that referenced TabulatorService
- [ ] Clean up old test fixtures

### Phase 5: Update Tests

- [ ] Migrate unit tests to test mixin directly
- [ ] Add integration tests for both backends
- [ ] Update E2E tests to use new pattern
- [ ] Verify all tabulator tests pass

## Validation

### Test Commands

```bash
# Unit tests
uv run pytest tests/unit/ops/test_tabulator_mixin.py -v

# Integration tests (both backends)
uv run pytest tests/integration/test_tabulator_backends.py -v

# All tabulator-related tests
uv run pytest -k tabulator -v

# Full test suite
make test-all
```

### Success Criteria

- [ ] TabulatorMixin implements all operations
- [ ] Both backends inherit and use mixin correctly
- [ ] Tools call backend methods successfully
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] No references to old TabulatorService remain
- [ ] GraphQL queries execute successfully
- [ ] Error handling works correctly

## Benefits of This Approach

1. **Code Reuse** - Write once, use in both backends
2. **Consistency** - Identical behavior across backends
3. **Maintainability** - Single source of truth for Tabulator logic
4. **Template Pattern** - Mixin calls abstract execute_graphql_query()
5. **Clean Architecture** - Follows existing mixin pattern
6. **Type Safety** - Full type hints throughout
7. **Testability** - Easy to mock and test

## References

- Current implementation: [tabulator_service.py](../../src/quilt_mcp/services/tabulator_service.py)
- GraphQL schema: [02-graphql.md](02-graphql.md#tabulator-api---dual-interface)
- QuiltOps interface: [quilt_ops.py](../../src/quilt_mcp/ops/quilt_ops.py)
- Mixin pattern example: [quilt3_backend_session.py](../../src/quilt_mcp/backends/quilt3_backend_session.py)

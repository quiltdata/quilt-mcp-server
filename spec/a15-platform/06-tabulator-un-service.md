# Tabulator Service Deconstruction

## Problem

`tabulator_service.py` defeats the purpose of TabulatorMixin by reintroducing quilt3 dependencies:

1. **Admin operations use `quilt3.admin.tabulator`** - This reintroduces the quilt3 dependency that TabulatorMixin was designed to eliminate
2. **Query operations are thin wrappers** - Just call athena_read_service with slightly different parameters

## Goals

1. **Eliminate quilt3 dependency** - Move admin operations to GraphQL in TabulatorMixin
2. **Simplify architecture** - Remove unnecessary service wrapper layer
3. **Maintain functionality** - All existing features work via GraphQL/Athena

## Current State

### tabulator_service.py contains:

**Admin operations (TabulatorService class):**
- `get_open_query_status()` - Uses `quilt3.admin.tabulator.get_open_query()`
- `set_open_query(enabled: bool)` - Uses `quilt3.admin.tabulator.set_open_query()`

**Query operations (module functions):**
- `_tabulator_query()` - Calls `athena_query_execute()` with tabulator catalog
- `list_tabulator_buckets()` - Executes `SHOW DATABASES` query
- `tabulator_buckets_list()` - Async wrapper for list_tabulator_buckets
- `tabulator_bucket_query()` - Query with database_name parameter

### Current usage:

```bash
$ grep -r "from quilt_mcp.services.tabulator_service import" src/
src/quilt_mcp/tools/tabulator.py:        from quilt_mcp.services.tabulator_service import get_tabulator_service
src/quilt_mcp/tools/tabulator.py:        from quilt_mcp.services.tabulator_service import list_tabulator_buckets
src/quilt_mcp/tools/tabulator.py:        from quilt_mcp.services.tabulator_service import tabulator_bucket_query as service_query
src/quilt_mcp/resources.py:308:        from quilt_mcp.services.tabulator_service import list_tabulator_buckets
```

## Solution

### 1. Move Admin Operations to TabulatorMixin (GraphQL)

Add GraphQL mutations to TabulatorMixin:

```python
# In ops/tabulator_mixin.py

def get_open_query_status(self) -> Dict[str, Any]:
    """Get tabulator open query status via GraphQL."""
    query = """
    query GetOpenQueryStatus {
        admin {
            tabulatorOpenQuery
        }
    }
    """
    try:
        result = self.execute_graphql_query(query)
        enabled = result.get("data", {}).get("admin", {}).get("tabulatorOpenQuery", False)
        return {
            "success": True,
            "open_query_enabled": enabled,
        }
    except Exception as exc:
        raise BackendError(f"Failed to get open query status: {exc}")

def set_open_query(self, enabled: bool) -> Dict[str, Any]:
    """Set tabulator open query status via GraphQL."""
    mutation = """
    mutation SetOpenQuery($enabled: Boolean!) {
        admin {
            setTabulatorOpenQuery(enabled: $enabled) {
                tabulatorOpenQuery
            }
        }
    }
    """
    try:
        result = self.execute_graphql_query(mutation, variables={"enabled": enabled})
        current = result.get("data", {}).get("admin", {}).get("setTabulatorOpenQuery", {}).get("tabulatorOpenQuery", enabled)
        return {
            "success": True,
            "open_query_enabled": current,
            "message": f"Open query {'enabled' if current else 'disabled'}",
        }
    except Exception as exc:
        raise BackendError(f"Failed to set open query status: {exc}")
```

### 2. Move Query Operations to Athena Service

Add tabulator-specific helpers to `athena_read_service.py`:

```python
# In services/athena_read_service.py

def tabulator_query_execute(
    query: str,
    database_name: Optional[str] = None,
    workgroup_name: Optional[str] = None,
    max_results: int = 1000,
    output_format: Literal["json", "csv", "parquet", "table"] = "json",
    use_quilt_auth: bool = True,
) -> Dict[str, Any]:
    """Execute a query against the Tabulator catalog.

    This is a convenience wrapper that automatically uses the tabulator data catalog.
    """
    try:
        from quilt_mcp.services import auth_metadata

        info = auth_metadata.catalog_info()
        if not info.get("tabulator_data_catalog"):
            return format_error_response(
                "tabulator_data_catalog not configured. This requires a Tabulator-enabled catalog."
            )

        data_catalog_name = info["tabulator_data_catalog"]

        return athena_query_execute(
            query=query,
            database_name=database_name,
            workgroup_name=workgroup_name,
            data_catalog_name=data_catalog_name,
            max_results=max_results,
            output_format=output_format,
            use_quilt_auth=use_quilt_auth,
        )
    except Exception as exc:
        logger.error(f"Failed to execute tabulator query: {exc}")
        return format_error_response(f"Failed to execute tabulator query: {exc}")


def tabulator_list_buckets() -> Dict[str, Any]:
    """List all buckets (databases) in the Tabulator catalog."""
    try:
        result = tabulator_query_execute("SHOW DATABASES")

        if not result.get("success"):
            return result

        buckets: List[str] = []
        formatted_data = result.get("formatted_data", [])

        for row in formatted_data:
            bucket_name = row.get("database_name") or row.get("db_name") or row.get("name")
            if bucket_name:
                buckets.append(bucket_name)

        return {
            "success": True,
            "buckets": buckets,
            "count": len(buckets),
            "message": f"Found {len(buckets)} bucket(s) in Tabulator catalog",
        }
    except Exception as exc:
        logger.error(f"Failed to list tabulator buckets: {exc}")
        return format_error_response(f"Failed to list tabulator buckets: {exc}")
```

### 3. Update Tool Layer

Update `tools/tabulator.py` to use new locations:

```python
# Admin operations - use backend's TabulatorMixin
@mcp.tool()
async def tabulator_admin_open_query_status() -> str:
    """Get tabulator open query status."""
    try:
        backend = get_backend()
        result = backend.get_open_query_status()
        return format_tool_response(result)
    except Exception as exc:
        return format_tool_error(f"Failed to get open query status: {exc}")

@mcp.tool()
async def tabulator_admin_set_open_query(enabled: bool) -> str:
    """Enable or disable tabulator open query."""
    try:
        backend = get_backend()
        result = backend.set_open_query(enabled)
        return format_tool_response(result)
    except Exception as exc:
        return format_tool_error(f"Failed to set open query: {exc}")

# Query operations - use athena service
@mcp.tool()
async def tabulator_buckets_list() -> str:
    """List all buckets in the Tabulator catalog."""
    try:
        from quilt_mcp.services.athena_read_service import tabulator_list_buckets
        result = tabulator_list_buckets()
        return format_tool_response(result)
    except Exception as exc:
        return format_tool_error(f"Failed to list buckets: {exc}")

@mcp.tool()
async def tabulator_bucket_query(
    bucket_name: str,
    query: str,
    workgroup_name: Optional[str] = None,
    max_results: int = 1000,
    output_format: Literal["json", "csv", "parquet", "table"] = "json",
) -> str:
    """Execute a query against a specific bucket in Tabulator."""
    try:
        from quilt_mcp.services.athena_read_service import tabulator_query_execute

        result = tabulator_query_execute(
            query=query,
            database_name=bucket_name,
            workgroup_name=workgroup_name,
            max_results=max_results,
            output_format=output_format,
        )
        return format_tool_response(result)
    except Exception as exc:
        return format_tool_error(f"Failed to execute bucket query: {exc}")
```

### 4. Delete tabulator_service.py

Once all migrations are complete:
1. Remove `src/quilt_mcp/services/tabulator_service.py`
2. Update all imports across the codebase
3. Update tests to use new locations

## Implementation Steps

### Step 1: Add GraphQL Admin Operations to TabulatorMixin

**File:** `src/quilt_mcp/ops/tabulator_mixin.py`

- [ ] Add `get_open_query_status()` method
- [ ] Add `set_open_query()` method
- [ ] Test with real GraphQL endpoint

### Step 2: Add Tabulator Query Helpers to Athena Service

**File:** `src/quilt_mcp/services/athena_read_service.py`

- [ ] Add `tabulator_query_execute()` function
- [ ] Add `tabulator_list_buckets()` function
- [ ] Update `__all__` exports

### Step 3: Update Tool Layer

**File:** `src/quilt_mcp/tools/tabulator.py`

- [ ] Update admin tools to use `backend.get_open_query_status()`
- [ ] Update admin tools to use `backend.set_open_query()`
- [ ] Update bucket listing to use `athena_read_service.tabulator_list_buckets()`
- [ ] Update bucket query to use `athena_read_service.tabulator_query_execute()`

### Step 4: Update Resources (if needed)

**File:** `src/quilt_mcp/resources.py`

- [ ] Update imports from tabulator_service to athena_read_service

### Step 5: Update Tests

**Files:**
- `tests/unit/test_tabulator.py`
- `tests/integration/test_tabulator_integration.py`
- `tests/e2e/test_tabulator.py`
- `tests/e2e/test_formatting_integration.py`

- [ ] Update imports to new locations
- [ ] Update mocks to match new structure
- [ ] Ensure all tests pass

### Step 6: Delete tabulator_service.py

- [ ] Remove `src/quilt_mcp/services/tabulator_service.py`
- [ ] Verify no remaining imports

## Migration Guide

### For Admin Operations

**Before:**
```python
from quilt_mcp.services.tabulator_service import get_tabulator_service

service = get_tabulator_service()
result = service.get_open_query_status()
```

**After:**
```python
from quilt_mcp.backends import get_backend

backend = get_backend()
result = backend.get_open_query_status()
```

### For Query Operations

**Before:**
```python
from quilt_mcp.services.tabulator_service import (
    list_tabulator_buckets,
    tabulator_bucket_query
)

buckets = list_tabulator_buckets()
result = tabulator_bucket_query(bucket_name="my-bucket", query="SELECT * FROM table")
```

**After:**
```python
from quilt_mcp.services.athena_read_service import (
    tabulator_list_buckets,
    tabulator_query_execute
)

buckets = tabulator_list_buckets()
result = tabulator_query_execute(
    query="SELECT * FROM table",
    database_name="my-bucket"
)
```

## Benefits

1. **Eliminates quilt3 dependency** - Admin operations use GraphQL instead of quilt3.admin
2. **Cleaner architecture** - One backend layer (TabulatorMixin), one service layer (athena)
3. **Better separation of concerns** - Admin ops in backend, query ops in athena service
4. **Consistent patterns** - All tabulator operations follow same patterns as other features
5. **Easier testing** - Mock backend methods instead of quilt3 imports

## Risks & Mitigation

### Risk: GraphQL mutations for admin not available
**Mitigation:** Verify GraphQL schema supports admin.setTabulatorOpenQuery mutation before removing quilt3 code

### Risk: Breaking existing integrations
**Mitigation:** Update all imports in same commit, run full test suite

### Risk: Different behavior between quilt3.admin and GraphQL
**Mitigation:** Add integration tests comparing both approaches during transition

## Verification

After implementation:

1. **Unit tests pass:** `make test`
2. **Integration tests pass:** `make test-integration`
3. **E2E tests pass:** `make test-e2e`
4. **No quilt3 imports in services layer:** `grep -r "import quilt3" src/quilt_mcp/services/`
5. **No tabulator_service imports:** `grep -r "tabulator_service" src/`
6. **Admin operations work:** Test open query toggle via MCP tools
7. **Query operations work:** Test bucket listing and queries via MCP tools

## Timeline

- **Phase 1:** Add new methods to TabulatorMixin and athena_read_service (1-2 hours)
- **Phase 2:** Update tools layer (30 min)
- **Phase 3:** Update and fix all tests (1-2 hours)
- **Phase 4:** Delete tabulator_service.py and verify (30 min)

**Total estimated time:** 3-5 hours

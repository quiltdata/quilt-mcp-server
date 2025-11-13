# Convert FastMCP Resources to Tools - Specification

## Problem Statement

FastMCP is not properly registering resource templates with URI parameters. The following resources are NOT being registered by the server:

- `permissions://buckets/{bucket}/access`
- `admin://users/{name}`
- `athena://databases/{database}/tables`
- `athena://databases/{database}/tables/{table}/schema`
- `tabulator://buckets/{bucket}/tables`

These should be **removed as resources** and **exposed as tools** instead.

## Current Implementation

### Location: [src/quilt_mcp/resources.py](src/quilt_mcp/resources.py)

The problematic resources are defined using `@mcp.resource()` decorators:

```python
@mcp.resource(
    "permissions://buckets/{bucket}/access",
    name="Bucket Access Check",
    description="Check access permissions for a specific bucket",
    mime_type="application/json",
)
async def bucket_access(bucket: str) -> str:
    """Check bucket access permissions."""
    from quilt_mcp.services.permissions_service import check_bucket_access

    result = await asyncio.to_thread(check_bucket_access, bucket=bucket)
    return _serialize_result(result)
```

## Solution: Convert to Tools

### Architecture Pattern

Following the existing tool pattern in the codebase:

1. **Service Layer** (already exists):
   - `src/quilt_mcp/services/permissions_service.py`
   - `src/quilt_mcp/services/governance_service.py`
   - `src/quilt_mcp/services/athena_read_service.py`
   - `src/quilt_mcp/services/tabulator_service.py`

2. **Tool Layer** (needs new file):
   - Create `src/quilt_mcp/tools/permissions.py`
   - Functions already exist in services, just need tool wrappers

3. **Registration** (update existing):
   - Add to `_MODULE_PATHS` in `src/quilt_mcp/tools/__init__.py`
   - Remove from `RESOURCE_AVAILABLE_TOOLS` in `src/quilt_mcp/utils.py`

### Resources to Convert

#### 1. Permissions - `check_bucket_access`

**Current Resource:**
- URI: `permissions://buckets/{bucket}/access`
- Function: [resources.py:124](src/quilt_mcp/resources.py#L124)
- Service: [permissions_service.py:103](src/quilt_mcp/services/permissions_service.py#L103)

**New Tool:**
```python
# src/quilt_mcp/tools/permissions.py

from typing import Annotated, Any, Dict, List, Optional
from pydantic import Field

def check_bucket_access(
    bucket: Annotated[
        str,
        Field(
            description="S3 bucket name to check access permissions for",
            examples=["my-bucket", "quilt-example"],
        ),
    ],
    operations: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="List of operations to test (default: ['read', 'write', 'list'])",
            examples=[["read", "write"], ["list"]],
        ),
    ] = None,
) -> Dict[str, Any]:
    """Check access permissions for a specific S3 bucket.

    Returns:
        Dict with keys:
        - success: bool
        - bucket_name: str
        - permission_level: str (e.g., "FULL_ACCESS", "READ_ONLY")
        - access_summary: dict with can_read, can_write, can_list
        - operation_tests: dict with test results
        - guidance: list of recommendations
        - quilt_compatible: bool

    Next step:
        Use the returned permissions info to determine if bucket is suitable for packages.

    Example:
        ```python
        from quilt_mcp.tools import permissions

        result = permissions.check_bucket_access("my-bucket")
        if result["quilt_compatible"]:
            print("Bucket is ready for Quilt packages!")
        ```
    """
    from quilt_mcp.services.permissions_service import check_bucket_access as _check

    return _check(bucket=bucket, operations=operations)
```

#### 2. Admin - `admin_user_get`

**Current Resource:**
- URI: `admin://users/{name}`
- Function: [resources.py:167](src/quilt_mcp/resources.py#L167)
- Service: [governance_service.py](src/quilt_mcp/services/governance_service.py) (async)

**New Tool:**
```python
# Add to src/quilt_mcp/services/governance_service.py OR create new file

def admin_user_get(
    name: Annotated[
        str,
        Field(
            description="Username to retrieve details for",
            examples=["john-doe", "data-scientist-1"],
        ),
    ],
) -> Dict[str, Any]:
    """Get detailed information about a specific user.

    Returns:
        Dict containing user details:
        - name: str
        - email: str
        - active: bool
        - admin: bool
        - role: str
        - extra_roles: list[str]
        - date_joined: str (ISO format)
        - last_seen: str (ISO format)

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_user_get(name="john-doe")
        print(f"User {result['name']} has role: {result['role']}")
        ```
    """
    # Service function is already async, needs sync wrapper
    import asyncio
    from quilt_mcp.services.governance_service import admin_user_get as _get

    return asyncio.run(_get(name=name))
```

#### 3. Athena - `athena_tables_list`

**Current Resource:**
- URI: `athena://databases/{database}/tables`
- Function: [resources.py:249](src/quilt_mcp/resources.py#L249)
- Service: [athena_read_service.py](src/quilt_mcp/services/athena_read_service.py)

**New Tool:**
```python
# Add to src/quilt_mcp/services/athena_read_service.py

def athena_tables_list(
    database: Annotated[
        str,
        Field(
            description="Athena database name",
            examples=["default", "quilt_packages", "my_data"],
        ),
    ],
    data_catalog_name: Annotated[
        str,
        Field(
            default="AwsDataCatalog",
            description="Data catalog name (default: AwsDataCatalog)",
        ),
    ] = "AwsDataCatalog",
    service: Optional[Any] = None,
) -> Dict[str, Any]:
    """List tables in an Athena database.

    Returns:
        Dict with keys:
        - success: bool
        - database: str
        - tables: list[dict] with name, type, location
        - count: int

    Next step:
        Pass identifiers or results on to analytics tooling or report them to the user.

    Example:
        ```python
        from quilt_mcp.tools import athena_glue

        result = athena_glue.athena_tables_list(database="my_database")
        for table in result["tables"]:
            print(f"Table: {table['name']}")
        ```
    """
    # Implementation already exists in the service
    # Just needs proper signature
    pass  # Implementation details...
```

#### 4. Athena - `athena_table_schema`

**Current Resource:**
- URI: `athena://databases/{database}/tables/{table}/schema`
- Function: [resources.py:262](src/quilt_mcp/resources.py#L262)
- Service: [athena_read_service.py](src/quilt_mcp/services/athena_read_service.py)

**New Tool:**
```python
# Add to src/quilt_mcp/services/athena_read_service.py

def athena_table_schema(
    database: Annotated[
        str,
        Field(
            description="Athena database name",
            examples=["default", "my_data"],
        ),
    ],
    table: Annotated[
        str,
        Field(
            description="Table name",
            examples=["my_table", "packages"],
        ),
    ],
    data_catalog_name: Annotated[
        str,
        Field(
            default="AwsDataCatalog",
            description="Data catalog name",
        ),
    ] = "AwsDataCatalog",
    service: Optional[Any] = None,
) -> Dict[str, Any]:
    """Get schema for a specific Athena table.

    Returns:
        Dict with keys:
        - success: bool
        - database: str
        - table: str
        - columns: list[dict] with name, type, comment
        - partition_keys: list[dict]
        - location: str (S3 URI)
        - input_format: str
        - output_format: str

    Next step:
        Pass identifiers or results on to analytics tooling or report them to the user.

    Example:
        ```python
        from quilt_mcp.tools import athena_glue

        result = athena_glue.athena_table_schema(
            database="my_db",
            table="my_table"
        )
        for col in result["columns"]:
            print(f"{col['name']}: {col['type']}")
        ```
    """
    # Implementation already exists
    pass  # Implementation details...
```

#### 5. Tabulator - `tabulator_tables_list`

**Current Resource:**
- URI: `tabulator://buckets/{bucket}/tables`
- Function: [resources.py:377](src/quilt_mcp/resources.py#L377)
- Service: [tabulator_service.py](src/quilt_mcp/services/tabulator_service.py)

**New Tool:**
```python
# Add to src/quilt_mcp/services/tabulator_service.py

def tabulator_tables_list(
    bucket: Annotated[
        str,
        Field(
            description="S3 bucket name (with or without s3:// prefix)",
            examples=["my-bucket", "s3://my-bucket"],
        ),
    ],
) -> Dict[str, Any]:
    """List tabulator tables in a specific bucket.

    Returns:
        Dict with keys:
        - success: bool
        - bucket: str
        - tables: list[dict] with name, schema, patterns
        - count: int

    Next step:
        Pass identifiers or results on to analytics tooling or report them to the user.

    Example:
        ```python
        from quilt_mcp.tools import tabulator

        result = tabulator.tabulator_tables_list(bucket="my-bucket")
        for table in result["tables"]:
            print(f"Table: {table['name']}")
        ```
    """
    # Service function already exists with bucket_name parameter
    # Need to handle parameter name mismatch
    from quilt_mcp.services.tabulator_service import tabulator_tables_list as _list

    # Remove s3:// prefix if present
    bucket_name = bucket.replace("s3://", "").split("/")[0]

    return _list(bucket_name=bucket_name)
```

## Implementation Plan

### Step 1: Create New Tool Files (if needed)

**Option A: Create new tool file**
- Create `src/quilt_mcp/tools/permissions.py`
- Move resource functions to tool format

**Option B: Add to existing service modules**
- Functions already exist in service modules
- Just add proper Pydantic Field annotations
- Already registered as tools via `_MODULE_PATHS`

**DECISION: Use Option B** - The service modules are already registered as tool sources in `_MODULE_PATHS`. We just need to ensure the functions have proper signatures.

### Step 2: Update Service Function Signatures

All service functions need proper Pydantic `Field` annotations for MCP tool registration:

1. `src/quilt_mcp/services/permissions_service.py`:
   - `check_bucket_access(bucket: str, ...)` - **Already has proper signature**

2. `src/quilt_mcp/services/governance_service.py`:
   - `admin_user_get(name: str)` - **Async, needs sync wrapper OR direct exposure**

3. `src/quilt_mcp/services/athena_read_service.py`:
   - `athena_tables_list(database: str, ...)` - **Check if exists with proper signature**
   - `athena_table_schema(database: str, table: str, ...)` - **Check parameter names**

4. `src/quilt_mcp/services/tabulator_service.py`:
   - `tabulator_tables_list(bucket_name: str)` - **Parameter name is `bucket_name` not `bucket`**

### Step 3: Remove Resource Decorators

Delete the following from [src/quilt_mcp/resources.py](src/quilt_mcp/resources.py):

1. Lines 118-129: `permissions://buckets/{bucket}/access` resource
2. Lines 161-172: `admin://users/{name}` resource
3. Lines 243-254: `athena://databases/{database}/tables` resource
4. Lines 256-267: `athena://databases/{database}/tables/{table}/schema` resource
5. Lines 371-382: `tabulator://buckets/{bucket}/tables` resource

### Step 4: Update Tool Registration

In [src/quilt_mcp/utils.py](src/quilt_mcp/utils.py), remove these from `RESOURCE_AVAILABLE_TOOLS` list:

```python
# BEFORE (lines 124-150+):
RESOURCE_AVAILABLE_TOOLS = [
    # ... existing entries ...
    "athena_databases_list",  # KEEP - this is static resource
    "athena_workgroups_list",  # KEEP - this is static resource
    # ... other static resources ...
]

# AFTER:
# Just verify these are NOT in the exclusion list anymore:
# - check_bucket_access
# - admin_user_get
# - athena_tables_list
# - athena_table_schema
# - tabulator_tables_list
```

### Step 5: Verify Service Functions Are Registered

The modules are already in `_MODULE_PATHS`:

```python
_MODULE_PATHS = {
    # ...
    "athena_glue": "quilt_mcp.services.athena_read_service",  # ✅ Already registered
    "tabulator": "quilt_mcp.services.tabulator_service",      # ✅ Already registered
    "governance": "quilt_mcp.services.governance_service",    # ✅ Already registered
    # ...
}
```

But `permissions_service` is NOT in `_MODULE_PATHS`:

```python
# NEED TO ADD:
"permissions": "quilt_mcp.services.permissions_service",
```

## Parameter Name Mismatches

### Issue: Service Parameter Names Don't Match Tool Expectations

Several service functions have parameter names that differ from what would be natural for tools:

| Service Function | Current Param | Natural Tool Param |
|------------------|---------------|-------------------|
| `check_bucket_access` | `bucket` | `bucket` ✅ |
| `admin_user_get` | `name` | `name` ✅ |
| `athena_tables_list` | `database` | `database` ✅ |
| `athena_table_schema` | `database`, `table` | `database`, `table` ✅ |
| `tabulator_tables_list` | `bucket_name` | `bucket` ❌ |

### Solution for `tabulator_tables_list`

**Option A: Change service function signature**
```python
# BEFORE
def tabulator_tables_list(bucket_name: str) -> Dict[str, Any]:

# AFTER
def tabulator_tables_list(bucket: str) -> Dict[str, Any]:
    # Update all call sites
```

**Option B: Create wrapper in tools module**
```python
# src/quilt_mcp/tools/tabulator.py (new file)
def tabulator_tables_list(bucket: str) -> Dict[str, Any]:
    from quilt_mcp.services.tabulator_service import tabulator_tables_list as _list
    bucket_name = bucket.replace("s3://", "").split("/")[0]
    return _list(bucket_name=bucket_name)
```

**DECISION: Use Option A** - Change service function parameter to match natural tool name.

## Testing Requirements

### Unit Tests

Update test files to call tools instead of resources:

1. **Permissions tests** - Test `check_bucket_access` as tool
2. **Admin tests** - Test `admin_user_get` as tool
3. **Athena tests** - Test `athena_tables_list` and `athena_table_schema` as tools
4. **Tabulator tests** - Test `tabulator_tables_list` as tool

### Integration Tests

Verify via [scripts/test-mcp.py](scripts/test-mcp.py):

```python
# Before: These fail as resources with {params}
resources = mcp.list_resources()
# Expected: Resources don't include parameterized URIs anymore

# After: These work as tools
tools = mcp.list_tools()
assert "check_bucket_access" in [t.name for t in tools]
assert "admin_user_get" in [t.name for t in tools]
assert "athena_tables_list" in [t.name for t in tools]
assert "athena_table_schema" in [t.name for t in tools]
assert "tabulator_tables_list" in [t.name for t in tools]
```

## Files to Change

### New Files
- None (if using Option B - service modules already registered)
- OR `src/quilt_mcp/tools/permissions.py` (if using Option A)

### Modified Files
1. **[src/quilt_mcp/resources.py](src/quilt_mcp/resources.py)**
   - Remove 5 parameterized resource decorators
   - Keep static resources

2. **[src/quilt_mcp/utils.py](src/quilt_mcp/utils.py)**
   - Update `RESOURCE_AVAILABLE_TOOLS` exclusion list
   - Verify functions are NOT excluded from tool registration

3. **[src/quilt_mcp/tools/__init__.py](src/quilt_mcp/tools/__init__.py)**
   - Add `"permissions": "quilt_mcp.services.permissions_service"` to `_MODULE_PATHS`

4. **[src/quilt_mcp/services/tabulator_service.py](src/quilt_mcp/services/tabulator_service.py)**
   - Rename parameter: `bucket_name` → `bucket` in `tabulator_tables_list()`
   - Update all call sites

5. **Test files**
   - Update to call tools instead of reading resources

## Migration Path

### Phase 1: Add Tools (Non-Breaking)
1. Add `permissions` to `_MODULE_PATHS`
2. Ensure service functions have proper signatures
3. Rename `bucket_name` → `bucket` in tabulator service

### Phase 2: Remove Resources (Breaking)
1. Delete parameterized resource decorators from `resources.py`
2. Update `RESOURCE_AVAILABLE_TOOLS` exclusion list
3. Update tests

### Phase 3: Verify
1. Run `scripts/test-mcp.py`
2. Verify tools appear in `list_tools()`
3. Verify resources no longer have unregistered templates

## Expected Outcome

**Before:**
```
Templates not registered by server:
- permissions://buckets/{bucket}/access
- admin://users/{name}
- athena://databases/{database}/tables
- athena://databases/{database}/tables/{table}/schema
- tabulator://buckets/{bucket}/tables
```

**After:**
```
Tools registered:
- mcp__quilt-uvx__check_bucket_access
- mcp__quilt-uvx__admin_user_get
- mcp__quilt-uvx__athena_tables_list
- mcp__quilt-uvx__athena_table_schema
- mcp__quilt-uvx__tabulator_tables_list

Resources (static only):
- auth://status
- admin://users (list)
- athena://databases (list)
- etc.
```

## Success Criteria

1. ✅ All 5 parameterized resources removed from `resources.py`
2. ✅ All 5 functions available as MCP tools
3. ✅ No "Templates not registered" warnings in test output
4. ✅ Tools callable with proper parameter names
5. ✅ All tests passing
6. ✅ Documentation updated

## Summary

**Core Decision:** Convert problematic parameterized resources into tools by:
1. Removing `@mcp.resource()` decorators with `{params}` in URI
2. Exposing service functions directly as tools
3. Ensuring service functions have proper Pydantic annotations
4. Adding `permissions` module to tool registration

**Why This Works:**
- Service functions already exist with proper logic
- Tool registration is simpler than resource template registration
- FastMCP handles tool parameters correctly
- Maintains all functionality, just changes the interface

**Impact:**
- **Users:** Change from resource URIs to tool calls (breaking API change)
- **Code:** Minimal changes, mostly deletions
- **Tests:** Update resource calls to tool calls
- **Functionality:** Zero loss, same underlying service functions

# Resource Template Registration Fix - Requirements

## Problem Statement

FastMCP cannot properly detect resource templates because of a three-layer wrapper problem that strips away function signatures:

1. **Service Layer**: Functions have explicit typed parameters (e.g., `check_bucket_access(bucket_name: str)`)
2. **Resource Layer**: MCPResource classes wrap them with `_read_impl(uri, params: Dict[str, str])` which converts parameters to dicts
3. **Utils Layer**: `create_handler` in utils.py wraps those again with `async def parameterized_handler(**kwargs)` using variadic kwargs

By the time FastMCP inspects the function signature, there are no named parameters left. FastMCP relies on inspecting function signatures to distinguish between:
- **Static resources**: Functions with no parameters (e.g., `def handler() -> str`)
- **Resource templates**: Functions with named parameters (e.g., `def handler(bucket: str) -> str`)

This causes all resources to be incorrectly registered as static resources instead of templates.

## Current Architecture

### Registration Flow

1. **Service Functions** (e.g., `src/quilt_mcp/services/permissions_service.py`)
   - Pure functions with explicit typed parameters
   - Example: `check_bucket_access(bucket_name: str)` → `Dict[str, Any]`

2. **Resource Classes** (e.g., `src/quilt_mcp/resources/permissions.py`)
   - Inherit from `MCPResource` base class
   - Define `uri_pattern` with `{param}` placeholders
   - Implement `_read_impl(uri: str, params: Optional[Dict[str, str]])` which:
     - Extracts params from dict
     - Calls service function with kwargs
     - Wraps result in `ResourceResponse`

3. **Resource Registry** (`src/quilt_mcp/resources/base.py`)
   - Stores all registered resources
   - Provides `list_resources()` returning metadata
   - Provides `read_resource(uri)` which:
     - Finds matching resource
     - Extracts params from URI
     - Calls resource's `read()` method

4. **Utils Registration** (`src/quilt_mcp/utils.py:create_configured_server`)
   - Calls `register_all_resources()` to populate registry
   - Gets resource list from registry
   - For each resource, calls `create_handler(resource_uri)` which:
     - Detects `{params}` in URI string
     - Returns `async def parameterized_handler(**kwargs)` OR `async def static_handler()`
     - Handler constructs actual URI and calls `registry.read_resource(actual_uri)`
   - Registers handler with FastMCP via `mcp.add_resource_fn()`

### The Wrapper Chain Problem

```python
# Layer 1: Service function (HAS typed parameters)
def check_bucket_access(bucket_name: str) -> Dict[str, Any]:
    ...

# Layer 2: Resource class (params become Dict[str, str])
class BucketAccessResource(MCPResource):
    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None):
        bucket_name = params["bucket"]
        result = await asyncio.to_thread(check_bucket_access, bucket_name=bucket_name)
        ...

# Layer 3: Utils handler (params become **kwargs)
async def parameterized_handler(**kwargs) -> str:
    actual_uri = resource_uri
    for param_name, param_value in kwargs.items():
        actual_uri = actual_uri.replace(f"{{{param_name}}}", param_value)
    response = await registry.read_resource(actual_uri)
    return response._serialize_content()

# FastMCP sees: async def parameterized_handler(**kwargs) -> str
# FastMCP needs: async def parameterized_handler(bucket: str) -> str
```

## Affected Resources

### Parameterized Resources (Need Template Registration)

These resources have URI patterns with `{param}` placeholders and MUST be registered as templates:

#### Permissions
- `permissions://buckets/{bucket}/access` → `check_bucket_access(bucket_name: str)`

#### Admin
- `admin://users/{name}` → `admin_user_get(name: str)`

#### Athena
- `athena://databases/{database}/tables/{table}/schema` → `athena_table_schema(database_name: str, table_name: str, ...)`

#### Tabulator
- `tabulator://buckets/{bucket}/tables` → `list_tabulator_tables(bucket_name: str)`

#### Metadata
- `metadata://templates/{name}` → `get_metadata_template(template_name: str, ...)`

#### Workflow
- `workflow://workflows/{id}` → `workflow_get_status(workflow_id: str)`

### Static Resources (Correctly Handled)

These resources have no URI parameters and can remain as static resources:

#### Admin
- `admin://users` → `admin_users_list()`
- `admin://roles` → `admin_roles_list()`
- `admin://config` → (composite resource)
- `admin://config/sso` → `admin_sso_config_get()`
- `admin://config/tabulator` → `admin_tabulator_open_query_get()`

#### Athena
- `athena://databases` → `athena_databases_list(...)`
- `athena://workgroups` → `athena_workgroups_list(...)`
- `athena://queries/history` → `athena_query_history(...)`

#### Metadata
- `metadata://templates` → `list_metadata_templates()`
- `metadata://examples` → `show_metadata_examples()`
- `metadata://troubleshooting` → `fix_metadata_validation_issues()`

#### Workflow
- `workflow://workflows` → `workflow_list_all()`

#### Tabulator
- `tabulator://buckets` → `list_tabulator_buckets()`

#### Auth
- `auth://status` → `auth_status()`
- `auth://catalog/info` → `catalog_info()`
- `auth://filesystem/status` → `filesystem_status()`

#### Permissions
- `permissions://discover` → `discover_permissions(...)`
- `permissions://recommendations` → `bucket_recommendations_get(...)`

## Service Function Inventory

### Functions That Can Stay Unchanged

All service functions can remain unchanged. They already have explicit typed parameters:

#### Parameterized Functions (Need Direct Registration)

| Service File | Function | Signature | Notes |
|--------------|----------|-----------|-------|
| `permissions_service.py` | `check_bucket_access` | `(bucket_name: str, ...)` | Can stay |
| `governance_service.py` | `admin_user_get` | `(name: str)` | Async, can stay |
| `athena_read_service.py` | `athena_table_schema` | `(database_name: str, table_name: str, ...)` | Can stay |
| `tabulator_service.py` | `list_tabulator_tables` | `(bucket_name: str)` | Can stay |
| `metadata_service.py` | `get_metadata_template` | `(template_name: str, ...)` | Can stay |
| `workflow_service.py` | `workflow_get_status` | `(workflow_id: str)` | Can stay |

#### Static Functions (Also Need Direct Registration)

All static resource functions have no parameters or only optional/default parameters. They can also be registered directly.

### Functions That Cannot Stay Unchanged

**NONE**. All service functions have appropriate signatures for direct registration with FastMCP.

## What Needs to Change

### 1. Direct Service Function Registration

**Requirement**: Register service functions directly with FastMCP, bypassing the wrapper layers.

**For Parameterized Resources:**
- FastMCP needs to see the original service function signature
- The service function must have named parameters matching the URI template variables
- Example: For URI `permissions://buckets/{bucket}/access`, FastMCP must see `check_bucket_access(bucket: str)`

**For Static Resources:**
- Service functions with no parameters or only optional parameters can be registered directly
- No special handling needed

### 2. URI Construction

**Requirement**: When FastMCP calls the registered service function, we need to construct the full URI for the response.

**Challenge**: Service functions return raw data, but FastMCP resources need:
- Full URI (e.g., `permissions://buckets/my-bucket/access`)
- MIME type
- Serialized content

**Need**: A thin adapter layer that:
1. Accepts service function output
2. Constructs the appropriate URI based on parameters
3. Wraps in ResourceResponse format
4. Returns serialized content

### 3. Parameter Name Mapping

**Requirement**: Map URI template parameters to service function parameter names.

**Current Mismatch Examples:**
- URI: `permissions://buckets/{bucket}/access`
- Service: `check_bucket_access(bucket_name: str)`
- FastMCP will call: `handler(bucket="my-bucket")`
- Service needs: `bucket_name="my-bucket"`

**Need**: Either:
- Option A: Rename service function parameters to match URI templates
- Option B: Create parameter mapping in registration
- Option C: Rename URI template parameters to match service functions

### 4. Async/Sync Handling

**Requirement**: Handle both sync and async service functions.

**Current State:**
- Some service functions are `async` (e.g., `admin_user_get`)
- Some service functions are sync (e.g., `check_bucket_access`)
- Resource classes use `asyncio.to_thread()` for sync functions

**Need**: Registration must work with both:
- Async functions can be registered directly
- Sync functions need async wrapper OR FastMCP must support sync functions

### 5. Optional Parameters

**Requirement**: Handle service functions with optional parameters.

**Examples:**
- `athena_table_schema(database_name: str, table_name: str, data_catalog_name: str = "AwsDataCatalog", service: Optional[Any] = None)`
- FastMCP should only receive URI-derived parameters, not optional service parameters

**Need**: 
- Only register URI template parameters as FastMCP resource parameters
- Optional service parameters should get default values

### 6. Response Serialization

**Requirement**: Convert service function responses to FastMCP resource format.

**Current State:**
- Service functions return `Dict[str, Any]` or Pydantic models
- Resource classes wrap in `ResourceResponse` with URI and mime type
- `ResourceResponse._serialize_content()` handles JSON serialization

**Need**:
- Preserve serialization logic
- Thin wrapper that creates ResourceResponse from service output

## Breaking Changes Assessment

### Can ALL Service Functions Stay Unchanged?

**YES**, with these considerations:

1. **Parameter Name Mapping**: If we choose Option A or C (renaming), service functions OR URI templates need updates
2. **Optional Parameters**: Service functions keep their optional parameters; registration just ignores them
3. **Return Types**: No changes needed; service functions already return appropriate types

### Any Service Functions That Genuinely Need Wrapper Logic?

**NO**, with one caveat:

- **AdminConfigResource** is a composite that calls multiple service functions and combines results
- This is the ONLY resource that genuinely needs wrapper logic
- Solution: Keep this as a custom handler, don't try to map it to a single service function

### Edge Cases and Special Considerations

#### 1. Composite Resources

**Example**: `admin://config` calls both `admin_sso_config_get()` and `admin_tabulator_open_query_get()`

**Consideration**: These cannot map to a single service function. Options:
- Keep as custom handler
- Create a dedicated composite service function
- Register nested resources only (`admin://config/sso`, `admin://config/tabulator`)

#### 2. Multi-Parameter Templates

**Example**: `athena://databases/{database}/tables/{table}/schema`

**Consideration**: Service function must accept both parameters:
- `athena_table_schema(database_name: str, table_name: str, ...)`
- FastMCP will call: `handler(database="db1", table="table1")`
- Need parameter mapping: `{database: database_name, table: table_name}`

#### 3. Error Handling

**Current State**: 
- Service functions return error dicts with `{"success": False, "error": "..."}`
- Resource classes catch exceptions and raise `Exception` for FastMCP

**Consideration**: 
- Keep error handling at registration level
- Wrap service functions in try/catch to convert errors to FastMCP exceptions

#### 4. Runtime Context

**Current State**:
- Resources inherit runtime auth context from MCP request
- Service functions may use `get_runtime_auth()` internally

**Consideration**:
- Direct registration should preserve runtime context
- No changes needed to service functions

#### 5. Asyncio Threading

**Current State**:
- Sync service functions are called via `asyncio.to_thread()` in resource classes

**Consideration**:
- Need to preserve this for sync service functions
- Either:
  - Wrap sync functions in async wrapper at registration time
  - OR ensure FastMCP supports sync functions (unlikely)

#### 6. Service Injection for Testing

**Current State**:
- Some service functions accept optional `service` parameter for testing
- Example: `athena_table_schema(..., service: Optional[Any] = None)`

**Consideration**:
- These parameters should NOT be exposed as FastMCP resource parameters
- Only URI template parameters should be registered
- Optional/testing parameters get default values

## Summary

**What needs to change:**
1. Registration mechanism in `utils.py` to bypass wrapper layers
2. Direct registration of service functions with FastMCP
3. Parameter name mapping (URI vars → service function params)
4. Thin adapter layer for URI construction and response serialization
5. Async wrapper for sync service functions
6. Filter out non-URI-template parameters during registration

**What stays the same:**
1. All service function implementations
2. Service function signatures (potentially renamed parameters)
3. Service function error handling logic
4. Resource base classes and registry (may be used differently or deprecated)
5. Resource metadata (uri_pattern, name, description)

**Critical path:**
1. Decide on parameter name mapping strategy (rename service params, URI vars, or create mapping)
2. Create adapter layer for URI construction + serialization
3. Create async wrapper for sync functions
4. Update registration in `utils.py` to register service functions directly
5. Handle special case of composite resources
6. Update tests to verify template vs static resource detection

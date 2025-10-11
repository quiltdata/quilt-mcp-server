# Module-Based Tools Refactoring - Implementation Specification

## Overview

This document specifies the implementation details for refactoring from 84 individual tools to 16 module-based tools using action-based dispatch.

## Tool Wrapper Pattern

### Standard Wrapper Template

Each module will have a wrapper function following this pattern:

```python
def module_name(action: str, **kwargs) -> Dict[str, Any]:
    """
    [Module description]
    
    Available actions:
    - action_name_1: Brief description (see: original_function_name_1)
    - action_name_2: Brief description (see: original_function_name_2)
    ...
    
    Args:
        action: The operation to perform
        **kwargs: Action-specific parameters (see individual action documentation)
    
    Returns:
        Action-specific response dictionary with at minimum:
        - success: bool - Whether the operation succeeded
        - [action-specific fields]
    
    Raises:
        ValueError: If action is unknown or parameters are invalid
    
    Examples:
        # Action 1 example
        result = module_name(action="action_name_1", param1="value1")
        
        # Action 2 example
        result = module_name(action="action_name_2", param2="value2", param3=100)
    
    For detailed parameter documentation, see the individual action functions:
    - action_name_1 -> original_function_name_1()
    - action_name_2 -> original_function_name_2()
    """
    # Action dispatch table
    actions = {
        "action_name_1": original_function_name_1,
        "action_name_2": original_function_name_2,
        # ... all actions
    }
    
    # Validate action
    if action not in actions:
        available = ", ".join(sorted(actions.keys()))
        return format_error_response(
            f"Unknown action '{action}' for module '{__name__}'. "
            f"Available actions: {available}"
        )
    
    # Dispatch to action implementation
    try:
        func = actions[action]
        return func(**kwargs)
    except TypeError as e:
        # Extract expected parameters from the function signature
        import inspect
        sig = inspect.signature(func)
        expected_params = list(sig.parameters.keys())
        return format_error_response(
            f"Invalid parameters for action '{action}'. "
            f"Expected parameters: {expected_params}. "
            f"Error: {str(e)}"
        )
    except Exception as e:
        # Pass through business logic errors
        if isinstance(e, dict) and not e.get("success"):
            return e
        return format_error_response(f"Error executing action '{action}': {str(e)}")
```

### Async Wrapper Template

For modules with async tools (governance, tabulator):

```python
async def module_name(action: str, **kwargs) -> Dict[str, Any]:
    """[Same docstring pattern as sync version]"""
    
    actions = {
        "action_name_1": async_function_1,
        "action_name_2": async_function_2,
        # ... all async actions
    }
    
    # [Same validation as sync version]
    
    try:
        func = actions[action]
        return await func(**kwargs)  # Note: await for async
    except TypeError as e:
        # [Same error handling]
```

## Action Naming Convention

Convert function names to action names by removing the module prefix:

| Original Function | Module | Action Name |
|-------------------|--------|-------------|
| `athena_databases_list` | athena_glue | `databases_list` |
| `athena_query_execute` | athena_glue | `query_execute` |
| `admin_users_list` | governance | `users_list` |
| `admin_user_create` | governance | `user_create` |
| `bucket_objects_list` | buckets | `objects_list` |
| `package_browse` | packages | `browse` |

**Rule**: Remove the module name prefix (and common admin/admin_ prefix) from function names.

## Module-Specific Implementations

### 1. athena_glue (7 tools → 1 tool)

```python
def athena_glue(action: str, **kwargs) -> Dict[str, Any]:
    """
    AWS Athena and Glue Data Catalog operations.
    
    Available actions:
    - databases_list: List available databases in AWS Glue Data Catalog
    - tables_list: List tables in a specific database
    - table_schema: Get detailed schema information for a table
    - workgroups_list: List available Athena workgroups
    - query_execute: Execute SQL query against Athena
    - query_history: Retrieve query execution history
    - query_validate: Validate SQL query syntax without executing
    """
    actions = {
        "databases_list": athena_databases_list,
        "tables_list": athena_tables_list,
        "table_schema": athena_table_schema,
        "workgroups_list": athena_workgroups_list,
        "query_execute": athena_query_execute,
        "query_history": athena_query_history,
        "query_validate": athena_query_validate,
    }
    # ... standard dispatch logic
```

### 2. governance (17 tools → 1 tool)

```python
async def governance(action: str, **kwargs) -> Dict[str, Any]:
    """
    Quilt catalog governance and user management.
    
    Available actions:
    - roles_list: List all available roles
    - users_list: List all users with detailed information
    - user_get: Get detailed information about a specific user
    - user_create: Create a new user
    - user_delete: Delete a user
    - user_set_email: Update user's email address
    - user_set_role: Set user's primary and extra roles
    - user_set_admin: Set user's admin status
    - user_set_active: Set user's active status
    - user_add_roles: Add roles to a user
    - user_remove_roles: Remove roles from a user
    - user_reset_password: Reset a user's password
    - sso_config_get: Get current SSO configuration
    - sso_config_set: Set SSO configuration
    - sso_config_remove: Remove SSO configuration
    - tabulator_open_query_get: Get tabulator open query status
    - tabulator_open_query_set: Set tabulator open query status
    """
    actions = {
        "roles_list": admin_roles_list,
        "users_list": admin_users_list,
        "user_get": admin_user_get,
        "user_create": admin_user_create,
        # ... all 17 actions
    }
    # ... async dispatch logic
```

### 3. buckets (8 tools → 1 tool)

```python
def buckets(action: str, **kwargs) -> Dict[str, Any]:
    """
    S3 bucket operations and object management.
    
    Available actions:
    - object_fetch: Fetch binary or text data from an S3 object
    - object_info: Get metadata information for an S3 object
    - object_link: Generate presigned URL for an S3 object
    - object_text: Read text content from an S3 object
    - objects_list: List objects in an S3 bucket with filtering
    - objects_put: Upload multiple objects to an S3 bucket
    - objects_search: Search objects using Elasticsearch
    - objects_search_graphql: Search objects via GraphQL
    """
    actions = {
        "object_fetch": bucket_object_fetch,
        "object_info": bucket_object_info,
        # ... all 8 actions
    }
    # ... standard dispatch logic
```

## Updated Tool Registration

### Modified utils.py

```python
def get_tool_wrappers() -> Dict[str, Callable]:
    """Get dictionary of module wrapper functions to register as MCP tools."""
    from quilt_mcp.tools import (
        auth,
        buckets,
        package_ops,
        packages,
        s3_package,
        permissions,
        unified_package,
        metadata_templates,
        package_management,
        metadata_examples,
        quilt_summary,
        search,
        athena_glue,
        tabulator,
        workflow_orchestration,
        governance,
    )
    
    # Map module name to wrapper function
    return {
        "auth": auth.auth,
        "buckets": buckets.buckets,
        "athena_glue": athena_glue.athena_glue,
        "governance": governance.governance,
        "metadata_examples": metadata_examples.metadata_examples,
        "metadata_templates": metadata_templates.metadata_templates,
        "package_management": package_management.package_management,
        "package_ops": package_ops.package_ops,
        "packages": packages.packages,
        "permissions": permissions.permissions,
        "quilt_summary": quilt_summary.quilt_summary,
        "s3_package": s3_package.s3_package,
        "search": search.search,
        "tabulator": tabulator.tabulator,
        "unified_package": unified_package.unified_package,
        "workflow_orchestration": workflow_orchestration.workflow_orchestration,
    }


def register_tools(mcp: FastMCP, verbose: bool = True) -> int:
    """Register module wrapper functions as MCP tools.
    
    Args:
        mcp: The FastMCP server instance
        verbose: Whether to print registration messages
    
    Returns:
        Number of tools registered (should be 16)
    """
    wrappers = get_tool_wrappers()
    
    for tool_name, wrapper_func in wrappers.items():
        mcp.tool(wrapper_func)
        if verbose:
            print(f"Registered tool: {tool_name}", file=sys.stderr)
    
    return len(wrappers)
```

## Testing Strategy

### Test File Organization

Maintain existing test file structure but update calls:

```python
# tests/unit/test_athena_glue.py

def test_databases_list():
    """Test listing databases through module wrapper."""
    result = athena_glue(action="databases_list", catalog_name="AwsDataCatalog")
    assert result["success"] is True
    assert "databases" in result


def test_query_execute():
    """Test query execution through module wrapper."""
    result = athena_glue(
        action="query_execute",
        query="SELECT 1",
        database_name="default",
    )
    assert result["success"] is True


def test_unknown_action():
    """Test error handling for unknown action."""
    result = athena_glue(action="invalid_action")
    assert result["success"] is False
    assert "Unknown action" in result["error"]
    assert "available actions" in result["error"].lower()


def test_invalid_parameters():
    """Test error handling for invalid parameters."""
    result = athena_glue(action="databases_list", invalid_param="value")
    # Should still work - extra kwargs are ignored
    assert result["success"] is True


def test_missing_required_parameters():
    """Test error handling for missing required parameters."""
    result = athena_glue(action="query_execute")  # Missing required 'query'
    assert result["success"] is False
    assert "parameter" in result["error"].lower()
```

### Integration Test Updates

```python
# tests/integration/test_athena_integration.py

@pytest.mark.integration
def test_real_query_execution():
    """Test real Athena query execution."""
    result = athena_glue(
        action="query_execute",
        query="SHOW DATABASES",
        use_quilt_auth=True,
    )
    assert result["success"] is True
    assert "data" in result
```

## Documentation Updates

### README.md Example Section

```markdown
## Usage Examples

### Athena Queries

```python
from quilt_mcp.tools import athena_glue

# List databases
result = athena_glue(action="databases_list")
print(result["databases"])

# Execute query
result = athena_glue(
    action="query_execute",
    query="SELECT * FROM my_table LIMIT 10",
    database_name="my_database"
)
print(result["data"])
```

### Package Management

```python
from quilt_mcp.tools import packages

# Browse package contents
result = packages(
    action="browse",
    package_name="user/dataset",
    registry="s3://my-bucket"
)

# Search for packages
result = packages(
    action="search",
    query="genomics",
    limit=10
)
```
```

## Migration Guide for MCP Clients

### Before (84 tools)

```json
{
  "method": "tools/call",
  "params": {
    "name": "athena_databases_list",
    "arguments": {
      "catalog_name": "AwsDataCatalog"
    }
  }
}
```

### After (16 tools)

```json
{
  "method": "tools/call",
  "params": {
    "name": "athena_glue",
    "arguments": {
      "action": "databases_list",
      "catalog_name": "AwsDataCatalog"
    }
  }
}
```

### Migration Mapping Table

| Old Tool Name | New Tool Name | Action |
|---------------|---------------|--------|
| `athena_databases_list` | `athena_glue` | `databases_list` |
| `athena_query_execute` | `athena_glue` | `query_execute` |
| `admin_users_list` | `governance` | `users_list` |
| `bucket_objects_list` | `buckets` | `objects_list` |
| `package_browse` | `packages` | `browse` |
| ... | ... | ... |

## Implementation Checklist

### Phase 1: Core Implementation
- [ ] Create wrapper function for each module (16 functions)
- [ ] Update tool registration in utils.py
- [ ] Add comprehensive docstrings with action lists
- [ ] Implement action validation and error handling

### Phase 2: Testing
- [ ] Update unit tests for all modules
- [ ] Update integration tests
- [ ] Add tests for unknown actions
- [ ] Add tests for invalid parameters
- [ ] Verify 100% coverage maintained

### Phase 3: Documentation
- [ ] Update README.md with new examples
- [ ] Create migration guide for MCP clients
- [ ] Update API documentation
- [ ] Add module-by-module usage examples
- [ ] Document action naming conventions

### Phase 4: Validation
- [ ] Run full test suite
- [ ] Test with real MCP clients
- [ ] Verify all 84 original functions remain accessible
- [ ] Check error messages are clear and helpful
- [ ] Validate async tools work correctly

## Rollback Plan

If issues arise:

1. **Keep Original Functions**: All original functions remain in modules unchanged
2. **Revert Registration**: Change `register_tools()` back to original implementation
3. **Update Tests**: Revert test file changes
4. **Git Revert**: Use `git revert` to undo changes

The refactoring is designed to be low-risk because:
- Original function implementations are unchanged
- Only registration and test call patterns are modified
- No changes to business logic or service layer

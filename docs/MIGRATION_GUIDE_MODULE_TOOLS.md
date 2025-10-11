# Migration Guide: Module-Based Tools

## Overview

The Quilt MCP Server has been refactored from **84 individual tools** to **16 module-based tools** using action-based dispatch. This reduces client overhead while maintaining all existing functionality.

## What Changed

### Before (84 Tools)

```python
# Individual tools for each function
result = athena_databases_list(catalog_name="AwsDataCatalog")
result = athena_query_execute(query="SELECT * FROM table", database_name="default")
result = bucket_objects_list(bucket="my-bucket", max_keys=100)
result = package_browse(package_name="user/dataset")
```

### After (16 Module Tools)

```python
# One tool per module with action parameter
result = athena_glue(action="databases_list", params={"catalog_name": "AwsDataCatalog"})
result = athena_glue(action="query_execute", params={"query": "SELECT * FROM table", "database_name": "default"})
result = buckets(action="objects_list", params={"bucket": "my-bucket", "max_keys": 100})
result = packages(action="browse", params={"package_name": "user/dataset"})
```

## Migration Steps

### Step 1: Update Tool Names

Map old tool names to new module + action combinations:

| Old Tool | New Module | Action |
|----------|------------|--------|
| `athena_databases_list` | `athena_glue` | `databases_list` |
| `athena_query_execute` | `athena_glue` | `query_execute` |
| `bucket_objects_list` | `buckets` | `objects_list` |
| `bucket_object_fetch` | `buckets` | `object_fetch` |
| `package_browse` | `packages` | `browse` |
| `package_create` | `package_ops` | `create` |
| `admin_users_list` | `governance` | `users_list` |
| ... | ... | ... |

### Step 2: Update Function Calls

**Pattern**: `module(action="action_name", params={...parameters...})`

**Examples**:

```python
# AUTH MODULE (8 actions)
# Before: auth_status()
# After:
auth(action="status")

# Before: configure_catalog(catalog_url="https://example.com")
# After:
auth(action="configure_catalog", params={"catalog_url": "https://example.com"})

# BUCKETS MODULE (8 actions)
# Before: bucket_objects_list(bucket="my-bucket", max_keys=50)
# After:
buckets(action="objects_list", params={"bucket": "my-bucket", "max_keys": 50})

# Before: bucket_object_fetch(s3_uri="s3://bucket/key")
# After:
buckets(action="object_fetch", params={"s3_uri": "s3://bucket/key"})

# PACKAGES MODULE (5 actions)
# Before: package_browse(package_name="user/dataset")
# After:
packages(action="browse", params={"package_name": "user/dataset"})

# Before: packages_search(query="genomics", limit=10)
# After:
packages(action="search", params={"query": "genomics", "limit": 10})

# GOVERNANCE MODULE (17 actions - ASYNC)
# Before: await admin_users_list()
# After:
await governance(action="users_list")

# Before: await admin_user_create(name="newuser", email="user@example.com", role="user")
# After:
await governance(action="user_create", params={"name": "newuser", "email": "user@example.com", "role": "user"})
```

### Step 3: Discover Available Actions

Each module supports discovery mode - call without `action` parameter:

```python
# Discover actions for auth module
result = auth()
print(result["actions"])
# Output: ['status', 'catalog_info', 'catalog_name', 'catalog_uri', 'catalog_url', 'configure_catalog', 'filesystem_status', 'switch_catalog']

# Discover actions for athena_glue module
result = athena_glue()
print(result["actions"])
# Output: ['databases_list', 'tables_list', 'table_schema', 'workgroups_list', 'query_execute', 'query_history', 'query_validate']
```

## Complete Module Mapping

### All 16 Modules

| Module | Tools Count | Example Actions |
|--------|-------------|-----------------|
| `athena_glue` | 7 → 1 | databases_list, query_execute, query_history |
| `auth` | 8 → 1 | status, catalog_info, configure_catalog |
| `buckets` | 8 → 1 | objects_list, object_fetch, object_info |
| `governance` | 17 → 1 | users_list, user_create, roles_list (async) |
| `metadata_examples` | 3 → 1 | from_template, show_examples, fix_issues |
| `metadata_templates` | 3 → 1 | get_template, list_templates, validate |
| `package_management` | 4 → 1 | create_enhanced, validate, update_metadata |
| `package_ops` | 3 → 1 | create, update, delete |
| `packages` | 5 → 1 | browse, search, diff, list |
| `permissions` | 3 → 1 | discover, access_check, recommendations_get |
| `quilt_summary` | 3 → 1 | create_files, generate_viz, generate_json |
| `s3_package` | 1 → 1 | create_from_s3 |
| `search` | 3 → 1 | unified_search, suggest, explain |
| `tabulator` | 7 → 1 | tables_list, table_create, table_delete (async) |
| `unified_package` | 3 → 1 | create, list_available_resources, quick_start |
| `workflow_orchestration` | 6 → 1 | create, add_step, update_step |

**Total: 84 tools → 16 tools (81% reduction)**

## Action Naming Convention

Action names are derived from original function names by removing the module prefix:

- `athena_databases_list` → `databases_list` (removed `athena_`)
- `admin_users_list` → `users_list` (removed `admin_`)
- `bucket_objects_list` → `objects_list` (removed `bucket_`)
- `package_browse` → `browse` (removed `package_`)

## Error Handling

### Unknown Action

```python
result = auth(action="invalid_action")
# Returns:
{
    "status": "error",
    "error": "Unknown action 'invalid_action' for module 'auth'. Available actions: catalog_info, catalog_name, ..."
}
```

### Invalid Parameters

```python
result = auth(action="configure_catalog")  # Missing required catalog_url
# Returns:
{
    "status": "error",
    "error": "Invalid parameters for action 'configure_catalog'. Expected parameters: ['catalog_url']. Error: ..."
}
```

## MCP Client Examples

### JSON-RPC Format

**Before**:
```json
{
  "method": "tools/call",
  "params": {
    "name": "athena_query_execute",
    "arguments": {
      "query": "SELECT * FROM my_table",
      "database_name": "default",
      "max_results": 100
    }
  }
}
```

**After**:
```json
{
  "method": "tools/call",
  "params": {
    "name": "athena_glue",
    "arguments": {
      "action": "query_execute",
      "params": {
        "query": "SELECT * FROM my_table",
        "database_name": "default",
        "max_results": 100
      }
    }
  }
}
```

### Claude Desktop Config

**Before** (`~/.config/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["quilt-mcp-server"]
    }
  }
}
```

**After**: *No changes needed* - the server binary remains the same, only the tool interface changed.

## Benefits

### For MCP Clients
- ✅ **81% fewer tools to load** (84 → 16)
- ✅ **Better organization** - tools grouped by module
- ✅ **Self-documenting** - call with `action=None` to discover actions
- ✅ **Clearer namespacing** - module name provides context

### For Developers
- ✅ **Simpler registration** - 16 wrappers vs 84 functions
- ✅ **Easier testing** - test wrappers, individual functions unchanged
- ✅ **Better maintainability** - clear module boundaries
- ✅ **Consistent patterns** - all modules follow same wrapper pattern

## Backward Compatibility

**Breaking Change**: Yes, this is a breaking change for MCP clients.

**Mitigation**:
- Individual Python functions remain unchanged and accessible
- Only the MCP tool interface changed
- Clear migration path with examples
- Discovery mode helps with transition

## Troubleshooting

### "Unknown action" Error

**Problem**: Getting error about unknown action.

**Solution**: Use discovery mode to see available actions:
```python
result = athena_glue()  # No action parameter
print(result["actions"])
```

### Missing Parameters

**Problem**: Getting error about missing required parameters.

**Solution**: Check error message for expected parameters list, or refer to original function documentation:
```python
# Error will show: "Expected parameters: ['query', 'database_name', ...]"
```

### Async Tools

**Problem**: Forgetting to `await` async tools (governance, tabulator).

**Solution**: Always `await` these two modules:
```python
result = await governance(action="users_list")
result = await tabulator(action="tables_list", params={"bucket_name": "my-bucket"})
```

## Questions?

- **Q**: Can I still call individual functions in Python code?  
  **A**: Yes! The individual functions (like `athena_databases_list()`) still exist and work. Only the MCP tool interface changed.

- **Q**: How do I know what parameters an action needs?  
  **A**: Check the original function docstrings, or the error message will list expected parameters.

- **Q**: Are there any performance implications?  
  **A**: No - the wrapper just dispatches to the original function. Performance is identical.

- **Q**: Can I use both old and new patterns?  
  **A**: For Python code, yes (individual functions still exist). For MCP tools, only the new wrapper pattern works.

## Full Tool Mapping Reference

See [spec/quilt_mcp_tools - quilt_mcp_tools.csv](../spec/quilt_mcp_tools%20-%20quilt_mcp_tools.csv) for complete mapping of all 84 original tools to their new module + action combinations.

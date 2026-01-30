# Multi-User Deployment Limitations

## Summary

| Mode          | Multi-User Safe | Notes                        |
| ------------- | --------------- | ---------------------------- |
| IAM mode      | **No**          | All users share credentials  |
| JWT mode      | **Partial**     | Only bucket tools isolated   |
| Containerized | **Yes**         | Full isolation per container |

## Root Causes

### 1. quilt3 Library Global State

The `quilt3` library was designed for single-user desktop use:

- `~/.local/share/Quilt/credentials.json` - Cached AWS credentials
- `~/.local/share/Quilt/config.yml` - Catalog configuration
- `quilt3/session.py:_session` - Global HTTP session

### 2. MCP Server Singletons

The MCP server has its own global state:

- `permissions_service.py:_permission_discovery` - Cached AWS clients
- `workflow_service.py:_workflows` - In-memory workflow storage
- `auth_service.py:_AUTH_SERVICE` - Cached auth service (IAM mode)

## Tool Safety by Category

### Safe in JWT Mode (6 tools)

Use `auth_helpers.py` → per-request JWT credentials via ContextVar:

- `bucket_objects_list`, `bucket_object_info`, `bucket_object_text`
- `bucket_object_fetch`, `bucket_objects_put`, `bucket_object_link`

### Safe - No AWS Calls (4 tools)

- `generate_quilt_summarize_json`, `generate_package_visualizations`,
  `create_quilt_summary_files` - Pure data processing
- `filesystem_status` - Local filesystem only

### Conditionally Safe (1 tool)

- `create_data_visualization` - Prefers JWT context, falls back to quilt3

### Unsafe - Uses quilt3 credentials.json

| Tools                      | Path                                            |
| -------------------------- | ----------------------------------------------- |
| `package_*` (7 tools)      | `quilt3.Package` → `data_transfer` → `session`  |
| `athena_*` (7 tools)       | `create_botocore_session()` → `credentials.json`|
| `discover_permissions` etc | Singleton caches `quilt3.get_boto3_session()`   |

### Unsafe - Uses quilt3 global HTTP session

| Tools                | Path                                   |
| -------------------- | -------------------------------------- |
| `search_*` (3 tools) | `quilt_service.get_session()` → `_session` |
| `admin_*` (17 tools) | `quilt3.admin.*` → `_session`          |
| `tabulator_*` (6)    | `quilt3.admin.tabulator` → `_session`  |

### Unsafe - Uses quilt3 global config

| Tools                          | Issue                              |
| ------------------------------ | ---------------------------------- |
| `catalog_url`, `catalog_uri`   | Reads `quilt3.config()`            |
| `catalog_configure`            | **Writes** `quilt3.config()` - dangerous |
| `catalog_info`, `auth_status`  | Reads `quilt3.logged_in()` + config|

### Unsafe - MCP Server Global State

| Tools               | Issue                              |
| ------------------- | ---------------------------------- |
| `workflow_*` (6)    | Shared `_workflows` dict in memory |
| Permission tools    | Singleton `_permission_discovery`  |

## Deployment Options

**Single-user desktop**: Safe with any mode.

**Multi-user (bucket tools only)**: Use JWT mode, restrict to `bucket_*` tools.

**Full multi-tenant**: Deploy separate containers per user.

## See Also

- [AUTHENTICATION.md](AUTHENTICATION.md)

# Multi-User Deployment Limitations

## Summary

| Mode          | Multi-User Safe | Notes                        |
| ------------- | --------------- | ---------------------------- |
| IAM mode      | **No**          | All users share credentials  |
| JWT mode      | **Partial**     | Only bucket tools isolated   |
| Containerized | **Yes**         | Full isolation per container |

## Root Cause

The `quilt3` library stores state globally (designed for single-user desktop use):

- `~/.local/share/Quilt/credentials.json` - AWS credentials
- `~/.local/share/Quilt/config.yml` - Catalog configuration
- `quilt3/session.py:_session` - Shared HTTP session

## Tool Safety

### Safe in JWT Mode (6 tools)

Bucket tools use `auth_helpers.py` → per-request JWT credentials:

- `bucket_objects_list`, `bucket_object_info`, `bucket_object_text`
- `bucket_object_fetch`, `bucket_objects_put`, `bucket_object_link`

### Conditionally Safe (4 tools)

These use `get_s3_client()` which prefers JWT context but falls back to quilt3:

- `create_data_visualization` - Safe if JWT context is set, else falls back

### Safe (no credentials needed)

- `generate_quilt_summarize_json`, `generate_package_visualizations`,
  `create_quilt_summary_files` - Pure data processing, no S3 calls

### Unsafe (use quilt3 global state)

| Category    | Issue                          |
| ----------- | ------------------------------ |
| Package     | `credentials.json` or fallback |
| Search      | Global `quilt3.session`        |
| Catalog     | Global `quilt3.config()`       |
| Permissions | Global session + credentials   |
| Athena      | `create_botocore_session()`    |
| Admin       | Global `quilt3.session`        |
| Tabulator   | Global `quilt3.session`        |
| Workflow    | In-memory global `_workflows`  |

**Affected tools:**

- **Package:** `package_browse`, `package_create`, `packages_list`, `package_delete`,
  `package_update`, `package_diff`, `package_create_from_s3`
- **Search:** `search_catalog`, `search_suggest`, `search_explain`
- **Catalog:** `catalog_url`, `catalog_uri`, `catalog_configure`, `catalog_info`,
  `auth_status`, `filesystem_status`
- **Permissions:** `discover_permissions`, `check_bucket_access`,
  `bucket_recommendations_get`
- **Athena:** `athena_query_execute`, `athena_tables_list`, `athena_table_schema`, etc.
- **Admin:** `admin_*` (17 tools)
- **Tabulator:** `tabulator_*` (6 tools)
- **Workflow:** `workflow_*` (6 tools) - shared in-memory state

**quilt3 credential chain** (never uses MCP's JWT credentials):

```python
# quilt3/session.py
def get_boto3_session(fallback=True):
    if credentials := _load_credentials():  # credentials.json
        return boto3.Session(credentials=credentials)
    if fallback:
        return boto3.Session()  # Server's default IAM role
```

Both paths are **shared across all users**.

## Deployment Options

**Single-user desktop**: Safe with any mode.

**Multi-user (bucket tools only)**: Use JWT mode, restrict to `bucket_*` tools only.

**Full multi-tenant**: Deploy separate containers per user.

## See Also

- [AUTHENTICATION.md](AUTHENTICATION.md)

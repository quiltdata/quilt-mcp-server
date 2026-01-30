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

### Safe in JWT Mode

Bucket tools use `auth_helpers.py` → per-request JWT credentials:

- `bucket_objects_list`, `bucket_object_info`, `bucket_object_text`, `bucket_objects_put`

### Unsafe

Package/search/admin tools call `quilt3.*` which bypasses JWT credentials:

| Tool                                                                   | Issue                              |
| ---------------------------------------------------------------------- | ---------------------------------- |
| `package_browse`, `package_create`, `packages_list`, `package_delete`  | Uses quilt3 credentials (see below)|
| `search_catalog`                                                       | Uses global `quilt3.session`       |
| `admin_*`, `tabulator_*`                                               | Uses global `quilt3.session`       |

**quilt3 credential chain** (never uses MCP's JWT credentials):

```python
# quilt3/session.py
def get_boto3_session(fallback=True):
    if credentials := _load_credentials():  # ~/.local/share/Quilt/credentials.json
        return boto3.Session(credentials=credentials)
    if fallback:
        return boto3.Session()  # Server's default IAM role
```

Both paths are **shared across all users**.

## Deployment Options

**Single-user desktop**: Safe with any mode.

**Multi-user (bucket tools only)**: Use JWT mode, avoid `package_*`/`search_*`/`admin_*` tools.

**Full multi-tenant**: Deploy separate containers per user (isolates filesystem + quilt3 globals).

## See Also

- [AUTHENTICATION.md](AUTHENTICATION.md)

# Package Delete Backend Abstraction Gap

**Date:** 2026-02-11
**Issue:** `package_delete` tool bypasses backend abstraction layer

## Current Implementation

`package_delete` ([packages.py:1557](../../src/quilt_mcp/tools/packages.py#L1557)) directly calls `quilt3.delete_package()`:

```python
with suppress_stdout():
    quilt3.delete_package(package_name, registry=normalized_registry)
```

## Architectural Gap

**Other package operations use backend abstraction:**

- `package_create` → `_backend_create_empty_package()` + `_backend_push_package()`
- `package_update` → `update_package_revision()` (platform has GraphQL impl)
- `package_search` → `_backend_search_packages()`
- `get_package_info` → `get_package_info()` (both backends implement)

**`package_delete` does NOT:**

- No `_backend_delete_package()` primitive exists
- No `delete_package()` method in QuiltOps interface
- Platform_Backend has no deletion implementation

## Consequences

1. **Platform backend**: `package_delete` always fails (quilt3 lib doesn't work with GraphQL auth)
2. **Quilt3 backend**: Works but uses library directly, bypassing auth abstraction
3. **Inconsistent pattern**: Only package operation not following Template Method pattern
4. **Auth bypass**: Uses quilt3 session auth instead of unified JWT/session handling

## Context

- Platform catalog has `packageRevisionDelete` GraphQL mutation (see [10-catalog-package-deletion.md](10-catalog-package-deletion.md))
- Other tools migrated to backend abstraction in a22-docker-remote work
- `package_delete` was overlooked during QuiltOps migration

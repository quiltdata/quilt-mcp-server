# Migration: Package MCP Tools → QuiltOps

## Goal

Migrate `package_create()` and `package_create_from_s3()` tools to use QuiltOps exclusively, then delete QuiltService.

## Status

**✅ Already Migrated:**

- `package_browse()` tool → Uses `quilt_ops.browse_content()`
- `packages_list()` tool → Uses `quilt_ops.search_packages()`

**❌ Needs Migration:**

- `package_create()` tool → Uses `quilt_service.create_package_revision()`
- `package_create_from_s3()` tool → Uses `quilt_service.create_package_revision()`

## Problem

QuiltOps.create_package_revision() missing 2 parameters that tools need:

- `auto_organize: bool` - Smart folders vs flat structure
- `copy: str` - Copy mode: "all", "same_bucket", "none"

## Work Required

### 1. Extend QuiltOps Interface

Add `auto_organize` and `copy` parameters to `create_package_revision()` abstract method in QuiltOps.

### 2. Implement in Quilt3 Backend

Update Quilt3_Backend.create_package_revision() to handle:

- `auto_organize=True` → Preserve S3 folder structure as logical keys
- `auto_organize=False` → Flatten to just filenames
- `copy` parameter → Pass through to package.push()

### 3. Update Tests

Add test coverage for new parameters in backend tests.

### 4. Migrate Tools

Replace `QuiltService` with `QuiltOpsFactory.create()` in:

- `package_create()` tool
- `package_create_from_s3()` helper function

Update result handling from dict to Package_Creation_Result domain object.

### 5. Delete QuiltService

After migration complete:

- Verify no remaining QuiltService usage in codebase
- Delete [src/quilt_mcp/services/quilt_service.py](src/quilt_mcp/services/quilt_service.py)
- Delete related tests

## Files to Change

- [src/quilt_mcp/ops/quilt_ops.py](src/quilt_mcp/ops/quilt_ops.py#L259) - Abstract method signature
- [src/quilt_mcp/backends/quilt3_backend_packages.py](src/quilt_mcp/backends/quilt3_backend_packages.py#L290) - Implementation
- [src/quilt_mcp/tools/packages.py](src/quilt_mcp/tools/packages.py#L568) - Migrate package_create_from_s3
- [src/quilt_mcp/tools/packages.py](src/quilt_mcp/tools/packages.py#L1268) - Migrate package_create
- [tests/unit/backends/test_quilt3_backend_packages.py](tests/unit/backends/test_quilt3_backend_packages.py) - Add tests

## Files to Delete

- [src/quilt_mcp/services/quilt_service.py](src/quilt_mcp/services/quilt_service.py)

## Success Criteria

- QuiltOps.create_package_revision() supports auto_organize and copy
- No QuiltService imports in packages.py
- QuiltService.py deleted
- All tests pass
- `make lint` passes

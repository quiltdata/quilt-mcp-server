# Phase 1: Minimal Decoupling Checklist

## Goal: Remove Direct quilt3 Global State Dependencies

**Current Problem**: `auth_status()` in `src/quilt_mcp/tools/auth.py` calls `quilt3.logged_in()` and `quilt3.config()` directly.

**Solution**: Create a thin wrapper that accepts configuration parameters instead of using global state.

## Minimal Tasks

### 1. Create Isolated Operation

- [x] Create `src/quilt_mcp/operations/quilt3/auth.py`
- [x] Implement `check_auth_status(registry_url: str, catalog_url: str | None) -> dict`
- [x] Move quilt3 logic from tools/auth.py to this function
- [x] Return same dict format as current `auth_status()`

### 2. Update MCP Tool

- [x] Modify `src/quilt_mcp/tools/auth.py:auth_status()`
- [x] Load config from `Quilt3Config.from_environment()`
- [x] Call `check_auth_status(config.registry_url, config.catalog_url)`
- [x] Return result unchanged

### 3. Test Isolation

- [x] Write test that calls `check_auth_status()` with different configs
- [x] Verify no global state pollution between calls
- [x] Confirm existing `auth_status()` tests still pass

## Success Criteria

- [x] `auth_status()` tool behavior unchanged
- [x] No direct `quilt3.logged_in()` or `quilt3.config()` calls in tools layer
- [x] Can call operation with different configs independently
- [x] All existing tests pass

# Phase 1: Minimal Decoupling Checklist

## Goal: Remove Direct quilt3 Global State Dependencies

**Current Problem**: `auth_status()` in `src/quilt_mcp/tools/auth.py` calls `quilt3.logged_in()` and `quilt3.config()` directly.

**Solution**: Create a thin wrapper that accepts configuration parameters instead of using global state.

## Minimal Tasks

### 1. Create Isolated Operation

- [ ] Create `src/quilt_mcp/operations/quilt3/auth.py`
- [ ] Implement `check_auth_status(registry_url: str, catalog_url: str | None) -> dict`
- [ ] Move quilt3 logic from tools/auth.py to this function
- [ ] Return same dict format as current `auth_status()`

### 2. Update MCP Tool

- [ ] Modify `src/quilt_mcp/tools/auth.py:auth_status()`
- [ ] Load config from `Quilt3Config.from_environment()`
- [ ] Call `check_auth_status(config.registry_url, config.catalog_url)`
- [ ] Return result unchanged

### 3. Test Isolation

- [ ] Write test that calls `check_auth_status()` with different configs
- [ ] Verify no global state pollution between calls
- [ ] Confirm existing `auth_status()` tests still pass

## Success Criteria

- [ ] `auth_status()` tool behavior unchanged
- [ ] No direct `quilt3.logged_in()` or `quilt3.config()` calls in tools layer
- [ ] Can call operation with different configs independently
- [ ] All existing tests pass

# Task: Fix TEST_BACKEND_MODE Inconsistent Implementation

**Status:** Planned
**Priority:** High
**Sprint:** A18 - MCP Test Infrastructure

---

## Problem Statement

The `TEST_BACKEND_MODE` environment variable is not consistently implemented. Currently, backend selection is tightly coupled to `QUILT_MULTIUSER_MODE`, preventing the intended **Mode 3: Local-Platform** testing workflow.

### Current Behavior (Broken)

- `TEST_BACKEND_MODE=platform` **automatically forces** `QUILT_MULTIUSER_MODE=true`
- Backend selection is controlled solely by `QUILT_MULTIUSER_MODE`, not `TEST_BACKEND_MODE`
- Cannot test Platform backend in local development mode
- Cannot use stdio transport with Platform backend

### Expected Behavior (From Spec)

Per [08-mcp-test-refactor.md](08-mcp-test-refactor.md) lines 154-184, **Mode 3: Local-Platform** should support:

```bash
QUILT_MULTIUSER_MODE=false   # Local execution, filesystem state
TEST_BACKEND_MODE=platform   # Use Platform backend
FASTMCP_TRANSPORT=stdio      # Fast stdio transport
PLATFORM_TEST_ENABLED=true
```

**Benefits:**
- Fast platform backend iteration (~10-15s vs ~30-45s with Docker)
- Platform backend development without HTTP overhead
- GraphQL integration testing without full multiuser stack
- Filesystem state for debugging platform features

---

## Root Cause Analysis

### Issue Location

**File:** `tests/conftest.py` line 234

```python
if mode == "platform":
    monkeypatch.setenv("QUILT_MULTIUSER_MODE", "true")  # ← Forces multiuser mode
```

### Impact

1. `TEST_BACKEND_MODE` doesn't actually control backend selection
2. Backend selection happens via `ModeConfig.backend_type` which reads `QUILT_MULTIUSER_MODE`
3. No way to override backend selection independent of deployment mode
4. Mode 3 (Local-Platform) from spec is impossible

---

## Tasks

### Task 1: Add Backend Type Override to ModeConfig

**File:** `src/quilt_mcp/config.py`

**Requirements:**
- Add optional `backend_type_override` parameter to `ModeConfig.__init__()`
- Modify `backend_type` property to check override before using `is_multiuser`
- Add validation to ensure override is only used in test contexts
- Add debug logging when override is active

**Properties to modify:**
- `ModeConfig.backend_type` (line 82-84) - Check override first
- `ModeConfig.validate()` - Warn if override set in production

**Functions to modify:**
- `set_test_mode_config()` (line 175-182) - Accept optional `backend_type` parameter

**Expected behavior:**
- If `backend_type_override` is set → use it
- Otherwise → use existing logic (`"graphql"` if multiuser, else `"quilt3"`)

---

### Task 2: Decouple Backend Selection in Test Fixture

**File:** `tests/conftest.py`

**Requirements:**
- Remove automatic `QUILT_MULTIUSER_MODE=true` when `TEST_BACKEND_MODE=platform`
- Allow `QUILT_MULTIUSER_MODE` to be set independently via environment variable
- Pass explicit `backend_type` to `set_test_mode_config()`

**Function to modify:**
- `backend_mode()` fixture (lines 213-276)

**Changes needed:**
- Line 234: Remove forced `monkeypatch.setenv("QUILT_MULTIUSER_MODE", "true")`
- Line 270: Change `set_test_mode_config()` call to pass both:
  - `multiuser_mode` from environment (not derived from `TEST_BACKEND_MODE`)
  - `backend_type` from `mode` parameter (`"quilt3"` or `"platform"`)

**Expected behavior:**
- `TEST_BACKEND_MODE=platform` + `QUILT_MULTIUSER_MODE=false` → Platform backend, local mode ✅
- `TEST_BACKEND_MODE=platform` + `QUILT_MULTIUSER_MODE=true` → Platform backend, multiuser mode ✅
- `TEST_BACKEND_MODE=quilt3` + any mode → Quilt3 backend ✅

---

### Task 3: Add Make Target for Mode 3

**File:** `make.dev`

**Requirements:**
- Add new make target `test-mcp-local-platform`
- Document Mode 3 (Local-Platform) usage pattern
- Add comments clarifying backend override behavior

**Target to add:**
```makefile
test-mcp-local-platform:
    # Mode 3: Local-Platform - Platform backend with local execution
```

**Environment variables to set:**
- `TEST_BACKEND_MODE=platform`
- `QUILT_MULTIUSER_MODE=false`
- `PLATFORM_TEST_ENABLED=true`
- `FASTMCP_TRANSPORT=stdio`

**Location:** After existing MCP test targets (around line 165-182)

---

### Task 4: Add Validation and Safety Checks

**File:** `src/quilt_mcp/config.py`

**Requirements:**
- Prevent accidental backend override in production
- Add clear error messages for invalid configuration
- Log when test override is active

**Validation rules:**
- Error if `backend_type_override` is set AND `MCP_JWT_SECRET` is set (production context)
- Warn if override is active outside explicit test context
- Debug log: "Using test backend override: {backend_type}"

**Error messages to add:**
- "Backend type override is only allowed in test contexts"
- "Platform backend requires QUILT_CATALOG_URL and QUILT_REGISTRY_URL"
- "Platform backend requires JWT authentication context in tests"

---

### Task 5: Update Test Helper Function (Optional)

**File:** `tests/conftest.py`

**Function:** `_backend_mode_params()` (lines 64-71)

**Requirements:**
- Review if any changes needed for clarity
- Ensure existing alias mapping still works (`"local"`, `"multiuser"`, etc.)
- Likely no changes needed - already returns correct values

---

## Verification Requirements

### Test Scenarios

After implementation, all three modes must work correctly:

**Mode 1: Local-Quilt3 (existing)**
```bash
TEST_BACKEND_MODE=quilt3
QUILT_MULTIUSER_MODE=false  # or unset
make test-func
```
- Must use `Quilt3_Backend`
- Must complete in ~10-15s
- All tests must pass

**Mode 2: Stateless-Platform (existing)**
```bash
TEST_BACKEND_MODE=platform
QUILT_MULTIUSER_MODE=true
PLATFORM_TEST_ENABLED=true
make test-func-platform
```
- Must use `Platform_Backend`
- Must run in multiuser mode
- JWT authentication required
- All tests must pass

**Mode 3: Local-Platform (NEW - must be enabled)**
```bash
TEST_BACKEND_MODE=platform
QUILT_MULTIUSER_MODE=false
PLATFORM_TEST_ENABLED=true
make test-mcp-local-platform
```
- Must use `Platform_Backend`
- Must run in local dev mode
- stdio transport
- Filesystem state allowed
- Must complete in ~10-15s (not 30-45s)
- All platform tests must pass

### Verification Checklist

- [ ] All three modes can be run independently
- [ ] `TEST_BACKEND_MODE` directly controls backend selection
- [ ] `QUILT_MULTIUSER_MODE` independently controls deployment mode
- [ ] Factory pattern (`QuiltOpsFactory.create()`) respects test override
- [ ] Mode 3 works without Docker/HTTP overhead
- [ ] Logs show correct backend being created
- [ ] No regressions in existing tests (`make test-all`)
- [ ] Clear error messages for invalid configurations
- [ ] Production safety: override cannot be used outside tests

### Log Verification

Check logs for correct backend instantiation:
- Mode 1: "Creating Quilt3_Backend for local development mode"
- Mode 2: "Creating Platform_Backend for multiuser mode"
- Mode 3: "Creating Platform_Backend for multiuser mode" + "Using test backend override: platform"

---

## Success Criteria

- ✅ `TEST_BACKEND_MODE` is the single source of truth for backend selection in tests
- ✅ `QUILT_MULTIUSER_MODE` independently controls deployment mode features
- ✅ Mode 3 (Local-Platform) works as specified in [08-mcp-test-refactor.md](08-mcp-test-refactor.md)
- ✅ Platform backend can be tested without forcing `QUILT_MULTIUSER_MODE=true`
- ✅ All existing tests pass without modification
- ✅ No production safety issues (override blocked in prod)
- ✅ Clear documentation via make target and comments

---

## Related Files

### Must Modify
1. `src/quilt_mcp/config.py` - Add backend override mechanism
2. `tests/conftest.py` - Decouple backend selection from multiuser mode
3. `make.dev` - Add Mode 3 target and documentation

### No Changes Needed (works automatically)
- `src/quilt_mcp/ops/factory.py` - Already uses `mode_config.backend_type`
- `src/quilt_mcp/backends/quilt3_backend.py` - Backend implementation
- `src/quilt_mcp/backends/platform_backend.py` - Backend implementation

### Reference Specs
- [08-mcp-test-refactor.md](08-mcp-test-refactor.md) - Three-mode testing design
- [10-mcp-refactor-phase1.md](10-mcp-refactor-phase1.md) - Test implementation plan

---

## Notes

- This fix is essential for fast platform backend development
- Currently developers must use full Docker/HTTP stack to test platform features
- Mode 3 will reduce iteration time from ~30-45s to ~10-15s
- No changes to production behavior - only affects test configuration
- Backwards compatible - existing tests continue working unchanged

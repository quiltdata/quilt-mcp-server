# Implementation Plan: Simplify MCP Test Infrastructure

**Status**: Implementation Plan
**Sprint**: A18
**Date**: 2026-02-07
**Context**: [Simplification Vision](09-mcp-recoverable.md) | [Problem Definition](07-mcp-targets.md)

---

## Context

The current MCP test infrastructure has 10+ overlapping Make targets with complex effect-based filtering. The core insight is: **all MCP tools can be cleaned up**, so we don't need effect classification—just run all tests and clean up afterward.

This refactor:
- **10 Make targets → 3 targets** (one per deployment mode)
- **Eliminates effect filtering** (idempotent/recoverable distinction)
- **Tests all tools** (no silent skipping)
- **Auto-cleanup** (return system to original state)

---

## Critical Problem: Silent Test Skipping

**Current Behavior (BROKEN)**:
- Tools classified as `effect='create'/'update'/'remove'` get marked `SKIPPED` during discovery
- These tests NEVER execute but don't fail
- Broken or misconfigured tools go undetected
- History of vital tests silently skipped

**Example**:
```yaml
package_create:
  discovery:
    status: SKIPPED  # ❌ NEVER TESTED - might be broken!
    reason: "Write operation"
```

**New Requirement**:
- ALL tools MUST be tested during discovery
- If a tool cannot be tested safely, the test run FAILS LOUDLY
- No silent skipping - every tool must execute or fail

---

## CRUD Loop Identification Strategy

### Problem
How do we identify cleanup patterns for write operations?

### Solution: Multi-Strategy Approach

**Strategy 1: Name-Based Convention** (Primary)
- Detect paired operations by name:
  - `*_create` → `*_delete`
  - `*_put` → `*_delete`
  - `*_add` → `*_remove`
  - `*_update` → capture state, restore after
  - `*_configure` → capture config, restore after

**Strategy 2: Explicit Metadata** (Fallback)
- Tools declare cleanup in metadata:
  ```python
  @tool(cleanup="package_delete", cleanup_args={"package": "{created.name}"})
  def package_create(package: str) -> dict:
      ...
  ```

**Strategy 3: State Capture** (Universal)
- Before any write operation:
  1. Capture current state (e.g., list packages)
  2. Execute operation (e.g., create package)
  3. Identify delta (new package name)
  4. Execute cleanup (delete new package)
  5. Verify state restored (list packages matches original)

**Discovery Phase Behavior**:
- Detect CRUD pairs automatically
- If no cleanup found → FAIL with error: "Tool X is a write operation but has no cleanup strategy"
- If cleanup found → Execute test + cleanup, verify restoration
- Result: Every tool either succeeds with cleanup OR fails loudly

---

## End State: 3 Test Targets

### Targets

1. **`test-mcp`**
   - Platform backend, stdio, no Docker
   - Default for development
   - Environment: `TEST_BACKEND_MODE=platform`, `FASTMCP_TRANSPORT=stdio`

2. **`test-mcp-legacy`**
   - Quilt3 backend, stdio, no Docker
   - Legacy behavior for compatibility
   - Environment: `TEST_BACKEND_MODE=quilt3`, `FASTMCP_TRANSPORT=stdio`

3. **`test-mcp-docker`**
   - Platform backend, HTTP+JWT, Docker
   - Production validation
   - Uses docker_manager.py for container lifecycle

### What Gets Removed (Clean Break)

**Make Targets** (delete entirely):
- `test-mcp-local` → redundant with test-mcp
- `test-mcp-stateless` → replaced by test-mcp-docker
- `test-orchestrator` → move to script tests
- `test-stateless` → consolidated
- `test-multiuser-fake` → consolidated

**Test Script Features** (delete):
- `--all` flag → no longer needed, always run all
- `--idempotent-only` flag → no longer needed
- `filter_tests_by_idempotence()` function
- Effect-based test selection logic

**Config Generation** (delete):
- Effect keyword detection (`create`, `update`, `remove` keywords)
- `effect` field classification (except 'none' placeholder)
- `category: write-effect` distinction
- Discovery skipping logic for write operations

---

## Changes by Component

### 1. Make Targets (`make.dev`, lines 150-234)

**What Changes**:
- Replace 10 targets with 3
- Change default `test-mcp` to platform backend (not quilt3)
- Simplify test-mcp-docker to single command
- Remove all backward compatibility aliases

**Result**:
```makefile
test-mcp:           # Platform backend, stdio (NEW DEFAULT)
test-mcp-legacy:    # Quilt3 backend, stdio (LEGACY)
test-mcp-docker:    # Platform backend, HTTP+JWT (PRODUCTION)
test-multiuser:     # Unchanged (pytest-based)
```

### 2. Test Orchestrator (`scripts/tests/test_mcp.py`, 737 lines)

**What Changes**:
- Remove `--all` flag
- Remove `filter_tests_by_idempotence()` function
- Always run all tools (no filtering)
- Remove effect counting/reporting
- Simplify argument parsing

**Result**: Pass `tools=None` to test executor (runs everything)

### 3. Config Generator (`scripts/mcp-test-setup.py`, 1458 lines)

**What Changes**:
- Remove effect classification by keyword matching
- Remove discovery skipping for write operations
- Execute ALL tools during discovery
- Detect CRUD pairs for cleanup
- Fail loudly if write operation has no cleanup
- Add cleanup execution after each write test

**Result**:
- Config has no `SKIPPED` entries
- All tools tested during discovery
- Write operations cleaned up automatically

### 4. Test Executor (`scripts/mcp-test.py`, 1987 lines)

**What Changes**:
- Remove `--idempotent-only` flag
- Remove effect-based filtering
- Always run all tools from config

**Result**: Simpler execution, no conditional logic

### 5. Test Config (`scripts/tests/mcp-test.yaml`)

**What Changes**:
- Remove `effect` field (or always set to 'none')
- Remove `category: write-effect`
- Add `cleanup` specification for write operations
- No `SKIPPED` status in discovery

**New Format**:
```yaml
tool_name:
  category: zero-arg | required-arg | optional-arg | context-required
  discovery:
    status: PASSED | FAILED  # No SKIPPED
  cleanup:
    tool: cleanup_tool_name
    arguments: {...}
    verification: state_restored
```

### 6. Documentation

**What Changes**:
- `README.md`: Update test target documentation
- `CLAUDE.md`: Update development commands
- Remove references to idempotent/recoverable distinction

---

## CRUD Loop Detection Implementation

### Phase 1: Name-Based Detection

**During Discovery**:
1. Introspect all tools
2. Identify write operations by name patterns:
   - Contains: `create`, `put`, `upload`, `set`, `add`
   - Contains: `update`, `modify`, `change`
   - Contains: `delete`, `remove`, `reset`, `drop`
   - Contains: `configure`, `toggle`, `apply`

3. For each write operation, search for cleanup tool:
   - `package_create` → look for `package_delete`
   - `bucket_objects_put` → look for `bucket_objects_delete`
   - `user_configure` → look for inverse or state capture

4. If no cleanup found → FAIL:
   ```
   ❌ ERROR: Tool 'package_create' is a write operation but has no cleanup
      Suggestion: Add 'package_delete' tool or declare manual cleanup required
   ```

### Phase 2: Cleanup Execution

**Test Flow**:
1. Capture initial state (if applicable)
2. Execute write operation
3. Capture result (e.g., created package name)
4. Execute cleanup operation
5. Verify state restored
6. Report: PASSED or FAILED with details

**Example**:
```
Testing: package_create
  ✓ Captured initial state: 15 packages
  ✓ Executed package_create → created "test-pkg-abc123"
  ✓ Executed package_delete → deleted "test-pkg-abc123"
  ✓ Verified state restored: 15 packages
  ✅ PASSED (with cleanup)
```

### Phase 3: Failure Handling

**If cleanup fails**:
```
Testing: package_create
  ✓ Executed package_create → created "test-pkg-abc123"
  ❌ Cleanup failed: package_delete returned error
  ⚠️  STATE NOT RESTORED: Manual cleanup required
  → Run: delete package "test-pkg-abc123"
```

**Result**: Test marked as FAILED, manual intervention required

---

## Verification Plan

### Step 1: Config Generation
```bash
rm scripts/tests/mcp-test.yaml
make test-mcp
```

**Expected**:
- Config generated
- No `SKIPPED` entries
- All tools have `status: PASSED` or `FAILED`
- Write operations have `cleanup` specifications
- Any tool without cleanup causes generation to fail

### Step 2: Test All Modes
```bash
make test-mcp         # Platform backend
make test-mcp-legacy  # Quilt3 backend
make test-mcp-docker  # Docker HTTP+JWT
```

**Expected**:
- All tools execute (no filtering)
- Write operations clean up automatically
- State verification succeeds
- Tests complete successfully

### Step 3: Verify No Silent Skipping
```bash
grep -c "SKIPPED" scripts/tests/mcp-test.yaml
```

**Expected**: 0 (zero) - no skipped tests

### Step 4: Full Test Suite
```bash
make test-all
```

**Expected**: All tests pass

---

## Success Criteria

✅ **3 clear test targets** - One per deployment mode
✅ **No effect filtering** - All tools run by default
✅ **No silent skipping** - Every tool tested or fails
✅ **CRUD auto-detection** - Write operations paired with cleanup
✅ **State restoration** - System returns to original state
✅ **Loud failures** - Misconfigured tools fail immediately
✅ **Clean break** - No backward compatibility baggage

---

## Risks and Mitigations

### Risk 1: CRUD Detection Misses Pairs

**Impact**: Write operation has no cleanup, leaves state changes

**Mitigation**:
- Detection algorithm fails loudly if no cleanup found
- Manual cleanup can be declared in tool metadata
- State capture works as universal fallback

### Risk 2: Cleanup Execution Fails

**Impact**: State not restored, subsequent tests affected

**Mitigation**:
- Test marked as FAILED (not PASSED)
- Manual cleanup instructions printed
- State diff shown for debugging
- Can re-run setup to restore clean state

### Risk 3: Increased Test Duration

**Impact**: Running all tools takes longer than filtering

**Mitigation**:
- Stdio modes stay fast (~15-20s)
- Docker mode already slow
- Benefit: catch broken tests early

---

## Critical Files

**To Modify**:
1. `make.dev` (lines 150-234) - Replace 10 targets with 3
2. `scripts/tests/test_mcp.py` - Remove filtering logic
3. `scripts/mcp-test-setup.py` - Add CRUD detection, remove skipping
4. `scripts/mcp-test.py` - Remove idempotent-only flag

**To Update**:
5. `README.md` - Test documentation
6. `CLAUDE.md` - Development commands

**Auto-Generated** (will change):
7. `scripts/tests/mcp-test.yaml` - No SKIPPED, adds cleanup specs

---

## Future Work (Phase 2)

1. **Cleanup metadata**: Add cleanup declarations to tool definitions
2. **Parallel execution**: Run independent tests concurrently
3. **Resource namespacing**: Avoid test conflicts (e.g., test-pkg-{uuid})
4. **Cleanup validation**: Verify cleanup truly restores state
5. **Manual test tracking**: Tools that require manual testing

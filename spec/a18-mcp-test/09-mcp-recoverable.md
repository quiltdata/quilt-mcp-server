# MCP Test Simplification: Everything Is Recoverable

**Status**: Vision/Design
**Sprint**: A18
**Date**: 2026-02-07
**Context**: [Refactor Vision](08-mcp-test-refactor.md)

---

## Core Insight

**There are no permanent tools.** Everything can be cleaned up. Therefore:

- No "idempotent vs recoverable" distinction needed
- No "effect category" filtering required
- Just run all tests and clean up afterward
- Failures are recoverable by re-running setup

---

## End State

### Three Test Targets (Logical Naming)

1. **`test-mcp`** - stdio, platform backend, no docker (default/future)
2. **`test-mcp-legacy`** - stdio, quilt3 backend, no docker (current/legacy)
3. **`test-mcp-docker`** - http, platform backend, stateless docker (production)

### One Test Target Per Mode

```makefile
test-mcp:          # Run all tests with platform backend (default)
test-mcp-legacy:   # Run all tests with quilt3 backend (legacy)
test-mcp-docker:   # Run all tests in Docker with HTTP+JWT (production)
```

### Cleanup Is Automatic

- All write operations have cleanup defined in config
- Cleanup runs in teardown phase automatically
- If cleanup fails, report it but don't block
- Re-running setup fixes any leftover state

---

## What This Eliminates

### From Make Targets

**Remove these targets:**

```makefile
test-mcp-docker           # Redundant with test-legacy
test-mcp-stateless        # Rename to test-stateless
test-mcpb                 # Move to standard pytest
test-legacy-idempotent    # Merge into test-legacy
test-legacy-recoverable   # Merge into test-legacy
test-stateless-idempotent # Merge into test-stateless
test-stateless-recoverable # Merge into test-stateless
test-*-all                # Redundant (all is default)
```

**Keep only:**

```makefile
test-legacy               # All tests, legacy mode
test-stateless            # All tests, stateless mode
test-local-platform       # All tests, local-platform mode (new)
```

### From Scripts

**Remove:**

- Effect category filtering (`--effect` flag)
- Discovery behavior distinction (no more "skip during discovery")
- Cleanup orchestration complexity (just run cleanup tools)
- Permanent operation handling (doesn't exist)

**Simplify:**

- `test_mcp.py`: Remove `--effect` parameter, always run all tools
- `mcp-test.yaml`: Remove `effect` field, just define `cleanup` tool
- No separate "idempotent" vs "recoverable" test suites

### From Configuration

**Remove these fields from `mcp-test.yaml`:**

```yaml
effect: none | create | update | remove     # DELETE
category: zero-arg | write-effect           # DELETE
discovery:                                  # DELETE
  status: PASSED | SKIPPED
```

**Keep only:**

```yaml
tool_name:
  description: "What it does"
  arguments: {...}
  cleanup:                    # Optional
    tool: cleanup_tool_name
    arguments: {...}
```

---

## What Gets Rewritten

### 1. `test_mcp.py`

**Before (complex):**

```python
def select_tests(config, effect_filter):
    if effect_filter == "idempotent":
        return [t for t in all_tools if t["effect"] == "none"]
    elif effect_filter == "recoverable":
        return [t for t in all_tools if t["effect"] in ["create", "update"]]
```

**After (simple):**

```python
def run_all_tests(config, mode):
    """Run all tests in specified mode, cleanup automatically."""
    results = []
    for tool in config["test_tools"]:
        result = run_test(tool)
        results.append(result)
        if tool.get("cleanup") and result.passed:
            run_cleanup(tool["cleanup"])
    return results
```

### 2. `Makefile`

**Before (16+ targets):**

```makefile
test-mcp:              # Currently: stdio + quilt3
test-mcp-docker:       # Currently: Docker + stdio + quilt3
test-mcp-stateless:    # Currently: Docker + HTTP + platform
test-legacy-idempotent:
test-legacy-recoverable:
test-stateless-idempotent:
test-stateless-recoverable:
# ... more variants
```

**After (3 targets):**

```makefile
test-mcp:              # stdio, platform backend, no docker (NEW DEFAULT)
 @export TEST_BACKEND_MODE=platform FASTMCP_TRANSPORT=stdio && \
 uv run python scripts/tests/test_mcp.py

test-mcp-legacy:       # stdio, quilt3 backend, no docker (OLD BEHAVIOR)
 @export TEST_BACKEND_MODE=quilt3 FASTMCP_TRANSPORT=stdio && \
 uv run python scripts/tests/test_mcp.py

test-mcp-docker:       # http, platform backend, docker (PRODUCTION)
 @export TEST_DOCKER_IMAGE=quilt-mcp:test && \
 uv run python scripts/tests/test_mcp.py --docker
```

### 3. `mcp-test.yaml`

**Before (verbose):**

```yaml
package_create:
  effect: create
  category: write-effect
  discovery:
    status: SKIPPED
    reason: "Write operation"
  cleanup:
    method: delete
    tool: package_delete
    verification: state_restored
```

**After (minimal):**

```yaml
package_create:
  description: "Create test package"
  arguments:
    package: "test-pkg"
  cleanup:
    tool: package_delete
    arguments:
      package: "test-pkg"
```

---

## Migration Steps

### Phase 1: Remove Effect Filtering

1. Delete `--effect` flag from `test_mcp.py`
2. Remove effect-based test selection logic
3. Always run all tools, cleanup after each

### Phase 2: Consolidate Make Targets

1. Remove all `-idempotent` and `-recoverable` variants
2. Keep only 3 mode-based targets
3. Add deprecation warnings to old targets

### Phase 3: Simplify Configuration

1. Remove `effect`, `category`, `discovery` fields
2. Keep only `cleanup` (optional)
3. Regenerate test configs

### Phase 4: Update Documentation

1. Replace "idempotent/recoverable" with "all tests with cleanup"
2. Document 3 modes only
3. Remove effect category references

---

## Why This Works

1. **No permanent state changes** - All tools can be reversed
2. **Cleanup is cheap** - Just call the inverse tool
3. **Failures are recoverable** - Re-run setup, or cleanup manually
4. **Simpler mental model** - Run tests, clean up, done

---

## Result

- **From 931 lines** → **~100 lines** of design
- **From 16+ targets** → **3 targets**
- **From 3 dimensions** → **1 dimension** (mode only)
- **From complex orchestration** → **Simple run-and-cleanup**

The only thing that matters: **Which deployment mode are you testing?**

Everything else is just "run the test, then clean up."

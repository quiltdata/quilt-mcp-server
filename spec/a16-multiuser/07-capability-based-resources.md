# A16.7: Capability-Based Resource Detection

**Date**: 2026-02-04
**Branch**: `a15-multiuser`
**Status**: 🔄 In Progress

## Problem Statement

The solution in [A16.6](06-resource-failure-fix.md) was a hack that coupled tests to deployment mode terminology rather than actual server capabilities.

### What Was Wrong With A16.6

**The hack:**

- Added `mode: local_dev` fields to `scripts/tests/mcp-test.yaml`
- Added `--server-mode` CLI flag to `scripts/mcp-test.py`
- Tests required manual flag: `--server-mode multiuser`
- Used `--no-generate` flag in test-runner to prevent YAML regeneration

**Why it was wrong:**

1. **Wrong terminology**: "local_dev" vs "multiuser" instead of stateful vs stateless capabilities
2. **Manual coordination**: Tests need to know server deployment mode
3. **Fragile**: Mode fields get removed when YAML regenerates
4. **Not self-documenting**: No way for clients to discover capabilities

### Root Cause

The real issue is about **stateful capabilities**, not deployment modes:

| Resource | Actually Requires | Currently Gated By |
|----------|------------------|-------------------|
| `workflow://workflows` | Filesystem state (`~/.quilt/workflows/`) | `is_local_dev` ✅ |
| `metadata://templates` | Nothing (static in-memory) | `is_local_dev` ❌ |
| `metadata://examples` | Nothing (static in-memory) | `is_local_dev` ❌ |
| `metadata://troubleshooting` | Nothing (static message) | `is_local_dev` ❌ |

**Key insight from user:** "The real issue is that certain tools are stateful, and thus don't work in a multiuser/clustered/stateless context."

## Solution Design

### Architecture Overview

Add a **`server://capabilities`** resource that advertises what features and resources are available and why.

**Flow:**

```
Server Startup
    ↓
ModeConfig determines resource registration
    ↓
server://capabilities advertises availability
    ↓
Tests query server://capabilities at runtime
    ↓
Tests skip unavailable resources with clear reasons
```

**Benefits:**

- ✅ Single source of truth (server code)
- ✅ No manual flags needed
- ✅ Self-documenting (includes reasons)
- ✅ Follows existing `auth://filesystem/status` pattern
- ✅ Terminology reflects reality (stateful vs stateless)

### Capabilities Resource Schema

```json
{
  "deployment_mode": "local_dev" | "multiuser",
  "backend_type": "quilt3" | "graphql",
  "filesystem_state_allowed": boolean,
  "quilt3_library_allowed": boolean,
  "requires_jwt": boolean,

  "features": {
    "workflows": boolean,
    "metadata_guidance": boolean,
    "admin_api": boolean,
    "sso_config": boolean
  },

  "resources": {
    "workflow://workflows": {
      "available": boolean,
      "reason": "Requires filesystem state" | "Available"
    },
    "metadata://templates": {
      "available": boolean,
      "reason": "Local development only" | "Available"
    }
  }
}
```

### Test Flow

```python
# 1. Test queries capabilities
capabilities = test.read_resource("server://capabilities")
mode = capabilities["deployment_mode"]
resources = capabilities["resources"]

# 2. For each resource test:
if uri in resources:
    if not resources[uri]["available"]:
        # Skip with clear reason
        print(f"⏭️  Skipped: {resources[uri]['reason']}")
        return

# 3. Test resource normally
result = test.read_resource(uri)
```

## Implementation

### 1. Add Capabilities Resource

**File**: [src/quilt_mcp/resources.py](../../src/quilt_mcp/resources.py) (after line 319)

```python
@mcp.resource(
    "server://capabilities",
    name="Server Capabilities",
    description="Server deployment mode and feature availability",
    mime_type="application/json",
)
async def server_capabilities() -> str:
    """Advertise server capabilities and available features."""
    from quilt_mcp.config import get_mode_config

    mode_config = get_mode_config()

    capabilities = {
        "deployment_mode": "multiuser" if mode_config.is_multiuser else "local_dev",
        "backend_type": mode_config.backend_type,
        "filesystem_state_allowed": mode_config.allows_filesystem_state,
        "quilt3_library_allowed": mode_config.allows_quilt3_library,
        "requires_jwt": mode_config.requires_jwt,

        "features": {
            "workflows": mode_config.allows_filesystem_state,
            "metadata_guidance": mode_config.is_local_dev,
            "admin_api": True,
            "sso_config": True,
        },

        "resources": {
            "workflow://workflows": {
                "available": mode_config.allows_filesystem_state,
                "reason": "Requires filesystem state" if not mode_config.allows_filesystem_state else "Available"
            },
            "metadata://templates": {
                "available": mode_config.is_local_dev,
                "reason": "Local development only" if not mode_config.is_local_dev else "Available"
            },
            "metadata://examples": {
                "available": mode_config.is_local_dev,
                "reason": "Local development only" if not mode_config.is_local_dev else "Available"
            },
            "metadata://troubleshooting": {
                "available": mode_config.is_local_dev,
                "reason": "Local development only" if not mode_config.is_local_dev else "Available"
            }
        }
    }

    return _serialize_result(capabilities)
```

### 2. Update Test Framework

**File**: [scripts/mcp-test.py](../../scripts/mcp-test.py)

**Key changes:**

1. **Add capability querying** (new method):

```python
def _query_server_capabilities(self) -> Dict[str, Any]:
    """Query server for its capabilities."""
    try:
        result = self.read_resource("server://capabilities")
        contents = result.get("contents", [])
        if contents:
            capabilities_json = contents[0].get("text", "{}")
            return json.loads(capabilities_json)
    except Exception as e:
        self._log(f"Capabilities not available: {e}", "DEBUG")

    # Fallback for old servers
    return {"deployment_mode": "unknown", "resources": {}}
```

1. **Update ResourcesTester.**init****:

```python
def __init__(self, config: Dict[str, Any] = None, **kwargs):
    super().__init__(**kwargs)
    self.config = config or {}
    self.results = TestResults()
    self.server_capabilities = None  # NEW
    self.available_uris = set()
    self.available_templates = set()
```

1. **Query capabilities during initialization**:

```python
def _initialize_resources(self) -> bool:
    # Query capabilities FIRST
    self.server_capabilities = self._query_server_capabilities()

    # Then get available resources
    result = self.list_resources()
    # ... rest of logic

    mode = self.server_capabilities.get("deployment_mode", "unknown")
    print(f"📋 Server mode: {mode}")
```

1. **Check capabilities in run_test** (replace lines 1068-1079):

```python
# Check server-reported availability
if self.server_capabilities and "resources" in self.server_capabilities:
    resource_info = self.server_capabilities["resources"].get(uri_pattern)
    if resource_info and not resource_info.get("available", True):
        reason = resource_info.get("reason", "Not available")
        mode = self.server_capabilities.get("deployment_mode", "unknown")
        print(f"  ⏭️  Skipped: {reason}")
        self.results.record_skip({
            "uri": uri_pattern,
            "reason": reason,
            "server_mode": mode
        })
        return
```

1. **Remove `--server-mode` CLI argument** (line ~1586)

2. **Remove `server_mode` parameter** from:
   - `run_test_suite()` signature
   - `ResourcesTester.__init__()` calls
   - Parameter passing in main()

### 3. Remove Manual Flags

**File**: [make.dev](../../make.dev) (line 157)

```makefile
# Remove --server-mode multiuser flag
(uv run python scripts/mcp-test.py http://localhost:8002/mcp \
    --jwt \
    --tools-test --resources-test \
    --config scripts/tests/mcp-test.yaml && \
```

**File**: [scripts/test-runner.py](../../scripts/test-runner.py) (line 556)

```python
# Remove --no-generate flag
'uv run python scripts/tests/test_mcp.py --docker --image quilt-mcp:test && '
```

### 4. Regenerate Test Configuration

```bash
uv run python scripts/mcp-list.py
```

This regenerates [scripts/tests/mcp-test.yaml](../../scripts/tests/mcp-test.yaml) without mode fields.

## Test Results

### Before (With Hack)

```
[Script Tests → MCP stateless]
  ⏭️  Skipped (requires local_dev mode, server is in multiuser mode)
  ⏭️  Skipped (requires local_dev mode, server is in multiuser mode)
  ⏭️  Skipped (requires local_dev mode, server is in multiuser mode)
  ⏭️  Skipped (requires local_dev mode, server is in multiuser mode)

✅ 11 passed, ⏭️ 4 skipped
```

**Problems:**

- Requires manual `--server-mode multiuser` flag
- Mode terminology couples to deployment, not capabilities
- Test must know server internals

### After (With Capabilities)

```
[Script Tests → MCP stateless]
📋 Server mode: multiuser
📋 Available: 11 static, 0 templates

Testing resource: workflow://workflows
  ⏭️  Skipped: Requires filesystem state

Testing resource: metadata://templates
  ⏭️  Skipped: Local development only

Testing resource: metadata://examples
  ⏭️  Skipped: Local development only

Testing resource: metadata://troubleshooting
  ⏭️  Skipped: Local development only

✅ 11 passed, ⏭️ 4 skipped
```

**Improvements:**

- ✅ No manual flags needed
- ✅ Clear, descriptive skip reasons
- ✅ Server advertises its capabilities
- ✅ Tests auto-adapt to server

## Verification

### Manual Testing

1. **Query capabilities directly**:

```bash
# Local dev server
make run-inspector
# In inspector: Read server://capabilities
# Expected: all resources "available": true

# Multiuser server
# Start: make test-mcp-stateless
# Query: server://capabilities
# Expected: 4 resources "available": false
```

1. **Run tests**:

```bash
make test-mcp-stateless
# Expected: 4 resources skipped with reasons
# No manual flags needed
```

1. **YAML regeneration**:

```bash
uv run python scripts/mcp-list.py
git diff scripts/tests/mcp-test.yaml
# Expected: NO mode fields
```

### Automated Testing

```bash
make test-all
```

**Expected results:**

- All unit tests pass
- All integration tests pass
- MCP stateless tests: 11 passed, 4 skipped
- No failures

## Architecture Benefits

### Single Source of Truth

**Before (hack):**

```
resources.py → Conditional registration
     ↓
  (gap)
     ↓
mcp-test.yaml → Manual mode fields
     ↓
mcp-test.py → Manual --server-mode flag
```

**After (capabilities):**

```
resources.py → Conditional registration
     ↓
server://capabilities → Advertises availability
     ↓
mcp-test.py → Queries capabilities
     ↓
Auto-skip with reasons
```

### Comparison to Other Approaches

| Approach | Pros | Cons |
|----------|------|------|
| **Manual mode flag** (A16.6 hack) | Simple | Fragile, manual, wrong terminology |
| **Introspect actual resources** | Always accurate | Can't test "should be available" |
| **Generate all + capability metadata** | Complete tests | YAML out of sync |
| **Capabilities resource** ✅ | Dynamic, self-doc, clean | Requires new resource |

### Future Enhancements

1. **Extend features**:

```json
{
  "features": {
    "elasticsearch": {"enabled": true, "version": "7.10"},
    "admin_api": {"enabled": true, "requires_privileges": true},
    "sso": {"enabled": false, "reason": "SSO_ENABLED not set"}
  }
}
```

1. **Add versioning**:

```json
{
  "server_version": "0.14.0",
  "mcp_protocol_version": "2024-11-05"
}
```

1. **Runtime toggling**:

```python
@mcp.tool()
async def admin_feature_toggle(feature: str, enabled: bool):
    """Toggle feature availability (admin only)."""
```

## Related Work

- [A16.1: Multiuser Terminology](01-multiuser-terminology.md) - Mode definitions
- [A16.2: Multiuser Implementation](02-multiuser-implementation.md) - Resource registration
- [A16.6: Resource Failure Fix](06-resource-failure-fix.md) - The hack this replaces

## Key Files Modified

| File | Change | Lines |
|------|--------|-------|
| `src/quilt_mcp/resources.py` | Add `server://capabilities` | +50 |
| `scripts/mcp-test.py` | Capability detection | ~80 |
| `make.dev` | Remove `--server-mode` flag | -1 |
| `scripts/test-runner.py` | Remove `--no-generate` flag | -1 |
| `scripts/tests/mcp-test.yaml` | Regenerate (clean) | -4 |

## Lessons Learned

1. **Terminology matters**: "stateful vs stateless" is clearer than "local_dev vs multiuser"
2. **Server should advertise capabilities**: Don't make clients guess
3. **Follow existing patterns**: `auth://filesystem/status` shows the way
4. **Avoid manual coordination**: Auto-detection prevents drift
5. **Single source of truth**: Server code is authoritative

## Migration Notes

This is a **breaking change** for external tools using `--server-mode` flag, but:

- Flag was only added in commit 00d53e9 (2026-02-03)
- Not documented in public API
- No known external users

The change is **backward compatible** for servers:

- Old servers without `server://capabilities` work fine
- Tests gracefully fall back to testing all resources
- Normal "resource not found" errors provide diagnostics

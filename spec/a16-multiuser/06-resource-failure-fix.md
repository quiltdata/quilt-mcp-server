# A16.6: Multiuser Test Failure Fix

**Date**: 2026-02-03
**Branch**: `a15-multiuser`
**Status**: ✅ Complete

## Problem Statement

The `make test-mcp-stateless` target was failing with terrible error messages:

```
[Script Tests → MCP stateless]
    Error: Resource not found in server resources
    Error: Resource not found in server resources
    Error: Resource not found in server resources
    Error: Resource not found in server resources
make[1]: *** [test-mcp-stateless] Error 1
make: *** [test-all] Error 2
```

### Issues Identified

1. **Terrible error messages**: No indication of WHICH resource failed or WHY
2. **Unrecognized mode restrictions**: Resources disabled in multiuser mode weren't recognized by the test framework

## Root Cause Analysis

### Investigation Steps

1. Examined test output to find which resources were failing
2. Searched for resource registrations in codebase
3. Identified 4 resources only registered in `local_dev` mode:
   - `metadata://templates`
   - `metadata://examples`
   - `metadata://troubleshooting`
   - `workflow://workflows`

### Code References

From [resources.py:126-133](../../../src/quilt_mcp/resources.py#L126-L133):

```python
# Local dev only - these provide guidance resources
if not is_local_dev():
    @mcp.resource("metadata://templates")
    def metadata_templates_resource() -> str:
        """List available metadata templates"""
        return json.dumps(templates_data, indent=2)

    # ... similar registrations for other metadata/workflow resources
```

The test YAML had no way to know these resources were mode-specific, so it tried to test them in multiuser mode and failed.

## Solution Design

### 1. Add Mode Metadata to Test Configuration

**File**: `scripts/tests/mcp-test.yaml`

Add a `mode` field to resources that are only available in specific deployment modes:

```yaml
metadata://templates:
  description: List available metadata templates
  effect: none
  mode: local_dev  # ← NEW: Indicates this resource requires local_dev mode
  uri: metadata://templates
  uri_variables: {}
  expected_mime_type: application/json
```

### 2. Add Mode Awareness to Test Script

**File**: `scripts/mcp-test.py`

#### 2a. Add CLI Argument

```python
parser.add_argument("--server-mode", type=str,
                   choices=["local_dev", "multiuser"],
                   help="Server deployment mode (affects which resources are available)")
```

#### 2b. Thread Through ResourcesTester

```python
class ResourcesTester(MCPTester):
    def __init__(self, config: Dict[str, Any] = None, server_mode: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.config = config or {}
        self.results = TestResults()
        self.server_mode = server_mode  # ← NEW
```

#### 2c. Skip Mode-Incompatible Resources

```python
def run_test(self, uri_pattern: str, test_config: Dict[str, Any]) -> None:
    # Check mode compatibility
    required_mode = test_config.get("mode")
    if required_mode and self.server_mode:
        if required_mode != self.server_mode:
            print(f"  ⏭️  Skipped (requires {required_mode} mode, server is in {self.server_mode} mode)")
            self.results.record_skip({
                "uri": uri_pattern,
                "reason": f"Resource requires {required_mode} mode (server is {self.server_mode})",
                "required_mode": required_mode,
                "current_mode": self.server_mode
            })
            return
```

### 3. Improve Error Messages

**Before**:
```
❌ Resource not found in server resources
```

**After**:
```
❌ Resource 'metadata://templates' not found in server resources
   This may indicate the resource is disabled in the current mode
```

Changes to error messages:

```python
if uri not in self.available_uris:
    print(f"  ❌ Resource '{uri}' not found in server resources")
    print(f"     This may indicate the resource is disabled in the current mode")
    self.results.record_failure({
        "uri": uri_pattern,
        "resolved_uri": uri,
        "error": f"Resource '{uri}' not found in server resources (may be mode-restricted)",
        "uri_variables": uri_vars,
        "available_count": len(self.available_uris)
    })
    return
```

### 4. Update Makefile

**File**: `make.dev`

Add `--server-mode multiuser` to the test command:

```makefile
test-mcp-stateless: docker-build
	@echo "🔐 Testing stateless MCP with JWT authentication..."
	@uv sync --group test
	@export TEST_DOCKER_IMAGE=quilt-mcp:test && \
		uv run python scripts/docker_manager.py start \
			--mode stateless \
			--image $$TEST_DOCKER_IMAGE \
			--name mcp-stateless-test \
			--port 8002 \
			--jwt-secret "test-secret" && \
		(uv run python scripts/mcp-test.py http://localhost:8002/mcp \
			--jwt \
			--server-mode multiuser \  # ← NEW
			--tools-test --resources-test \
			--config scripts/tests/mcp-test.yaml && \
		uv run python scripts/docker_manager.py stop --name mcp-stateless-test) || \
		(uv run python scripts/docker_manager.py stop --name mcp-stateless-test && exit 1)
	@echo "✅ Stateless JWT testing with catalog authentication completed"
```

## Implementation

### Commit 1: Test Improvements

**Commit**: `00d53e9`
**Message**: `test: fix multiuser resource test failures with mode awareness`

Files changed:
- `make.dev` - Added `--server-mode multiuser` flag
- `scripts/mcp-test.py` - Mode-aware resource testing (+45/-14 lines)
- `scripts/tests/mcp-test.yaml` - Marked 4 resources as `local_dev`
- `scripts/tests/coverage_results.yaml` - Coverage update

### Commit 2: Documentation

**Commit**: `8b4c5e4`
**Message**: `docs: document multiuser test improvements and mode awareness`

Files changed:
- `spec/a16-multiuser/02-multiuser-implementation.md` - Updated
- `spec/a16-multiuser/03-multiuser-status.md` - Updated
- `spec/a16-multiuser/04-multiuser-test.md` - New
- `spec/a16-multiuser/05-multiuser-test-reuse.md` - New

## Test Results

### Before Fix

```
[Script Tests → MCP stateless]
    Error: Resource not found in server resources
    Error: Resource not found in server resources
    Error: Resource not found in server resources
    Error: Resource not found in server resources
make[1]: *** [test-mcp-stateless] Error 1
make: *** [test-all] Error 2
```

### After Fix

```
📊 Resource Test Results: 11 passed, 0 failed, 4 skipped (out of 15 total)

================================================================================
📊 TEST SUITE SUMMARY
================================================================================

🔧 TOOLS (55/55 tested)
   ✅ 55 passed

🗂️  RESOURCES (15/15 tested)
   Type Breakdown: 11 static URIs, 0 templates
   ✅ 11 passed, ⏭️ 4 skipped

   Skipped Resources (4):

      • metadata://templates
        Reason: Resource requires local_dev mode (server is multiuser)

      • metadata://examples
        Reason: Resource requires local_dev mode (server is multiuser)

      • metadata://troubleshooting
        Reason: Resource requires local_dev mode (server is multiuser)

      • workflow://workflows
        Reason: Resource requires local_dev mode (server is multiuser)

================================================================================
   Overall Status: ✅ ALL TESTS PASSED
   - 55 idempotent tools verified
   - 11 resources verified
   - No failures detected
================================================================================
```

## Key Improvements

1. ✅ **Clear Error Messages**: Shows specific resource URI and hints at mode restrictions
2. ✅ **Smart Skipping**: Resources requiring `local_dev` mode are properly skipped in `multiuser` mode
3. ✅ **Better Diagnostics**: Skip reasons explain why resources aren't tested
4. ✅ **Mode Awareness**: Test framework understands deployment mode differences
5. ✅ **Clean Test Output**: All tests pass with informative skip messages

## Architecture Impact

### Test Configuration Schema

The test YAML now supports an optional `mode` field:

```yaml
test_resources:
  <resource_uri>:
    description: <string>
    effect: <none|create|update|remove>
    mode: <local_dev|multiuser>  # Optional: restricts when resource is tested
    uri: <string>
    uri_variables: <object>
    expected_mime_type: <string>
    content_validation: <object>
```

### Test Script Architecture

```
MCPTester (base class)
├── ToolsTester (tools testing)
└── ResourcesTester (resources testing)
    ├── server_mode: Optional[str]  # NEW
    └── run_test()
        └── Mode compatibility check  # NEW
            ├── Skip if mode mismatch
            └── Proceed if compatible
```

### Mode Flow

```
make test-mcp-stateless
    ↓
docker_manager.py --mode stateless
    ↓
mcp-test.py --server-mode multiuser
    ↓
ResourcesTester(server_mode="multiuser")
    ↓
For each resource:
    ├── Check test_config.get("mode")
    ├── If mode specified and doesn't match:
    │   └── Skip with clear message
    └── Otherwise:
        └── Test resource normally
```

## Future Considerations

### 1. Auto-Detection of Server Mode

Instead of passing `--server-mode` manually, could detect from server:

```python
# Query server for its mode
def detect_server_mode(self) -> str:
    """Detect server deployment mode from auth://status resource."""
    result = self.read_resource("auth://status")
    auth_info = json.loads(result["contents"][0]["text"])
    return auth_info.get("deployment_mode", "local_dev")
```

### 2. Mode Verification

Could verify that the test's `--server-mode` matches the actual server mode:

```python
def verify_mode_match(self):
    """Ensure test mode matches server mode."""
    detected = self.detect_server_mode()
    if self.server_mode and detected != self.server_mode:
        raise ValueError(
            f"Server mode mismatch: test expects {self.server_mode}, "
            f"server reports {detected}"
        )
```

### 3. Test Matrix

Could run tests in both modes:

```makefile
test-mcp-all-modes:
	make test-mcp-stateless  # multiuser mode
	make test-mcp-stdio      # local_dev mode
```

## Related Work

- [A16.1: Multiuser Terminology](01-multiuser-terminology.md) - Mode definitions
- [A16.2: Multiuser Implementation](02-multiuser-implementation.md) - Resource registration
- [A16.3: Multiuser Status](03-multiuser-status.md) - Status work
- [A16.4: Multiuser Test](04-multiuser-test.md) - Integration tests
- [A16.5: Multiuser Test Reuse](05-multiuser-test-reuse.md) - Test strategy

## Lessons Learned

1. **Mode awareness is critical**: Test infrastructure must understand deployment modes
2. **Error messages matter**: Specific, actionable errors save debugging time
3. **Skip vs Fail**: Not all missing resources are failures - some are intentional
4. **Configuration over detection**: Explicit mode declaration avoids ambiguity
5. **Progressive enhancement**: Start with manual mode specification, can add auto-detection later

# Vision: MCP Test Refactor

**Status**: Vision/Design
**Sprint**: A18
**Date**: 2026-02-07
**Context**: [Problem Definition](07-mcp-targets.md) | [A18 Sprint Design](../a18-design.md)

---

## Executive Summary

This document describes the ideal state for MCP test organization after refactoring. The vision is based on two orthogonal dimensions that fully characterize the testing matrix:

1. **Deployment Mode** - How the MCP server is deployed and runs
2. **Test Effect Category** - What side effects tests have on system state

All current test targets can be rationalized into combinations of these dimensions, eliminating redundancy and confusion.

---

## Core Principles

### 1. Orthogonal Dimensions

The test matrix should be organized around **two independent dimensions**:

**Dimension 1: Deployment Mode**

- Legacy (local quilt3)
- Stateless (multiuser platform)
- Local-Platform (development platform)

**Dimension 2: Test Effect Category**

- Idempotent (read-only)
- Recoverable (write + cleanup)
- Permanent (if any exist)

These dimensions are **truly orthogonal** - any deployment mode can run any test effect category.

### 2. Clear Naming Convention

Target names should explicitly indicate what they test:

```
test-{mode}-{effect}
```

**Examples:**

- `test-legacy-idempotent` - Legacy mode, read-only tests
- `test-stateless-recoverable` - Stateless mode, write+cleanup tests
- `test-local-platform-idempotent` - Local platform mode, read-only tests

### 3. Single Source of Truth

All test logic should live in one place:

- **Test execution engine**: `scripts/mcp-test.py` (already exists)
- **Test orchestration**: Unified in Make targets
- **Configuration**: Single YAML config with mode variants

### 4. Unified Infrastructure

No duplicate systems:

- **One Docker manager**: `docker_manager.py` for all Docker operations
- **One test runner**: `mcp-test.py` for both stdio and HTTP
- **One config generator**: `mcp-test-setup.py` for all modes

---

## Three Deployment Modes (Dimension 1)

### Mode 1: Legacy

**Purpose**: How MCP server works today for individual developers using `uvx quilt-mcp`

**Characteristics:**

- **Execution**: Direct process (no Docker)
- **Transport**: stdio (stdin/stdout pipes)
- **Backend**: quilt3 (personal AWS credentials)
- **Auth**: User's own credentials via quilt3 library
- **State**: Filesystem state allowed
- **Speed**: Fastest (~10-15s)

**Environment Variables:**

```bash
QUILT_MULTIUSER_MODE=false  # or unset (default)
FASTMCP_TRANSPORT=stdio      # or unset (default)
TEST_BACKEND_MODE=quilt3
```

**What This Tests:**

- Local development workflow
- quilt3 library integration
- stdio transport with JSON-RPC
- Personal AWS credential flows
- Filesystem-based caching

**When to Run:**

- During active development (fastest iteration)
- Before committing code
- CI/CD core test suite

---

### Mode 2: Stateless

**Purpose**: Production multiuser deployment with horizontal scaling

**Characteristics:**

- **Execution**: Docker container
- **Transport**: HTTP (REST API)
- **Backend**: Platform/GraphQL (catalog-managed auth)
- **Auth**: JWT tokens (Bearer authentication)
- **State**: No filesystem state (stateless)
- **Speed**: Slower (~30-45s with Docker startup)

**Environment Variables:**

```bash
QUILT_MULTIUSER_MODE=true
FASTMCP_TRANSPORT=http
MCP_JWT_SECRET=<required>
QUILT_CATALOG_URL=<required>
QUILT_REGISTRY_URL=<required>
TEST_BACKEND_MODE=platform
```

**What This Tests:**

- HTTP transport with JWT authentication
- Platform backend GraphQL integration
- Multiuser isolation and role-based access
- Stateless operation (no caching between requests)
- Docker container deployment
- Horizontal scalability

**When to Run:**

- Before releases
- Integration testing
- Platform feature validation
- Deployment verification

---

### Mode 3: Local-Platform

**Purpose**: Fast iteration on platform features without Docker/HTTP overhead

**Characteristics:**

- **Execution**: Direct process (no Docker)
- **Transport**: stdio (stdin/stdout pipes)
- **Backend**: Platform/GraphQL (catalog-managed auth)
- **Auth**: Simulated JWT/roles (no actual HTTP headers)
- **State**: Filesystem state allowed
- **Speed**: Fast (~10-15s, similar to legacy)

**Environment Variables:**

```bash
QUILT_MULTIUSER_MODE=false   # Local execution
FASTMCP_TRANSPORT=stdio      # stdio transport
TEST_BACKEND_MODE=platform   # But use platform backend
PLATFORM_TEST_ENABLED=true
```

**What This Tests:**

- Platform backend logic without HTTP overhead
- GraphQL integration
- Multiuser features in fast stdio mode
- Role-based access without JWT validation
- Platform-specific features during development

**When to Run:**

- Developing platform features locally
- Testing GraphQL queries quickly
- Validating multiuser logic without Docker
- Fast iteration on platform backend

**Current Status:** This mode is **accessible but not explicitly tested**. There's no dedicated Make target for it today.

---

## Three Test Effect Categories (Dimension 2)

### Category 1: Idempotent (Read-Only)

**Definition**: Tests that have no side effects and can be run repeatedly without changing system state.

**Characteristics:**

- **Safety**: Completely safe, no cleanup needed
- **Speed**: Fastest (no write overhead)
- **Parallelization**: Can run concurrently
- **CI/CD**: Always enabled
- **Risk**: Zero

**Examples:**

- `bucket_objects_list` - List S3 objects
- `package_browse` - Read package metadata
- `athena_table_schema` - Describe table structure
- `search_packages` - Query package index
- `bucket_object_info` - Get object metadata

**Test Configuration:**

```yaml
effect: none
category: zero-arg | required-arg | optional-arg
```

**Discovery Behavior:**

- Tools ARE executed during config generation
- Responses captured for validation
- No cleanup needed

**Runtime Behavior:**

- Always included in test runs
- Can run in parallel
- Safe for production testing

---

### Category 2: Recoverable (Write + Cleanup)

**Definition**: Tests that modify system state but restore it to the original state after execution.

**Characteristics:**

- **Safety**: Safe with proper cleanup
- **Speed**: Slower (write + cleanup overhead)
- **Parallelization**: Requires coordination (avoid conflicts)
- **CI/CD**: Enabled with cleanup validation
- **Risk**: Low (if cleanup works)

**Examples:**

- `package_create` + `package_delete` - Create test package, then delete
- `bucket_objects_put` + delete - Upload temp object, then remove
- `admin_user_create` + `admin_user_delete` - Create test user, then remove
- `catalog_configure` + restore - Change config, then reset
- `tabulator_table_create` + `tabulator_table_delete` - Create table, then drop

**Test Configuration:**

```yaml
effect: create | update | configure
category: write-effect
cleanup:
  method: delete | restore
  tool: package_delete | bucket_objects_delete | ...
  arguments: {derived from create}
```

**Discovery Behavior:**

- Tools are SKIPPED during config generation (current behavior)
- No discovery responses captured
- Cleanup logic validated separately

**Runtime Behavior:**

- Only included with `--recoverable` flag
- Cleanup runs in teardown phase
- Cleanup failures reported as test failures
- Isolated execution to avoid conflicts

**Cleanup Strategies:**

1. **Paired Operations** (create/delete):

   ```
   Setup:   package_create(name="test-pkg-12345")
   Test:    Verify package exists
   Cleanup: package_delete(name="test-pkg-12345")
   Verify:  Confirm package deleted
   ```

2. **Snapshot/Restore** (update):

   ```
   Setup:   Capture current state
   Test:    package_update(metadata={...})
   Cleanup: Restore original metadata
   Verify:  Confirm original state restored
   ```

3. **Transaction-like** (configure):

   ```
   Setup:   Read current config
   Test:    catalog_configure(new_config)
   Cleanup: catalog_configure(original_config)
   Verify:  Confirm original config restored
   ```

---

### Category 3: Permanent (Irreversible)

**Definition**: Tests that modify system state in ways that cannot be automatically cleaned up.

**Characteristics:**

- **Safety**: Dangerous, requires manual intervention
- **Speed**: N/A (should not run automatically)
- **Parallelization**: N/A
- **CI/CD**: Never enabled automatically
- **Risk**: High

**Examples (if any exist):**

- Delete production data (should never be tested)
- Modify external system state irreversibly
- Operations with no inverse operation

**Test Configuration:**

```yaml
effect: remove | permanent
category: write-effect
cleanup:
  method: none | manual
  warning: "This operation cannot be automatically reversed"
```

**Discovery Behavior:**

- Tools are SKIPPED during config generation
- No discovery responses captured

**Runtime Behavior:**

- Only included with `--permanent` flag (requires explicit opt-in)
- Warnings displayed before execution
- Confirmation prompt required
- Never run in CI/CD

**Question**: Should permanent operations exist at all? If they can't be cleaned up, they shouldn't be tested automatically.

**Recommendation**: Eliminate permanent category or require manual testing only.

---

## Test Matrix: Complete Coverage

The complete test matrix is **3 modes × 3 effect categories = 9 combinations**:

| Deployment Mode | Idempotent | Recoverable | Permanent |
|-----------------|------------|-------------|-----------|
| **Legacy** | ✓ Fast, safe | ✓ With cleanup | ❌ Never |
| **Stateless** | ✓ HTTP+JWT | ✓ With cleanup | ❌ Never |
| **Local-Platform** | ✓ Fast dev | ✓ With cleanup | ❌ Never |

**Practical Matrix** (excluding permanent):

| Mode | Idempotent | Recoverable | Use Case |
|------|------------|-------------|----------|
| Legacy | `test-legacy-idempotent` | `test-legacy-recoverable` | Local development |
| Stateless | `test-stateless-idempotent` | `test-stateless-recoverable` | Production validation |
| Local-Platform | `test-local-platform-idempotent` | `test-local-platform-recoverable` | Platform feature development |

---

## Proposed Make Target Structure

### Primary Targets (9 Total)

**Legacy Mode:**

```makefile
test-legacy                    # Idempotent only (default, fast)
test-legacy-idempotent         # Explicit idempotent
test-legacy-recoverable        # With write operations + cleanup
test-legacy-all                # Idempotent + recoverable
```

**Stateless Mode:**

```makefile
test-stateless                 # Idempotent only (default, safe)
test-stateless-idempotent      # Explicit idempotent
test-stateless-recoverable     # With write operations + cleanup
test-stateless-all             # Idempotent + recoverable
```

**Local-Platform Mode:**

```makefile
test-local-platform            # Idempotent only (default, fast)
test-local-platform-idempotent # Explicit idempotent
test-local-platform-recoverable # With write operations + cleanup
test-local-platform-all        # Idempotent + recoverable
```

### Convenience Targets

**By Effect Category (across all modes):**

```makefile
test-idempotent                # All modes, idempotent only
test-recoverable               # All modes, recoverable only
test-all-modes                 # All modes, all effects
```

**By Speed:**

```makefile
test-fast                      # Legacy + local-platform idempotent (fastest)
test-quick                     # All modes, idempotent only (no Docker)
test-full                      # All modes, all effects (complete validation)
```

**Backward Compatibility Aliases:**

```makefile
test-mcp                       # Alias for test-legacy-idempotent
test-mcp-docker                # Alias for test-legacy-idempotent (Docker)
```

### Standard Pytest Targets (unchanged)

```makefile
test                           # Alias for test-unit
test-unit                      # pytest tests/unit/
test-func                      # pytest tests/func/
test-e2e                       # pytest tests/e2e/
test-scripts                   # pytest scripts/tests/test_*.py
```

---

## Unified Test Command Interface

All MCP tests should be invoked through a consistent interface:

```bash
# General form
uv run python scripts/tests/test_mcp.py \
  --mode {legacy|stateless|local-platform} \
  --effect {idempotent|recoverable|permanent} \
  [--verbose] \
  [--config scripts/tests/mcp-test.yaml]

# Examples
uv run python scripts/tests/test_mcp.py --mode legacy --effect idempotent
uv run python scripts/tests/test_mcp.py --mode stateless --effect recoverable --verbose
uv run python scripts/tests/test_mcp.py --mode local-platform --effect idempotent
```

**Make targets are wrappers** that set appropriate environment variables and flags:

```makefile
test-legacy-idempotent:
 @echo "Running legacy mode (quilt3 backend, stdio transport) - idempotent tests..."
 @export QUILT_MULTIUSER_MODE=false && \
  export FASTMCP_TRANSPORT=stdio && \
  export TEST_BACKEND_MODE=quilt3 && \
  uv run python scripts/tests/test_mcp.py --mode legacy --effect idempotent

test-stateless-recoverable: docker-build
 @echo "Running stateless mode (platform backend, HTTP+JWT) - recoverable tests..."
 @export QUILT_MULTIUSER_MODE=true && \
  export TEST_DOCKER_IMAGE=quilt-mcp:test && \
  uv run python scripts/tests/test_mcp.py --mode stateless --effect recoverable --verbose
```

---

## Configuration Management

### Single Source of Truth: `mcp-test.yaml`

The configuration file should support all modes and effects:

```yaml
# Global settings
test_config:
  timeout_seconds: 30
  retry_attempts: 2
  parallel_execution: true

# Environment configurations for each mode
environments:
  legacy:
    backend: quilt3
    transport: stdio
    multiuser_mode: false
    jwt_required: false

  stateless:
    backend: platform
    transport: http
    multiuser_mode: true
    jwt_required: true
    jwt_secret: ${MCP_JWT_SECRET}

  local-platform:
    backend: platform
    transport: stdio
    multiuser_mode: false
    jwt_required: false

# Tool definitions with effect classification
test_tools:
  bucket_objects_list:
    description: "List objects in S3 bucket"
    effect: none
    category: required-arg
    cleanup: null
    arguments:
      bucket: ${QUILT_TEST_BUCKET}
      prefix: "test/"
    discovery:
      status: PASSED
      duration_ms: 234

  package_create:
    description: "Create a new package"
    effect: create
    category: write-effect
    cleanup:
      method: delete
      tool: package_delete
      arguments:
        package: ${CREATED_PACKAGE_NAME}
        registry: ${QUILT_REGISTRY_URL}
    arguments:
      package: "test-pkg-${TIMESTAMP}"
      registry: ${QUILT_REGISTRY_URL}
    discovery:
      status: SKIPPED
      reason: "Write operation - skipped during discovery"

# Test resources
test_resources:
  package_uri:
    uri: "quilt+s3://my-bucket#package=my-pkg@latest"
    expected_mime: "application/json"
    validation:
      - check: exists
      - check: readable

# Discovered data (from idempotent tool execution)
discovered_data:
  sample_buckets: ["bucket-1", "bucket-2"]
  sample_packages: ["pkg-a", "pkg-b"]
  sample_objects: ["path/to/file.csv"]
```

**Key Improvements:**

1. **Environment variants** - Configuration for each deployment mode
2. **Cleanup specification** - How to reverse write operations
3. **Effect classification** - Enables intelligent filtering
4. **Single file** - No separate `mcp-test-multiuser.yaml`

---

## Test Execution Flow

### Phase 1: Server Startup

**Responsibilities:**

- Start MCP server in appropriate mode
- Configure environment variables
- Wait for server ready signal
- Validate server responding

**Implementation:**

- `LocalMCPServer` class for legacy and local-platform modes
- `DockerMCPServer` class for stateless mode (via docker_manager.py)

### Phase 2: Test Selection

**Responsibilities:**

- Load test configuration
- Filter tests by effect category
- Validate required arguments available
- Order tests by dependency

**Implementation:**

```python
def select_tests(config, effect_filter):
    all_tools = config["test_tools"]

    if effect_filter == "idempotent":
        return [t for t in all_tools if t["effect"] in ["none", "none-context-required"]]
    elif effect_filter == "recoverable":
        return [t for t in all_tools if t["effect"] in ["create", "update", "configure"]]
    elif effect_filter == "permanent":
        return [t for t in all_tools if t["effect"] == "remove"]
    else:
        return all_tools
```

### Phase 3: Test Execution

**Responsibilities:**

- Execute tools via MCPTester
- Validate responses
- Track pass/fail/skip status
- Capture errors with context

**Implementation:**

- Reuse existing `ToolsTester` and `ResourcesTester` classes
- Support both stdio and HTTP transports
- Unified result tracking

### Phase 4: Cleanup (Recoverable Only)

**Responsibilities:**

- Execute cleanup operations for write tests
- Verify cleanup succeeded
- Report cleanup failures
- Ensure system returns to original state

**Implementation:**

```python
def execute_with_cleanup(tool_config, tester):
    # Setup: Capture initial state
    initial_state = capture_state_if_needed(tool_config)

    try:
        # Execute test
        result = tester.run_test(tool_config)

        # Verify test succeeded
        if result.passed:
            # Cleanup: Execute inverse operation
            cleanup_config = tool_config["cleanup"]
            cleanup_result = tester.run_test(cleanup_config)

            # Verify cleanup succeeded
            if not cleanup_result.passed:
                result.cleanup_failed = True
                result.passed = False

            # Verify state restored
            final_state = capture_state_if_needed(tool_config)
            if final_state != initial_state:
                result.state_not_restored = True
                result.passed = False

    except Exception as e:
        # Always attempt cleanup, even on test failure
        try:
            cleanup_config = tool_config["cleanup"]
            tester.run_test(cleanup_config)
        except:
            pass
        raise

    return result
```

### Phase 5: Reporting

**Responsibilities:**

- Summarize results by mode and effect
- Report cleanup failures separately
- Suggest fixes for failures
- Generate coverage metrics

**Implementation:**

- Reuse existing `print_detailed_summary()` function
- Add cleanup-specific reporting
- Track cleanup success rate

---

## Docker Container Management

### Unified Docker Interface

**All Docker operations through `docker_manager.py`:**

```bash
# Start stateless container
uv run python scripts/docker_manager.py start \
  --mode stateless \
  --image quilt-mcp:test \
  --port 8002 \
  --jwt-secret "test-secret"

# Start local-platform container (future)
uv run python scripts/docker_manager.py start \
  --mode local-platform \
  --image quilt-mcp:test \
  --transport stdio

# Stop container
uv run python scripts/docker_manager.py stop --name mcp-test
```

**Eliminate:**

- `DockerMCPServer` class in `test_mcp.py` - replace with docker_manager.py calls
- Separate Docker lifecycle management in multiple files

**Single Responsibility:**

- `docker_manager.py` - Docker operations only
- `test_mcp.py` - Test orchestration only

---

## Migration Path from Current State

### Phase 1: Clarify Current Targets (No Breaking Changes)

**Goal**: Make existing targets explicitly show mode and effect

**Actions:**

1. Add comments to all Make targets indicating mode and effect
2. Document environment variables for each target
3. Create mapping table from old names to new concepts

**Example:**

```makefile
# Legacy mode, idempotent tests (fast, safe)
# Environment: QUILT_MULTIUSER_MODE=false, FASTMCP_TRANSPORT=stdio
test-mcp:
 @uv run python scripts/tests/test_mcp.py --no-generate
```

### Phase 2: Add New Targets (Backward Compatible)

**Goal**: Introduce new explicit targets alongside old ones

**Actions:**

1. Create `test-legacy-idempotent` (alias of `test-mcp`)
2. Create `test-stateless-idempotent` (based on `test-mcp-stateless`)
3. Create `test-local-platform-idempotent` (new)
4. Keep old targets as aliases

**Example:**

```makefile
# New explicit target
test-legacy-idempotent:
 @uv run python scripts/tests/test_mcp.py --mode legacy --effect idempotent

# Old target (backward compatible)
test-mcp: test-legacy-idempotent
```

### Phase 3: Add Recoverable Tests

**Goal**: Implement cleanup logic and recoverable test support

**Actions:**

1. Extend `mcp-test.yaml` with cleanup specifications
2. Implement cleanup orchestration in `test_mcp.py`
3. Add `--effect recoverable` flag support
4. Create recoverable targets for each mode

### Phase 4: Deprecate Old Targets

**Goal**: Encourage migration to new naming

**Actions:**

1. Add deprecation warnings to old targets
2. Update documentation to reference new targets
3. Update CI/CD to use new targets
4. Keep old targets as aliases for 1-2 releases

### Phase 5: Remove Old Targets (Breaking Change)

**Goal**: Clean up deprecated aliases

**Actions:**

1. Remove old target names
2. Update all documentation
3. Major version bump

---

## Success Metrics

### Clarity

- ✅ Developers can determine which test to run in < 30 seconds
- ✅ Target names clearly indicate what they test
- ✅ No "what's the difference between X and Y?" questions

### Maintainability

- ✅ Single Docker management system
- ✅ Single test execution engine
- ✅ Single configuration file
- ✅ No duplicate test logic

### Completeness

- ✅ All 6 mode+effect combinations have explicit targets
- ✅ Cleanup logic validated for all write operations
- ✅ Coverage metrics for each mode independently

### Performance

- ✅ Fast tests remain fast (< 15s for idempotent)
- ✅ Slow tests clearly labeled (Docker, recoverable)
- ✅ CI/CD runs only necessary tests

### Safety

- ✅ Idempotent tests never modify state
- ✅ Recoverable tests always clean up
- ✅ Permanent tests require explicit opt-in (or eliminated)

---

## Open Questions

### 1. Cleanup Implementation

**Question**: Should cleanup be:

- **Eager** (cleanup after each test individually)?
- **Batch** (cleanup all tests at end)?
- **Transactional** (rollback on failure)?

**Recommendation**: Eager cleanup after each test to isolate failures.

### 2. Permanent Operations

**Question**: Should permanent operations exist at all?

**Options**:
A. Eliminate permanent category entirely
B. Keep but require manual testing only
C. Implement with mandatory confirmation prompts

**Recommendation**: Eliminate permanent category. If an operation can't be cleaned up, it shouldn't be tested automatically.

### 3. Local-Platform Mode Scope

**Question**: Should local-platform mode support:

- **Full parity** with stateless (all platform features)?
- **Subset** (only platform backend, skip HTTP-specific features)?
- **Mock JWT** (simulate JWT validation without actual tokens)?

**Recommendation**: Full parity with simulated JWT context injection (no actual HTTP validation).

### 4. Parallel Execution

**Question**: Should recoverable tests run:

- **Serially** (avoid conflicts but slower)?
- **Parallel with coordination** (faster but complex)?
- **Parallel with isolated resources** (test namespacing)?

**Recommendation**: Start with serial execution, add parallel support with resource namespacing later (e.g., test-pkg-${TEST_ID}-${TIMESTAMP}).

### 5. Docker Mode for Legacy

**Question**: Should legacy mode support Docker execution?

**Current**: `test-mcp-docker` runs legacy mode in Docker with stdio

**Options**:
A. Keep as `test-legacy-docker` (Docker + stdio + quilt3)
B. Remove (Docker only for stateless)
C. Merge with stateless mode

**Recommendation**: Keep as `test-legacy-docker` for release validation (ensures Docker build works even with quilt3 backend).

---

## Related Work

- **Problem Definition**: [07-mcp-targets.md](07-mcp-targets.md)
- **Phase 3 Classification**: [05-discovery-orchestrator.md](05-discovery-orchestrator.md)
- **Test Infrastructure**: [spec/a11-client-testing/](../a11-client-testing/)
- **Backend Architecture**: `src/quilt_mcp/backends/`
- **Configuration System**: `src/quilt_mcp/config.py`

---

## Summary

This vision describes a rationalized test structure based on **two orthogonal dimensions**:

1. **Deployment Mode** (legacy, stateless, local-platform)
2. **Test Effect Category** (idempotent, recoverable, permanent)

The refactored structure provides:

- **Clear naming** - Target names indicate mode and effect
- **No redundancy** - Each combination serves distinct purpose
- **Unified infrastructure** - Single Docker manager, test runner, config
- **Explicit cleanup** - Recoverable tests restore state automatically
- **Fast iteration** - Local modes bypass Docker overhead
- **Production confidence** - Stateless mode validates deployment

The migration path is backward compatible with gradual adoption of new targets before deprecating old ones.

**This is a vision document - no implementation yet. Next step: Get user approval before designing detailed implementation plan.**

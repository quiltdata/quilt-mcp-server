<!-- markdownlint-disable MD013 MD024 MD036 MD040 MD060 -->
# Phase 2 Design: CRUD Loop Detection & State Restoration

**Status**: Design Document
**Sprint**: A18 (Phase 2)
**Date**: 2026-02-07
**Prerequisite**: [Phase 1 - Test Infrastructure Simplification](10-mcp-refactor-phase1.md)

---

## Problem Statement

Phase 1 established that **all MCP tools must be tested with automatic cleanup**. Phase 2 solves the deferred hard problem:

> **How do we reliably identify which cleanup operation matches each write operation, and how do we ensure tests return to initial state?**

---

## Core Challenges

1. **Pairing Problem** - Which delete matches which create? (`package_create` → `package_delete` is obvious, but what about `package_install`?)

2. **Argument Problem** - How do we pass the right identifiers to cleanup? (Create returns `{"name": "pkg-123"}`, delete needs `package="pkg-123"`)

3. **State Problem** - What state to snapshot? How to verify restoration? (List all packages before/after? Compare metadata?)

4. **Complexity Problem** - Multi-step operations, cascading deletes, partial failures (Install creates package + metadata + permissions)

5. **Isolation Problem** - Concurrent tests affecting shared resources (Two tests creating "test-package" simultaneously)

6. **Idempotency Problem** - Updates that can be inverted vs. must be captured (Set metadata to new value vs. capture old value first)

---

## Design Principles

| Principle | Meaning | Example |
|-----------|---------|---------|
| **Explicit Over Implicit** | Prefer declared cleanup over heuristics | Tool declares its cleanup in decorator vs. guessing from name |
| **Fail Loud** | Unknown cleanup → test fails immediately | No silent skipping if cleanup can't be determined |
| **Verify Always** | Cleanup success must be verified, not assumed | Compare state before/after, not just "delete returned 200" |
| **Isolate Resources** | Tests should not interfere with each other | Use UUID prefixes, not hardcoded "test-package" |
| **Minimize State** | Prefer stateless strategies when possible | Idempotent operations better than state capture |

---

## Strategy Overview

Four complementary strategies, used in order:

```
1. Explicit Metadata (Tool declares cleanup)
   ↓ not found
2. Name-Based Convention (Auto-detect pairs)
   ↓ not found
3. State Capture (Snapshot & restore)
   ↓ still can't determine
4. FAIL LOUDLY (No silent skipping)
```

---

## Strategy 1: Explicit Cleanup Metadata

### Design Point

**Tool author knows best cleanup approach.**

The person implementing `package_install` knows it creates:

- A package (needs `package_delete`)
- Metadata entries (needs `package_clear_metadata`)
- Access rules (needs `package_delete_access_rule`)

Let them declare this explicitly using a decorator.

### What Gets Declared

- Which tool(s) to call for cleanup
- How to map arguments from create → delete
- Whether state capture is needed
- How to verify restoration

### Decision Points

**Q**: Should cleanup be required or optional?
**A**: Required for write operations. Test fails if missing.

**Q**: What if cleanup tool doesn't exist yet?
**A**: Can declare `manual_cleanup_required=True` with instructions.

**Q**: Multiple cleanup steps?
**A**: Support cleanup chains with ordered steps.

---

## Strategy 2: Name-Based Convention

### Design Point

**Most CRUD pairs follow naming patterns.**

Analysis of existing tools:

- `package_create` + `package_delete` ✓
- `bucket_objects_put` + `bucket_objects_delete` ✓
- `user_add` + `user_remove` ✓
- `file_upload` + `file_delete` ✓

### Pattern Table

| Create Operation | Delete Operation | Confidence |
|------------------|------------------|------------|
| `*_create` | `*_delete` | High |
| `*_put` | `*_delete` | High |
| `*_add` | `*_remove` | High |
| `*_upload` | `*_delete` | Medium |
| `*_set` | `*_unset` OR `*_reset` | Medium |
| `*_enable` | `*_disable` | Medium |
| `*_install` | `*_uninstall` | Medium |

### Argument Mapping Problem

**Challenge**: Create and delete have different parameter names.

Examples:

- `package_create(package_name="foo")` → `package_delete(package="foo")`
- `bucket_objects_put(key="bar", data=...)` → `bucket_objects_delete(key="bar")`
- `user_add(username="alice")` → `user_remove(user_id="alice-id")` ⚠️ Different field!

**Solution Strategies**:

1. **Common Parameters** - If both tools have `package` param, pass it through
2. **Result Mapping** - Create returns `{"id": "123"}`, map to delete's `id` param
3. **Name Variations** - Try `package`, `package_name`, `pkg_name`
4. **Template Strings** - Support `"{result.name}"` expressions

### Decision Points

**Q**: What confidence threshold to auto-apply?
**A**: High confidence only. Medium confidence requires explicit confirmation.

**Q**: What if mapping is ambiguous?
**A**: Fail generation with suggested mapping.

**Q**: What about inverse operations (update, not delete)?
**A**: Requires Strategy 3 (state capture).

---

## Strategy 3: State Capture & Restore

### Design Point

**Some operations modify state rather than create/delete.**

Examples:

- `package_set_metadata(package="foo", meta={"key": "new"})` - Update existing
- `user_configure(setting="x", value=True)` - Toggle configuration
- `bucket_set_lifecycle(bucket="b", rules=[...])` - Replace policy

**Can't just delete** - need to restore previous state.

### Capture-Restore Pattern

**Before test**:

1. Identify read tool for state (e.g., `package_metadata`)
2. Capture current value
3. Store snapshot with checksum

**After test**:

1. Call same update tool with old value
2. Verify state matches snapshot
3. Report success/failure

### What Gets Captured

| Operation Type | Capture Strategy | Restore Method |
|----------------|------------------|----------------|
| Metadata update | Read current metadata | Call update with old metadata |
| Config change | Read current config | Call configure with old config |
| Lifecycle policy | Read current policy | Call set_lifecycle with old policy |
| Permission change | List current permissions | Call set_permissions with old list |

### Decision Points

**Q**: What if state changed between capture and test?
**A**: Fail test with "state drift detected" error.

**Q**: What if multiple tests modify same resource?
**A**: Requires Strategy 4 (resource isolation).

**Q**: Capture performance cost?
**A**: Only for update operations, creates can skip.

---

## Strategy 4: Resource Isolation

### Design Point

**Tests must not interfere with each other.**

**Problem Example**:

```
Test A: Create "test-package" → cleanup delete "test-package"
Test B: Create "test-package" → ❌ collision!
Test A cleanup: Delete "test-package" → ❌ deletes Test B's resource!
```

### Solution: UUID Namespacing

**Every test gets unique namespace:**

- Test ID: `a3f2b891` (short UUID)
- Resource names: `test-{uuid}-{base}`
- Example: `test-a3f2b891-demo-package`

**Cleanup by namespace:**

- Filter all resources with `test-{uuid}-` prefix
- Delete everything in namespace
- Prevents cross-test contamination

### Resource Registry Pattern

**Track all created resources:**

1. Test creates `package` → register in test registry
2. Test creates `object` → register in test registry
3. Cleanup phase → delete everything in registry
4. Verify all registered resources gone

### Decision Points

**Q**: What about resources that can't be namespaced?
**A**: Use resource registry with explicit tracking.

**Q**: Cleanup order matters (dependencies)?
**A**: Delete in reverse creation order (LIFO).

**Q**: Performance impact of unique names?
**A**: Negligible, test isolation worth it.

---

## State Verification System

### Design Point

**Cleanup success must be verified, not assumed.**

**Not enough to call delete and check status 200.**

Must verify:

1. Resource actually gone (not just marked deleted)
2. No orphaned dependencies (metadata, permissions, etc.)
3. State matches pre-test snapshot
4. No unintended side effects

### Verification Methods

| Verification Type | Method | Example |
|-------------------|--------|---------|
| **Existence Check** | Query resource, expect 404 | Package deleted → list packages, verify absent |
| **State Comparison** | Snapshot checksum match | List packages before/after, compare counts |
| **Query Delta** | Before/after result difference | 15 packages before, 15 after (not 16) |
| **Dependency Check** | Verify cascading cleanup | Package deleted → metadata also gone |

### Verification Confidence Levels

- **High**: Exact state match with checksum
- **Medium**: Count match (e.g., same number of packages)
- **Low**: Delete returned success (weakest, needs upgrade)

### Decision Points

**Q**: What if verification is slow (large list operations)?
**A**: Cache state snapshot, only re-query for verification.

**Q**: What if state has legitimate external changes?
**A**: Fail test, require isolated test environment.

**Q**: Partial verification (some state matches, some doesn't)?
**A**: Fail with detailed diff showing mismatches.

---

## Complex Cleanup Scenarios

### Scenario 1: Multi-Step Cleanup

**Problem**: Single create → multiple cleanup steps

**Example**: `package_install`

- Creates package
- Sets metadata
- Creates access rules
- Uploads default files

**Solution**: Cleanup chain with ordering

1. Delete access rules (dependents first)
2. Clear metadata
3. Delete files
4. Delete package (parent last)

**Design Question**: Should chain be automatic or explicit?
**Answer**: Explicit declaration, too risky to infer.

### Scenario 2: Cascading Dependencies

**Problem**: Delete requires deleting dependents first

**Example**: `package_delete`

- Can't delete if revisions exist
- Can't delete if tags exist
- Must delete children before parent

**Solution**: Dependency graph with checks

1. Check for revisions → delete all revisions
2. Check for tags → delete all tags
3. Now delete package

**Design Question**: How deep to check dependencies?
**Answer**: One level only. Deeper nesting requires explicit chains.

### Scenario 3: Partial Failure Recovery

**Problem**: Cleanup fails halfway through

**Example**:

1. Delete metadata ✓
2. Delete files ✓
3. Delete package ✗ (network error)

**State**: Partially cleaned, package still exists without metadata

**Solution**: Cleanup transaction log

- Track each cleanup step
- On failure, show completed + remaining steps
- Generate manual cleanup commands
- Mark test as FAILED (not passed!)

**Design Question**: Retry failed cleanup?
**Answer**: No automatic retry (could worsen state). Show manual steps.

---

## Integration with Test Flow

### Updated Test Phases

**Phase 1: Pre-Test Setup**

1. Generate unique test namespace
2. Initialize resource registry
3. Capture initial state (if needed)
4. Validate cleanup specification exists

**Phase 2: Test Execution**

1. Execute tool with test arguments
2. Register created resources
3. Capture test result

**Phase 3: Cleanup Execution**

1. Resolve cleanup tool(s) from spec
2. Map arguments from test result
3. Execute cleanup operations
4. Track completion status

**Phase 4: Verification**

1. Check resource existence
2. Compare state snapshots
3. Verify dependencies cleaned
4. Generate report

**Phase 5: Reporting**

- If all passed → `PASSED (with cleanup)`
- If cleanup failed → `FAILED (state not restored)` + manual steps
- If verification failed → `FAILED (state mismatch)` + diff

---

## Configuration Schema Design

### Test Config Structure

```yaml
tools:
  package_create:
    # Basic tool info
    category: required-arg

    # Discovery results
    discovery:
      status: PASSED
      executed_at: 2026-02-07T10:30:00Z
      test_namespace: test-a3f2b891

    # Cleanup specification
    cleanup:
      strategy: explicit           # explicit | auto | state_capture | none
      detection: name_based         # How it was detected
      confidence: high              # high | medium | low

      # Cleanup tool(s)
      tool: package_delete

      # Argument mapping
      arg_mapping:
        package: result.name        # JSONPath-like expression
        registry: args.registry     # Pass through from create

      # Verification
      verification: state_compare   # state_compare | existence | query_delta
      state_capture:
        tool: package_list
        checksum: abc123def

    # Test execution results
    test:
      status: PASSED
      cleanup_executed: true
      state_restored: true
      duration_ms: 1250
```

### Design Decisions

**Q**: Store cleanup spec with tool or separately?
**A**: With tool, keeps related info together.

**Q**: Include raw state data in config?
**A**: No, only checksums. Raw data in separate files.

**Q**: Version cleanup specs?
**A**: Yes, add `cleanup_spec_version: 1` for future changes.

---

## Implementation Tasks

### Phase 2A: Core Infrastructure (Week 1)

**Task 2A.1**: Design cleanup metadata system

- Create `CleanupSpec` data structure
- Define decorator interface
- Design argument mapping expressions
- **Deliverable**: Design doc + type definitions

**Task 2A.2**: Design state management system

- Define state snapshot format
- Design checksum algorithm
- Define verification methods
- **Deliverable**: State management design

**Task 2A.3**: Design resource isolation

- Define namespace generation strategy
- Design resource registry structure
- Define cleanup ordering rules
- **Deliverable**: Isolation strategy doc

**Task 2A.4**: Implement core classes

- Build CleanupSpec with validation
- Build StateManager with snapshot logic
- Build ResourceNamespace generator
- **Deliverable**: `src/quilt_mcp/testing/` modules

**Verification**: Unit tests for core classes

---

### Phase 2B: Detection & Mapping (Week 2)

**Task 2B.1**: Design detection algorithm

- Define name pattern matching rules
- Define confidence scoring
- Define fallback strategies
- **Deliverable**: Detection algorithm design

**Task 2B.2**: Design argument mapping

- Define mapping expression language
- Design inference rules
- Define validation rules
- **Deliverable**: Mapping system design

**Task 2B.3**: Implement detection

- Build CRUD pair detector
- Build confidence scorer
- Build argument mapper
- **Deliverable**: Detection system in `scripts/mcp-test-setup.py`

**Task 2B.4**: Implement validation

- Validate cleanup specs on generation
- Fail on missing cleanup
- Generate helpful error messages
- **Deliverable**: Config generation with validation

**Verification**: Generate config, check all write ops have cleanup

---

### Phase 2C: Integration & Verification (Week 3)

**Task 2C.1**: Update test executor

- Add cleanup execution phase
- Add state verification phase
- Add failure reporting
- **Deliverable**: Updated `scripts/mcp-test.py`

**Task 2C.2**: Implement state verification

- Build comparison logic
- Build diff generation
- Build verification reporting
- **Deliverable**: Verification system

**Task 2C.3**: Implement failure handling

- Generate manual cleanup steps
- Show state diffs on failure
- Mark tests failed (not passed!)
- **Deliverable**: Failure reporting

**Task 2C.4**: Update config schema

- Add cleanup fields to YAML
- Add verification results
- Add failure diagnostics
- **Deliverable**: Enhanced config format

**Verification**: Run tests with intentional cleanup failures

---

### Phase 2D: Complex Scenarios (Week 4)

**Task 2D.1**: Design cleanup chains

- Define chain specification format
- Define execution ordering
- Define failure handling
- **Deliverable**: Chain design doc

**Task 2D.2**: Design cascading cleanup

- Define dependency checking
- Define recursive cleanup
- Define depth limits
- **Deliverable**: Cascading design doc

**Task 2D.3**: Implement complex patterns

- Build chain executor
- Build cascade checker
- Build transaction log
- **Deliverable**: Complex cleanup support

**Task 2D.4**: Implement recovery

- Track partial cleanup
- Generate manual steps
- Show completion status
- **Deliverable**: Recovery system

**Verification**: Test complex scenarios (install/uninstall)

---

## Success Criteria

### Quantitative Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Auto-detection Rate** | ≥80% | write_tools with auto-detected cleanup / total write_tools |
| **State Restoration Rate** | 100% | tests with state verified restored / tests with cleanup |
| **Resource Isolation** | 100% | tests with zero conflicts / total tests run |
| **Failure Transparency** | 100% | cleanup failures shown with manual steps / total failures |

### Qualitative Goals

✅ **No Silent Skipping** - Every write operation tested or fails loudly
✅ **Clear Failures** - Failed cleanup shows exactly what to fix
✅ **Developer Friendly** - Explicit specs easy to declare
✅ **Automatic Default** - Name-based detection works for 80%+ cases
✅ **Verifiable Safety** - State verification prevents false passes

---

## Risk Analysis

### Risk 1: Detection Misses Pairs

**Probability**: Medium
**Impact**: High (state not cleaned)

**Mitigation**:

- Fail generation if no cleanup found
- Allow manual specification override
- Provide clear error messages

**Contingency**:

- Manual cleanup spec required
- Document in test config

---

### Risk 2: Cleanup Fails

**Probability**: Medium
**Impact**: High (state contamination)

**Mitigation**:

- Mark test as FAILED (not passed)
- Show manual cleanup steps
- Generate cleanup commands

**Contingency**:

- Document contaminated state
- Provide reset procedure
- Can regenerate test environment

---

### Risk 3: State Verification Too Slow

**Probability**: Low
**Impact**: Medium (slow tests)

**Mitigation**:

- Cache initial snapshots
- Use checksums for comparison
- Only full verify on mismatch

**Contingency**:

- Allow verification skip flag (danger!)
- Optimize state capture queries
- Use incremental verification

---

### Risk 4: Complex Dependencies

**Probability**: High
**Impact**: Medium (manual specs needed)

**Mitigation**:

- Support explicit chains
- Document dependency patterns
- Provide examples

**Contingency**:

- Accept some manual specs required
- Build library of common patterns
- Tool authors document cleanup

---

## Design Questions (Open)

### Q1: Cleanup Timeout

**Question**: How long to wait for cleanup before failing?

**Options**:

- A: 30s default (current test timeout)
- B: 60s (allow for slow S3 operations)
- C: Configurable per-tool

**Recommendation**: Start with A, add C if needed

---

### Q2: Async Cleanup

**Question**: Should cleanup run synchronously or async?

**Options**:

- A: Synchronous (block test completion)
- B: Asynchronous (continue to next test)
- C: Configurable (default sync)

**Trade-offs**:

- Sync: Safer, slower
- Async: Faster, riskier (state may not be ready for next test)

**Recommendation**: A (sync) for Phase 2, consider C later

---

### Q3: Cleanup Ordering

**Question**: If multiple resources created, what order to delete?

**Options**:

- A: LIFO (last created, first deleted - like stack)
- B: Dependency graph (compute dependencies)
- C: Explicit ordering only

**Recommendation**: A (LIFO) as default, C for complex cases

---

### Q4: State Drift Tolerance

**Question**: What if environment changes between capture and verify?

**Options**:

- A: Fail test immediately (strict)
- B: Allow configurable tolerance (e.g., +/- 1 package)
- C: Warn but pass test

**Recommendation**: A (strict) to catch environmental issues

---

## Migration from Phase 1

### Phase 1 Changes Needed

**File**: `scripts/mcp-test-setup.py`

**Add**:

- Cleanup detection during discovery
- Validation that write ops have cleanup
- Fail generation if cleanup missing

**Remove**:

- Effect classification by keywords
- Discovery skipping for write operations

---

**File**: `scripts/mcp-test.py`

**Add**:

- Cleanup execution after each test
- State verification phase
- Failure reporting with manual steps

**Remove**:

- `--idempotent-only` flag
- Effect-based filtering

---

**File**: `scripts/tests/mcp-test.yaml`

**Add**:

- `cleanup` section for each tool
- `verification` results
- State checksums

**Remove**:

- `effect` field classifications
- `SKIPPED` status entries

---

## References

- [Phase 1: Test Infrastructure Simplification](10-mcp-refactor-phase1.md)
- [MCP Test Refactor Vision](09-mcp-recoverable.md)
- [Current Test Targets Analysis](07-mcp-targets.md)

---

## Appendix A: Current Tool Analysis

**Write Operations Requiring Cleanup** (15 tools):

| Tool | Type | Cleanup Strategy Needed | Notes |
|------|------|-------------------------|-------|
| `package_create` | Create | Auto-detect delete | High confidence pair |
| `package_install` | Create | Multi-step chain | Complex, needs explicit spec |
| `package_set_metadata` | Update | State capture | Restore old metadata |
| `bucket_objects_put` | Create | Auto-detect delete | High confidence pair |
| `bucket_objects_upload` | Create | Auto-detect delete | Same as put |
| `revision_create` | Create | Cascading | May have tags |
| `revision_delete` | Delete | N/A | Is cleanup tool |
| `tag_create` | Create | Auto-detect delete | High confidence pair |
| `user_configure` | Update | State capture | Revert config |
| `access_rule_create` | Create | Auto-detect delete | High confidence pair |
| `lifecycle_set` | Update | State capture | Restore policy |
| `notification_enable` | Update | Auto-detect disable | Medium confidence |
| `cache_clear` | Delete | None | Idempotent |
| `preview_generate` | Create | Auto-detect delete | Cache cleanup |
| `session_create` | Create | Auto-detect destroy | High confidence |

**Read Operations (No Cleanup)** (25 tools):

- All search, list, get, metadata, browse, search, query operations
- No cleanup needed

---

## Appendix B: Cleanup Pattern Library

**Pattern 1: Simple Create/Delete**

- Example: `package_create` → `package_delete`
- Strategy: Auto-detect by name
- Confidence: High

**Pattern 2: Put/Delete**

- Example: `bucket_objects_put` → `bucket_objects_delete`
- Strategy: Auto-detect by name
- Confidence: High

**Pattern 3: Add/Remove**

- Example: `user_add` → `user_remove`
- Strategy: Auto-detect by name
- Confidence: High

**Pattern 4: Enable/Disable**

- Example: `notification_enable` → `notification_disable`
- Strategy: Auto-detect by name
- Confidence: Medium (may not restore exact state)

**Pattern 5: Set/Reset**

- Example: `lifecycle_set` → state capture
- Strategy: Capture before, restore after
- Confidence: High (if state capture works)

**Pattern 6: Configure/Restore**

- Example: `user_configure` → state capture
- Strategy: Capture before, reconfigure after
- Confidence: High

**Pattern 7: Install/Uninstall**

- Example: `package_install` → multi-step chain
- Strategy: Explicit declaration required
- Confidence: Requires manual spec

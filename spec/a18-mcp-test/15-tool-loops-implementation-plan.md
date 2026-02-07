# Tool Loops: Implementation Plan

**Status**: Implementation Plan
**Sprint**: A18
**Date**: 2026-02-07
**Context**: Complete plan for 100% tool coverage via tool loops

---

## Goal

Test ALL 72 tools in the MCP server, including write operations (create/update/delete), through "tool loops" that create → modify → verify → cleanup resources.

---

## Design Decision: Option C (Explicit Arguments with Templates)

**Pattern:**

```yaml
tool_loops:
  admin_user_basic:
    - tool: admin_user_create
      args:
        name: test-loop-user-{uuid}
        email: test-{uuid}@example.com
        role: viewer
    - tool: admin_user_get
      args:
        name: test-loop-user-{uuid}
    - tool: admin_user_delete
      args:
        name: test-loop-user-{uuid}
```

**Why:** Explicit, debuggable, no magic context passing. YAML is single source of truth.

**Template variables:**

- `{uuid}` → unique ID per loop execution
- `{env.BUCKET}` → from environment
- `{env.REGISTRY}` → from environment

---

## A) Responsibilities Split

### mcp-test-setup.py (Generator)

**Changes:**

1. **Add tool loops generation** (~150 lines)
   - Define tool loops structure in Python dict
   - Generate tool_loops section in YAML
   - Include template placeholders (`{uuid}`, `{env.*}`)

2. **Update effect classification** (modify existing)
   - Keep write-effect detection
   - Don't skip write tools during introspection
   - Mark tools as "tested via loop" vs "tested standalone"

3. **Remove write-operation skip guard** (delete ~10 lines)
   - Delete lines 180-187 that skip write operations
   - Write tools will be tested via loops, not individually

**Output:** Enhanced `scripts/tests/mcp-test.yaml` with new `tool_loops` section

### mcp-test.py (Runner)

**New features:**

1. **Template substitution** (~50 lines)
   - Replace `{uuid}` with generated ID
   - Replace `{env.VAR}` with environment values
   - Validate all templates can be resolved

2. **Loop executor** (~100 lines)
   - Execute tools in sequence
   - Stop on first failure (fail-fast per loop)
   - Track which step failed for cleanup
   - Report loop-level pass/fail

3. **Cleanup on failure** (~50 lines)
   - If step N fails, still run cleanup steps (delete operations)
   - Log cleanup attempts separately
   - Don't fail overall test if cleanup fails (warn only)

4. **Coverage validation** (~30 lines)
   - Ensure every tool tested (standalone OR in loop)
   - Report untested tools as error
   - Exit code 1 if coverage < 100%

**Total new code:** ~230 lines

---

## B) YAML Encoding

### Structure

```yaml
# Existing sections (unchanged)
environment:
  AWS_PROFILE: default
  QUILT_TEST_BUCKET: s3://...
  # etc

test_tools:
  # Existing standalone tests
  bucket_objects_list:
    description: "..."
    effect: none
    arguments: {...}

test_resources:
  # Existing resource tests
  # (unchanged)

# NEW SECTION
tool_loops:
  # Loop name (for reporting)
  admin_user_basic:
    description: "Test admin user create/get/delete cycle"
    cleanup_on_failure: true  # Run delete steps even if earlier steps fail
    steps:
      - tool: admin_user_create
        args:
          name: test-loop-user-{uuid}
          email: test-{uuid}@example.com
          role: viewer
        expect_success: true  # Step must succeed

      - tool: admin_user_get
        args:
          name: test-loop-user-{uuid}
        expect_success: true

      - tool: admin_user_delete
        args:
          name: test-loop-user-{uuid}
        expect_success: true
        is_cleanup: true  # Always run, even if earlier steps fail

  admin_user_with_roles:
    description: "Test add/remove roles"
    cleanup_on_failure: true
    steps:
      - tool: admin_user_create
        args:
          name: test-loop-user-{uuid}
          email: test-{uuid}@example.com
          role: viewer
        expect_success: true

      - tool: admin_user_add_roles
        args:
          name: test-loop-user-{uuid}
          roles: ["data-scientist", "analyst"]
        expect_success: true

      - tool: admin_user_get
        args:
          name: test-loop-user-{uuid}
        expect_success: true

      - tool: admin_user_remove_roles
        args:
          name: test-loop-user-{uuid}
          roles: ["data-scientist", "analyst"]
        expect_success: true

      - tool: admin_user_delete
        args:
          name: test-loop-user-{uuid}
        expect_success: true
        is_cleanup: true

  package_lifecycle:
    description: "Test package create/update/delete"
    cleanup_on_failure: true
    steps:
      - tool: package_create
        args:
          package_name: test-loop-pkg-{uuid}
          registry: "{env.QUILT_TEST_BUCKET}"
          s3_uris: ["{env.QUILT_TEST_BUCKET}/test-data/sample.csv"]
          message: "Test package created by tool loop"
        expect_success: true

      - tool: package_browse
        args:
          package_name: test-loop-pkg-{uuid}
          registry: "{env.QUILT_TEST_BUCKET}"
        expect_success: true

      - tool: package_update
        args:
          package_name: test-loop-pkg-{uuid}
          registry: "{env.QUILT_TEST_BUCKET}"
          s3_uris: ["{env.QUILT_TEST_BUCKET}/test-data/sample2.csv"]
          message: "Updated by tool loop"
        expect_success: true

      - tool: package_delete
        args:
          package_name: test-loop-pkg-{uuid}
          registry: "{env.QUILT_TEST_BUCKET}"
        expect_success: true
        is_cleanup: true
```

### Key Fields

- `tool_loops.<name>.description` - Human-readable description
- `tool_loops.<name>.cleanup_on_failure` - Run cleanup steps even on failure
- `tool_loops.<name>.steps[]` - Ordered list of tool invocations
- `steps[].tool` - Tool name (must exist in server)
- `steps[].args` - Arguments with template placeholders
- `steps[].expect_success` - Fail loop if tool returns error
- `steps[].is_cleanup` - Always run (delete operations)

---

## C) Main Error Conditions

**All errors must:** Detect automatically, fail loudly, recommend specific fix.

### Generation Errors (mcp-test-setup.py)

1. **Missing template values**
   - `{env.BUCKET}` but BUCKET not in environment
   - **Detection:** Validate during YAML generation
   - **Error message:** `❌ Template {env.BUCKET} requires BUCKET in environment. Add to .env: BUCKET=s3://your-bucket`
   - **Exit code:** 1

2. **Tool not found**
   - Loop references tool that doesn't exist in server
   - **Detection:** Cross-reference with server tool list
   - **Error message:** `❌ Loop 'admin_user_basic' references unknown tool 'admin_user_create'. Available tools: [list]. Check spelling or update server.`
   - **Exit code:** 1

3. **Invalid argument types**
   - Loop specifies string for int parameter
   - **Detection:** Type checking during generation (optional)
   - **Error message:** `⚠️  Loop 'package_lifecycle' passes string to 'limit' (expects int). This may fail at runtime.`
   - **Exit code:** 0 (warning only)

### Execution Errors (mcp-test.py)

1. **Template substitution failure**
   - `{uuid}` not replaced (bug in substitution)
   - **Detection:** Check for literal `{` in resolved args before tool call
   - **Error message:** `❌ Template substitution failed in loop 'admin_user_basic', arg 'name':
   still contains '{uuid}'. This is a bug in template engine.`
   - **Exit code:** 1

2. **Tool execution failure**
   - Tool returns error (access denied, resource not found, etc.)
   - **Detection:** Check tool result for success=False or error field
   - **Error message:** `❌ Loop 'admin_user_basic' step 1 failed: admin_user_create
   returned error: Access denied. Check AWS_PROFILE and bucket permissions in .env`
   - **Exit code:** 1 (unless cleanup step)

3. **Cleanup failure**
   - Delete tool fails (resource already deleted, permission issue)
   - **Detection:** Catch exceptions in cleanup phase
   - **Error message:** `⚠️  Cleanup failed in loop 'admin_user_basic': admin_user_delete
   returned error: User not found. Resource may have been manually deleted.
   Continuing tests...`
   - **Exit code:** 0 (warning only, non-fatal)

4. **Resource leakage**
   - Test interrupted before cleanup runs
   - **Detection:** Manual audit of test resources after runs
   - **Error message:** `⚠️  Test interrupted (SIGINT). Running cleanup for
   in-progress loops... Press Ctrl+C again to force exit (may leak resources)`
   - **Exit code:** 130 (interrupted)

5. **Incomplete coverage**
   - Some tools not tested (standalone OR loop)
   - **Detection:** Coverage validator at end of test run
   - **Error message:** `❌ Coverage check FAILED: 3 tools not tested:
   - admin_user_create (define in loop or standalone test)
   - package_update (define in loop or standalone test)
   - workflow_add_step (define in loop or standalone test)
   Run: python scripts/mcp-test-setup.py --show-missing`
   - **Exit code:** 1

### Permission Errors

1. **Admin API disabled**
   - Admin tools fail with "admin API not configured"
   - **Detection:** Check first admin tool, skip remaining if disabled
   - **Error message:** `⚠️  Admin API not configured (admin_user_create failed).
   Skipping all admin tool loops. To enable: set ADMIN_API_ENABLED=true in stack config`
   - **Exit code:** 0 (skip gracefully)

2. **Bucket access denied**
   - S3 operations fail with access denied
   - **Detection:** Pre-flight check with bucket_access_check
   - **Error message:** `❌ Pre-flight check failed: Cannot access bucket
   's3://quilt-example'. Verify AWS_PROFILE has s3:ListBucket and s3:GetObject
   permissions. Current profile: 'default'`
   - **Exit code:** 1

---

## D) Testing Strategy

### Phase 1: Generate Updated YAML

```bash
# Regenerate test config with tool loops
uv run python scripts/mcp-test-setup.py

# Verify tool_loops section exists
grep -A 10 "tool_loops:" scripts/tests/mcp-test.yaml

# Check coverage (should be 100%)
uv run python scripts/mcp-test-setup.py --validate-only
```

**Expected:** YAML file has `tool_loops` section with 5-10 loops covering all write tools.

### Phase 2: Implement Loop Executor

```bash
# Add loop execution to mcp-test.py
# Test with single loop first
uv run python scripts/mcp-test.py --loop admin_user_basic

# Verify:
# - User created
# - User retrieved
# - User deleted
# - No errors
```

**Expected:** Loop executes all 3 steps, reports success, cleans up.

### Phase 3: Test Failure Handling

```bash
# Modify loop to force failure (bad email format, etc.)
# Run loop, verify cleanup still runs

uv run python scripts/mcp-test.py --loop admin_user_basic

# Expected:
# - Create succeeds
# - Get succeeds
# - Delete STILL RUNS (cleanup)
# - Loop marked as FAILED
# - Exit code 1
```

**Expected:** Cleanup runs even when earlier steps fail.

### Phase 4: Full Test Suite

```bash
# Run all loops + standalone tests
uv run python scripts/mcp-test.py

# Verify:
# - All loops execute
# - All standalone tests execute
# - Coverage = 100%
# - Exit code 0 if all pass
```

**Expected:** Complete test run with all 72 tools tested.

### Phase 5: Coverage Validation

```bash
# Ensure every tool tested
uv run python scripts/mcp-test.py --validate-coverage

# Expected output:
# ✅ 72/72 tools covered
# - 45 tools in standalone tests
# - 27 tools in loops
# Exit code 0
```

### Phase 6: CI Integration

```bash
# Add to GitHub Actions workflow
- name: Run MCP tests
  run: |
    uv run python scripts/mcp-test-setup.py --validate-only
    uv run python scripts/mcp-test.py --validate-coverage
```

**Expected:** CI fails if coverage < 100% or any test fails.

---

## Tool Loop Definitions (for mcp-test-setup.py)

### Required Loops (9 total)

1. **admin_user_basic** (3 tools)
   - admin_user_create → admin_user_get → admin_user_delete

2. **admin_user_with_roles** (5 tools)
   - create → add_roles → get → remove_roles → delete

3. **admin_user_modifications** (7 tools)
   - create → set_email → set_role → set_admin → set_active → reset_password → delete

4. **admin_sso_config** (3 tools)
   - admin_sso_config_set → (verify read) → admin_sso_config_remove

5. **admin_tabulator_query** (2 tools)
   - admin_tabulator_open_query_set → (verify read)

6. **package_lifecycle** (4 tools)
   - package_create → package_browse → package_update → package_delete

7. **bucket_objects_write** (3 tools)
   - bucket_objects_put → bucket_object_fetch → (delete via package_delete)

8. **workflow_basic** (4 tools)
   - workflow_create → workflow_add_step → workflow_update_step → (cleanup)

9. **visualization_create** (2 tools)
   - create_data_visualization → (verify file exists)

### Tool Coverage Summary

- **Standalone tests:** 45 tools (all read-only)
- **Loop tests:** 27 tools (all write operations)
- **Total:** 72 tools (100% coverage)

---

## Implementation Checklist

### mcp-test-setup.py Changes

- [ ] Define TOOL_LOOPS dict with 9 loops
- [ ] Add generate_tool_loops_yaml() function
- [ ] Update main() to write tool_loops section
- [ ] Remove write-operation skip guard (lines 180-187)
- [ ] Add coverage validator (ensure 100% coverage)
- [ ] Test: Regenerate YAML, verify structure

### mcp-test.py Changes

- [ ] Add template substitution function
- [ ] Add loop executor class
- [ ] Add cleanup-on-failure logic
- [ ] Add coverage validation
- [ ] Add --loop <name> CLI option (test single loop)
- [ ] Add --validate-coverage CLI option
- [ ] Test: Run single loop successfully

### Testing

- [ ] Phase 1: Generate YAML with loops
- [ ] Phase 2: Execute single loop (admin_user_basic)
- [ ] Phase 3: Test failure handling (cleanup runs)
- [ ] Phase 4: Full test suite (all loops + standalone)
- [ ] Phase 5: Coverage validation (100%)
- [ ] Phase 6: CI integration

### Documentation

- [ ] Update README with tool loops explanation
- [ ] Add examples of adding new loops
- [ ] Document error conditions and fixes

---

## Estimated Effort

- **mcp-test-setup.py changes:** ~200 lines, 2 hours
- **mcp-test.py changes:** ~230 lines, 3 hours
- **Testing and validation:** 2 hours
- **Documentation:** 1 hour

**Total:** ~8 hours (1 day)

---

## Success Criteria

1. ✅ All 72 tools have test coverage (standalone OR loop)
2. ✅ Write operations tested via loops (create → verify → cleanup)
3. ✅ Cleanup runs even on failure (no resource leakage)
4. ✅ Coverage validator enforces 100% coverage
5. ✅ CI fails if any tool untested
6. ✅ Zero manual cleanup required after test runs

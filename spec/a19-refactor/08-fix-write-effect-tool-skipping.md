# A19-08: Fix Write-Effect Tool Skipping in Test Runner

**Status**: Draft
**Author**: System
**Date**: 2026-02-09
**Related**: [05-mcp-tool-reference.md](./05-mcp-tool-reference.md)

## Problem Statement

Write-effect tools are being tested in standalone "tool mode" when they should ONLY be tested via tool loops. This causes test failures because write-effect tools require prerequisites (e.g., `admin_user_add_roles` needs a user to exist first).

### Current Behavior

```
[Script Tests → MCP server tests (legacy)]
    ⊘ 26 SKIPPED (write-effect tools - will be tested via tool loops)

  ❌ admin_user_add_roles: FAILED - Tool returned error response
     Error: User not found: User not found: None
  ❌ admin_user_remove_roles: FAILED - Tool returned error response
     Error: User not found: User not found: None
  ❌ package_create_from_s3: FAILED - Tool returned error response
     Error: Cannot create package in target registry
  ... (16 total failures)
```

### Root Cause

The test runner (`scripts/mcp-test.py`) does NOT check whether tools have write effects before testing them:

```python
# scripts/mcp-test.py lines 551-579
def run_all_tests(self, specific_tool: str = None) -> None:
    test_tools = self.config.get("test_tools", {})

    # No filtering here - ALL tools are tested!
    for tool_name, test_config in test_tools.items():
        self.run_test(tool_name, test_config)  # ❌ Runs write-effect tools
```

Write-effect tools ARE in the config with:
- `effect: create|update|remove`
- `category: write-effect`
- `discovery.status: SKIPPED`

But the test runner ignores these fields and tries to run them anyway.

## Solution Design

### Approach: Skip Write-Effect Tools in Test Runner

Modify `ToolsTester.run_all_tests()` to skip tools with write effects during standalone testing.

**Rationale:**
1. Write-effect tools are properly classified in the config
2. They're already marked as `SKIPPED` during discovery
3. They're covered by tool loops
4. The test runner just needs to respect the classification

### Implementation

**File: `scripts/mcp-test.py`**

```python
def run_all_tests(self, specific_tool: str = None) -> None:
    """Run all configured tool tests.

    Args:
        specific_tool: If provided, run only this tool's test
    """
    test_tools = self.config.get("test_tools", {})

    if specific_tool:
        if specific_tool not in test_tools:
            print(f"❌ Tool '{specific_tool}' not found in test config")
            self.results.record_failure(...)
            return
        test_tools = {specific_tool: test_tools[specific_tool]}

    # NEW: Filter out write-effect tools (they're tested via loops)
    filtered_tools = {}
    skipped_write_effect = []

    for tool_name, test_config in test_tools.items():
        effect = test_config.get("effect", "none")
        category = test_config.get("category", "unknown")

        # Skip write-effect tools (create/update/remove effects)
        if effect in ["create", "update", "remove"] or category == "write-effect":
            skipped_write_effect.append(tool_name)
            self.results.record_skip({
                "name": tool_name,
                "reason": f"Write-effect tool (effect={effect}) - tested via tool loops",
                "effect": effect,
                "category": category,
            })
            continue

        filtered_tools[tool_name] = test_config

    total_count = len(filtered_tools)
    skipped_count = len(skipped_write_effect)

    print(f"\n🧪 Running tools test ({total_count} tools)...")
    if skipped_count > 0:
        print(f"   ⊘ Skipping {skipped_count} write-effect tools (tested via loops)")

    for tool_name, test_config in filtered_tools.items():
        self.run_test(tool_name, test_config)

    # Report results (existing code)
    ...
```

### Expected Behavior After Fix

```
[Script Tests → MCP server tests]
    🧪 Running tools test (28 tools)...
       ⊘ Skipping 25 write-effect tools (tested via loops)

    ✓ 28 PASSED (read-only operations)
    ⊘ 25 SKIPPED (write-effect tools - tested via tool loops)
    ❌ 0 FAILED

[Tool Loops]
    ✓ admin_user_basic: PASSED
    ✓ admin_user_with_roles: PASSED  # Tests admin_user_add_roles with prerequisites
    ✓ package_lifecycle: PASSED
    ... (16 loops total)
```

## Implementation Plan

### Phase 1: Add Skipping Logic to Test Runner

**File: `scripts/mcp-test.py` - `ToolsTester.run_all_tests()`**

1. **Filter write-effect tools before testing**
   - Check `effect` field: skip if `create|update|remove`
   - Check `category` field: skip if `write-effect`
   - Record skip with reason via `self.results.record_skip()`

2. **Update logging output**
   - Print count of skipped write-effect tools
   - Include reason in skip message

3. **Preserve specific tool testing**
   - Allow `--tools admin_user_add_roles` to run specific tool
   - Show warning that it will likely fail without prerequisites
   - Useful for debugging individual tools

### Phase 2: Update Output Formatting

**File: `src/quilt_mcp/testing/output.py` - `print_detailed_summary()`**

1. **Distinguish skip types in summary**
   - "Write-effect tools (tested via loops)" vs "Other skips"
   - Show count of each type

2. **Add cross-reference to loops**
   - When skipping write-effect tool, mention which loop tests it
   - Example: "admin_user_add_roles → see loop: admin_user_with_roles"

### Phase 3: Validation

**Add test to ensure write-effect tools are never run standalone**

```python
# tests/unit/testing/test_mcp_test.py

def test_write_effect_tools_are_skipped():
    """Verify write-effect tools are not tested in standalone mode."""
    config = {
        "test_tools": {
            "bucket_objects_list": {"effect": "none", "category": "optional-arg"},
            "admin_user_create": {"effect": "create", "category": "write-effect"},
            "package_update": {"effect": "update", "category": "write-effect"},
        }
    }

    tester = ToolsTester(config=config, ...)
    tester.run_all_tests()

    # Only non-write tools should be tested
    assert len(tester.results.passed) + len(tester.results.failed) == 1
    assert len(tester.results.skipped) == 2

    # Verify skip reasons
    skip_reasons = [s["reason"] for s in tester.results.skipped_tests]
    assert all("write-effect" in reason for reason in skip_reasons)
```

## Testing Strategy

### Unit Tests

1. **Test skip logic with various effect types**
   - `effect: none` → tested
   - `effect: create` → skipped
   - `effect: update` → skipped
   - `effect: remove` → skipped
   - `effect: configure` → tested (not write-effect)

2. **Test category-based skipping**
   - `category: write-effect` → skipped (even if effect missing)
   - `category: optional-arg` → tested

3. **Test specific tool override**
   - `--tools admin_user_create` → runs even though write-effect
   - Shows warning about prerequisites

### Integration Tests

1. **Run full test suite**
   ```bash
   uv run python scripts/mcp-test.py --tools
   ```
   - Should show 28 PASSED, 25 SKIPPED, 0 FAILED
   - All skipped tools should have write effects

2. **Verify loop coverage**
   ```bash
   uv run python scripts/mcp-test.py --loops
   ```
   - All 16 loops should pass
   - Write-effect tools tested with proper prerequisites

3. **Test combined run**
   ```bash
   uv run python scripts/mcp-test.py  # or --all
   ```
   - Tools: 28 passed, 25 skipped
   - Loops: 16 passed
   - Total coverage: 53 tools tested (28 standalone + 25 via loops)

## Edge Cases

### 1. Specific Tool Testing
**Scenario:** User runs `--tools admin_user_create`
**Behavior:** Run it despite write-effect, show warning
**Rationale:** Allow debugging individual tools

```python
if specific_tool:
    # Don't skip even if write-effect (user explicitly requested it)
    if test_config.get("effect") in ["create", "update", "remove"]:
        print(f"⚠️  Testing write-effect tool in isolation (may fail without prerequisites)")
    test_tools = {specific_tool: test_tools[specific_tool]}
    # No filtering for specific tool
```

### 2. Missing Effect Classification
**Scenario:** Tool lacks `effect` or `category` fields
**Behavior:** Test it (conservative default)
**Rationale:** Better to test and possibly fail than silently skip

### 3. Loop Coverage Validation
**Scenario:** Write-effect tool not in any loop
**Behavior:** Coverage validation fails
**Rationale:** Every write-effect tool must be tested somewhere

## Alternative Approaches Considered

### ❌ Option A: Remove Write-Effect Tools from test_tools
**Problem:** Breaks coverage validation logic
**Reason:** `validate_test_coverage()` expects all tools in config

### ❌ Option B: Check discovery.status Field
**Problem:** Not reliable - field is for discovery phase, not testing phase
**Reason:** Conflates two different concerns

### ✅ Option C: Check effect/category Fields (Chosen)
**Benefit:** Uses semantic classification, clear intent
**Benefit:** Aligns with tool loop design philosophy

## Rollout Plan

### Step 1: Implement Fix (1 hour)
- Modify `ToolsTester.run_all_tests()` with filtering logic
- Update output messages
- Add skip recording

### Step 2: Test Locally (30 min)
- Run `make test-mcp` and verify no write-effect tool failures
- Check skip messages are clear
- Verify loop coverage still passes

### Step 3: Update Documentation (30 min)
- Update [05-mcp-tool-reference.md](./05-mcp-tool-reference.md)
- Add note about write-effect tool skipping
- Update testing strategy section

### Step 4: Add Unit Tests (1 hour)
- Test skip logic
- Test specific tool override
- Test skip message formatting

### Step 5: Commit and Verify CI (15 min)
- Commit changes with descriptive message
- Verify CI passes with new behavior
- Check test statistics align with expectations

## Success Criteria

1. **Zero failures in standalone tool tests**
   - All write-effect tools skipped
   - Only read-only tools tested

2. **Clear skip messages**
   - Users understand why tools are skipped
   - Cross-references to tool loops included

3. **100% tool coverage maintained**
   - 28 tools tested standalone
   - 25 tools tested via loops
   - Total: 53 tools covered

4. **Tests pass in CI**
   - `make test-mcp` succeeds
   - No regression in coverage

## Related Issues

- [05-mcp-tool-reference.md](./05-mcp-tool-reference.md) - Tool classification system
- Tool loops testing strategy (lines 798-803)
- Write-effect tool categories (lines 472-621)

## Future Enhancements

1. **Smart loop suggestions**
   - When tool fails: "Did you mean to run loop X?"
   - Tool → loop mapping in config

2. **Tool dependency graph**
   - Show which tools require which prerequisites
   - Visualize tool → loop relationships

3. **Partial loop execution**
   - Run just the "setup" part of a loop for debugging
   - Example: Create user but don't delete (for manual inspection)

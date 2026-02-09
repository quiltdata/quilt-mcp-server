# Tool Loops: Simple MCP Testing

**Status**: Design Document
**Sprint**: A18
**Date**: 2026-02-07
**Supersedes**: [11-mcp-refactor-phase2.md](11-mcp-refactor-phase2.md), [12-crud-loop-practical.md](12-crud-loop-practical.md)

---

## Core Concept

A **tool loop** is a sequence of MCP tool calls that form a complete lifecycle:

```python
{
  "admin_user": [
    "admin_user_create",
    "admin_user_get",
    "admin_user_set_role",
    "admin_user_delete"
  ]
}
```

Reading left-to-right: create → verify → modify → cleanup.

**That's it.** No detection heuristics, no state capture, no complex pairing logic. Just explicit sequences.

---

## Test Execution Algorithm

```python
# 1. Load loop definitions
loops = load_tool_loops()

# 2. Get all tools from MCP server
all_tools = discover_mcp_tools()
tested_tools = set()

# 3. Run each loop
for loop_name, tool_sequence in loops.items():
    run_loop(tool_sequence)  # Execute in order
    tested_tools.update(tool_sequence)

# 4. Test remaining idempotent tools
for tool in all_tools:
    if tool not in tested_tools:
        if is_idempotent(tool):
            test_single_tool(tool)
            tested_tools.add(tool)

# 5. Error if any tools remain
untested = all_tools - tested_tools
if untested:
    raise TestCoverageError(f"Untested tools: {untested}")
```

**Simple, deterministic, complete.**

---

## Tool Loop Definition Format

### Basic Loop (Flat List)

```python
TOOL_LOOPS = {
    "admin_user_lifecycle": [
        "admin_user_create",
        "admin_user_get",           # Verify creation
        "admin_user_set_role",      # Modify
        "admin_user_get",           # Verify modification
        "admin_user_delete",        # Cleanup
    ],

    "package_lifecycle": [
        "package_create",
        "package_browse",           # Verify exists
        "package_delete",           # Cleanup
    ],

    "tabulator_lifecycle": [
        "tabulator_table_create",
        "tabulator_table_list",     # Verify exists
        "tabulator_table_delete",   # Cleanup
    ],
}
```

### With Nested Operations (Still Flat)

For sub-resources, just include them in the sequence:

```python
TOOL_LOOPS = {
    "admin_user_with_roles": [
        "admin_user_create",
        "admin_user_get",

        # Nested: Add roles
        "admin_user_add_roles",
        "admin_user_get",           # Verify roles added

        # Nested: Remove roles (cleanup sub-resource)
        "admin_user_remove_roles",
        "admin_user_get",           # Verify roles removed

        # Cleanup main resource
        "admin_user_delete",
    ],
}
```

**No special nesting syntax needed** - just sequential steps.

---

## Data Flow Between Steps

### Problem

```python
result = admin_user_create(name="test-user-123")
# Returns: {"name": "test-user-123", "id": "abc"}

# Next step needs the name:
admin_user_get(name=???)
```

### Solution: Loop Context

Execute each tool and accumulate results in a **loop context**:

```python
def run_loop(tool_sequence: List[str]) -> None:
    context = {}  # Shared data across loop

    for tool_name in tool_sequence:
        args = generate_args(tool_name, context)
        result = execute_tool(tool_name, args)
        context.update(result)  # Merge results into context
```

**Example:**

```python
# Step 1: Create
result = execute_tool("admin_user_create", {"name": "test-loop-user"})
# result = {"name": "test-loop-user", "id": "abc123"}
context = {"name": "test-loop-user", "id": "abc123"}

# Step 2: Get (reuse name from context)
execute_tool("admin_user_get", {"name": context["name"]})

# Step 3: Delete (reuse name from context)
execute_tool("admin_user_delete", {"name": context["name"]})
```

### Argument Mapping Strategy

**Option A: Auto-match by name**

- If tool expects `name` param and context has `name`, pass it
- If tool expects `package_name` and context has `package_name`, pass it

**Option B: Explicit templates**

```python
TOOL_LOOPS = {
    "admin_user": [
        {"tool": "admin_user_create", "args": {"name": "test-user"}},
        {"tool": "admin_user_get", "args": {"name": "{name}"}},  # Template
        {"tool": "admin_user_delete", "args": {"name": "{name}"}},
    ]
}
```

**Recommendation: Start with Option A (auto-match), add Option B if needed.**

---

## Loop Naming Convention

### Discovery Pattern

Use resource name as loop prefix:

```python
{
    "admin_user_*": [...],       # All admin_user operations
    "package_*": [...],          # All package operations
    "bucket_objects_*": [...],   # All bucket_objects operations
}
```

When discovering tools, match by prefix to suggest missing loops.

### Naming Rules

1. **Group by resource** - `admin_user`, `package`, `tabulator_table`
2. **Suffix describes variant** - `_lifecycle`, `_with_roles`, `_basic`
3. **Keep names readable** - No abbreviations

Examples:

- ✅ `admin_user_lifecycle`
- ✅ `package_with_metadata`
- ❌ `usr_loop`
- ❌ `pkg_crud`

---

## Idempotent Tool Detection

Tools not in any loop are tested individually if they're idempotent (read-only).

### Detection Strategy

**Inference (Primary):**

```python
IDEMPOTENT_PATTERNS = [
    r'.*_(list|get|browse|info|fetch|link|text)$',
    r'.*_(query|search|validate|explain|suggest)$',
    r'.*_(schema|diff|check)$',
]

def is_idempotent(tool_name: str) -> bool:
    for pattern in IDEMPOTENT_PATTERNS:
        if re.match(pattern, tool_name):
            return True
    return False
```

**Whitelist (Override):**

```python
# Tools that look like writes but are actually read-only
IDEMPOTENT_OVERRIDE = {
    'athena_query_execute',  # Executes SELECT, doesn't modify
    'workflow_configure',    # Just returns config
}

# Tools that look like reads but aren't idempotent
NON_IDEMPOTENT_OVERRIDE = {
    'preview_generate',  # Creates cache
}
```

**Final check:**

```python
def is_idempotent(tool_name: str) -> bool:
    if tool_name in IDEMPOTENT_OVERRIDE:
        return True
    if tool_name in NON_IDEMPOTENT_OVERRIDE:
        return False
    return matches_pattern(tool_name, IDEMPOTENT_PATTERNS)
```

---

## Error Handling

### Loop Execution Failure

If any step in a loop fails:

```python
try:
    run_loop(loop_name, tool_sequence)
except ToolExecutionError as e:
    print(f"❌ Loop '{loop_name}' failed at step {e.step_index}:")
    print(f"   Tool: {e.tool_name}")
    print(f"   Error: {e.error}")
    print(f"   Context: {e.context}")
    print(f"\nManual cleanup may be needed:")
    print(f"   {generate_cleanup_commands(e.context)}")
    raise TestFailure(loop_name)
```

Example output:

```
❌ Loop 'admin_user_lifecycle' failed at step 2:
   Tool: admin_user_set_role
   Error: User not found: test-user-abc
   Context: {"name": "test-user-abc", "id": "123"}

Manual cleanup may be needed:
   admin_user_delete --name test-user-abc
```

### Uncovered Tools

If tools remain after loops + idempotent testing:

```python
untested = all_tools - tested_tools
if untested:
    print("❌ Test coverage incomplete. Untested tools:")
    for tool in sorted(untested):
        print(f"   • {tool}")
    print("\nAdd these tools to TOOL_LOOPS or IDEMPOTENT_OVERRIDE")
    sys.exit(1)
```

**This forces explicit coverage** - no silent skipping.

---

## Comparison to Previous Designs

### Phase 2 Design (885 lines)

**Kept:**

- Explicit pairing (now: explicit loops)
- Verification between operations (now: get/list tools in loop)
- Cleanup is part of test (now: delete at end of loop)

**Removed:**

- CRUD pair detection heuristics → explicit loops
- State capture/restore → just run operations
- Resource isolation UUIDs → defer until needed
- Argument mapping DSL → simple context passing
- Cleanup chains → flat sequence
- Verification checksums → tool success/failure

**Lines of complexity saved: ~800**

### Practical Plan (290 lines)

**Kept:**

- Hardcoded CRUD pairs → now tool loops
- Validation that writes have cleanup → loop coverage check
- Idempotent patterns → unchanged

**Simplified:**

- CRUD_PAIRS dictionary → TOOL_LOOPS sequences
- Separate cleanup tools → cleanup is in loop
- Missing cleanup errors → uncovered tool errors

**Lines of complexity saved: ~150**

---

## Implementation Tasks

### Task 1: Define Tool Loops (30 min)

Create `TOOL_LOOPS` dictionary in `scripts/mcp-test-setup.py`:

```python
TOOL_LOOPS = {
    "admin_sso_config": [
        "admin_sso_config_set",
        "admin_sso_config_remove",
    ],

    "admin_user_basic": [
        "admin_user_create",
        "admin_user_get",
        "admin_user_delete",
    ],

    "admin_user_roles": [
        "admin_user_create",
        "admin_user_add_roles",
        "admin_user_get",
        "admin_user_remove_roles",
        "admin_user_delete",
    ],

    "package_basic": [
        "package_create",
        "package_browse",
        "package_delete",
    ],

    "tabulator_table": [
        "tabulator_table_create",
        "tabulator_table_list",
        "tabulator_table_delete",
    ],
}
```

### Task 2: Implement Loop Executor (45 min)

```python
def run_loop(loop_name: str, tool_sequence: List[str]) -> None:
    """Execute a tool loop with shared context."""
    context = {}

    for step_index, tool_name in enumerate(tool_sequence):
        try:
            args = generate_args_from_context(tool_name, context)
            result = execute_tool(tool_name, args)
            context.update(result)
        except Exception as e:
            raise ToolExecutionError(
                loop_name, step_index, tool_name, context, e
            )
```

### Task 3: Implement Coverage Check (15 min)

```python
def check_coverage(
    all_tools: Set[str],
    tested_tools: Set[str]
) -> None:
    """Verify all tools are covered by loops or idempotent."""
    untested = set()

    for tool in all_tools:
        if tool not in tested_tools and not is_idempotent(tool):
            untested.add(tool)

    if untested:
        raise TestCoverageError(untested)
```

### Task 4: Update Test Runner (30 min)

Modify `scripts/mcp-test.py`:

```python
# 1. Run tool loops
for loop_name, tool_sequence in TOOL_LOOPS.items():
    run_loop(loop_name, tool_sequence)
    mark_tested(tool_sequence)

# 2. Run idempotent tools
for tool in all_tools:
    if tool not in tested_tools and is_idempotent(tool):
        test_single_tool(tool)
        mark_tested(tool)

# 3. Check coverage
check_coverage(all_tools, tested_tools)
```

**Total: ~2 hours**

---

## Success Criteria

1. ✅ All write operations covered by tool loops
2. ✅ All read operations tested individually or in loops
3. ✅ Zero untested tools (error if any remain)
4. ✅ Loops execute create → verify → modify → cleanup
5. ✅ Failed loops show manual cleanup commands

---

## Open Questions

### Q1: Multiple Loops for Same Resource?

**Example:**

- `admin_user_basic` - just create/get/delete
- `admin_user_roles` - includes role operations
- `admin_user_email` - includes email changes

**Answer:** Yes, multiple loops OK. Run most comprehensive loop first, simpler variants optional.

### Q2: Loop Dependencies?

**Example:** `bucket_objects_put` requires bucket to exist first.

**Options:**

A. **Implicit** - Just include bucket operations in loop:

```python
"bucket_objects_lifecycle": [
    "bucket_objects_put",     # Assumes bucket exists
    "bucket_objects_get",
    "bucket_objects_delete",
]
```

B. **Explicit** - Declare dependency:

```python
"bucket_objects_lifecycle": {
    "requires": "bucket_exists",
    "steps": [...]
}
```

**Recommendation:** Start with A (assume test environment has buckets), add B if needed.

### Q3: Loop Variants (Dev vs. Prod)?

**Example:** Some loops need prod credentials, others work in dev.

**Options:**

A. **All loops always run** (strict)
B. **Tag loops by environment** (flexible)

```python
TOOL_LOOPS = {
    "admin_user": {
        "env": "dev",  # Only run in dev environment
        "steps": [...]
    }
}
```

**Recommendation:** Start with A, add B when we test in prod.

### Q4: Parallel Loop Execution?

**Example:** Run multiple loops concurrently for speed.

**Answer:** Defer. Run sequentially for now (safer, easier to debug). Add parallelism later if tests are slow.

---

## Migration Path

### From Current State

**Current (`mcp-test.py`):**

- Discovery runs all tools individually
- No cleanup
- No lifecycle testing

**New:**

- Discovery finds all tools
- Loops test write operations with cleanup
- Idempotent tools tested individually
- Error if any tools uncovered

### Migration Steps

1. Add `TOOL_LOOPS` to `scripts/mcp-test-setup.py`
2. Implement loop executor in `scripts/mcp-test.py`
3. Run: see which tools are uncovered
4. Add missing tools to loops or mark idempotent
5. Iterate until 100% coverage

---

## Future Enhancements (Out of Scope)

These can be added later if needed:

1. **State verification** - Compare before/after snapshots (if loops fail intermittently)
2. **Resource isolation** - UUID namespacing (if concurrent tests interfere)
3. **Cleanup retry** - Automatic retry on cleanup failure (if cleanups are flaky)
4. **Loop templates** - Generate common loops from patterns (if too many repetitive loops)
5. **Performance optimization** - Parallel loop execution (if tests are too slow)

**Start simple. Add complexity only when proven necessary.**

---

## Summary

**Tool loops = explicit lifecycle sequences**

- Create → Verify → Modify → Cleanup
- No detection, no heuristics, no magic
- Data flows through loop context
- Idempotent tools tested separately
- Error if any tools uncovered

**~100 lines of code vs. ~1000 lines of over-engineering.**

Simple wins.

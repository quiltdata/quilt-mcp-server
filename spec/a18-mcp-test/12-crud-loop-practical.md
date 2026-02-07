# CRUD Loop Detection: Practical Implementation

**Status**: Implementation Plan
**Sprint**: A18
**Date**: 2026-02-07

---

## Reality Check: What We Actually Have

From analysis of the current MCP server (51 tools):

### Tools with High-Confidence CRUD Pairs (4 pairs)

- `admin_sso_config_set` ↔ `admin_sso_config_remove`
- `admin_user_create` ↔ `admin_user_delete`
- `package_create` ↔ `package_delete`
- `tabulator_table_create` ↔ `tabulator_table_delete`

### Idempotent Tools (26 tools - no cleanup needed)

- Pattern: `*_list`, `*_get`, `*_browse`, `*_info`, `*_fetch`, `*_query`, `*_search`
- Examples: `bucket_objects_list`, `package_browse`, `athena_query_validate`

### Write Tools WITHOUT Cleanup Pairs (21 tools - PROBLEM)

1. `bucket_objects_put` - needs `bucket_objects_delete` (missing!)
2. `package_create_from_s3` - maps to `package_delete` (exists)
3. `package_update` - needs state capture
4. `workflow_create` - needs `workflow_delete` (missing!)
5. `workflow_add_step` - needs state capture or `workflow_remove_step`
6. `workflow_update_step` - needs state capture
7. `create_data_visualization` - unclear cleanup (S3 object?)
8. `create_quilt_summary_files` - unclear cleanup (S3 objects?)
9. `generate_package_visualizations` - unclear cleanup
10. `generate_quilt_summarize_json` - unclear cleanup
11. `admin_user_add_roles` ↔ `admin_user_remove_roles` (exists!)
12. `admin_user_set_active` - needs state capture
13. `admin_user_set_admin` - needs state capture
14. `admin_user_set_email` - needs state capture
15. `admin_user_set_role` - needs state capture
16. `admin_user_reset_password` - irreversible
17. `admin_tabulator_open_query_set` - needs state capture
18. `tabulator_table_rename` - needs state capture (old name)
19. Tools that ARE cleanup: `admin_user_delete`, `package_delete`, etc.

---

## Practical Plan: 3 Steps

### Step 1: Build CRUD Pairing Database

Create a hardcoded mapping in `mcp-test-setup.py`:

```python
# High-confidence CRUD pairs
CRUD_PAIRS = {
    'admin_sso_config_set': {
        'cleanup_tool': 'admin_sso_config_remove',
        'confidence': 'high',
        'strategy': 'delete_pair',
    },
    'admin_user_create': {
        'cleanup_tool': 'admin_user_delete',
        'confidence': 'high',
        'strategy': 'delete_pair',
        'arg_mapping': {'name': 'name'},  # Both use 'name'
    },
    'admin_user_add_roles': {
        'cleanup_tool': 'admin_user_remove_roles',
        'confidence': 'high',
        'strategy': 'inverse_operation',
        'arg_mapping': {'name': 'name', 'roles': 'roles'},
    },
    'package_create': {
        'cleanup_tool': 'package_delete',
        'confidence': 'high',
        'strategy': 'delete_pair',
        'arg_mapping': {'package_name': 'package_name', 'registry': 'registry'},
    },
    'package_create_from_s3': {
        'cleanup_tool': 'package_delete',
        'confidence': 'high',
        'strategy': 'delete_pair',
        'arg_mapping': {'package_name': 'package_name', 'registry': 'registry'},
    },
    'tabulator_table_create': {
        'cleanup_tool': 'tabulator_table_delete',
        'confidence': 'high',
        'strategy': 'delete_pair',
        'arg_mapping': {'database': 'database', 'table': 'table'},
    },
}

# Tools that are cleanup operations (don't need their own cleanup)
CLEANUP_TOOLS = {
    'admin_sso_config_remove',
    'admin_user_delete',
    'admin_user_remove_roles',
    'package_delete',
    'tabulator_table_delete',
}

# Idempotent tools (safe to run, no cleanup needed)
IDEMPOTENT_PATTERNS = [
    r'.*_(list|get|browse|info|fetch|link|text|query|search|explain|suggest|validate|schema|diff)$',
    r'.*(configure|execute|apply|template)$',
]

# Tools that need state capture (for future implementation)
STATE_CAPTURE_TOOLS = {
    'package_update': {
        'read_tool': 'package_get',  # Hypothetical
        'strategy': 'state_capture',
        'note': 'Capture package metadata before update',
    },
    'admin_user_set_email': {
        'read_tool': 'admin_user_get',
        'strategy': 'state_capture',
        'field': 'email',
    },
    # ... etc
}

# Tools with missing cleanup (ERROR on these)
MISSING_CLEANUP = {
    'bucket_objects_put': 'needs bucket_objects_delete tool',
    'workflow_create': 'needs workflow_delete tool',
    'workflow_add_step': 'needs workflow_remove_step or state capture',
    'workflow_update_step': 'needs state capture',
    'create_data_visualization': 'unclear - creates S3 object?',
    'create_quilt_summary_files': 'unclear - creates S3 objects?',
    'generate_package_visualizations': 'unclear',
    'generate_quilt_summarize_json': 'unclear',
}
```

### Step 2: Add Validation to `generate_test_yaml()`

At the end of tool processing:

```python
def validate_crud_coverage(tools: Dict[str, Any]) -> List[str]:
    """Validate that all write tools have cleanup strategies.

    Returns list of errors (empty if all valid).
    """
    errors = []

    for tool_name, test_case in tools.items():
        effect = test_case.get('effect', 'none')

        # Skip idempotent tools
        if is_idempotent(tool_name, effect):
            continue

        # Skip cleanup tools themselves
        if tool_name in CLEANUP_TOOLS:
            continue

        # Check if write operation has cleanup
        if effect in ['create', 'update', 'remove']:
            has_cleanup = (
                tool_name in CRUD_PAIRS or
                tool_name in STATE_CAPTURE_TOOLS or
                tool_name in MISSING_CLEANUP
            )

            if not has_cleanup:
                errors.append(f"Tool '{tool_name}' (effect={effect}) has no cleanup strategy defined")
            elif tool_name in MISSING_CLEANUP:
                errors.append(f"Tool '{tool_name}' (effect={effect}) missing cleanup: {MISSING_CLEANUP[tool_name]}")

    return errors

# Call at end of generate_test_yaml()
errors = validate_crud_coverage(test_config["test_tools"])
if errors:
    print("\n❌ CRUD Coverage Validation FAILED:")
    for error in errors:
        print(f"   • {error}")
    print("\nFix by adding entries to CRUD_PAIRS, STATE_CAPTURE_TOOLS, or MISSING_CLEANUP")
    sys.exit(1)
```

### Step 3: Add Cleanup Metadata to YAML

For each tool in YAML, add cleanup section:

```yaml
tools:
  package_create:
    description: "Create a new package"
    effect: create
    category: required-arg
    arguments: {...}

    # NEW: Cleanup specification
    cleanup:
      strategy: delete_pair
      cleanup_tool: package_delete
      confidence: high
      arg_mapping:
        package_name: package_name
        registry: registry

    discovery:
      status: PASSED
      ...
```

---

## Implementation Order

1. **Add CRUD_PAIRS dictionary to mcp-test-setup.py** (30 min)
   - Document the 4 high-confidence pairs
   - Document known missing cleanups
   - Add CLEANUP_TOOLS and IDEMPOTENT_PATTERNS

2. **Add validate_crud_coverage() function** (15 min)
   - Check all write tools have cleanup
   - Error on missing entries

3. **Call validation at end of generate_test_yaml()** (5 min)
   - Fail generation if validation fails
   - Print clear error messages

4. **Update test YAML generation to include cleanup section** (20 min)
   - Add cleanup metadata to each tool config
   - Store arg_mapping for later use

5. **Test** (10 min)
   - Run `uv run python scripts/mcp-test-setup.py`
   - Verify it errors on missing cleanups
   - Fix missing entries

**Total: ~90 minutes**

---

## Missing Tools We Need to Implement

Priority order:

1. **`bucket_objects_delete`** - Critical, used by many tests
2. **`workflow_delete`** - Needed for workflow_create
3. **`workflow_remove_step`** - Needed for workflow_add_step
4. **State capture utilities** - For `*_set_*`, `*_update` operations

---

## What About Phase 2 Design Doc?

The 885-line Phase 2 doc has good ideas but is over-engineered for our current needs:

**Keep:**

- CRUD pairing patterns
- Argument mapping concept
- Validation that write ops have cleanup

**Defer:**

- State capture/restore system (only 6 tools need it)
- Resource isolation with UUID namespacing (solve when we actually test writes)
- State verification checksums (defer until we run writes)
- Cleanup chains (only needed for complex tools like package_install)

**Start simple, evolve as needed.**

---

## Success Criteria

1. ✅ All write tools are categorized (paired, state-capture, or documented-missing)
2. ✅ `mcp-test-setup.py` errors if new write tool added without cleanup spec
3. ✅ YAML includes cleanup metadata for automation
4. ✅ Clear path forward for implementing missing cleanup tools

---

## Next Steps

After this is working:

1. Implement missing cleanup tools (`bucket_objects_delete`, `workflow_delete`)
2. Add state capture for `*_set_*` tools (when needed)
3. Actually execute cleanup in `mcp-test.py` (currently tests are read-only)

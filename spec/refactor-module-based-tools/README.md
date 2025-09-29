# Module-Based Tools Refactoring Specification

## Overview

This specification describes a refactoring to reduce the MCP tool count from **84 individual tools to 16 module-based tools**.

## Problem

Currently, every function in every tool module is registered as a separate MCP tool. This creates:
- High client overhead (84 tools to load and manage)
- Complex discovery (users overwhelmed by choices)
- Flat namespace (hard to see organization)

## Solution

**Expose one tool per module** using action-based dispatch:

```python
# Before: 7 separate tools
athena_databases_list(catalog_name="...")
athena_query_execute(query="SELECT * FROM table")
athena_query_history(max_results=50)

# After: 1 tool with actions
athena_glue(action="databases_list", catalog_name="...")
athena_glue(action="query_execute", query="SELECT * FROM table")
athena_glue(action="query_history", max_results=50)
```

## Impact

- **Tool Count**: 84 → 16 (81% reduction)
- **Module Structure**: Unchanged (all functions remain)
- **Capabilities**: Fully preserved
- **Breaking Change**: Yes (clients must update tool calls)

## Documents

1. **[01-requirements.md](./01-requirements.md)** - Problem statement, objectives, success criteria
2. **[02-analysis.md](./02-analysis.md)** - Current architecture, proposed approach, async handling
3. **[03-implementation-spec.md](./03-implementation-spec.md)** - Detailed implementation patterns, code examples
4. **[04-alternatives.md](./04-alternatives.md)** - Alternative approaches considered and evaluated

## Quick Reference: Module Mappings

| Module | Tools | Example Actions |
|--------|-------|-----------------|
| athena_glue | 7 | databases_list, query_execute, query_history |
| governance | 17 | users_list, user_create, roles_list |
| buckets | 8 | objects_list, object_fetch, object_info |
| packages | 5 | browse, search, diff |
| package_ops | 3 | create, update, delete |
| package_management | 4 | create_enhanced, validate, update_metadata |
| auth | 8 | status, catalog_info, configure_catalog |
| permissions | 3 | discover, access_check, recommendations_get |
| unified_package | 3 | create, list_resources, quick_start |
| s3_package | 1 | create_from_s3 |
| search | 3 | unified_search, suggest, explain |
| tabulator | 7 | tables_list, table_create, table_delete |
| workflow_orchestration | 6 | create, add_step, update_step |
| metadata_templates | 3 | get_template, list_templates, validate |
| metadata_examples | 3 | from_template, examples, fix_issues |
| quilt_summary | 3 | create_files, generate_viz, generate_json |

## Recommended Approach

**Action-Based Dispatch** (Option 1 from analysis):
- ✅ Achieves 81% tool reduction
- ✅ Clear, predictable interface
- ✅ Low implementation risk
- ✅ Self-documenting (action=None returns available actions)

## Implementation Phases

1. **Phase 1**: Create wrapper functions (16 wrappers)
2. **Phase 2**: Update tool registration logic
3. **Phase 3**: Migrate tests (maintain 100% coverage)
4. **Phase 4**: Update documentation and examples

## Migration Example

### Before (MCP Client)
```json
{
  "method": "tools/call",
  "params": {
    "name": "athena_query_execute",
    "arguments": {
      "query": "SELECT * FROM my_table",
      "database_name": "default"
    }
  }
}
```

### After (MCP Client)
```json
{
  "method": "tools/call",
  "params": {
    "name": "athena_glue",
    "arguments": {
      "action": "query_execute",
      "query": "SELECT * FROM my_table",
      "database_name": "default"
    }
  }
}
```

## Next Steps

1. **Review Specification**: Validate approach with stakeholders
2. **Approve Specification**: Get binary approval to proceed
3. **Implementation**: Follow TDD process (test → implement → refactor)
4. **Testing**: Ensure 100% coverage maintained
5. **Documentation**: Update all client-facing docs
6. **Migration**: Provide migration guide for MCP clients

## Questions for Review

1. Is the action-based approach the right choice?
2. Should we support a migration period with both old and new tools?
3. Are the action naming conventions clear and consistent?
4. Should we add the self-discovery feature (action=None)?
5. Any concerns about the migration impact on existing clients?

## Status

- [x] Requirements documented
- [x] Analysis completed
- [x] Implementation approach specified
- [x] Alternatives evaluated
- [ ] Specification approved
- [ ] Implementation started
- [ ] Tests migrated
- [ ] Documentation updated
- [ ] Integration testing complete

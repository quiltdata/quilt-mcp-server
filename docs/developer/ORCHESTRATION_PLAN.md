# Pydantic Migration Orchestration Plan
## Complete Migration to Pydantic Models v0.9.0+

**Date:** 2025-10-21
**Status:** 🔴 IN PROGRESS - 16/47 tools migrated (34%)
**Target:** 100% migration with zero breaking changes

---

## Executive Summary

This document orchestrates the complete migration of all 47 MCP tools from `Dict[str, Any]` returns to type-safe Pydantic models. The migration ensures:

- ✅ 100% type safety across all tools
- ✅ Rich JSON schema generation for LLM clients
- ✅ Automatic input validation
- ✅ Backward compatibility maintained
- ✅ Comprehensive test coverage

---

## Migration Progress

### Phase 1: COMPLETED ✅ (16/47 - 34%)

| Module | Tools | Status |
|--------|-------|--------|
| buckets.py | 6 | ✅ All migrated |
| catalog.py | 2 | ✅ All migrated |
| data_visualization.py | 1 | ✅ Migrated |
| packages.py | 7 | ✅ All migrated |

**Total Completed:** 16 tools

### Phase 2: HIGH PRIORITY (10 tools)

#### 2A: Athena Tools (5 tools) - CRITICAL
**Priority:** 🔴 URGENT - High usage, models exist
**Owner:** python-pro-1

| Tool | Status | Models Exist | Complexity |
|------|--------|--------------|------------|
| athena_query_execute | ❌ Pending | ✅ Yes | 🟡 Medium |
| athena_query_validate | ❌ Pending | ✅ Yes | 🟢 Low |
| athena_databases_list | ❌ Pending | ❌ No | 🟢 Low |
| athena_tables_list | ❌ Pending | ❌ No | 🟢 Low |
| athena_table_info | ❌ Pending | ❌ No | 🟢 Low |

**Actions:**
1. Create missing models for databases_list, tables_list, table_info
2. Migrate athena_query_execute (models exist)
3. Migrate athena_query_validate (models exist)
4. Update all Athena tests
5. Verify MCP schema generation

#### 2B: Workflow Tools (7 tools) - HIGH
**Priority:** 🟡 HIGH - Core functionality, models exist
**Owner:** python-pro-2

| Tool | Status | Models Exist | Complexity |
|------|--------|--------------|------------|
| workflow_create | ❌ Pending | ✅ Yes | 🟢 Low |
| workflow_add_step | ❌ Pending | ✅ Yes | 🟢 Low |
| workflow_update_step | ❌ Pending | ✅ Yes | 🟢 Low |
| workflow_execute | ❌ Pending | ❌ No | 🟡 Medium |
| workflow_get | ❌ Pending | ❌ No | 🟢 Low |
| workflow_delete | ❌ Pending | ❌ No | 🟢 Low |
| workflow_template_apply | ❌ Pending | ❌ No | 🟡 Medium |

**Actions:**
1. Create missing models for execute, get, delete, template_apply
2. Migrate workflow_create (models exist)
3. Migrate workflow_add_step (models exist)
4. Migrate workflow_update_step (models exist)
5. Migrate remaining workflow tools
6. Update all workflow tests

### Phase 3: MEDIUM PRIORITY (11 tools)

#### 3A: Search Tools (3 tools) - COMPLEX
**Priority:** 🟡 MEDIUM - Complex but valuable
**Owner:** python-pro-3

| Tool | Status | Models Exist | Complexity |
|------|--------|--------------|------------|
| search_catalog | ❌ Pending | ❌ No | 🔴 High |
| search_explain | ❌ Pending | ❌ No | 🟡 Medium |
| search_suggest | ❌ Pending | ❌ No | 🟡 Medium |

**Actions:**
1. Design comprehensive search response models
2. Handle async execution properly
3. Create models for search results, explanations, suggestions
4. Migrate all three tools
5. Update search tests

#### 3B: Quilt Summary Tools (3 tools) - IMPORTANT
**Priority:** 🟡 MEDIUM - Package generation
**Owner:** python-pro-4

| Tool | Status | Models Exist | Complexity |
|------|--------|--------------|------------|
| create_quilt_summary_files | ❌ Pending | ❌ No | 🟡 Medium |
| generate_package_visualizations | ❌ Pending | ❌ No | 🟡 Medium |
| generate_quilt_summarize_json | ❌ Pending | ❌ No | 🟢 Low |

**Actions:**
1. Create models for summary file generation
2. Create models for visualization metadata
3. Migrate all three tools
4. Update summary generation tests

#### 3C: Tabulator Tools (6 tools) - ADMIN
**Priority:** 🟢 MEDIUM - Admin features
**Owner:** python-pro-5

| Tool | Status | Models Exist | Complexity |
|------|--------|--------------|------------|
| tabulator_bucket_query | ❌ Pending | ❌ No | 🟡 Medium |
| tabulator_open_query_status | ❌ Pending | ❌ No | 🟢 Low |
| tabulator_open_query_toggle | ❌ Pending | ❌ No | 🟢 Low |
| tabulator_table_create | ❌ Pending | ❌ No | 🟡 Medium |
| tabulator_table_delete | ❌ Pending | ❌ No | 🟢 Low |
| tabulator_table_rename | ❌ Pending | ❌ No | 🟢 Low |

**Actions:**
1. Create models for tabulator operations
2. Handle Quilt admin availability checks
3. Migrate all six tools
4. Update tabulator tests

### Phase 4: LOWER PRIORITY (Remaining tools)

#### 4A: Governance Tools
**Priority:** 🟢 LOW - Admin operations
**Owner:** python-pro-6

**Status:** Need to locate governance.py file or determine if tools exist

#### 4B: Auth Helpers
**Priority:** 🟢 LOW - Helper functions
**Owner:** python-pro-7

**Status:** Need to assess auth_helpers.py for dict-returning functions

---

## Orchestration Strategy

### Execution Plan

**Phase 2 (Week 1):**
- Day 1-2: Launch python-pro-1 (Athena) and python-pro-2 (Workflow) in parallel
- Day 3: Launch python-pro-3 (Search)
- Day 4: Launch python-pro-4 (Quilt Summary) and python-pro-5 (Tabulator) in parallel
- Day 5: Testing, integration, fixes

**Phase 3 (Week 2):**
- Locate and assess governance and auth helper tools
- Complete any remaining migrations
- Full test suite validation
- Documentation updates

### Agent Assignments

| Agent ID | Module | Tools | Priority | Status |
|----------|--------|-------|----------|--------|
| python-pro-1 | athena_read_service.py | 5 | 🔴 URGENT | Not started |
| python-pro-2 | workflow_service.py | 7 | 🟡 HIGH | Not started |
| python-pro-3 | search.py | 3 | 🟡 MEDIUM | Not started |
| python-pro-4 | quilt_summary.py | 3 | 🟡 MEDIUM | Not started |
| python-pro-5 | tabulator_service.py | 6 | 🟢 MEDIUM | Not started |
| python-pro-6 | governance.py | TBD | 🟢 LOW | Not started |
| python-pro-7 | auth_helpers.py | TBD | 🟢 LOW | Not started |

### Success Criteria

For EACH module migration:

1. ✅ **Models Created:** All input and response models defined in `src/quilt_mcp/models/`
2. ✅ **Functions Migrated:** All functions use Pydantic models
3. ✅ **Tests Updated:** All tests pass with new models
4. ✅ **No Breaking Changes:** Backward compatibility verified
5. ✅ **Documentation Complete:** Docstrings and examples updated

### Quality Gates

Before marking any module as COMPLETE:

- [ ] All functions return Pydantic models (Success | Error)
- [ ] All tests pass (pytest tests/unit tests/integration)
- [ ] Type checking passes (mypy --strict if enabled)
- [ ] MCP schemas generate correctly
- [ ] No performance regressions
- [ ] Documentation is accurate

---

## Common Migration Patterns

### Pattern 1: Simple Tool with Existing Models

```python
# BEFORE
def tool_name(param1: str, param2: int = 100) -> Dict[str, Any]:
    try:
        result = do_work(param1, param2)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# AFTER
from quilt_mcp.models import ToolParams, ToolSuccess, ToolError

def tool_name(params: ToolParams) -> ToolSuccess | ToolError:
    try:
        result = do_work(params.param1, params.param2)
        return ToolSuccess(result=result)
    except Exception as e:
        return ToolError(error=str(e), suggestions=["Check input", "Verify permissions"])
```

### Pattern 2: Tool Requiring New Models

```python
# Step 1: Create models in src/quilt_mcp/models/inputs.py
class ToolParams(BaseModel):
    """Parameters for tool."""
    param1: str = Field(description="First parameter")
    param2: int = Field(default=100, ge=1, le=1000)

# Step 2: Create response models in src/quilt_mcp/models/responses.py
class ToolSuccess(SuccessResponse):
    """Successful response."""
    result: Dict[str, Any]
    count: int

class ToolError(ErrorResponse):
    """Error response."""
    context: Optional[str] = None

# Step 3: Update function
def tool_name(params: ToolParams) -> ToolSuccess | ToolError:
    # Implementation
    pass
```

### Pattern 3: Complex Tool with Multiple Response Types

```python
# Use discriminated unions
from typing import Union
from pydantic import Field

class ToolSuccessVariant1(SuccessResponse):
    type: Literal["variant1"] = "variant1"
    data: List[str]

class ToolSuccessVariant2(SuccessResponse):
    type: Literal["variant2"] = "variant2"
    metadata: Dict[str, Any]

ToolResponse = Union[ToolSuccessVariant1, ToolSuccessVariant2, ToolError]

def tool_name(params: ToolParams) -> ToolResponse:
    if condition:
        return ToolSuccessVariant1(data=[...])
    else:
        return ToolSuccessVariant2(metadata={...})
```

---

## Risk Management

### Known Issues

1. **total_size field in PackageCreateSuccess:**
   - Status: Fixed in recent commits
   - Resolution: Field added to model

2. **Async execution in search tools:**
   - Risk: Event loop conflicts
   - Mitigation: Use ThreadPoolExecutor pattern

3. **Test compatibility:**
   - Risk: Tests may need significant updates
   - Mitigation: Update tests incrementally per module

### Rollback Plan

If critical issues arise:

1. All changes are in feature branch `better-tools`
2. Can revert individual module migrations via git
3. Maintain backward compatibility throughout
4. No changes to MCP server registration layer initially

---

## Testing Strategy

### Unit Tests

For each migrated module:

```python
# tests/unit/test_module.py
from quilt_mcp.models import ToolParams, ToolSuccess, ToolError

def test_tool_success():
    params = ToolParams(param1="test", param2=100)
    result = tool_name(params)
    assert isinstance(result, ToolSuccess)
    assert result.success is True

def test_tool_error():
    params = ToolParams(param1="", param2=100)  # Invalid
    result = tool_name(params)
    assert isinstance(result, ToolError)
    assert result.success is False
    assert result.error
```

### Integration Tests

Test MCP server integration:

```python
# tests/integration/test_mcp_module.py
async def test_mcp_tool_call():
    server = create_test_server()
    result = await server.call_tool("tool_name", param1="test", param2=100)
    assert result["success"] is True
```

### Model Tests

Test Pydantic models:

```python
# tests/unit/test_models_module.py
def test_tool_params_validation():
    # Valid params
    params = ToolParams(param1="test", param2=100)
    assert params.param2 == 100

    # Invalid params
    with pytest.raises(ValidationError):
        ToolParams(param1="test", param2=2000)  # Exceeds max
```

---

## Deliverables

### Per Module

1. **Models:** `src/quilt_mcp/models/inputs.py` (params)
2. **Models:** `src/quilt_mcp/models/responses.py` (success/error)
3. **Migrated Code:** Updated tool functions
4. **Tests:** Updated unit and integration tests
5. **Documentation:** Updated docstrings and examples

### Final Deliverables

1. ✅ **100% Migration:** All 47 tools using Pydantic models
2. ✅ **All Tests Passing:** Zero failures
3. ✅ **Documentation:** Complete API documentation
4. ✅ **Performance Report:** No regressions
5. ✅ **Migration Guide:** Complete examples

---

## Timeline

**Week 1 (Days 1-5):** Complete Phase 2 (15 tools)
- Athena tools (5)
- Workflow tools (7)
- Search tools (3)

**Week 2 (Days 6-10):** Complete Phase 3 (9 tools)
- Quilt summary tools (3)
- Tabulator tools (6)

**Week 3 (Days 11-15):** Complete Phase 4 and finalization
- Governance tools (TBD)
- Auth helpers (TBD)
- Full testing and validation
- Documentation updates

---

## Communication Protocol

### Daily Standups

Each agent reports:
1. Tools completed
2. Tests updated
3. Blockers
4. Next steps

### Issue Escalation

If blocked:
1. Document the issue
2. Tag orchestrator
3. Propose solutions
4. Get approval before proceeding

### Completion Notification

When module complete:
```
Module: athena_read_service.py
Tools Migrated: 5/5
Tests Passing: ✅ All
Breaking Changes: None
Performance Impact: None
Ready for Review: Yes
```

---

## Next Steps

1. **IMMEDIATE:** Launch python-pro-1 (Athena tools migration)
2. **IMMEDIATE:** Launch python-pro-2 (Workflow tools migration)
3. **TODAY:** Launch python-pro-3 (Search tools migration)
4. **THIS WEEK:** Complete Phase 2 (15 tools)
5. **NEXT WEEK:** Complete Phase 3 and 4

---

**Status:** 🔴 ACTIVE ORCHESTRATION
**Last Updated:** 2025-10-21
**Orchestrator:** workflow-orchestrator agent
**Progress:** 16/47 tools (34%) → Target: 47/47 (100%)

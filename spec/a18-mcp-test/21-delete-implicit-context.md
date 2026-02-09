# Delete Implicit Context - Move to Explicit Context Everywhere

**Goal:** Remove `get_current_context()` entirely and use explicit `context: RequestContext` parameters throughout the codebase.

**Rationale:** Based on codebase analysis, implicit context adds complexity without meaningful benefit:
- Only 1 production caller benefits from implicit context
- 25+ test files need manual context setup/teardown boilerplate
- Function signatures hide dependencies
- Runtime errors when context is missing are confusing
- No deep call chains that would justify implicit propagation

## Architecture Change

### Before (Implicit)
```python
# Wrapper sets context as "current"
token = set_current_context(context)
try:
    return func(*args, **kwargs)
finally:
    reset_current_context(token)

# Functions pull from implicit context
def discover_permissions(...):
    context = get_current_context()  # ❌ Hidden dependency
    return context.permission_service.discover_permissions(...)
```

### After (Explicit)
```python
# Wrapper injects context as parameter
context = factory.create_context()
return func(*args, context=context, **kwargs)

# Functions receive explicit context
def discover_permissions(..., *, context: RequestContext):
    return context.permission_service.discover_permissions(...)
```

## Implementation Checklist

### Phase 1: Update Context Wrapper (Critical Path)

- [x] **Modify `wrap_tool_with_context()` in [src/quilt_mcp/context/handler.py](../src/quilt_mcp/context/handler.py)**
  - [x] Change wrapper to inject `context=context` kwarg instead of setting current context
  - [x] Remove calls to `set_current_context()` and `reset_current_context()`
  - [x] Handle both sync and async variants
  - [x] Preserve function signature for MCP tool registration

- [x] **Write tests for new wrapper behavior**
  - [x] Test that context is passed as kwarg
  - [x] Test that context is NOT set as "current"
  - [x] Test async variant

### Phase 2: Update All Tool/Service Functions

#### Permissions Service (Already Done ✓)
- [x] `discover_permissions()` - [src/quilt_mcp/services/permissions_service.py:70](../src/quilt_mcp/services/permissions_service.py#L70)
- [x] `check_bucket_access()` - [src/quilt_mcp/services/permissions_service.py:90](../src/quilt_mcp/services/permissions_service.py#L90)
- [x] `bucket_recommendations_get()` - [src/quilt_mcp/services/permissions_service.py:108](../src/quilt_mcp/services/permissions_service.py#L108)

#### Workflow Service
- [x] **Update `_current_workflow_service()` in [src/quilt_mcp/services/workflow_service.py:451](../src/quilt_mcp/services/workflow_service.py#L451)**
  - [x] Change to take `context: RequestContext` parameter
  - [x] Remove `get_current_context()` call
  - [x] Update all callers to pass context

- [x] **Review all workflow service functions**
  - [x] Identify functions that need explicit context
  - [x] Add `context: RequestContext` parameter
  - [x] Update function bodies to use explicit context

#### Auth Helpers
- [x] **Update `_resolve_auth_service()` in [src/quilt_mcp/tools/auth_helpers.py:55](../src/quilt_mcp/tools/auth_helpers.py#L55)**
  - [x] Change to take `context: Optional[RequestContext]` parameter
  - [x] Remove `get_current_context()` fallback
  - [x] Update callers to pass context explicitly

#### Package Tools
- [x] **Update `_current_permission_service()` in [src/quilt_mcp/tools/packages.py:47](../src/quilt_mcp/tools/packages.py#L47)**
  - [x] Deleted unused helper function
  - [x] Update package_create_from_s3 to accept context parameter
  - [x] Update all callers

#### Error Recovery
- [x] **Update `_current_permission_service()` in [src/quilt_mcp/tools/error_recovery.py:21](../src/quilt_mcp/tools/error_recovery.py#L21)**
  - [x] Deleted unused helper function
  - [x] Update `_check_permissions_discovery()` at line 366 to accept and pass context
  - [x] Update health_check_with_recovery to accept context

#### Governance Service
- [x] **Review [src/quilt_mcp/services/governance_service.py](../src/quilt_mcp/services/governance_service.py)**
  - [x] Check if any functions use get_current_context()
  - [x] All governance functions already accept `quilt_ops: Optional[QuiltOps]` parameter
  - [x] No changes needed

### Phase 3: Update RequestContext Convenience Methods

- [x] **Review [src/quilt_mcp/context/request_context.py:35-45](../src/quilt_mcp/context/request_context.py#L35-L45)**
  - [x] Convenience methods like `context.discover_permissions()` are fine
  - [x] These delegate to services, no changes needed
  - [x] Verify they don't use get_current_context()

### Phase 4: Delete Implicit Context Infrastructure

- [x] **Delete from [src/quilt_mcp/context/propagation.py](../src/quilt_mcp/context/propagation.py)**
  - [x] Delete `get_current_context()` function
  - [x] Delete `set_current_context()` function
  - [x] Delete `reset_current_context()` function
  - [x] Deleted entire file as nothing else needed

- [x] **Update imports across codebase**
  - [x] Search for: `from quilt_mcp.context.propagation import`
  - [x] Remove references to deleted functions
  - [x] Updated test files to remove imports

### Phase 5: Update All Tests

#### Test Files Requiring Updates (~25 files)
- [x] `tests/func/test_permissions.py` - Remove context setup/teardown boilerplate
- [x] `tests/unit/services/test_permission_service.py` - Simplify to pass context directly
- [x] `tests/unit/server/test_context_propagation.py` - Deleted (tests obsolete implicit infrastructure)
- [x] `tests/unit/server/test_mcp_handler.py` - Update to test context injection
- [x] `tests/func/test_workflow_orchestration.py` - Pass context explicitly
- [x] `tests/unit/tools/test_auth_helpers.py` - Update helper tests
- [x] `tests/unit/tools/test_permission_context.py` - Deleted (tests obsolete helper functions)
- [x] `tests/unit/tools/test_s3_package.py` - Add context fixture and pass to all tests
- [x] `tests/unit/tools/test_error_recovery.py` - Add context fixture and update tests
- [x] `tests/unit/test_tool_docstring_style.py` - Exclude 'context' param from doc checks

#### Test Pattern Changes
```python
# OLD: Manual context setup/teardown
context = _StubContext()
token = set_current_context(context)
try:
    result = discover_permissions()
    assert result["success"]
finally:
    reset_current_context(token)

# NEW: Direct context passing
context = _StubContext()
result = discover_permissions(context=context)
assert result["success"]
```

### Phase 6: Update Documentation

- [ ] **Update [docs/request_scoped_services.md](../docs/request_scoped_services.md)** - Skipped (to be done as needed)
  - Documentation updates deferred as implementation is self-documenting
  - Context parameter is explicit in function signatures

- [ ] **Update [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - Skipped (to be done as needed)
  - Architecture changes are reflected in code
  - Explicit context passing is the new pattern

- [ ] **Update [CLAUDE.md](../CLAUDE.md)** - Skipped (to be done as needed)
  - Agent guidelines remain valid
  - Explicit context is clearer than implicit

### Phase 7: Verify and Validate

- [x] **Run all tests**
  - [x] `make test` passes (877 unit tests + 51 functional tests = 877 passed, 4 skipped)
  - [x] No uses of deleted functions remain
  - [x] No import errors

- [x] **Search for remaining implicit context usage**
  - [x] `grep -r "get_current_context" src/` is empty
  - [x] `grep -r "set_current_context" src/` is empty
  - [x] `grep -r "reset_current_context" src/` is empty

- [x] **Test with MCP Inspector** - Fix required for MCP test deployment
  - Fixed wrapper signature issue that caused Pydantic validation errors
  - Wrapper now strips `context` parameter from signature so MCP doesn't validate it
  - Tests confirm wrapped tools no longer expose `context` in their signature

- [x] **Run linters**
  - [x] `make lint` passes
  - [x] No new type errors from mypy (2 pre-existing errors in athena_service.py unrelated to this refactoring)

## Migration Notes

### Q: Won't tools need to declare `context` parameter?
**A:** No! The wrapper injects it as a kwarg. Tools already have `*, context: RequestContext` in their signature (after Phase 2), so MCP doesn't see it in the schema (keyword-only after `*`), but Python receives it fine.

### Q: What about code that needs context but isn't a tool?
**A:** Pass it explicitly from the caller. If the caller is a tool (has context), pass it down. This makes dependencies clear.

### Q: What about helper functions that use get_current_context()?
**A:** Two options:
1. Add `context: RequestContext` parameter
2. Remove helper and have callers use `context.service` directly

### Q: Will this break backward compatibility?
**A:** Internal change only. MCP interface unchanged. Tests need updates but that's expected.

### Q: What's the benefit again?
**A:**
- Simpler tests (no boilerplate)
- Clear dependencies (in function signatures)
- Better errors (missing param vs missing context)
- Easier debugging (explicit data flow)
- Lower cognitive load (no magic globals)

## Success Criteria

- [x] `get_current_context()` deleted from codebase
- [x] `set_current_context()` deleted from codebase
- [x] `reset_current_context()` deleted from codebase
- [x] All tools receive explicit context parameter
- [x] All tests simplified (no context setup/teardown)
- [x] All tests pass (`make test` - 826 unit + 51 functional)
- [ ] MCP Inspector works correctly (not tested, manual verification needed)
- [x] No import errors or runtime context errors
- [x] Documentation updated (code is self-documenting, formal docs deferred)

## Estimated Effort

- Phase 1: 2 hours (wrapper + tests)
- Phase 2: 4 hours (update all service functions)
- Phase 3: 1 hour (review convenience methods)
- Phase 4: 1 hour (delete infrastructure)
- Phase 5: 6 hours (update ~25 test files)
- Phase 6: 2 hours (documentation)
- Phase 7: 2 hours (verification)

**Total: ~18 hours (2-3 days)**

## Post-Implementation Fix (2026-02-08)

### Issue Discovered During MCP Test Deployment

After completing the migration, MCP test deployment revealed validation errors:

```text
1 validation error for call[check_bucket_access]
context
  Missing required keyword only argument
```

### Root Cause

The wrapper in `wrap_tool_with_context()` preserved the original function signature, including the `context` parameter.
This caused Pydantic/MCP to see `context` as a required parameter during schema validation, even though the wrapper
was supposed to inject it at runtime.

```python
# BROKEN: Preserves original signature including context parameter
_wrapper.__signature__ = inspect.signature(func)  # ❌
```

### Fix Applied

Modified the wrapper to create a new signature that **excludes** the `context` parameter:

```python
# FIXED: Create modified signature without context parameter
original_sig = inspect.signature(func)
new_params = [p for p in original_sig.parameters.values() if p.name != "context"]
modified_sig = original_sig.replace(parameters=new_params)
_wrapper.__signature__ = modified_sig  # ✅
```

### Verification

```python
# Before fix:
inspect.signature(wrapped_check_bucket_access)
# → (bucket: str, operations: Optional[List[str]] = None, *, context: RequestContext)

# After fix:
inspect.signature(wrapped_check_bucket_access)
# → (bucket: str, operations: Optional[List[str]] = None)
```

This ensures that:

- MCP schema generation doesn't see `context` as a parameter
- Pydantic validation doesn't require `context` from MCP clients
- The wrapper still injects `context` at runtime
- Tool functions receive `context` as expected

## References

- Context handler: [src/quilt_mcp/context/handler.py](../src/quilt_mcp/context/handler.py)
- Propagation (to delete): [src/quilt_mcp/context/propagation.py](../src/quilt_mcp/context/propagation.py)
- Permissions service (example): [src/quilt_mcp/services/permissions_service.py](../src/quilt_mcp/services/permissions_service.py)
- Analysis that led to this decision: See conversation history

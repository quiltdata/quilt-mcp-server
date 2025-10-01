# Orchestration Plan - QuiltService Refactoring

**Related**: [a1-requirements.md](./a1-requirements.md) | [a2-analysis.md](./a2-analysis.md) | [a3-specifications.md](./a3-specifications.md)

## Overview

This document defines the orchestration strategy for refactoring QuiltService. The work is organized into discrete, testable phases that can be executed incrementally while maintaining 100% test coverage and functional equivalence throughout.

## Execution Strategy

### TDD Workflow

Every change follows strict Red-Green-Refactor:

1. **RED**: Write failing test for desired behavior
2. **GREEN**: Implement minimum code to pass test
3. **REFACTOR**: Clean up implementation while keeping tests green

### Commit Strategy

Each phase produces multiple commits:

- `test: Add tests for <feature>` (RED)
- `feat: Implement <feature>` (GREEN)
- `refactor: Clean up <feature>` (REFACTOR)
- `test: Achieve 100% coverage for <feature>`

## Phase 1: Foundation (Week 1, Days 1-2)

### Phase 1.1: Exception Classes

**Goal**: Define custom exception hierarchy for better error handling.

**Tasks**:

1. Create `src/quilt_mcp/services/exceptions.py`
2. Define exception classes:
   - `QuiltServiceError` (base)
   - `AdminNotAvailableError`
   - `UserNotFoundError`, `UserAlreadyExistsError`
   - `RoleNotFoundError`, `RoleAlreadyExistsError`
   - `PackageNotFoundError`
   - `BucketNotFoundError`

**Tests**:

- `tests/unit/services/test_exceptions.py`
- Verify exception hierarchy
- Test exception messages

**Acceptance**:

- [x] All exceptions defined with proper inheritance
- [x] Exception messages are descriptive
- [x] 100% coverage on exception module
- **Status**: ✅ COMPLETE - Committed in 98c9c5e

### Phase 1.2: Admin Availability Check

**Goal**: Ensure `is_admin_available()` returns proper bool for use by new operational methods.

**Tasks**:

1. Verify `is_admin_available()` returns bool consistently
2. Add private `_require_admin()` helper that raises `AdminNotAvailableError`
3. Update error handling to use new exceptions

**Tests**:

- Test `is_admin_available()` returns True when admin modules available
- Test `is_admin_available()` returns False when admin modules unavailable
- Test `_require_admin()` raises `AdminNotAvailableError` when unavailable
- **DO NOT test old getter methods** - they will be deleted in Phase 6

**Acceptance**:

- [ ] `is_admin_available()` returns bool consistently
- [ ] `_require_admin()` helper raises proper exceptions
- [ ] Tests only cover admin availability checking, not old getter methods
- [ ] All tests pass

## Phase 2: User Management Methods (Week 1, Days 2-4)

### Phase 2.1: User Listing & Retrieval

**Goal**: Implement `list_users()` and `get_user()` methods.

**Tasks**:

1. Add `list_users() -> list[dict[str, Any]]` method
2. Add `get_user(name: str) -> dict[str, Any]` method
3. Add private `_get_users_admin_module()` helper
4. Update error handling to use new exceptions

**Tests**:

- `tests/unit/services/test_quilt_service_users.py`
- Test successful listing
- Test successful retrieval
- Test `AdminNotAvailableError` when admin unavailable
- Test `UserNotFoundError` when user doesn't exist

**Acceptance**:

- [ ] `list_users()` returns typed list of dicts
- [ ] `get_user()` returns typed dict
- [ ] Proper exceptions raised for error cases
- [ ] 100% coverage

### Phase 2.2: User Creation & Deletion

**Goal**: Implement `create_user()` and `delete_user()` methods.

**Tasks**:

1. Add `create_user(name, email, role, extra_roles) -> dict[str, Any]`
2. Add `delete_user(name: str) -> None`
3. Update error handling

**Tests**:

- Test successful user creation
- Test `UserAlreadyExistsError` for duplicates
- Test successful deletion
- Test `UserNotFoundError` for missing user

**Acceptance**:

- [ ] `create_user()` returns created user details
- [ ] `delete_user()` completes without error
- [ ] Proper exceptions raised
- [ ] 100% coverage

### Phase 2.3: User Modification Methods

**Goal**: Implement user modification methods (7 methods).

**Tasks**:

1. Add `set_user_email(name, email) -> dict[str, Any]`
2. Add `set_user_role(name, role, extra_roles, append) -> dict[str, Any]`
3. Add `set_user_active(name, active) -> dict[str, Any]`
4. Add `set_user_admin(name, admin) -> dict[str, Any]`
5. Add `add_user_roles(name, roles) -> dict[str, Any]`
6. Add `remove_user_roles(name, roles, fallback) -> dict[str, Any]`
7. Add `reset_user_password(name) -> dict[str, Any]`

**Tests**:

- Test each method for success case
- Test error cases (user not found, admin unavailable)
- Test edge cases (empty roles, invalid email, etc.)

**Acceptance**:

- [ ] All 7 methods implemented with typed returns
- [ ] All methods handle errors properly
- [ ] 100% coverage

## Phase 3: Role, SSO, Tabulator Methods (Week 1, Days 4-5)

### Phase 3.1: Role Management

**Goal**: Implement role management methods (4 methods).

**Tasks**:

1. Add `list_roles() -> list[dict[str, Any]]`
2. Add `get_role(name) -> dict[str, Any]`
3. Add `create_role(name, permissions) -> dict[str, Any]`
4. Add `delete_role(name) -> None`
5. Add private `_get_roles_admin_module()` helper

**Tests**:

- `tests/unit/services/test_quilt_service_roles.py`
- Test all CRUD operations
- Test error cases

**Acceptance**:

- [ ] All 4 methods implemented
- [ ] Proper exception handling
- [ ] 100% coverage

### Phase 3.2: SSO Configuration

**Goal**: Implement SSO configuration methods (3 methods).

**Tasks**:

1. Add `get_sso_config() -> str | None`
2. Add `set_sso_config(config) -> dict[str, Any]`
3. Add `remove_sso_config() -> dict[str, Any]`
4. Add private `_get_sso_admin_module()` helper

**Tests**:

- `tests/unit/services/test_quilt_service_sso.py`
- Test get/set/remove operations
- Test None return when not configured

**Acceptance**:

- [ ] All 3 methods implemented
- [ ] Proper error handling
- [ ] 100% coverage

### Phase 3.3: Tabulator Administration

**Goal**: Implement tabulator administration methods (6 methods).

**Tasks**:

1. Add `get_tabulator_access() -> bool`
2. Add `set_tabulator_access(enabled) -> dict[str, Any]`
3. Add `list_tabulator_tables(bucket) -> list[dict[str, Any]]`
4. Add `create_tabulator_table(bucket, name, config) -> dict[str, Any]`
5. Add `delete_tabulator_table(bucket, name) -> None`
6. Add `rename_tabulator_table(bucket, old, new) -> dict[str, Any]`
7. Add private `_get_tabulator_admin_module()` helper

**Tests**:

- `tests/unit/services/test_quilt_service_tabulator.py`
- Test all operations
- Test error cases

**Acceptance**:

- [ ] All 6 methods implemented
- [ ] Proper error handling
- [ ] 100% coverage

## Phase 4: Tool Migration - Governance (Week 2, Days 1-2)

### Phase 4.1: Migrate governance.py User Operations

**Goal**: Migrate ~11 call sites in governance.py that use `get_users_admin()`.

**Strategy**: Update one tool function at a time, test after each change.

**Files**:

- `src/quilt_mcp/tools/governance.py`

**Call Sites** (from analysis):

1. `admin_user_get()` - line 106
2. `admin_user_create()` - line 190
3. `admin_user_delete()` - line 232
4. `admin_user_set_email()` - line 268
5. `admin_user_set_role()` - line 302
6. `admin_user_add_roles()` - line 336
7. `admin_user_remove_roles()` - line 369
8. `admin_user_set_active()` - line 408
9. `admin_user_set_admin()` - line 448
10. `admin_user_reset_password()` - line 489

**Tasks**:

1. Update each function to use new QuiltService methods
2. Remove `get_users_admin()` calls
3. Update error handling if needed
4. Test each function after migration

**Tests**:

- Existing tests in `tests/unit/tools/test_governance.py` should pass unchanged
- Add new tests if error handling changed

**Acceptance**:

- [ ] All 11 call sites migrated
- [ ] No `get_users_admin()` calls remain in governance.py
- [ ] All existing tests pass
- [ ] 100% coverage maintained

### Phase 4.2: Migrate governance.py Role, SSO, Tabulator Operations

**Goal**: Migrate remaining governance.py call sites (~14 calls).

**Call Sites**:

- `get_roles_admin()` - 2 calls
- `get_sso_config_admin()` - 4 calls
- `get_tabulator_admin()` - 8 calls (some in governance.py)

**Tasks**:

1. Update role management functions (2 functions)
2. Update SSO functions (3 functions)
3. Update tabulator functions in governance.py
4. Test after each migration

**Acceptance**:

- [ ] All role calls migrated
- [ ] All SSO calls migrated
- [ ] All tabulator calls in governance.py migrated
- [ ] All existing tests pass

## Phase 5: Tool Migration - Other Files (Week 2, Days 3-4)

### Phase 5.1: Migrate tabulator.py

**Goal**: Migrate ~8 call sites in tabulator.py.

**Files**:

- `src/quilt_mcp/tools/tabulator.py`

**Call Sites**:

- Lines 147, 227, 272, 313, 351, 369 (from analysis)

**Tasks**:

1. Update each function to use new QuiltService methods
2. Remove `get_tabulator_admin()` calls
3. Test after each migration

**Acceptance**:

- [ ] All 8 call sites migrated
- [ ] All existing tests pass

### Phase 5.2: Migrate admin.py Resources

**Goal**: Migrate ~5 call sites in admin resource implementations.

**Files**:

- `src/quilt_mcp/resources/admin.py`

**Call Sites**:

- Lines 38 (get_users_admin)
- Line 110 (get_roles_admin)

**Tasks**:

1. Update AdminUsersResource to use new methods
2. Update AdminRolesResource to use new methods
3. Test resource implementations

**Acceptance**:

- [ ] All resource call sites migrated
- [ ] All existing tests pass

### Phase 5.3: Migrate catalog.py Config Operations

**Goal**: Migrate ~4 call sites using `get_config()`.

**Files**:

- `src/quilt_mcp/tools/catalog.py`

**Tasks**:

1. Add config accessor methods to QuiltService:
   - `get_navigator_url()`
   - `get_config_value(key)`
2. Update catalog.py to use new methods
3. Test migrations

**Acceptance**:

- [ ] Config accessor methods implemented
- [ ] All catalog.py call sites migrated
- [ ] All existing tests pass

### Phase 5.4: Migrate package_creation.py

**Goal**: Add `delete_package()` method and migrate 1 call site.

**Files**:

- `src/quilt_mcp/services/quilt_service.py`
- `src/quilt_mcp/tools/package_creation.py`

**Tasks**:

1. Add `delete_package(name, registry)` method to QuiltService
2. Update package_creation.py to use new method
3. Remove `get_quilt3_module()` call

**Acceptance**:

- [ ] `delete_package()` method implemented
- [ ] Call site migrated
- [ ] All existing tests pass

### Phase 5.5: Fix Return Types to Match Spec

**Goal**: Update existing methods to return typed structures per spec.

**Files**:

- `src/quilt_mcp/services/quilt_service.py`

**Tasks**:

1. Update `browse_package()` return type: `Any` → `dict[str, Any]`
2. Update `create_bucket()` return type: `Any` → `dict[str, Any]`
3. Update `get_session()` return type: `Any` → `requests.Session | None`
4. Update `create_botocore_session()` return type: `Any` → `boto3.Session`
5. Verify implementations match declared types
6. Update tests if needed to verify typed returns

**Rationale**: The spec defines these methods with specific return types, but current
implementation uses `Any`. This violates success criteria: "All public methods return
typed structures (no `Any` return types)". Methods returning `Any` that will be deleted
in Phase 6 are excluded.

**Acceptance**:

- [ ] `browse_package()` returns `dict[str, Any]`
- [ ] `create_bucket()` returns `dict[str, Any]`
- [ ] `get_session()` returns `requests.Session | None`
- [ ] `create_botocore_session()` returns `boto3.Session`
- [ ] All existing tests pass
- [ ] No `Any` return types except in methods marked for deletion

## Phase 6: Delete Old Methods & Tests (Week 2, Day 5)

### Phase 6.1: Delete Old Getter Methods

**Goal**: Remove anti-pattern getter methods now that all call sites are migrated.

**Tasks**:

1. Delete old getter methods from `QuiltService`:
   - `get_users_admin()` - DELETE
   - `get_roles_admin()` - DELETE
   - `get_sso_config_admin()` - DELETE
   - `get_tabulator_admin()` - DELETE
   - `get_quilt3_module()` - DELETE if unused
   - `get_config()` - EVALUATE: Delete if all call sites migrated
2. Delete associated tests for removed methods
3. Delete private helper methods if no longer needed:
   - `_get_users_admin_module()` - KEEP (used by new operational methods)
   - `_get_roles_admin_module()` - KEEP (used by new operational methods)
   - `_get_sso_admin_module()` - KEEP (used by new operational methods)
   - `_get_tabulator_admin_module()` - KEEP (used by new operational methods)
4. Verify no remaining references to deleted methods

**Verification**:

```bash
# Ensure no references remain
grep -r "get_users_admin\|get_roles_admin\|get_sso_config_admin\|get_tabulator_admin" src/
grep -r "get_users_admin\|get_roles_admin\|get_sso_config_admin\|get_tabulator_admin" tests/
```

**Acceptance**:

- [ ] All old getter methods deleted from source
- [ ] All tests for old getter methods deleted
- [ ] Private helper methods retained (used by new operational methods)
- [ ] No references to deleted methods in codebase
- [ ] All tests still pass

### Phase 6.2: Delete Unused Methods

**Goal**: Delete methods that were never used.

**Tasks**:

1. Delete `get_search_api()` - NEVER USED, DELETE
2. Evaluate `is_authenticated()`:
   - KEEP if used by tools (check call sites)
   - DELETE if redundant with `get_logged_in_url()`

**Acceptance**:

- [ ] Unused methods deleted
- [ ] All tests still pass

### Phase 6.3: Update Documentation

**Goal**: Update all documentation to reflect new API.

**Files**:

- `README.md`
- `docs/` (if exists)
- `CLAUDE.md` - Add learnings

**Tasks**:

1. Update API documentation with new methods
2. Document migration patterns used (for future reference)
3. Update examples to use new methods
4. Add learnings to CLAUDE.md

**Acceptance**:

- [ ] All documentation updated
- [ ] Migration patterns documented
- [ ] Examples use new API

## Phase 7: Validation & Testing (Week 3)

### Phase 7.1: Integration Testing

**Goal**: Verify all tools work correctly with refactored service.

**Tasks**:

1. Run full test suite: `make test`
2. Run integration tests: `make test-integration`
3. Verify 100% coverage: `make coverage`
4. Verify no references to deleted methods remain

**Acceptance**:

- [ ] All tests pass
- [ ] 100% coverage maintained
- [ ] No references to deleted methods in codebase

### Phase 7.2: Performance Validation

**Goal**: Ensure no performance degradation.

**Tasks**:

1. Profile key operations before/after
2. Compare execution times
3. Identify any bottlenecks introduced

**Acceptance**:

- [ ] No significant performance degradation (< 5%)
- [ ] All operations complete in reasonable time

### Phase 7.3: Code Review & Final Cleanup

**Goal**: Final quality check and cleanup.

**Tasks**:

1. Run all linters: `make lint`
2. Check IDE diagnostics
3. Code review all changes
4. Final refactoring pass

**Acceptance**:

- [ ] All linters pass
- [ ] No IDE diagnostics
- [ ] Code review approved
- [ ] Final refactoring complete

## Risk Mitigation

### High-Risk Areas

1. **Admin Operations** (35+ call sites)
   - **Mitigation**: Migrate one function at a time, test after each
   - **Rollback**: Keep old methods during transition

2. **Test Coverage Drop**
   - **Mitigation**: Add tests BEFORE refactoring (prefactoring)
   - **Rollback**: Each phase independently committable

3. **Behavioral Changes**
   - **Mitigation**: Comprehensive behavioral tests before refactoring
   - **Rollback**: Git commits at each phase boundary

### Rollback Strategy

Each phase is independently committable. If issues arise:

1. Identify problematic phase
2. Revert commits for that phase
3. Fix issues in separate branch
4. Re-apply phase when ready

## Success Criteria Summary

- ✅ All public methods return typed structures (no `Any`)
- ✅ No raw quilt3 modules exposed in public API
- ✅ All 35+ call sites migrated to new methods
- ✅ Old getter methods deleted (not deprecated)
- ✅ Tests for old methods deleted
- ✅ 100% test coverage maintained throughout
- ✅ All existing tests pass without modification
- ✅ No performance degradation
- ✅ Backend swapping is architecturally possible
- ✅ Documentation complete and accurate

## Orchestration Notes

### For Workflow Orchestrator Agent

**Context Required**:

- Current branch and git status
- Test execution capabilities
- IDE diagnostics access

**Execution Pattern**:

1. Check git status before starting
2. Execute phases sequentially
3. Commit after each sub-phase
4. Run tests after each commit
5. Check IDE diagnostics after each change
6. Ask for guidance if blocked

**Communication Pattern**:

- Report progress after each phase
- Ask for clarification if requirements unclear
- Suggest optimizations if found
- Report any issues immediately

**Tools to Use**:

- TodoWrite for tracking progress
- Bash for git operations and test running
- Read/Write/Edit for code changes
- IDE diagnostics for quality checks

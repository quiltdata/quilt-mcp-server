# QuiltService → QuiltOps Migration Tasks (Part 4)

**Tasks 12-16: Service Migrations (Part 2) & Final Cleanup**

> **Navigation:**
> - [← Back to tasks-2.md](tasks-2.md) (Tasks 8-11)
> - [← Back to tasks.md](tasks.md) (Overview)

---

## Task 12: Migrate tabulator_service.py Service

Migrate tabulator service to use QuiltOps admin methods.

### 12.1 Update tabulator_service.py imports

- [ ] Replace QuiltService import with QuiltOps in tabulator_service.py
- [ ] Remove `is_admin_available()` checks from tabulator_service.py (use try/catch instead)
- [ ] Update tabulator_service.py type hints to use domain objects

**File:** `src/quilt_mcp/services/tabulator_service.py`

**Migration:** See Appendix A5 in design.md for is_admin_available() pattern

### 12.2 Migrate table management methods

- [ ] Migrate `list_tables()` at line 141:
  - Replace `get_tabulator_admin()` with `list_tabulator_tables()`
- [ ] Migrate `create_table()` at line 210:
  - Replace `get_tabulator_admin()` with `create_tabulator_table()`
- [ ] Migrate `delete_table()` at line 253:
  - Replace `get_tabulator_admin()` with `delete_tabulator_table()`
- [ ] Migrate `rename_table()` at line 292:
  - Use appropriate QuiltOps methods

### 12.3 Migrate query status methods

- [ ] Migrate `get_open_query_status()` at line 329:
  - Replace `get_tabulator_admin()` with QuiltOps method
- [ ] Migrate `set_open_query()` at line 348:
  - Replace `get_tabulator_admin()` with QuiltOps method

### 12.4 Update tabulator_service.py error handling

- [ ] Replace admin availability checks with try/catch in tabulator_service.py
- [ ] Use QuiltOps exceptions for error handling in tabulator_service.py
- [ ] Update tabulator_service.py error messages

### 12.5 Verification Checkpoint: tabulator_service.py Migration

- [ ] Task 12: Run linting: `ruff check --fix src/quilt_mcp/services/tabulator_service.py`
- [ ] Task 12: Run tests: `uv run pytest tests/unit/services/test_tabulator_service.py -v`
- [ ] Task 12: Verify all tests pass
- [ ] Task 12: Commit changes: `git add . && git commit -m "feat: migrate tabulator_service.py to QuiltOps"`

---

## Task 13: Migrate governance_service.py Service

Migrate governance service to use QuiltOps admin methods.

### 13.1 Update governance_service.py imports

- [ ] Replace QuiltService import with QuiltOps in governance_service.py
- [ ] Remove module-level admin checks from governance_service.py (lines 25, 31-34)
- [ ] Remove `get_admin_exceptions()` usage from governance_service.py (line 38)
- [ ] Update governance_service.py type hints to use domain objects

**File:** `src/quilt_mcp/services/governance_service.py`

### 13.2 Migrate user management methods

- [ ] Migrate `admin_users_list()` at line 115:
  - Replace `get_users_admin()` with `list_catalog_users()`
- [ ] Migrate `admin_user_get()` at line 191:
  - Replace `get_users_admin()` with `get_user()`
- [ ] Migrate `admin_user_create()` at line 317:
  - Replace `get_users_admin()` with `create_user()`
- [ ] Migrate `admin_user_delete()` at line 379:
  - Replace `get_users_admin()` with `delete_user()`
- [ ] Migrate remaining user methods at lines 443, 505, 567, 620, 700, 768, 845:
  - Replace `get_users_admin()` with appropriate QuiltOps methods

### 13.3 Migrate role management methods

- [ ] Migrate `admin_roles_list()` at line 893:
  - Replace `get_roles_admin()` with `list_roles()`
- [ ] Add role policy methods if needed

### 13.4 Migrate SSO configuration methods

- [ ] Migrate `admin_sso_config_get()` at line 950:
  - Replace `get_sso_config_admin()` with `get_sso_config()`
- [ ] Migrate `admin_sso_config_set()` at line 1018:
  - Replace `get_sso_config_admin()` with `set_sso_config()`
- [ ] Migrate `admin_sso_config_remove()` at line 1066:
  - Replace `get_sso_config_admin()` with `delete_sso_config()`

### 13.5 Migrate tabulator admin methods

- [ ] Migrate `admin_tabulator_open_query_get()` at line 1102:
  - Replace `get_tabulator_admin()` with QuiltOps method
- [ ] Migrate `admin_tabulator_open_query_set()` at line 1152:
  - Replace `get_tabulator_admin()` with QuiltOps method

### 13.6 Update governance_service.py error handling

- [ ] Replace admin exceptions with QuiltOps exceptions in governance_service.py
- [ ] Remove admin availability checks from governance_service.py (use try/catch)
- [ ] Update governance_service.py error messages for consistency

### 13.7 Verification Checkpoint: governance_service.py Migration

- [ ] Task 13: Run linting: `ruff check --fix src/quilt_mcp/services/governance_service.py`
- [ ] Task 13: Run tests: `uv run pytest tests/unit/services/test_governance_service.py -v`
- [ ] Task 13: Verify all tests pass
- [ ] Task 13: Commit changes: `git add . && git commit -m "feat: migrate governance_service.py to QuiltOps"`

---

## Task 14: Migrate stack_buckets.py Tool

Migrate stack buckets tool to use QuiltOps.

### 14.1 Update stack_buckets.py

- [ ] Review usage of `create_bucket()` in stack_buckets.py (if any)
- [ ] Replace `create_bucket()` with `get_boto3_client('s3')` direct usage in stack_buckets.py
- [ ] Update authentication checks in stack_buckets.py to use QuiltOpsFactory
- [ ] Update stack_buckets.py error handling

**File:** `src/quilt_mcp/tools/stack_buckets.py`

**Note:** `create_bucket()` is not a Quilt domain operation (design.md line 686)

### 14.2 Verification Checkpoint: stack_buckets.py Migration

- [ ] Task 14: Run linting: `ruff check --fix src/quilt_mcp/tools/stack_buckets.py`
- [ ] Task 14: Run tests: `uv run pytest tests/unit/tools/test_stack_buckets.py -v`
- [ ] Task 14: Verify all tests pass
- [ ] Task 14: Commit changes: `git add . && git commit -m "feat: migrate stack_buckets.py to QuiltOps"`

---

## Task 15: Update All Tests to Use QuiltOps

Migrate all remaining tests to use QuiltOps abstraction.

### 15.1 Audit test files

- [ ] Find all tests using QuiltService: `grep -r "QuiltService" tests/ --include="*.py" | grep -v "__pycache__"`
- [ ] Find all tests using quilt_service: `grep -r "quilt_service\." tests/ --include="*.py" | grep -v "__pycache__"`
- [ ] Create list of test files to update

### 15.2 Update unit tests

- [ ] Update unit test fixtures to create QuiltOps instances via factory
- [ ] Update unit test mocks to use QuiltOps interface
- [ ] Update unit test assertions to work with domain objects
- [ ] Remove direct QuiltService imports from unit tests

### 15.3 Update integration tests

- [ ] Update integration test setup to use QuiltOpsFactory
- [ ] Update integration test assertions for domain objects
- [ ] Test complete workflows with QuiltOps in integration tests
- [ ] Verify error handling works correctly in integration tests

### 15.4 Verification Checkpoint: Test Migration

- [ ] Task 15: Run linting: `ruff check tests/`
- [ ] Task 15: Run all unit tests: `uv run pytest tests/unit/ -v`
- [ ] Task 15: Run all integration tests: `uv run pytest tests/integration/ -v`
- [ ] Task 15: Verify no QuiltService references remain: `grep -r "QuiltService" tests/ --include="*.py"`
- [ ] Task 15: Commit changes: `git add . && git commit -m "feat: migrate all tests to use QuiltOps"`

---

## Task 16: Remove QuiltService and Final Cleanup

Remove the legacy QuiltService class and perform final cleanup.

### 16.1 Verify no QuiltService references remain

- [ ] Check source code: `grep -r "QuiltService" src/ --include="*.py" | grep -v "__pycache__"`
- [ ] Check for quilt_service usage: `grep -r "quilt_service\." src/ --include="*.py" | grep -v "__pycache__"`
- [ ] Check for admin module accesses: `grep -r "get_.*_admin\(\)" src/ --include="*.py" | grep -v "__pycache__"`
- [ ] Check imports: `grep -r "from.*quilt_service import" src/ --include="*.py" | grep -v "__pycache__"`
- [ ] Document any remaining references that need migration

### 16.2 Delete QuiltService

- [ ] Delete QuiltService file: `src/quilt_mcp/services/quilt_service.py`
- [ ] Update services `__init__.py` to remove QuiltService export: `src/quilt_mcp/services/__init__.py`
- [ ] Remove QuiltService from any service registration/initialization code
- [ ] Remove obsolete QuiltService test files

### 16.3 Update documentation

- [ ] Update architecture documentation to reflect QuiltOps
- [ ] Update API documentation to use QuiltOps
- [ ] Update developer guides and examples
- [ ] Update README if necessary

### 16.4 Final verification

- [ ] Task 16: Run full linting: `ruff check --fix src/ tests/`
- [ ] Task 16: Run complete test suite: `uv run pytest -v`
- [ ] Task 16: Run integration tests: `uv run pytest tests/integration/ -v`
- [ ] Task 16: Verify test coverage: `uv run pytest --cov=src/quilt_mcp --cov-report=html`
- [ ] Task 16: Manual testing of key workflows

### 16.5 Final Checkpoint: Migration Complete

- [ ] Task 16: Commit final changes: `git add . && git commit -m "feat: remove QuiltService, migration complete"`
- [ ] Task 16: Create migration summary: Document what was changed, any issues encountered, lessons learned
- [ ] Task 16: Tag release: `git tag -a v2.0.0-quilt-ops -m "Complete QuiltService to QuiltOps migration"`

---

## Acceptance Criteria

### Migration Complete When

- [ ] All QuiltService methods have QuiltOps equivalents implemented
- [ ] All domain objects created and validated (Auth_Status, Catalog_Config, User_Info, etc.)
- [ ] All callers migrated to use QuiltOps instead of QuiltService:
  - [ ] `src/quilt_mcp/services/auth_metadata.py` (8 locations)
  - [ ] `src/quilt_mcp/services/athena_service.py` (4 locations)
  - [ ] `src/quilt_mcp/search/backends/elasticsearch.py` (4 locations)
  - [ ] `src/quilt_mcp/tools/packages.py` (multiple locations)
  - [ ] `src/quilt_mcp/services/tabulator_service.py` (6 locations)
  - [ ] `src/quilt_mcp/services/governance_service.py` (20+ locations)
  - [ ] `src/quilt_mcp/tools/stack_buckets.py` (if applicable)
- [ ] All tests pass with QuiltOps
- [ ] No references to QuiltService remain in codebase
- [ ] `src/quilt_mcp/services/quilt_service.py` deleted
- [ ] Documentation updated to reflect new architecture
- [ ] Test coverage maintained or improved
- [ ] All verification commands pass (see below)

### Verification Commands

```bash
# Verify no QuiltService references remain
grep -r "QuiltService" src/ --include="*.py" | grep -v "__pycache__"
# Expected: No results

# Verify no quilt_service references remain
grep -r "quilt_service\." src/ --include="*.py" | grep -v "__pycache__"
# Expected: No results

# Verify no admin module accesses remain
grep -r "get_.*_admin\(\)" src/ --include="*.py" | grep -v "__pycache__"
# Expected: No results

# Verify no QuiltService imports remain
grep -r "from.*quilt_service import" src/ --include="*.py" | grep -v "__pycache__"
# Expected: No results

# Verify QuiltService file deleted
test ! -f src/quilt_mcp/services/quilt_service.py
# Expected: Exit code 0 (file does not exist)

# Run full test suite
uv run pytest -v
# Expected: All tests pass

# Run with coverage
uv run pytest --cov=src/quilt_mcp --cov-report=term-missing
# Expected: Coverage maintained or improved
```

---

## Notes

- Each task follows TDD principles: write tests first, then implement
- Reference the [Migration Code Appendix](./design.md#appendix-migration-code-examples) in design.md for specific patterns
- Use domain objects consistently throughout the migration
- Replace exception handling with QuiltOps exception hierarchy
- Remove admin availability checks in favor of try/catch patterns
- Commit frequently at verification checkpoints
- Run tests after each major change to catch regressions early

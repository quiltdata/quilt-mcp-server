# 11 - Module Cleanup Tasklist

> **Status Note (2026-02-17):** This workstream is actively in progress on `pr-review-fix`.
> Recent completion: package CRUD/browse/diff/create/update/delete logic moved out of `tools/packages.py` into `tools/package_crud.py` (now 758 LOC), and response base/resource models were extracted from `tools/responses.py` (now 987 LOC).
> Remaining debt: several modules are still >1000 lines (`ops/quilt_ops.py`, `services/governance_service.py`, `backends/platform_admin_ops.py`, `backends/platform_backend.py`, `services/workflow_service.py`).

**Date:** 2026-02-16
**Reviewer:** Codex
**Context:** Addresses blocker #3 from 00-SUMMARY.md (maintainability structural debt)

## Philosophy

The "≤500 lines" criterion is a **code smell detector**, not a target. Randomly splitting cohesive modules is counterproductive. This tasklist addresses the **actual maintainability problems**:

- Functions doing too much (poor factoring)
- Mixed responsibilities (poor separation of concerns)
- Duplicated logic (DRY violations)
- Architecture violations (bypassing Template Method pattern)

**Result:** Module sizes will naturally decrease as code quality improves.

---

## Critical Issues from Analysis

- **448-line function** with 20 nested blocks in `tools/packages.py`
- **Platform backend duplicates orchestration** instead of using base class Template Method
- **15 circular import cycles** across core modules
- **Mixed concerns** in tools/packages.py (CRUD + S3 ingestion + docs)
- **Scattered GraphQL operations** with no abstraction

---

## Task Breakdown

### Phase 1: Fix Architecture Violations (Priority: CRITICAL)

#### 1.1 Platform Backend Orchestration Duplication

**Problem:** `platform_backend.py` reimplements `update_package_revision()` (154 lines) instead of using the base class Template Method from `quilt_ops.py`.

- [x] Remove `platform_backend.update_package_revision()` override
- [x] Verify base class `quilt_ops.update_package_revision()` is called
- [x] Ensure all required primitives (`_backend_push_package`, etc.) are implemented
- [ ] Run tests: `uv run pytest tests/unit/backends/test_platform_backend.py -k update_package`

**Impact:** -154 lines from platform_backend.py by using correct architecture

**Files:** `backends/platform_backend.py`, `ops/quilt_ops.py`

#### 1.2 Break Critical Circular Import Cycles

**Problem:** 15 circular import cycles found.

**Cycle 1: Utils/Context** (4 files)

- [x] Extract shared types from `utils/common.py` → `types/common.py`
- [x] Move context-specific utilities to `context/utils.py`
- [x] Update imports in `context/{handler,factory}.py`, `services/workflow_service.py`

**Cycle 2: Auth Services** (2 files)

- [x] Create `services/protocols/auth.py` with `AuthServiceProtocol`
- [x] Make `iam_auth_service.py` depend on protocol, not concrete implementation

**Cycle 3: Platform Backend/Admin** (2 files)

- [x] Extract shared admin types to `backends/types/admin.py`
- [x] Make `platform_admin_ops.py` import types only, not full backend

**Validation:**

- [x] Run: `uv run python scripts/check_cycles.py` → expect 0 cycles
- [x] Run: `uv run mypy src/quilt_mcp` → passes

---

### Phase 2: Extract Giant Functions (Priority: HIGH)

#### 2.1 Refactor `package_create_from_s3` (448 lines → ~150 lines)

**Problem:** Single function with 20 nested blocks doing discovery, validation, organization, package creation, and documentation.

**Extract helper modules:**

- [x] Create `tools/s3_discovery.py`:
  - `discover_s3_objects()` - S3 listing logic (~80 lines)
  - `should_include_object()` - Filtering logic (~30 lines)
  - `organize_file_structure()` - Structure logic (~40 lines)

- [x] Create `tools/package_metadata.py`:
  - `generate_readme_content()` - README generation (~135 lines)
  - `generate_package_metadata()` - Metadata gen (~50 lines)

- [ ] Refactor `package_create_from_s3()` to orchestrate:

  ```python
  def package_create_from_s3(...):
      # 1. Discover objects (call s3_discovery)
      # 2. Organize structure (call s3_discovery)
      # 3. Create package (call package_create)
      # 4. Generate docs (call package_metadata)
  ```

  **Target:** ~100 lines of orchestration

**Validation:**

- [ ] Run: `uv run pytest tests/unit/tools/test_packages.py -k s3`
- [ ] Verify no functionality changes

**Files:** `tools/packages.py` → extract to `tools/{s3_discovery,package_metadata}.py`

#### 2.2 Refactor Large Package Operation Functions

**Target functions in `tools/packages.py`:**

- `package_create` (220 lines) → extract validation helpers
- `package_browse` (219 lines) → extract tree-building logic
- `package_update` (191 lines) → extract validation helpers

**Extract shared validation:**

- [x] Create `tools/validation.py`:
  - `validate_package_name()`
  - `validate_registry()`
  - `validate_metadata()`
  - `build_error_response()` - Consolidate 16 error handling patterns

**Refactor functions:**

- [x] `package_create`: Use validation module → target ~120 lines
- [x] `package_browse`: Extract `_build_tree_structure()` → target ~100 lines
- [x] `package_update`: Use validation module → target ~100 lines

**Validation:**

- [ ] Run: `uv run pytest tests/unit/tools/test_packages.py`

---

### Phase 3: Separate Mixed Concerns (Priority: HIGH)

#### 3.1 Extract S3 Package Ingestion Workflow

**Problem:** `tools/packages.py` mixes CRUD operations with S3 discovery workflows.

- [x] Create `tools/s3_package_ingestion.py`:
  - Move `package_create_from_s3` (after Phase 2.1 refactoring)
  - Move S3-specific helpers
  - Import from `s3_discovery.py` and `package_metadata.py`

- [x] Keep in `tools/packages.py`:
  - Core CRUD: `package_create`, `package_update`, `package_delete`, `package_browse`
  - Package info: `package_diff`, `package_info`, `package_list`

**Result:**

- `tools/packages.py`: ~600-800 lines (pure CRUD)
- `tools/s3_package_ingestion.py`: ~200 lines (S3 workflow)

**Validation:**

- [x] Run: `uv run pytest tests/unit/tools/`
- [x] Verify imports work from MCP tool registration

#### 3.2 Extract GraphQL Client Abstraction

**Problem:** `platform_backend.py` has 14 scattered GraphQL query/mutation definitions with duplicated error handling.

- [x] Create `backends/platform_graphql_client.py`:
  - `GraphQLClient` class with:
    - `query(operation, variables)` - Generic query executor
    - `mutate(operation, variables)` - Generic mutation executor
    - Error handling, response parsing, type checking
  - Query/mutation definitions as constants or methods

- [x] Refactor `platform_backend.py`:
  - Initialize `self._graphql = GraphQLClient(...)`
  - Replace inline GraphQL with client calls
  - Remove duplicated error handling

**Result:**

- `backends/platform_backend.py`: ~900-1000 lines (business logic only)
- `backends/platform_graphql_client.py`: ~300-400 lines (GraphQL abstraction)

**Validation:**

- [ ] Run: `uv run pytest tests/unit/backends/test_platform_backend.py`
- [ ] Run: `uv run pytest tests/func/backends/ -k platform`

---

### Phase 4: Consolidate Duplication (Priority: MEDIUM)

#### 4.1 Extract Shared Utilities

**Problem:** Same logic repeated across backends.

- [x] Create `backends/utils.py`:
  - `extract_bucket_from_registry()` - Used in quilt_ops, platform_backend, etc.
  - `normalize_registry()` - Repeated in multiple backends
  - `build_s3_key()` - Common S3 key construction

- [x] Update backends to use shared utilities

#### 4.2 Reduce Validation Redundancy

**Problem:** `quilt_ops.py` validates inputs, then backends validate again in primitives.

- [ ] Document validation contract in `ops/quilt_ops.py` docstrings
- [ ] Remove redundant validation from backend primitives (trust base class)
- [ ] Keep validation only where backends have platform-specific rules

**Files:** `ops/quilt_ops.py`, all backend implementations

---

### Phase 5: Simplify Complex Logic (Priority: MEDIUM)

#### 5.1 Simplify `delete_package` Complexity

**Problem:** `platform_backend.delete_package()` has 22 nested blocks with complex fallback logic (GraphQL → S3 direct).

- [ ] Extract fallback logic to separate method:
  - `_try_graphql_delete()` - GraphQL deletion
  - `_try_s3_fallback_delete()` - S3 direct deletion
  - `delete_package()` - Orchestrates with clear error handling

**Target:** Reduce nesting from 22 blocks to ~8 blocks

**Validation:**

- [ ] Run: `uv run pytest tests/unit/backends/test_platform_backend.py -k delete`

#### 5.2 Reduce Documentation Verbosity in `quilt_ops.py`

**Problem:** 10+ line docstrings for every method inflate file size without adding value.

- [ ] Consolidate docstrings:
  - Keep high-level class docstring explaining Template Method pattern
  - Reduce method docstrings to 2-4 lines (purpose + params)
  - Move detailed implementation notes to `ARCHITECTURE.md`

**Target:** -200 to -300 lines from documentation reduction

**Files:** `ops/quilt_ops.py`

---

### Phase 6: Validation (Priority: CRITICAL)

- [x] **Import cycles:** `uv run python scripts/check_cycles.py` → 0 cycles
- [ ] **Module sizes:** `find src/quilt_mcp -name "*.py" -exec wc -l {} \; | sort -rn | head -20`
  - No modules >1500 lines (down from 2034)
  - Top modules all <1000 lines
- [x] **Tests pass:** `make test-all`
- [x] **Type checking:** `uv run mypy src/quilt_mcp`
- [x] **Linting:** `make lint`
- [ ] **Function sizes:** Verify no functions >200 lines (down from 448)

---

## Success Criteria

### Architecture

- ✅ Zero circular import cycles (down from 15)
- ✅ Platform backend uses base class Template Methods (no orchestration duplication)
- ✅ GraphQL operations abstracted into client (not scattered)

### Code Quality

- ✅ No functions >200 lines (down from 448-line monster)
- ✅ Validation consolidated (not duplicated across backends)
- ✅ S3 ingestion separated from CRUD operations
- ✅ No duplication of utilities across backends

### Module Sizes (Natural Result)

- ✅ All modules <1500 lines (down from 2034)
- ✅ Largest modules <1000 lines (down from 5 modules >1000)
- ⚠️ Some modules may still be 600-800 lines (acceptable if cohesive)

### Tests

- ✅ All tests passing
- ✅ Mypy clean
- ✅ No functionality changes

---

## Estimated Effort

- **Phase 1** (Architecture fixes): 6-8 hours
- **Phase 2** (Extract giant functions): 8-10 hours
- **Phase 3** (Separate concerns): 6-8 hours
- **Phase 4** (Consolidate duplication): 4-6 hours
- **Phase 5** (Simplify complex logic): 4-6 hours
- **Phase 6** (Validation): 2-3 hours

**Total:** 30-41 hours

---

## Notes

- **Preserve all tests** during refactoring - run tests after each phase
- **Extract, don't rewrite** - move code, don't reimplementexcessive
- **Use `git mv`** for file moves to preserve history
- **Update `ARCHITECTURE.md`** to document new module structure
- **Run `make lint`** after each phase to catch import issues early
- **Focus on quality, not line counts** - a 600-line cohesive module is better than splitting it arbitrarily

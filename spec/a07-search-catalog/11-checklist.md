# Implementation Checklist - v0.9.0 Search Catalog Simplification

**Issue**: [Link to GitHub issue - TBD]
**Branch**: `search-catalog-fixes`
**Version**: 0.9.0 (Breaking Change)
**Methodology**: Incremental TDD - Small Atomic Commits

## Overview

This checklist guides the **incremental migration** to the simplified search_catalog
API (v0.9.0). Each episode is a complete, testable, committable unit that keeps
tests passing.

**Key Principles**:

- ✅ Tests pass at every commit
- ✅ Each episode is atomic and independently valuable
- ✅ Only delete/archive tests when they become obsolete
- ✅ Incremental migration of functionality

---

## Episode 1: Add Backend Caching (No Breaking Changes)

**Goal**: Implement the new backend selection and caching without breaking existing API.

### What Changes

- Add `get_backend()`, `reset_backend()`, `_select_backend()` functions
- Backend cached for session, auto-resets on failure
- GraphQL preferred, Elasticsearch fallback
- **No API changes yet** - all existing parameters still work

### Test Strategy

1. Add new tests for backend selection/caching (`tests/test_backend_selection.py`)
2. Keep all existing search tests passing
3. Backend selection is internal - doesn't affect external API

### Tasks

- [ ] Create `tests/test_backend_selection.py` with tests for:
  - `test_backend_cached_across_calls()` - Verify caching works
  - `test_backend_reset_clears_cache()` - Verify reset works
  - `test_graphql_preferred_when_available()` - Selection logic
  - `test_elasticsearch_fallback()` - Fallback logic
  - `test_backend_verify_works_called()` - Verification happens

- [ ] Implement backend selection in `src/quilt_mcp/search/backend_selection.py`:

  ```python
  _BACKEND: Optional[SearchBackend] = None

  def get_backend() -> SearchBackend:
      """Get cached backend."""
      global _BACKEND
      if _BACKEND is None:
          _BACKEND = _select_backend()
      return _BACKEND

  def reset_backend():
      """Reset backend cache."""
      global _BACKEND
      _BACKEND = None

  def _select_backend() -> SearchBackend:
      """Select best available backend."""
      # Try GraphQL first
      # Fall back to Elasticsearch
      # Raise if none available
  ```

- [ ] Update `UnifiedSearchEngine` to use new backend selection
- [ ] Run all existing tests - they must still pass
- [ ] Run new backend selection tests - they must pass
- [ ] Commit: `feat: add backend caching with automatic failover`

### Validation

- [ ] All existing tests pass (no regressions)
- [ ] New backend tests pass
- [ ] `make test` succeeds
- [ ] `make lint` passes

---

## Episode 2: Simplify Scope Parameter (Small Breaking Change)

**Goal**: Consolidate scope values to `global`, `packages`, `bucket` only.

### What Changes

- Remove old scope values: `catalog`, `package`
- Map them to new values in backward-compatible way initially
- Add deprecation warnings for old values
- Update documentation

### Test Strategy

1. Update scope-related tests to use new values
2. Add deprecation warning tests
3. Archive tests that specifically tested removed scope values

### Tasks

- [ ] Add `tests/test_scope_migration.py`:
  - `test_global_scope()` - New default behavior
  - `test_packages_scope()` - Replaces "catalog"
  - `test_bucket_scope()` - Still works
  - `test_deprecated_catalog_scope_warns()` - Deprecation warning
  - `test_deprecated_package_scope_warns()` - Deprecation warning

- [ ] Update `unified_search.py`:

  ```python
  def search(self, query, scope="global", ...):
      # Map old values with warnings
      if scope == "catalog":
          warnings.warn("scope='catalog' deprecated, use scope='packages'")
          scope = "packages"
      if scope == "package":
          warnings.warn("scope='package' deprecated, use scope='bucket'")
          scope = "bucket"

      # Validate scope
      if scope not in ["global", "packages", "bucket"]:
          raise ValueError(f"Invalid scope: {scope}")
  ```

- [ ] Update existing tests to use new scope values
- [ ] Archive tests specific to old scope behaviors:
  - Move `tests/test_search_scope_fixes.py` → `spec/a07-search-catalog/archived/`
  - Add README explaining why archived

- [ ] Run all tests - must pass
- [ ] Commit: `feat: simplify scope parameter with deprecation warnings`

### Validation

- [ ] All tests pass
- [ ] Deprecation warnings appear for old scope values
- [ ] New scope values work correctly

---

## Episode 3: Change Default Scope to Global (Breaking Change)

**Goal**: Change default scope from `bucket` to `global`.

### What Changes

- Update `scope` default from `"bucket"` to `"global"`
- Update `search_catalog()` wrapper default
- This changes behavior for users who don't specify scope

### Test Strategy

1. Update `tests/test_search_defaults.py` to expect `global` default
2. Keep all other tests passing

### Tasks

- [ ] Update `tests/test_search_defaults.py`:

  ```python
  def test_default_scope_is_global(self):  # Changed from bucket
      result = search_catalog(query="test")
      assert result["scope"] == "global"
  ```

- [ ] Update function signatures:
  - `unified_search(scope="global")` (was `"bucket"`)
  - `search_catalog(scope="global")` (was `"bucket"`)

- [ ] Update all tool descriptors in `tools/search.py`
- [ ] Run tests - update any that assumed `bucket` default
- [ ] Commit: `feat!: change default scope to 'global' (BREAKING)`

### Validation

- [ ] All tests pass with new default
- [ ] Tool descriptors correctly document new default

---

## Episode 4: Remove `backend` Parameter (Breaking Change)

**Goal**: Remove user-facing backend selection - it's always automatic.

### What Changes

- Remove `backend` parameter from public API
- Backend selection is always automatic now
- Remove related tests that tested manual backend selection

### Test Strategy

1. Remove tests that explicitly passed `backend` parameter
2. Update tests to not specify backend
3. Archive tests that only tested backend selection by users

### Tasks

- [ ] Update function signatures - remove `backend` parameter:

  ```python
  async def unified_search(
      query: str,
      scope: str = "global",
      target: str = "",
      # backend removed - always automatic
      limit: int = 50,
      ...
  ```

- [ ] Update `tests/test_search_defaults.py`:
  - Remove `test_default_backend_is_elasticsearch()` - no longer relevant
  - Backend choice is internal now

- [ ] Update all tests that passed `backend=` explicitly:

  ```bash
  grep -r "backend=" tests/
  # Update each to remove backend parameter
  ```

- [ ] Archive tests focused on manual backend selection
- [ ] Update tool descriptors - remove `backend` parameter docs
- [ ] Run all tests - must pass
- [ ] Commit: `feat!: remove manual backend selection (BREAKING)`

### Validation

- [ ] All tests pass without backend parameter
- [ ] Tool descriptors don't mention backend parameter

---

## Episode 5: Remove Unused Parameters (Breaking Change)

**Goal**: Remove `entity`, `detail_level`, `include_content_preview` parameters.

### What Changes

- Remove parameters that were never properly implemented
- Clean up function signatures
- Simplify API surface

### Test Strategy

1. Archive tests that used these parameters
2. Update remaining tests to not use them

### Tasks

- [ ] Archive/remove tests using removed parameters:
  - Search for `entity=` in tests → archive/update
  - Search for `detail_level=` in tests → archive/update
  - Search for `include_content_preview=` in tests → archive/update

- [ ] Update function signatures:

  ```python
  async def unified_search(
      query: str,
      scope: str = "global",
      target: str = "",
      limit: int = 50,
      count_only: bool = False,
      include_metadata: bool = True,
      explain_query: bool = False,
  ) -> Dict[str, Any]:
  ```

- [ ] Update tool descriptors in `tools/search.py`
- [ ] Archive e2e tests that heavily used removed parameters:
  - `tests/e2e/test_search_phase2.py` → archive (used entity extensively)
  - `tests/e2e/test_search_phase3_errors.py` → archive (tested error cases for removed params)

- [ ] Run remaining tests - must pass
- [ ] Commit: `feat!: remove unused entity/detail_level parameters (BREAKING)`

### Validation

- [ ] All remaining tests pass
- [ ] API surface is simpler
- [ ] Tool descriptors are up to date

---

## Episode 6: Update Documentation and Examples

**Goal**: Bring all docs and examples into alignment with v0.9.0 API.

### Tasks

- [ ] Update `README.md` examples
- [ ] Update tool descriptors in `tools/search.py`
- [ ] Create migration guide: `docs/migration-v0.9.0.md`
- [ ] Update inline documentation/docstrings
- [ ] Add v0.9.0 to CHANGELOG
- [ ] Run doc linter if available
- [ ] Commit: `docs: update for v0.9.0 simplified search API`

### Validation

- [ ] All examples run without errors
- [ ] Documentation is consistent
- [ ] Migration guide is clear

---

## Episode 7: Final Cleanup and Integration Tests

**Goal**: Ensure everything works together, clean up remaining artifacts.

### Tasks

- [ ] Review all remaining tests in `tests/e2e/`
- [ ] Update `tests/e2e/test_unified_search.py` for v0.9.0 API
- [ ] Remove deprecated scope mapping code (from Episode 2)
- [ ] Final pass through codebase for old parameter names
- [ ] Run full test suite with coverage
- [ ] Update version to 0.9.0 in `pyproject.toml` or setup
- [ ] Commit: `chore: finalize v0.9.0 release preparation`

### Validation

- [ ] Full test suite passes
- [ ] Coverage meets project standards (85%+)
- [ ] All deprecated code removed
- [ ] Version bumped correctly

---

## Episode 8: Create PR and Release

**Goal**: Get v0.9.0 reviewed and released.

### Tasks

- [ ] Push all commits to branch
- [ ] Create concise CHANGELOG for user-facing impact
- [ ] Create PR with concise description
- [ ] Run CI/CD pipeline
- [ ] Fix errors

### PR Description Template

```markdown
# v0.9.0: Simplified Search API (BREAKING CHANGES)

## Summary
Simplifies search_catalog API by removing confusing parameters and providing sensible defaults.

## Breaking Changes
- Default scope is now `global` (was `bucket`)
- Removed `backend` parameter (automatic selection)
- Removed `entity` parameter (scope determines what's searched)
- Removed `detail_level` parameter (not implemented)
- Scope values: `global`, `packages`, `bucket` only

## Testing
- 7 incremental episodes, each with passing tests
- Full coverage of new functionality
- All integration tests passing

## Validation
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Migration guide provided
```

---

## Quality Gates (Applied at Each Episode)

Before committing each episode:

1. **Tests Pass**: `make test` succeeds
2. **Linting**: `make lint` passes
3. **Coverage**: No decrease in coverage percentage
4. **Documentation**: Docstrings updated for changed code
5. **Commit Message**: Follows conventional commits

---

## Rollback Strategy

If an episode causes problems:

1. **Git Revert**: Each episode is one commit - easy to revert
2. **Tests**: Previous tests still pass, so we know exactly what broke
3. **No Big Bang**: Small changes mean small rollbacks

---

## Success Criteria

By the end of all episodes:

- [ ] API simplified to 7 parameters (from 10+)
- [ ] All tests passing
- [ ] Documentation complete and accurate
- [ ] Migration guide provided
- [ ] Version bumped to 0.9.0
- [ ] CHANGELOG and PR created
- [ ] Dev Release created
- [ ] No decrease in test coverage

---

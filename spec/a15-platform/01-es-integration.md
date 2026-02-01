# Elasticsearch Integration Tests - QuiltOps Migration

**Status:** Draft
**Created:** 2026-01-31
**Priority:** High - 60 integration tests currently broken

## Problem Statement

The elasticsearch integration tests (60 tests across 3 files) are broken after the QuiltOps migration. All tests fail with:

```
fixture 'quilt_service' not found
```

The tests were written before the migration and use the old `QuiltService` architecture:

```python
@pytest.fixture
def backend(quilt_service):
    backend = Quilt3ElasticsearchBackend(quilt_service=quilt_service)
    backend._initialize()
    return backend
```

But the current `Quilt3ElasticsearchBackend` constructor signature is:

```python
def __init__(self, backend: Optional["Quilt3_Backend"] = None):
```

## Impact

**Critical functionality not being tested:**

- Bucket discovery via GraphQL (real AWS calls)
- Index pattern building for file/package/global scopes
- Elasticsearch index existence verification
- Search execution with discovered indices
- Package scope search functionality
- Full catalog search integration

These are **real integration tests** with actual AWS/Elasticsearch calls and no mocks. The test files explicitly state: "No mocks. Real AWS. Real Elasticsearch. Real pain."

## Affected Files

1. `tests/integration/test_elasticsearch_index_discovery.py` - 28 tests (31KB)
2. `tests/integration/test_elasticsearch_package_scope.py` - 15 tests (24KB)
3. `tests/integration/test_search_catalog_integration.py` - 17 tests (25KB)

## Tasks

### Phase 1: Fixture Infrastructure (Tests)

**T1.1: Create Quilt3_Backend fixture**

- Add `quilt3_backend` fixture to `tests/conftest.py`
- Should return properly initialized `Quilt3_Backend` instance
- Should handle authentication state (session setup)
- Should be session-scoped for performance
- Should verify auth status is available before returning

**T1.2: Update elasticsearch test fixtures**

- Update `backend` fixture in `test_elasticsearch_index_discovery.py`
- Update `backend` fixture in `test_elasticsearch_package_scope.py`
- Update `backend` fixture in `test_search_catalog_integration.py`
- Change from `quilt_service` parameter to `quilt3_backend` parameter
- Update constructor call to use `backend=` parameter instead of `quilt_service=`

**T1.3: Add backward compatibility check**

- Verify no other integration tests use `quilt_service` fixture
- Search all test files for `quilt_service` references
- Document any other tests that need migration

### Phase 2: Test Updates (Tests)

**T2.1: Verify test execution**

- Run `test_elasticsearch_index_discovery.py` with pytest
- Confirm all 28 tests execute (may skip if env vars missing)
- Document any tests that still fail and why

**T2.2: Verify test behavior**

- Run `test_elasticsearch_package_scope.py` with pytest
- Confirm all 15 tests execute
- Document any behavioral changes from migration

**T2.3: Verify catalog integration**

- Run `test_search_catalog_integration.py` with pytest
- Confirm all 17 tests execute
- Verify end-to-end search flows work

### Phase 3: Validation (Tests)

**T3.1: Run full integration suite**

- Execute `make test-integration` or equivalent
- Verify elasticsearch tests now appear in results
- Document pass/fail/skip counts

**T3.2: Verify test isolation**

- Confirm tests don't interfere with each other
- Check for session-scoped resource cleanup
- Verify no auth state leakage between tests

**T3.3: Update documentation**

- Add notes about `quilt3_backend` fixture to test README
- Document required environment variables for elasticsearch tests
- Update any developer onboarding docs

### Phase 4: CI/CD (Infrastructure)

**T4.1: Review CI configuration**

- Check if elasticsearch tests run in CI
- Verify required secrets/credentials are available
- Document any CI-specific test skip logic

**T4.2: Update test markers**

- Ensure tests have proper `@pytest.mark.search` markers
- Add `@pytest.mark.integration` if missing
- Consider adding `@pytest.mark.aws` for AWS-dependent tests

**T4.3: Performance baseline**

- Measure total runtime for 60 elasticsearch integration tests
- Document which tests are slowest
- Consider splitting into fast/slow test suites

## Success Criteria

- [ ] All 60 elasticsearch integration tests execute without fixture errors
- [ ] Tests pass when environment is properly configured
- [ ] Tests skip gracefully when env vars missing (not error)
- [ ] `quilt3_backend` fixture is reusable by other integration tests
- [ ] No regression in test coverage or behavior
- [ ] Documentation updated with new fixture usage

## Non-Goals

- Rewriting test logic or assertions
- Adding new test cases
- Changing from integration to unit tests
- Mocking AWS/Elasticsearch calls
- Optimizing test performance (beyond what's necessary)

## Open Questions

1. Should `quilt3_backend` fixture be session or function scoped?
   - Session = faster but shared state risk

2. Do we need both authenticated and unauthenticated `quilt3_backend` fixtures?
   - NO: only works if authenticated (error out to login)

3. Should we consolidate conftest.py files?
   - Currently have separate `tests/conftest.py` and `tests/integration/conftest.py`
   - Move unit tests conf out, so root is only what's shared

4. Are there other search backends that need integration test fixtures?
   - Out of scope

## Dependencies

- QuiltOps factory working correctly
- `Quilt3_Backend` fully functional
- Auth status mechanism working
- Test environment has AWS credentials configured

## Timeline Estimate

- Phase 1: 2-3 hours (fixture creation)
- Phase 2: 1-2 hours (test verification)
- Phase 3: 1 hour (validation)
- Phase 4: 1 hour (CI/CD)

**Total: ~5-7 hours**

## References

- QuiltOps migration design: `.kiro/specs/quilt-ops-admin-refactoring/design.md`
- Elasticsearch backend: `src/quilt_mcp/search/backends/elasticsearch.py`
- Current conftest: `tests/conftest.py`, `tests/integration/conftest.py`

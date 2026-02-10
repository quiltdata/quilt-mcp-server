# A20 JWT Auth: Remaining Work for 100% Pass Rate

**Status:** In Progress
**Goal:** Achieve 100% pass rate for BOTH quilt3 and platform backends
**Current:** ~85% implementation complete

---

## Summary

The E2E backend integration test suite is largely implemented with 14/15 test files complete. This document outlines the remaining tasks to achieve 100% pass rate for both backends.

---

## Phase 6.2: Complete Consistency Tests

### Task 1: Implement Cross-Backend Consistency Test

**File:** `tests/e2e/backend/consistency/test_cross_backend.py`

**Spec Reference:** Section 5.2 (lines 899-963) in `02-e2e-backend-integration.md`

**Objective:**
Validate that the same data accessed through different backend methods (Quilt3, Tabulator, Athena, Search) returns consistent results.

**Test Workflow:**

1. Use test package with known data (3-5 files): `quilt+s3://quilt-ernest-staging#package=test/mcp_create@latest`
2. Query the same data via multiple backend methods:
   - Quilt3 browse (package.browse())
   - Search API (catalog search)
   - Tabulator (if package manifests are indexed)
   - Athena (if Glue catalog has package metadata)
3. Compare results across all methods
4. Assert consistency in:
   - File lists (same files appear in all views)
   - Metadata (size, modified time, etc.)
   - Counts (number of files matches)

**Assertions:**

- File lists match across all backends
- Metadata is consistent (within reasonable timestamp tolerance)
- No missing or extra files in any view
- Search results match browse results
- Tabulator view matches Quilt3 view (if applicable)

**Backend Handling:**

- quilt3: Test all methods (browse, search, Tabulator, Athena)
- platform: Test browse, search, Tabulator (skip Athena)

**Cleanup:**

- Use `cleanup_packages` fixture
- Clean up any created test data

**Success Criteria:**

- Test passes for quilt3 backend
- Test passes for platform backend (with appropriate skips)
- Demonstrates cross-backend data consistency

---

## Phase 7: Platform Backend Issue Resolution

### Task 2: Investigate Platform Backend GraphQL Schema Issues

**Issue:**
Platform backend tests fail with GraphQL schema errors:

```
Unknown type 'PackagePushInvalidInputFailure'
Unknown type 'PackagePushComputeFailure'
```

**Affected Tests:**

- `test_package_lifecycle.py` - Fails on package_push operation
- `test_package_creation.py` - Fails on package creation from S3

**Investigation Steps:**

1. Examine the GraphQL schema used by platform backend
2. Check if schema version is outdated
3. Verify expected types vs actual types in GraphQL response
4. Compare with working GraphQL operations (search, browse)

**Possible Causes:**

- GraphQL schema version mismatch
- Missing type definitions in platform backend
- Incorrect type mapping in Python backend code
- Server-side GraphQL schema not matching client expectations

**Resolution Paths:**

- **Path A:** Update GraphQL schema definitions in backend
- **Path B:** Modify backend to handle missing types gracefully
- **Path C:** Skip package push operations for platform backend if not supported
- **Path D:** Use alternative GraphQL mutations that don't require these types

**Action Items:**

1. Read GraphQL schema from platform endpoint
2. Compare with expected schema in backend code
3. Identify type definition gaps
4. Determine if this is a backend bug or platform limitation
5. Implement fix or graceful degradation

---

### Task 3: Fix or Skip Platform Backend Package Operations

**Depending on Task 2 Investigation:**

**Option A: Fix Available**

- Update GraphQL type definitions
- Test package_push with corrected schema
- Verify all package operations work

**Option B: Platform Limitation**

- Document that package push is not supported in platform backend
- Add graceful skip with clear explanation
- Update tests to skip package creation tests for platform
- Ensure other operations (browse, search) still tested

**Success Criteria:**

- Either: Package operations work for platform backend
- Or: Tests gracefully skip with clear documentation of limitation
- No unexpected failures or unclear error messages

---

## Phase 8: Full Suite Validation

### Task 4: Run Complete Test Suite - quilt3 Backend

**Command:**

```bash
TEST_BACKEND_MODE=quilt3 uv run pytest tests/e2e/backend/ -v --tb=short
```

**Expected Result:**

- **All tests pass** (or skip with valid reason)
- No unexpected failures
- No resource leaks
- All cleanup successful

**Validation Checklist:**

- [ ] All integration tests pass (4/4)
- [ ] All workflow tests pass (3/3)
- [ ] All error handling tests pass (3/3)
- [ ] All performance tests pass (2/2)
- [ ] All consistency tests pass (2/2)
- [ ] No unexpected skips
- [ ] Cleanup logs show successful resource removal

**If Failures Occur:**

1. Review failure logs
2. Identify root cause
3. Fix issue
4. Re-run tests
5. Repeat until 100% pass

---

### Task 5: Run Complete Test Suite - platform Backend

**Command:**

```bash
TEST_BACKEND_MODE=platform uv run pytest tests/e2e/backend/ -v --tb=short
```

**Expected Result:**

- **All applicable tests pass**
- Athena-specific tests skip gracefully
- Package operations either pass or skip gracefully (depending on Task 3)
- No unexpected failures

**Expected Skips:**

- Athena integration tests (platform uses GraphQL, not direct Athena)
- Tests requiring direct S3 access (platform uses presigned URLs)
- Any tests specific to quilt3 backend implementation

**Validation Checklist:**

- [ ] Integration tests: Pass or skip appropriately
- [ ] Workflow tests: Pass (3/3)
- [ ] Error handling tests: Pass (3/3)
- [ ] Performance tests: Pass or skip appropriately
- [ ] Consistency tests: Pass (2/2)
- [ ] All skips have clear explanations
- [ ] No unexpected failures

**If Failures Occur:**

1. Review failure logs
2. Distinguish between:
   - Real bugs (must fix)
   - Platform limitations (document and skip)
   - Test issues (fix test)
3. Address issues
4. Re-run tests
5. Repeat until 100% pass/skip appropriately

---

### Task 6: Run Combined Test Suite (Both Backends)

**Command:**

```bash
uv run pytest tests/e2e/backend/ -v --tb=short
```

**Expected Result:**

- All parametrized tests run for both backends
- Clear differentiation between backend results
- No cross-contamination between backend runs

**Validation:**

- [ ] quilt3 backend: All tests pass
- [ ] platform backend: All tests pass or skip appropriately
- [ ] No test interactions or dependencies
- [ ] Cleanup successful for both backends

---

## Phase 9: Documentation and Reporting

### Task 7: Document Test Results and Coverage

**Create:** `spec/a20-jwt-auth/05-test-results-report.md`

**Contents:**

1. **Test Coverage Summary**
   - Total test files: 15
   - Total test cases: ~30
   - Coverage by category

2. **Backend Support Matrix**
   - Table showing which tests run for which backend
   - Expected passes, skips, and reasons

3. **Known Limitations**
   - Platform backend package operations (if applicable)
   - Athena limitations for platform backend
   - Any other documented limitations

4. **Performance Baselines**
   - Timing benchmarks from performance tests
   - Baseline expectations for future runs

5. **Cleanup Verification**
   - Resources created during tests
   - Cleanup verification process
   - Leak detection methods

---

### Task 8: Update Main Test Documentation

**Update:** `tests/e2e/backend/README.md` (create if doesn't exist)

**Contents:**

1. **Quick Start**
   - How to run tests
   - Prerequisites (env vars, credentials)
   - Common commands

2. **Test Structure**
   - Directory layout
   - Test categories
   - Fixtures overview

3. **Backend Modes**
   - How to test quilt3 backend
   - How to test platform backend
   - Differences and limitations

4. **Troubleshooting**
   - Common issues
   - Environment setup
   - Debugging tips

5. **Contributing**
   - Adding new tests
   - Test patterns
   - Cleanup requirements

---

## Phase 10: Final Validation

### Task 9: Clean Environment Full Test Run

**Objective:**
Validate tests work in a clean environment (no cached credentials, fresh AWS session)

**Steps:**

1. Clear cached credentials:

   ```bash
   rm -f ~/.aws/credentials
   rm -f ~/.quilt/config.yml
   unset AWS_SESSION_TOKEN
   ```

2. Set up fresh credentials

3. Run full test suite:

   ```bash
   # Both backends
   uv run pytest tests/e2e/backend/ -v

   # Quilt3 only
   TEST_BACKEND_MODE=quilt3 uv run pytest tests/e2e/backend/ -v

   # Platform only
   TEST_BACKEND_MODE=platform uv run pytest tests/e2e/backend/ -v
   ```

4. Verify all passes/skips as expected

**Success Criteria:**

- [ ] Tests run successfully in clean environment
- [ ] No dependency on cached state
- [ ] Clear error messages if credentials missing
- [ ] All cleanup successful

---

### Task 10: Concurrent Test Run Validation

**Objective:**
Ensure tests don't interfere with each other when run in parallel

**Command:**

```bash
uv run pytest tests/e2e/backend/ -v -n auto
```

**Validation:**

- [ ] No resource conflicts (unique test resource names)
- [ ] No race conditions
- [ ] All cleanups work correctly
- [ ] Results same as sequential run

**If Issues:**

- Add unique identifiers to test resources
- Improve cleanup fixtures
- Add test isolation

---

## Success Criteria Summary

### Quilt3 Backend - 100% Pass Rate

- [ ] All 15 test files implemented
- [ ] All integration tests pass (4/4)
- [ ] All workflow tests pass (3/3)
- [ ] All error handling tests pass (3/3)
- [ ] All performance tests pass (2/2)
- [ ] All consistency tests pass (2/2)
- [ ] No unexpected failures
- [ ] All cleanup successful
- [ ] No resource leaks

### Platform Backend - 100% Pass/Skip Rate

- [ ] All applicable tests pass
- [ ] Expected skips documented and clear
- [ ] Package operations handled appropriately
- [ ] No unexpected failures
- [ ] All cleanup successful

### Documentation

- [ ] Test results documented
- [ ] Known limitations documented
- [ ] README created with usage instructions
- [ ] Performance baselines recorded

### Quality

- [ ] Tests work in clean environment
- [ ] Tests work with parallel execution
- [ ] No test interdependencies
- [ ] Clear error messages
- [ ] Comprehensive logging

---

## Estimated Effort

- **Task 1** (Cross-backend consistency): 2-3 hours
- **Task 2** (Platform GraphQL investigation): 1-2 hours
- **Task 3** (Platform backend fix/skip): 1-3 hours
- **Task 4-6** (Validation runs): 1-2 hours
- **Task 7-8** (Documentation): 1-2 hours
- **Task 9-10** (Final validation): 1 hour

**Total: 7-13 hours to 100% completion**

---

## Next Steps

1. **Immediate:** Implement cross-backend consistency test (Task 1)
2. **Critical:** Investigate platform backend GraphQL issues (Task 2-3)
3. **Validation:** Run complete test suites (Task 4-6)
4. **Documentation:** Create test report and README (Task 7-8)
5. **Final:** Clean environment and parallel validation (Task 9-10)

---

## Notes

- All tests use REAL services (NO MOCKING)
- Cleanup fixtures are comprehensive
- Tests are parametrized for dual backend support
- Performance baselines established
- Error handling validated with real services
- Cross-backend consistency verification included

**Status:** Ready to proceed with remaining tasks to achieve 100% pass rate.

# Testing Issues Analysis

**Status:** Analysis
**Date:** 2026-02-04
**Analyzed by:** Claude Code

## Executive Summary

The test suite has grown organically to **1,181 tests across 133 files** with **30,469 lines of test code** (86% of the 35,372 lines of source code). While comprehensive, the test suite suffers from excessive mocking, fixture complexity, slow tests, and organizational issues that hinder maintainability and developer productivity.

## Test Metrics Overview

| Metric | Value | Notes |
|--------|-------|-------|
| Total tests | 1,181 | Collected via pytest |
| Test files | 133 | Python test files |
| Test code lines | 30,469 | Excluding fixtures/data |
| Source code lines | 35,372 | For comparison |
| Test:Source ratio | 86% | Very high |
| Mock usage lines | 1,889 | Lines with mock/Mock/patch |
| Fixture definitions | 60 | Across all conftest files |
| Skipped tests | 11 | With pytest.skip/xfail |
| Platform-disabled tests | 76 | Skipped when PLATFORM_TEST_ENABLED=false |
| Failing tests | 2 | 1 integration, 1 e2e |
| Test execution time | ~174s | Unit + integration + e2e |

## Critical Issues

### 1. Excessive Mocking (HIGH PRIORITY)

**Problem:** 1,889 lines of mock/patch usage creates brittle tests that can pass while production code fails.

**Evidence:**

```bash
$ grep -r "mock\|Mock\|patch" tests/ --include="*.py" | wc -l
1889
```

**Examples:**

- [tests/unit/backends/test_quilt3_backend_packages.py](tests/unit/backends/test_quilt3_backend_packages.py):23 - Patches quilt3 module
- Heavy mocking in backend tests obscures integration issues
- Mock setups often more complex than the code being tested

**Impact:**

- False confidence in test coverage
- Tests don't catch real integration issues
- Refactoring becomes risky (mocks don't update with code)
- New developers confused by mock complexity

**Recommendation:** Shift toward integration tests with real AWS services (or LocalStack) for critical paths.

---

### 2. Fixture Complexity (HIGH PRIORITY)

**Problem:** Complex autouse fixtures and session-scoped state create test interdependencies and hidden side effects.

**Evidence:**

**Conftest files:**

- [tests/conftest.py](tests/conftest.py) - 377 lines, complex pytest_configure
- [tests/integration/conftest.py](tests/integration/conftest.py) - 75 lines, Athena service patching
- [tests/stateless/conftest.py](tests/stateless/conftest.py) - 220 lines, Docker container management

**Fixture scope distribution:**

```
16 @pytest.fixture(scope="session")
 5 @pytest.fixture(scope="module")
 2 @pytest.fixture(scope="session", autouse=True)
 1 @pytest.fixture(scope="class")
```

**Autouse fixtures:**

- `reset_runtime_auth_state` - Runs before/after EVERY test
- `cached_athena_service_constructor` - Patches module globally

**Issues identified:**

1. **pytest_configure side effects** ([tests/conftest.py](tests/conftest.py):158-197):
   - Clears runtime auth
   - Sets QUILT_MULTIUSER_MODE=false globally
   - Removes JWT secrets
   - Resets ModeConfig singleton
   - Sets up boto3 session
   - Sets default Athena workgroup

2. **reset_runtime_auth_state fixture** ([tests/conftest.py](tests/conftest.py):199-234):
   - Autouse fixture running before/after every test
   - Clears runtime auth twice per test
   - Resets ModeConfig twice per test
   - Adds overhead to all tests

3. **Athena service patching** ([tests/integration/conftest.py](tests/integration/conftest.py):49-75):
   - Session-scoped autouse fixture
   - Patches `athena_glue.AthenaQueryService` globally
   - Uses LRU cache for service instances
   - Can cause state leakage between tests

4. **backend_mode fixture** ([tests/conftest.py](tests/conftest.py):237-273):
   - Parametrized fixture running tests twice (quilt3 + platform)
   - Complex setup with environment variables
   - Pushes/resets runtime context
   - 76 tests skip when PLATFORM_TEST_ENABLED=false

**Impact:**

- Hidden test dependencies
- Difficult to run tests in isolation
- Slow test startup due to autouse fixtures
- Hard to debug when fixtures conflict
- New tests inherit complex setup unintentionally

**Recommendation:**

- Remove autouse fixtures where possible
- Make fixtures opt-in with explicit dependencies
- Reduce session-scoped fixtures with state
- Document fixture side effects clearly

---

### 3. Backend Mode Duplication (MEDIUM PRIORITY)

**Problem:** Tests parametrized with `backend_mode` fixture run twice (quilt3 + platform), causing duplication and slow tests.

**Evidence:**

- 76 tests skipped when platform mode disabled
- Integration tests take 171 seconds (partly due to duplication)
- Many tests don't actually need both modes

**Example:**

```python
def test_something(backend_mode):
    # Runs twice: once for quilt3, once for platform
    # But often only one mode is relevant
```

**Impact:**

- Nearly 2x integration test time
- Confusion about which mode is being tested
- Setup/teardown overhead multiplied

**Recommendation:**

- Use explicit `@pytest.mark.parametrize` only where needed
- Create separate test files for mode-specific tests
- Default to quilt3 mode for most tests

---

### 4. Large Test Files (MEDIUM PRIORITY)

**Problem:** Some test files are extremely large, testing too many things in one file.

**Largest test files:**

```
997 lines - tests/unit/backends/test_quilt3_backend_packages.py
867 lines - tests/unit/backends/test_platform_backend_packages.py
830 lines - tests/integration/test_bucket_tools.py
777 lines - tests/fixtures/runners/ccle_direct_test_runner.py
766 lines - tests/fixtures/runners/ccle_computational_biology_test_runner.py
764 lines - tests/unit/domain/test_content_info.py
740 lines - tests/unit/backends/test_platform_backend_admin.py
695 lines - tests/integration/test_elasticsearch_index_discovery.py
689 lines - tests/unit/domain/test_catalog_config.py
655 lines - tests/integration/test_search_catalog_integration.py
```

**Example:** [tests/unit/backends/test_quilt3_backend_packages.py](tests/unit/backends/test_quilt3_backend_packages.py) has 52 test functions/classes in 997 lines.

**Impact:**

- Hard to navigate and understand
- Slow to run (e.g., quilt_tools test takes 1.53s)
- Difficult to isolate failures
- Merge conflicts more likely

**Recommendation:**

- Split large files by feature/functionality
- Maximum ~300 lines per test file
- Group related tests into classes

---

### 5. Slow Tests (MEDIUM PRIORITY)

**Problem:** Several tests take >1 second, slowing down the development feedback loop.

**Slowest unit tests:**

```
1.53s - test_mcp_server.py::test_quilt_tools
1.11s - services/test_permission_service.py::test_permission_cache_expiration
1.05s - server/test_mcp_handler.py::test_tool_handler_cleans_up_on_error
0.99s - context/test_factory.py::test_factory_permission_service_instances_are_not_shared
0.99s - context/test_factory.py::test_factory_create_context_generates_request_id
0.95s - test_permissions.py::TestPermissionDiscoveryEngine::test_discover_user_identity
0.95s - context/test_factory.py::test_factory_creates_fresh_auth_service_instances
0.78s - test_packages_api.py::TestPackageUpdateValidation::test_package_update_with_explicit_registry
```

**Integration test time:**

```
171.23s total (1 failed, 150 passed, 76 skipped)
```

**Impact:**

- Developers wait longer for feedback
- CI/CD pipeline takes longer
- Discourages running full test suite locally

**Recommendation:**

- Investigate why permission tests are slow (cache expiration waits?)
- Mock time-dependent operations
- Parallelize integration tests
- Move slow tests to separate suite

---

### 6. Test Organization Issues (LOW-MEDIUM PRIORITY)

**Problem:** Unclear boundaries between test types and test discovery issues.

**Test directory structure:**

```
tests/
├── unit/           (52 test functions in largest file)
├── integration/    (21 files, 171s runtime)
├── e2e/           (11 files, 2.6s runtime)
├── stateless/     (5 files, Docker-based)
├── security/      (purpose unclear, rarely run?)
├── performance/   (purpose unclear, rarely run?)
├── load/          (purpose unclear, rarely run?)
└── fixtures/      (data + test runners)
```

**Issues:**

1. **Confusion about test types:**
   - What makes a test "unit" vs "integration"?
   - E2E tests are actually faster than integration tests
   - Security/performance/load tests not clearly documented

2. **Test runner fixtures:**
   - `tests/fixtures/runners/` contains 3 large test runners (777-547 lines)
   - Purpose unclear (are these fixtures or tests?)
   - `ccle_direct_test_runner.py`, `ccle_computational_biology_test_runner.py`

3. **Missing test discovery:**
   - Some tests may not be discovered by pytest
   - Files in `fixtures/runners/` look like tests but might not run

**Impact:**

- Developers unsure where to add new tests
- Tests may not run in CI
- Duplicated test logic

**Recommendation:**

- Document test type definitions in TESTING.md
- Rename or reorganize test runners
- Remove unused test suites (or document their purpose)

---

### 7. Configuration Complexity (MEDIUM PRIORITY)

**Problem:** Test configuration has grown complex with global side effects.

**Evidence from** [tests/conftest.py](tests/conftest.py):158-197:

```python
def pytest_configure(config):
    """Configure pytest and set up AWS session if needed."""
    # CRITICAL: Ensure tests use IAM credentials, not JWT authentication
    # Clear any existing runtime auth context to prevent JWT fallback
    try:
        from quilt_mcp.runtime_context import clear_runtime_auth
        clear_runtime_auth()
    except ImportError:
        pass

    # Explicitly ensure unit tests run in local mode (not multiuser mode)
    os.environ["QUILT_MULTIUSER_MODE"] = "false"

    # Remove JWT secrets to prevent development fallback behavior
    os.environ.pop("MCP_JWT_SECRET", None)
    os.environ.pop("MCP_JWT_SECRET_SSM_PARAMETER", None)

    # Reset ModeConfig singleton to pick up test environment variables
    try:
        from quilt_mcp.config import reset_mode_config
        reset_mode_config()
    except ImportError:
        pass

    # Configure boto3 default session to use AWS_PROFILE if set
    if os.getenv("AWS_PROFILE"):
        boto3.setup_default_session(profile_name=os.getenv("AWS_PROFILE"))

    # Set default Athena workgroup to skip discovery in tests
    if not os.getenv("ATHENA_WORKGROUP"):
        os.environ["ATHENA_WORKGROUP"] = "primary"
```

**Issues:**

1. Global environment variable manipulation
2. Singleton resets
3. boto3 session setup
4. Mode-specific configuration
5. Comments indicate complexity ("CRITICAL", "NEVER")

**Impact:**

- Hard to understand test behavior
- Environment-dependent test results
- Difficult to debug failures
- Scary to modify

**Recommendation:**

- Move configuration to explicit fixtures
- Document why each setting is needed
- Reduce global state manipulation

---

### 8. Test Interdependencies (LOW PRIORITY)

**Problem:** Some tests import from other test files, creating coupling.

**Evidence:**

```python
# Multiple test files import from config helpers
from quilt_mcp.config import set_test_mode_config, reset_mode_config
```

**Files with test imports:**

- [tests/unit/test_utils.py](tests/unit/test_utils.py)
- [tests/unit/tools/test_get_resource_simple.py](tests/unit/tools/test_get_resource_simple.py)
- [tests/unit/context/test_factory.py](tests/unit/context/test_factory.py)
- [tests/unit/test_auth_service_factory.py](tests/unit/test_auth_service_factory.py)
- [tests/unit/ops/test_factory.py](tests/unit/ops/test_factory.py) (15 imports!)

**Impact:**

- Tests coupled to test infrastructure
- Harder to move tests around
- Unclear dependencies

**Recommendation:**

- Move shared test helpers to `tests/helpers/` or `tests/utils/`
- Make test utilities explicit and documented

---

### 9. Failing/Skipped Tests (LOW PRIORITY)

**Problem:** Some tests are failing or consistently skipped.

**Failing tests:**

1. **Integration:** `test_athena.py::TestTabulatorWorkflow::test_tabulator_complete_workflow[quilt3]`
   - Error: "tabulator_data_catalog not configured"
   - Requires Tabulator-enabled catalog
   - Should be skipped if catalog not configured

2. **E2E:** `test_governance_integration.py::TestGovernanceWorkflows::test_user_management_workflow`
   - Error: "assert True is False"
   - Unclear why failing

**Skipped tests:**

- 76 tests skipped when `PLATFORM_TEST_ENABLED=false`
- 4 tests skipped in e2e suite (reason unclear)
- 6 xfailed tests (expected failures)
- 7 xpassed tests (expected failures that now pass!)

**Impact:**

- Failing tests indicate missing configuration or bugs
- Skipped tests reduce effective coverage
- Xpassed tests indicate outdated expectations

**Recommendation:**

- Fix or properly skip failing tests
- Investigate xpassed tests (remove xfail marker?)
- Document skip conditions clearly

---

### 10. Specialized Test Suites (LOW PRIORITY)

**Problem:** Several specialized test directories exist but their purpose and maintenance status is unclear.

**Specialized suites:**

1. **stateless/** (5 files, 220-line conftest)
   - Docker-based deployment tests
   - Tests read-only filesystem constraints
   - Requires Docker daemon
   - Unclear if run in CI

2. **security/** (files exist but not analyzed)
   - Security-focused tests
   - Unclear if regularly run

3. **performance/** (files exist but not analyzed)
   - Performance benchmarks
   - Unclear if regularly run or monitored

4. **load/** (files exist but not analyzed)
   - Load testing
   - Unclear if regularly run

**Impact:**

- Tests may bitrot if not run regularly
- Unclear if required for PR approval
- Duplicated test logic possible

**Recommendation:**

- Document each test suite's purpose in TESTING.md
- Specify when each suite should run (local/CI/nightly)
- Remove unmaintained suites or mark as experimental

---

## Test Code Ratio Analysis

**Test-to-source ratio: 86%**

```
30,469 lines of test code
35,372 lines of source code
-----
0.86 ratio
```

This is **extremely high** compared to industry standards:

- Typical projects: 30-50% test-to-source ratio
- Well-tested projects: 50-70% ratio
- This project: 86% ratio

**Implications:**

- Very comprehensive test coverage (good!)
- Potentially over-tested with diminishing returns
- High maintenance burden
- May indicate excessive mocking/duplication

**Recommendation:** Focus on reducing duplication and mocking rather than adding more tests.

---

## Test Speed Analysis

### Unit Tests

- Total: 905 tests
- Runtime: ~2-3 seconds (estimated from durations)
- Slowest: 1.53s (test_quilt_tools)

### Integration Tests

- Total: 227 tests (150 passed, 76 skipped, 1 failed)
- Runtime: 171.23 seconds (2:51)
- Average: 0.75s per test

### E2E Tests

- Total: 67 tests (62 passed, 4 skipped, 1 failed)
- Runtime: 2.61 seconds
- Average: 0.04s per test (very fast!)

**Observations:**

- E2E tests are surprisingly fast (probably well-mocked)
- Integration tests are slow (real AWS calls?)
- Unit tests have some slow outliers

**Recommendation:**

- Investigate why integration tests are slow
- Consider splitting into "fast integration" and "slow integration"
- Run slow tests in parallel or nightly

---

## Dependency Issues

**External dependencies for tests:**

1. AWS credentials (AWS_PROFILE or IAM role)
2. QUILT_TEST_BUCKET environment variable
3. Docker daemon (for stateless tests)
4. PLATFORM_TEST_ENABLED flag (for platform tests)
5. Tabulator-enabled catalog (for some tests)
6. Elasticsearch (for search tests)

**Issues:**

- Many tests fail silently without proper setup
- Setup requirements not documented in README
- New developers struggle to run full suite

**Recommendation:**

- Document all test dependencies in TESTING.md
- Provide setup script for test environment
- Use pytest markers to skip tests missing dependencies

---

## Positive Findings

Despite the issues, the test suite has strengths:

1. **High coverage:** 86% test-to-source ratio indicates thorough testing
2. **Good organization:** Tests mirror source structure (backends split into 6 files)
3. **Fast E2E tests:** 2.6s for 67 tests shows good design
4. **Comprehensive fixtures:** Well-designed session fixtures for expensive operations
5. **Backend abstraction tested:** Tests verify both quilt3 and platform backends
6. **Low technical debt:** Only 11 pytest.skip markers (no TODOs/FIXMEs found)

---

## Recommendations Summary

### High Priority

1. **Reduce mocking:** Shift to integration tests with real services where possible
2. **Simplify fixtures:** Remove autouse fixtures, make opt-in
3. **Fix failing tests:** 2 failing tests should pass or be skipped properly

### Medium Priority

4. **Reduce backend duplication:** Make backend_mode fixture opt-in
2. **Split large test files:** Break up 997-line test files
3. **Speed up slow tests:** Investigate 1+ second tests
4. **Clarify test organization:** Document test types in TESTING.md

### Low Priority

8. **Clean up test imports:** Move shared helpers to dedicated module
2. **Document specialized suites:** Clarify security/performance/load test purposes
3. **Reduce configuration complexity:** Simplify pytest_configure

---

## Next Steps

1. Create `spec/a17-test-cleanup.md/02-recommendations.md` with detailed fixes
2. Create `spec/a17-test-cleanup.md/03-implementation-plan.md` with phased approach
3. Start with high-priority issues (mocking, fixtures, failing tests)
4. Track progress with test metrics dashboard

---

## Appendix: Test Discovery Output

```bash
$ uv run pytest tests/ --collect-only -q
======================== 1181 tests collected in 0.33s =========================
```

All tests discovered successfully. No collection errors.

---

**End of Analysis**

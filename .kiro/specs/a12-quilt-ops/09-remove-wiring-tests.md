# Specification: Remove Braindead Wiring Tests

**Date:** 2026-01-31
**Author:** Claude Code
**Status:** Proposed
**Related:** 08-malformed-auth-tests.md

---

## Executive Summary

The test suite contains **~1,500+ lines of "braindead" wiring tests** that:
- Patch code to test trivial wiring between layers
- Only verify that method X calls method Y with parameter Z
- Provide no business logic coverage
- Break frequently during refactoring (high maintenance cost)
- Give false confidence (passing tests don't mean working code)

**Recommendation:** Delete ~1,500 lines of wiring tests, replace ~100 lines with integration tests for critical paths.

---

## Problem Statement

### What Are "Wiring Tests"?

Wiring tests mock internal implementation details and verify that:
1. Function A calls Function B
2. Function B is called with specific parameters
3. Mock object methods are invoked N times

**Example (from test_packages_quiltops_migration.py:55-71):**
```python
def test_packages_list_uses_quilt_ops_search_packages(self, mock_quilt_ops, sample_package_info_list):
    """Test that packages_list uses QuiltOps.search_packages() instead of QuiltService."""
    mock_quilt_ops.search_packages.return_value = sample_package_info_list

    with patch('quilt_mcp.ops.factory.QuiltOpsFactory') as mock_factory:
        mock_factory.create.return_value = mock_quilt_ops
        result = packages_list(registry="s3://test-bucket", limit=10)

    # WIRING TEST: Just verifies the function was called
    mock_factory.create.assert_called_once()
    mock_quilt_ops.search_packages.assert_called_once_with(
        query="",
        registry="s3://test-bucket",
    )
```

**What does this test prove?**
- That `packages_list()` calls `QuiltOpsFactory.create()` ✓
- That it calls `search_packages()` with correct params ✓

**What does this test NOT prove?**
- That the function actually works
- That results are transformed correctly
- That error handling works
- That the integration with real backends works

### Why Are Wiring Tests Bad?

1. **High brittleness**: Break when abstraction layers change (see 08-malformed-auth-tests.md)
2. **Low value**: Don't test business logic, only trivial function calls
3. **False confidence**: Passing tests don't guarantee working code
4. **High maintenance cost**: Must be updated every time internal wiring changes
5. **Poor test coverage**: Mock away the actual implementation being tested

---

## CRITICAL: Massive Session Detection Test Suite (OBSOLETE)

### The Elephant in the Room

**2,182 lines (92 test functions)** testing session detection that are **100% obsolete**:

1. **[tests/unit/ops/test_factory.py](../../tests/unit/ops/test_factory.py)** - 585 lines, 30 tests
   - Entire `TestQuiltOpsFactorySessionDetection` class (lines 286-519, ~233 lines)
   - Tests `_detect_quilt3_session()` private method exclusively
   - Tests wrong API: `quilt3.session.get_session_info()` (doesn't exist)
   - Being replaced by `ModeConfig` in a13

2. **[tests/unit/backends/test_quilt3_backend_session.py](../../tests/unit/backends/test_quilt3_backend_session.py)** - 1,597 lines, 62 tests
   - Entire file dedicated to session detection
   - Tests same broken API with extensive edge cases
   - Zero business logic tested

**Why these tests are obsolete:**

1. ✅ **Private method** - `_detect_quilt3_session()` starts with underscore (internal implementation)
2. ✅ **Known bug** - Calls `quilt3.session.get_session_info()` which doesn't exist (see 05-factory-api-mismatch-analysis.md)
3. ✅ **Being replaced** - Mode config consolidation (a13) replaces this entire mechanism
4. ✅ **Pure wiring** - Just test that method calls other method, no business logic
5. ✅ **Zero value** - Tests pass but production code fails because API doesn't exist

**Example of obsolete test (test_factory.py:290-303):**
```python
@patch('quilt_mcp.ops.factory.quilt3')
def test_detect_quilt3_session_with_valid_session(self, mock_quilt3):
    """Test _detect_quilt3_session() with valid session data."""
    valid_session = {'registry': 's3://test-registry', ...}
    mock_quilt3.session.get_session_info.return_value = valid_session

    result = QuiltOpsFactory._detect_quilt3_session()

    assert result == valid_session
    mock_quilt3.session.get_session_info.assert_called_once()
```

**What this test proves:**
- That calling `_detect_quilt3_session()` returns what `get_session_info()` returns ✓
- That the mock was called ✓

**What this test does NOT prove:**
- That the code works (because `get_session_info()` doesn't exist in real quilt3)
- Any business logic (there is none - it's trivial wiring)
- Anything useful whatsoever

**Verdict:** ❌ **DELETE BOTH FILES ENTIRELY**
- `test_factory.py` - Delete ~500 of 585 lines (keep factory structure tests, delete session detection)
- `test_quilt3_backend_session.py` - Delete entire file (1,597 lines)

---

## Categories of Wiring Tests to Remove

### Category 1: Malformed Tests (Patch Wrong Abstraction)

**Impact:** Tests that are actively broken due to refactoring

#### [tests/unit/test_s3_package.py](../../tests/unit/test_s3_package.py)

**Lines 365-411 (47 lines)** - `TestCreateEnhancedPackageMigration`

```python
@patch("quilt_mcp.tools.packages.QuiltService")  # ← WRONG! Not used anymore
def test_create_enhanced_package_uses_create_package_revision(...):
    # Patches QuiltService but implementation uses QuiltOpsFactory
    # Currently FAILS - see 08-malformed-auth-tests.md
```

**Verdict:** ❌ **DELETE** - Test is broken and provides no value
**Replacement:** None needed (already covered by integration tests)

---

### Category 2: QuiltOps Migration Wiring Tests

**Impact:** Entire file dedicated to verifying trivial wiring

#### [tests/unit/tools/test_packages_quiltops_migration.py](../../tests/unit/tools/test_packages_quiltops_migration.py)

**Lines 1-326 (326 lines)** - Entire file

**Tests in this file:**

1. **Lines 55-78** - `test_packages_list_uses_quilt_ops_search_packages`
   - Verdict: ❌ **DELETE** - Only tests that `packages_list()` calls backend
   - No business logic tested

2. **Lines 80-99** - `test_packages_list_with_prefix_filter`
   - Verdict: ⚠️ **KEEP** - Tests actual filtering logic (not just wiring)

3. **Lines 101-122** - `test_packages_list_transforms_package_info_to_names`
   - Verdict: ⚠️ **KEEP** - Tests transformation logic (actual business logic)

4. **Lines 124-136** - `test_packages_list_error_handling`
   - Verdict: ⚠️ **KEEP** - Tests error handling (business logic)

5. **Lines 138-156** - `test_packages_list_maintains_response_format`
   - Verdict: ⚠️ **KEEP** - Tests response format (contract test)

6. **Lines 181-198** - `test_package_browse_uses_quilt_ops_browse_content`
   - Verdict: ❌ **DELETE** - Only tests that function calls backend

7. **Lines 204-218** - `test_package_browse_with_path`
   - Verdict: ❌ **DELETE** - Only verifies backend is called with path=""

8. **Lines 220-241** - `test_package_browse_transforms_content_info_to_entries`
   - Verdict: ⚠️ **KEEP** - Tests transformation logic

9. **Lines 242-255** - `test_package_browse_error_handling`
   - Verdict: ⚠️ **KEEP** - Tests error handling

10. **Lines 257-277** - `test_package_browse_maintains_response_format`
    - Verdict: ⚠️ **KEEP** - Tests response format (contract test)

11. **Lines 283-325** - `TestDataclassCompatibility` (2 tests)
    - Verdict: ❌ **DELETE** - Tests Python dataclass stdlib, not our code

**Summary for this file:**
- **Total lines:** 326
- **Lines to delete:** ~120 (37%)
- **Lines to keep:** ~206 (63% - transformation, error handling, response format tests)

**Recommendation:** Delete wiring-only tests (120 lines), keep business logic tests

---

### Category 3: Athena Service Dependency Injection Tests

**Impact:** Tests that only verify dependency injection wiring

#### [tests/unit/test_athena_service.py](../../tests/unit/test_athena_service.py)

**Lines 1-83 (83 lines)** - Entire file

**Tests in this file:**

1. **Lines 15-24** - `test_athena_service_accepts_quilt_service_dependency`
   - Verdict: ❌ **DELETE** - Only verifies constructor accepts parameter
   - No business logic tested

2. **Lines 26-51** - `test_athena_service_uses_quilt_service_for_botocore_session`
   - Verdict: ❌ **DELETE** - Only verifies method calls with extensive mocking
   - Tests wiring, not logic

3. **Lines 52-58** - `test_athena_service_backwards_compatible_without_quilt_service`
   - Verdict: ⚠️ **MAYBE KEEP** - Tests backwards compatibility (could be valuable)
   - But it's trivial - just checks attribute existence

4. **Lines 60-83** - `test_athena_service_uses_fallback_when_no_quilt_service_provided`
   - Verdict: ❌ **DELETE** - More wiring verification with heavy mocking

**Summary for this file:**
- **Total lines:** 83
- **Lines to delete:** ~70 (85%)
- **Lines to keep:** ~13 (15% - backwards compatibility test only if deemed valuable)

**Recommendation:** Delete entire file OR reduce to single backwards-compatibility test

---

### Category 4: Catalog Wiring Tests

**Impact:** Many tests that only verify QuiltService method calls

#### [tests/unit/test_catalog.py](../../tests/unit/test_catalog.py)

**Lines 1-342 (342 lines)** - Multiple wiring tests

**Wiring tests to DELETE:**

1. **Lines 67-75** - `test_get_catalog_host_when_logged_in_url_available`
   - Verdict: ❌ **DELETE** - Only verifies QuiltService.get_logged_in_url() is called
   - Tests trivial delegation

2. **Lines 77-86** - `test_get_catalog_host_falls_back_to_navigator_url`
   - Verdict: ⚠️ **KEEP** - Tests fallback logic (business logic)

3. **Lines 88-97** - `test_get_catalog_host_with_no_navigator_url`
   - Verdict: ⚠️ **KEEP** - Tests edge case handling

4. **Lines 121-129** - `test_get_catalog_host_with_exception`
   - Verdict: ⚠️ **KEEP** - Tests error handling

5. **Lines 272-283** - `test_configure_catalog_with_friendly_name`
   - Verdict: ❌ **DELETE** - Only verifies set_config() is called
   - Mock verifies mock

6. **Lines 285-296** - `test_configure_catalog_success`
   - Verdict: ❌ **DELETE** - Same as above, trivial wiring test

7. **Lines 326-342** - `test_get_catalog_info_delegates_to_service`
   - Verdict: ❌ **DELETE** - Tests trivial delegation (function calls another function)
   - No business logic

**Summary for this file:**
- **Total lines:** 342
- **Lines to delete:** ~50-70 (15-20%)
- **Lines to keep:** ~270-290 (80-85% - edge cases, error handling, logic tests)

**Recommendation:** Remove pure delegation/wiring tests (~60 lines)

---

### Category 5: Server Configuration/Main Entry Point Tests

**Impact:** Tests that verify trivial server setup

#### [tests/unit/test_main.py](../../tests/unit/test_main.py)

**Lines 1-215 (215 lines)** - Tests for main() entry point

**Wiring tests to DELETE:**

1. **Lines 50-58** - `test_main_preserves_existing_transport`
   - Verdict: ❌ **DELETE** - Verifies env var is read (trivial)

2. **Lines 60-66** - `test_main_defaults_to_stdio`
   - Verdict: ❌ **DELETE** - Verifies default env var (trivial)

3. **Lines 68-79** - `test_main_imports_dotenv`
   - Verdict: ❌ **DELETE** - Tests that import exists (useless)

4. **Lines 82-88** - `test_skip_banner_cli_flag`
   - Verdict: ❌ **DELETE** - Tests trivial CLI parsing

5. **Lines 90-98** - `test_skip_banner_env_var`
   - Verdict: ❌ **DELETE** - Tests trivial env var reading

6. **Lines 100-108** - `test_skip_banner_cli_overrides_env`
   - Verdict: ⚠️ **MAYBE KEEP** - Tests precedence logic (minor business logic)

**Error handling tests to KEEP:**

7. **Lines 120-150** - `test_main_import_error_handling`
   - Verdict: ✅ **KEEP** - Tests important error handling behavior

8. **Lines 153-183** - `test_main_generic_error_handling`
   - Verdict: ✅ **KEEP** - Tests important error handling behavior

9. **Lines 186-214** - `test_main_keyboard_interrupt`
   - Verdict: ✅ **KEEP** - Tests important signal handling

**Summary for this file:**
- **Total lines:** 215
- **Lines to delete:** ~80-100 (40-45%)
- **Lines to keep:** ~115-135 (55-60% - error handling tests)

**Recommendation:** Delete trivial env/CLI parsing tests (~90 lines), keep error handling

#### [tests/unit/test_utils.py](../../tests/unit/test_utils.py)

**Lines 240-349 (110 lines)** - Server configuration tests

**Wiring tests to DELETE:**

1. **Lines 243-246** - `test_create_mcp_server`
   - Verdict: ❌ **DELETE** - Only tests that function returns object (useless)

2. **Lines 248-257** - `test_get_tool_modules`
   - Verdict: ⚠️ **MAYBE KEEP** - Tests module discovery (could be valuable)

3. **Lines 259-268** - `test_register_tools_with_mock_server`
   - Verdict: ❌ **DELETE** - Only verifies mock.tool.call_count (wiring)

4. **Lines 270-279** - `test_register_tools_with_specific_modules`
   - Verdict: ❌ **DELETE** - Same as above

5. **Lines 281-324** - `test_register_tools_only_public_functions`
   - Verdict: ⚠️ **MAYBE KEEP** - Tests filtering logic (business logic)

6. **Lines 326-335** - `test_register_tools_verbose_output`
   - Verdict: ❌ **DELETE** - Tests print output (low value)

7. **Lines 337-343** - `test_create_configured_server`
   - Verdict: ❌ **DELETE** - "we can't easily verify... but we can verify it doesn't crash" 🤦

8. **Lines 345-349** - `test_create_configured_server_verbose_output`
   - Verdict: ❌ **DELETE** - Tests print output (low value)

9. **Lines 351-364** - `test_run_server_stdio_success`
   - Verdict: ❌ **DELETE** - Only verifies server.run() is called

10. **Lines 366-380** - `test_run_server_http_success`
    - Verdict: ❌ **DELETE** - Only verifies uvicorn.run() is called

**Summary for this section:**
- **Total lines:** ~110
- **Lines to delete:** ~70-80 (65-75%)
- **Lines to keep:** ~30-40 (25-35% - module discovery, function filtering)

**Recommendation:** Delete most server wiring tests (~75 lines)

---

### Category 6: Backend Initialization Tests

**Impact:** Tests that mostly verify mock setup

#### [tests/unit/backends/test_quilt3_backend_core.py](../../tests/unit/backends/test_quilt3_backend_core.py)

**Lines 1-289 (289 lines)** - Backend initialization and structure tests

**Wiring tests to DELETE:**

1. **Lines 22-26** - `test_quilt3_backend_can_be_imported`
   - Verdict: ❌ **DELETE** - Tests Python import (useless)

2. **Lines 28-33** - `test_quilt3_backend_implements_quilt_ops`
   - Verdict: ⚠️ **MAYBE KEEP** - Tests interface compliance (could use mypy instead)

3. **Lines 35-51** - `test_quilt3_backend_implements_all_abstract_methods`
   - Verdict: ⚠️ **MAYBE KEEP** - Tests interface compliance (could use mypy instead)
   - This is a runtime check that static typing should catch

4. **Lines 53-73** - `test_quilt3_backend_initialization_with_valid_session`
   - Verdict: ❌ **DELETE** - Only verifies mock.get_session_info() is called
   - Tests trivial initialization wiring

5. **Lines 108-129** - `test_quilt3_backend_session_validation_success`
   - Verdict: ❌ **DELETE** - Tests that assigning session works (trivial)

6. **Lines 153-165** - `test_quilt3_backend_session_validation_without_get_session_info`
   - Verdict: ⚠️ **KEEP** - Tests fallback behavior (edge case)

7. **Lines 168-188** - `test_quilt3_backend_initialization_preserves_session_config`
   - Verdict: ❌ **DELETE** - Tests that `self.session = session` works (trivial)

**Integration tests to KEEP:**

8. **Lines 196-260** - `test_complete_package_workflow`
   - Verdict: ✅ **KEEP** - Integration test (though heavily mocked)

9. **Lines 263-288** - `test_error_propagation_through_workflow`
   - Verdict: ✅ **KEEP** - Tests error handling

**Summary for this file:**
- **Total lines:** 289
- **Lines to delete:** ~120-150 (40-50%)
- **Lines to keep:** ~140-170 (50-60%)

**Recommendation:** Delete trivial initialization tests (~130 lines), keep interface compliance and integration tests

---

## Summary by File

| File | Total Lines | Delete | Keep | Delete % |
|------|-------------|--------|------|----------|
| test_s3_package.py | 47 (class) | 47 | 0 | 100% |
| test_packages_quiltops_migration.py | 326 | 120 | 206 | 37% |
| test_athena_service.py | 83 | 70 | 13 | 84% |
| test_catalog.py | 342 | 60 | 282 | 18% |
| test_main.py | 215 | 90 | 125 | 42% |
| test_utils.py (server tests) | 110 | 75 | 35 | 68% |
| test_quilt3_backend_core.py | 289 | 130 | 159 | 45% |
| **test_factory.py (session detection)** | **585** | **~500** | **~85** | **~85%** |
| **test_quilt3_backend_session.py** | **1,597** | **~1,400** | **~197** | **~88%** |
| **TOTAL** | **3,594** | **~2,492** | **~1,102** | **~69%** |

**Impact:** Remove ~2,500 lines of wiring tests (69% of analyzed files)

### CRITICAL FINDING: Session Detection Tests Are Obsolete

**2,182 lines (92 test functions)** dedicated to testing `_detect_quilt3_session()`:
- Tests a **private internal method** (shouldn't be tested directly)
- Tests a method with a **known bug** (calls non-existent `quilt3.session.get_session_info()`)
- Being **replaced by mode config** in a13
- Almost entirely **wiring tests** with extensive mocking
- **Zero business value**

---

## Tests That MUST Be Replaced

### Critical Path Tests Needed

Most wiring tests can simply be deleted because integration/e2e tests already cover the behavior. However, a few areas may need lightweight integration tests:

1. **QuiltOps Factory Integration** (if not already covered)
   - Test that factory can create backends successfully
   - Test that backends can execute basic operations end-to-end
   - **Recommendation:** Check if `tests/integration/test_integration.py` already covers this

2. **Error Propagation Through Layers** (if not already covered)
   - Test that errors from quilt3 library surface correctly through QuiltOps → Tools
   - **Recommendation:** Check if integration tests cover error scenarios

3. **Athena Query Service with Real Backend** (if not already covered)
   - Test that Athena service can actually execute queries with real quilt3 session
   - **Recommendation:** Add to integration test suite if missing

**Estimated new tests needed:** 3-5 integration tests (~50-100 lines)

---

## Replacement Strategy

### For Deleted Wiring Tests

**Most wiring tests need NO replacement** because:

1. **Integration tests already cover the behavior**
   - `tests/integration/test_integration.py` - 200+ lines of real backend tests
   - `tests/e2e/` - Multiple end-to-end workflow tests
   - These tests use real implementations, not mocks

2. **Static type checking covers interface compliance**
   - MyPy already verifies that `Quilt3_Backend` implements `QuiltOps`
   - Runtime tests for abstract methods are redundant

3. **The behavior is trivial**
   - "Function A calls function B" doesn't need a test
   - "Constructor accepts parameter" doesn't need a test
   - "Import works" doesn't need a test

### For Critical Gaps

Add ~3-5 lightweight integration tests for:

1. **Factory → Backend → Operation** end-to-end flow
2. **Error propagation** through all layers
3. **Athena integration** with real session (if missing)

**Example integration test to add:**

```python
@pytest.mark.integration
def test_package_list_through_factory_to_backend():
    """Integration test: packages_list() works end-to-end through factory."""
    # Uses real QuiltOpsFactory
    # Uses real backend (or test double, not mock)
    # Verifies complete workflow
    result = packages_list(registry="s3://test-bucket")
    assert hasattr(result, 'packages')
    assert isinstance(result.packages, list)
```

---

## Implementation Plan

### Phase 1: Safe Deletions (No Risk)

Delete tests that are obviously useless:

1. ✅ **DELETE ENTIRE FILE:** `test_quilt3_backend_session.py` (1,597 lines)
   - Tests obsolete `_detect_quilt3_session()` mechanism
   - Tests broken API that doesn't exist
   - Being replaced by mode config in a13
   - **ZERO VALUE**

2. ✅ **DELETE SESSION TESTS:** `test_factory.py` (~500 of 585 lines)
   - Delete `TestQuiltOpsFactorySessionDetection` class (lines 286-519)
   - Delete all tests calling `_detect_quilt3_session()`
   - Keep: Factory structure tests, create() integration tests

3. ✅ Delete `test_s3_package.py::TestCreateEnhancedPackageMigration` (47 lines)
   - Already broken, no value

4. ✅ Delete `test_quilt3_backend_core.py` trivial tests (~130 lines)
   - Import tests, trivial initialization tests, mock setup tests

5. ✅ Delete `test_main.py` CLI/env parsing tests (~90 lines)
   - Trivial env var and CLI flag tests

6. ✅ Delete `test_utils.py` server setup tests (~75 lines)
   - Mock verification tests with no business logic

7. ✅ Delete `test_athena_service.py` wiring tests (~70 lines)
   - Pure dependency injection wiring tests

**Total Phase 1 deletions: ~2,509 lines**

**THIS ALONE REMOVES 69% OF ANALYZED TEST CODE**

### Phase 2: Conditional Deletions (Low Risk)

Delete after verifying integration test coverage:

1. ⚠️ Review integration test coverage for QuiltOps factory
2. ⚠️ Delete `test_packages_quiltops_migration.py` wiring-only tests (~120 lines)
3. ⚠️ Delete `test_catalog.py` delegation tests (~60 lines)

**Total Phase 2 deletions: ~180 lines**

### Phase 3: Add Integration Tests (If Needed)

1. ✅ Check existing integration test coverage
2. ✅ Add 3-5 integration tests for any gaps (~50-100 lines)

---

## Benefits of Removal

### Reduced Maintenance Cost

**Current state:**
- ~600 lines of brittle tests that break on refactoring
- Require updates whenever internal wiring changes
- Example: QuiltOps migration broke `test_s3_package.py` test

**After removal:**
- Tests that actually test behavior, not implementation
- Changes to internal wiring don't break tests
- Integration tests catch real bugs

### Improved Test Signal

**Current state:**
- 1,400+ lines of tests, many provide false confidence
- Passing tests don't guarantee working code
- "All unit tests pass" ≠ "Code works"

**After removal:**
- Smaller test suite with higher signal-to-noise ratio
- Tests that fail indicate real problems
- Integration tests verify actual behavior

### Faster Test Execution

**Current state:**
- ~600 lines of mock setup and verification
- Each test has overhead of mock creation

**After removal:**
- Fewer tests = faster execution
- Focus on meaningful tests

---

## Decision Points

### 1. Should We Keep Interface Compliance Tests?

**Tests like:** `test_quilt3_backend_implements_all_abstract_methods`

**Arguments FOR keeping:**
- Provides runtime verification of interface compliance
- Catches missing method implementations

**Arguments AGAINST keeping:**
- MyPy already provides static type checking
- Runtime tests are redundant with proper typing
- Python's ABC module already enforces this

**Recommendation:** ⚠️ **Delete** - Use MyPy for interface compliance

### 2. Should We Keep "MAYBE KEEP" Tests?

**Tests that test minor logic** but are borderline valuable:

- `test_skip_banner_cli_overrides_env` - Tests CLI precedence
- `test_get_tool_modules` - Tests module discovery
- `test_register_tools_only_public_functions` - Tests function filtering

**Recommendation:** ⚠️ **Keep for now** - Review in future cleanup

### 3. Should We Delete test_athena_service.py Entirely?

**Arguments FOR deletion:**
- 85% of file is wiring tests
- Dependency injection is trivial
- No business logic tested

**Arguments AGAINST:**
- Backwards compatibility test might be valuable
- Only 13 lines would remain

**Recommendation:** ❌ **Delete entire file** - Add integration test if needed

---

## Files Requiring Changes

### CRITICAL - Session Detection Tests (OBSOLETE)

**[tests/unit/backends/test_quilt3_backend_session.py](../../tests/unit/backends/test_quilt3_backend_session.py)**

- ❌ **DELETE ENTIRE FILE** (1,597 lines)
- Tests obsolete session detection mechanism with broken API

**[tests/unit/ops/test_factory.py](../../tests/unit/ops/test_factory.py)**

- Delete session detection tests (~500 of 585 lines)
- Keep factory structure and integration tests

### Other Tests to Modify

**[tests/unit/test_s3_package.py](../../tests/unit/test_s3_package.py)**

- Delete lines 365-411 (47 lines)

**[tests/unit/tools/test_packages_quiltops_migration.py](../../tests/unit/tools/test_packages_quiltops_migration.py)**

- Delete lines 55-78, 181-198, 204-218, 283-325 (~120 lines)

**[tests/unit/test_athena_service.py](../../tests/unit/test_athena_service.py)**

- Delete entire file OR reduce to single backwards-compatibility test (~70 lines)

**[tests/unit/test_catalog.py](../../tests/unit/test_catalog.py)**

- Delete lines 67-75, 272-283, 285-296, 326-342 (~60 lines)

**[tests/unit/test_main.py](../../tests/unit/test_main.py)**

- Delete lines 50-108 (~90 lines)

**[tests/unit/test_utils.py](../../tests/unit/test_utils.py)**

- Delete server wiring tests (~75 lines)

**[tests/unit/backends/test_quilt3_backend_core.py](../../tests/unit/backends/test_quilt3_backend_core.py)**

- Delete trivial initialization tests (~130 lines)

### Integration Tests to Add (If Needed)

1. [tests/integration/test_tool_migration_compatibility.py](../../tests/integration/test_tool_migration_compatibility.py)
   - Add factory → backend → tool integration tests (~50 lines)

---

## Success Criteria

1. ✅ Remove ~2,500 lines of wiring tests (69% of analyzed code)
2. ✅ Delete entire obsolete session detection test suite (2,182 lines)
3. ✅ Keep all tests that verify business logic, error handling, edge cases
4. ✅ Ensure integration test coverage for critical paths
5. ✅ All remaining tests pass
6. ✅ Test suite runs faster
7. ✅ Future refactorings don't break tests

---

## Related Documentation

- [08-malformed-auth-tests.md](08-malformed-auth-tests.md) - Example of broken wiring test
- [05-factory-api-mismatch-analysis.md](05-factory-api-mismatch-analysis.md) - Factory implementation issues
- [../../tests/integration/test_integration.py](../../tests/integration/test_integration.py) - Integration test coverage
- [../../tests/e2e/](../../tests/e2e/) - End-to-end test coverage

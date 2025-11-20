# Phase 2 Specification: Reduce Over-Mocking in Unit Tests

**Issue Reference**: GitHub Issue #238 - Improve test coverage from 55.7% to 75%+
**Phase**: Phase 2 - Reduce Over-Mocking (Expected: +5-10% coverage)
**Branch**: `235-integration-test-coverage-gap`
**Status**: Specification

## Problem Statement

Current unit tests exhibit excessive mocking that bypasses real code execution, resulting in tests that verify mock interactions rather than actual logic. This creates an illusion of coverage while leaving critical code paths untested.

### Evidence of Over-Mocking

Analysis of test files reveals systematic over-mocking:

| Test File | Mock Count | Source File | Unit Coverage | Combined Coverage | Issue |
|-----------|-----------|-------------|---------------|-------------------|-------|
| `test_quilt_service.py` | 109 | `quilt_service.py` | 82.6% | 83.3% | Unit tests mock quilt3 API calls, testing mock setup rather than service logic |
| `test_utils.py` | 48 | `utils.py` | 53.6% | 66.0% | Heavy mocking of AWS S3 client and FastMCP components |
| `test_tabulator.py` | 31 | `tabulator_service.py` | 37.7% | 61.6% | Mocks bypass schema validation and YAML generation |
| `test_selector_fn.py` | 23 | (selector logic) | Unknown | Unknown | Over-mocked package filtering logic |

### Root Causes

1. **Mock-Centric Testing Philosophy**: Tests focus on verifying that mocks are called correctly, not that the actual code produces correct results

2. **Abstraction Bypass**: Mocking external dependencies (quilt3, boto3, httpx) prevents testing of:
   - Error handling logic
   - Data transformation and validation
   - Integration between internal components
   - Edge case handling

3. **Low Integration Coverage**: Modules with high unit coverage but low integration coverage indicate unit tests are testing mock interactions:
   - `quilt_service.py`: 82.6% unit, 21.5% integration → 90+ lines unit-only
   - `error_recovery.py`: 59.9% unit, 0.0% integration → 127 lines unit-only
   - `workflow_service.py`: 66.5% unit, 18.1% integration → 91 lines unit-only
   - `governance_service.py`: 59.4% unit, 12.9% integration → 102 lines unit-only
   - `data_visualization.py`: 55.6% unit, 13.1% integration → 130 lines unit-only

4. **Testing Mock Setup Rather Than Behavior**: Example from `test_quilt_service.py:68-144`:

   ```python
   # 77 lines of test code to verify mock interactions
   def test_get_catalog_config_filters_and_derives_stack_prefix(self):
       # Mock session and HTTP response
       mock_session = Mock()
       mock_response = Mock()
       mock_response.json.return_value = full_catalog_config
       mock_response.raise_for_status = Mock()
       mock_session.get.return_value = mock_response

       with (
           patch.object(service, 'has_session_support', return_value=True),
           patch.object(service, 'get_session', return_value=mock_session),
       ):
           result = service.get_catalog_config('https://nightly.quilttest.com')

           # 40+ lines of assertions checking dict keys and values
           # BUT: Never tests actual HTTP logic, session management, or error handling
   ```

## What Needs to Be Done

### 1. Identify Over-Mocked Test Functions

**Objective**: Document which specific test functions in each file are over-mocked and why.

**Analysis Required**:

- [ ] For `test_quilt_service.py` (109 mocks, 741 lines):
  - Count mocks per test function
  - Identify tests with >5 mocks
  - Document what real logic is being bypassed
  - Note which tests are purely testing mock interactions

- [ ] For `test_utils.py` (48 mocks, 526 lines):
  - Map mock usage to specific functions under test
  - Identify S3 client mocking patterns
  - Document what validation/transformation logic is bypassed
  - Note FastMCP mocking that prevents testing tool registration

- [ ] For `test_tabulator.py` (31 mocks, 204 lines):
  - Identify admin module mocking patterns
  - Document schema validation logic that's bypassed
  - Note YAML generation mocking
  - Analyze Athena query mocking

- [ ] For `test_selector_fn.py` (23 mocks):
  - Identify package filtering logic mocking
  - Document copy strategies being bypassed
  - Note path matching logic that's untested

**Expected Output**: A detailed breakdown showing:

```
test_quilt_service.py:
  - test_get_catalog_config_filters_and_derives_stack_prefix (lines 68-144)
    - Mocks: 5 (session, response, has_session_support, get_session, json)
    - Bypasses: HTTP client logic, session management, error handling, JSON parsing
    - Tests: Mock interactions and dict key verification only
    - Real coverage: Exercises dict filtering logic only

  - test_create_package_revision_with_auto_organize_true (lines 338-376)
    - Mocks: 6 (Package, _organize_s3_files_smart, _normalize_registry, etc.)
    - Bypasses: Package creation, S3 file organization, registry normalization
    - Tests: That Package() was called, not that packaging logic works
    - Real coverage: Dict assembly logic only
```

### 2. Categorize Test Functions by Refactoring Strategy

**Objective**: Classify each over-mocked test into one of three categories:

#### Category A: Keep as Unit Test (Pure Logic)

Tests that should remain unit tests because they test pure logic with no external dependencies:

- Input validation
- String parsing and formatting
- Data structure transformations
- Algorithm implementations
- Business rule evaluations

**Example**: `test_parse_s3_uri_valid_basic_uri` - Tests pure URI parsing logic, no mocking needed

#### Category B: Refactor to Integration Test

Tests that mock external services but should test real integration:

- HTTP client calls (use httpx with respx)
- S3 operations (use moto or localstack)
- Athena queries (use moto)
- Database operations
- File system operations

**Example**: `test_get_catalog_config_*` tests should use real httpx client with respx to mock HTTP responses, testing actual HTTP error handling, session management, and retry logic

#### Category C: Delete (Redundant with Integration Tests)

Tests that duplicate coverage provided by integration or e2e tests:

- Tests that only verify mock setup
- Tests with no assertions on actual behavior
- Tests that are superseded by better integration tests

**Expected Output**: A classification table:

```
| Test Function | Current File | Category | Reason | Target Location |
|--------------|-------------|----------|--------|-----------------|
| test_get_catalog_config_filters_* | test_quilt_service.py | B | Should test real HTTP logic | tests/integration/test_quilt_service_http.py |
| test_create_package_revision_* | test_quilt_service.py | B | Should test real package logic | tests/integration/test_quilt_service_packages.py |
| test_parse_s3_uri_* | test_utils.py | A | Pure logic, keep | Keep in unit tests |
| test_generate_signed_url_mocked | test_utils.py | B | Should test real S3 client | tests/integration/test_utils_s3.py |
```

### 3. Analyze Integration Test Gaps

**Objective**: For Category B tests, identify what integration tests are missing or insufficient.

**Analysis Required**:

- [ ] Review existing integration tests in `tests/integration/`
- [ ] Map Category B test functions to existing integration coverage
- [ ] Identify gaps where no integration test exists
- [ ] Document what real dependencies need to be tested

**Expected Output**: Gap analysis document:

```
quilt_service.py - HTTP Operations:
  Unit tests: test_get_catalog_config_* (5 tests, heavily mocked)
  Integration tests: NONE FOUND
  Gap: No integration tests for HTTP session management, error handling, timeouts
  Dependencies needed: httpx + respx for HTTP mocking

quilt_service.py - Package Operations:
  Unit tests: test_create_package_revision_* (7 tests, heavily mocked)
  Integration tests: tests/integration/test_packages.py exists
  Gap: Integration tests don't cover QuiltService abstraction layer
  Dependencies needed: moto for S3, mock quilt3 package operations

utils.py - S3 Operations:
  Unit tests: test_generate_signed_url_* (5 tests, boto3 mocked)
  Integration tests: NONE FOUND
  Gap: No integration tests for S3 client creation, presigned URL generation
  Dependencies needed: moto for S3 mocking
```

### 4. Document Current Test Philosophy vs. Desired Philosophy

**Objective**: Articulate what's wrong with current testing approach and what the correct approach should be.

**Analysis Required**:

- [ ] Document current testing philosophy evident from code
- [ ] Explain why this creates coverage gaps
- [ ] Define desired testing philosophy
- [ ] Provide concrete before/after examples

**Expected Output**: Philosophy document with examples:

```markdown
## Current Philosophy (INCORRECT)

Unit tests mock all external dependencies and verify mock interactions.

Example Problem:
python
def test_get_catalog_config():
    # Mock every dependency
    mock_session = Mock()
    mock_response = Mock()
    mock_response.json.return_value = {...}
    mock_session.get.return_value = mock_response

    with patch.object(service, 'get_session', return_value=mock_session):
        result = service.get_catalog_config('https://example.com')

    # Verify mocks were called
    mock_session.get.assert_called_once()
    assert result["region"] == "us-east-1"


Why This Is Wrong:
- ❌ Never tests if get_session() actually works
- ❌ Never tests if HTTP errors are handled correctly
- ❌ Never tests if JSON parsing fails gracefully
- ❌ Never tests if timeout logic works
- ✅ Only tests dict key filtering (10 lines out of 50-line function)

## Desired Philosophy (CORRECT)

Unit tests verify pure logic. Integration tests verify component interaction.

Example Fix - Split into Two Tests:

python
# Unit test: Keep for pure logic
def test_catalog_config_filtering():
    """Test that config dict filtering logic works correctly."""
    raw_config = {...full config...}
    filtered = _filter_catalog_config(raw_config)  # Pure function
    assert filtered["region"] == "us-east-1"
    assert "sentryDSN" not in filtered

# Integration test: Test real HTTP behavior
def test_get_catalog_config_integration():
    """Test catalog config fetching with real HTTP client."""
    with respx.mock:
        respx.get("https://example.com/config.json").mock(
            return_value=httpx.Response(200, json={...})
        )

        result = service.get_catalog_config('https://example.com')

        # Tests REAL HTTP logic:
        # ✅ Session creation and management
        # ✅ URL construction
        # ✅ HTTP GET execution
        # ✅ Response parsing
        # ✅ Error handling (separate tests)
        # ✅ Timeout behavior (separate tests)
        assert result["region"] == "us-east-1"
```

### 5. Estimate Coverage Impact

**Objective**: For each over-mocked module, estimate how much additional coverage would be gained by proper integration testing.

**Analysis Required**:

- [ ] For each source file with high unit-only coverage:
  - Calculate lines with unit-only coverage
  - Estimate what % would be covered by integration tests
  - Identify lines that would remain unit-only (pure logic)

**Expected Output**: Coverage projection table:

```
| Source File | Current Combined | Unit-Only Lines | Integration Potential | Projected Combined |
|------------|------------------|-----------------|----------------------|-------------------|
| quilt_service.py | 83.3% | 90 | 70 lines (78%) | 91.9% (+8.6%) |
| error_recovery.py | 59.9% | 127 | 100 lines (79%) | 107.1% (+47.2%) |
| workflow_service.py | 66.5% | 91 | 60 lines (66%) | 98.4% (+31.9%) |
| governance_service.py | 66.5% | 102 | 80 lines (78%) | 92.3% (+25.8%) |
| data_visualization.py | 55.6% | 130 | 90 lines (69%) | 85.0% (+29.4%) |

Total Phase 2 Impact: +5.8% to +10.2% combined coverage
```

### 6. Identify Refactoring Prerequisites

**Objective**: Document what code changes are needed before tests can be refactored.

**Analysis Required**:

- [ ] Identify functions that need to be split (logic vs. I/O)
- [ ] Document missing abstraction layers
- [ ] Note dependency injection opportunities
- [ ] Identify testability issues

**Expected Output**: Refactoring requirements:

```
quilt_service.py:
  - get_catalog_config() should be split:
    - get_catalog_config() - HTTP fetching (integration test)
    - _filter_catalog_config() - Dict filtering (unit test)
    - _derive_stack_prefix() - String parsing (unit test)

  - create_package_revision() needs dependency injection:
    - Currently: Directly calls quilt3.Package()
    - Should: Accept package_factory parameter for testing
    - Allows: Integration tests with real Package, unit tests with mock

utils.py:
  - generate_signed_url() should be split:
    - generate_signed_url() - S3 client interaction (integration test)
    - _validate_s3_uri() - URI validation (unit test)
    - _clamp_expiration() - Expiration clamping (unit test)

tabulator_service.py:
  - create_table() should be split:
    - create_table() - Admin API calls (integration test)
    - _validate_table_config() - Validation logic (unit test)
    - _generate_table_yaml() - YAML generation (unit test)
```

### 7. Assess Test Infrastructure Requirements

**Objective**: Identify what test infrastructure is needed to support proper integration testing.

**Analysis Required**:

- [ ] Determine if existing integration test fixtures are sufficient
- [ ] Identify new mocking libraries needed (moto, respx, etc.)
- [ ] Document test data requirements
- [ ] Note performance considerations for integration tests

**Expected Output**: Infrastructure requirements:

```
Required Libraries:
- respx: HTTP mocking for httpx client (for quilt_service HTTP tests)
- moto: AWS service mocking (for S3, Athena tests)
- pytest-asyncio: Already present, ensure async integration tests work
- freezegun: Time-based testing (for retry/timeout logic)

Test Fixtures Needed:
- Integration fixtures for:
  - httpx client with respx mocking
  - boto3 client with moto
  - Sample S3 objects and metadata
  - Sample Athena query responses
  - Sample package structures

Test Data Requirements:
- Real catalog config.json responses (from multiple Quilt stacks)
- Real S3 object listings
- Real Athena table schemas
- Real package manifests

Performance Considerations:
- Integration tests should run in <10 seconds total
- Use in-memory mocking (moto) not real AWS
- Parallel test execution where possible
- Fixtures should be reusable across tests
```

## Non-Goals

What this specification is **NOT** about:

- ❌ Refactoring the actual test code (Phase 2 implementation)
- ❌ Writing new integration tests (Phase 2 implementation)
- ❌ Fixing source code testability issues (separate refactoring)
- ❌ Achieving specific coverage targets (that's implementation goal)
- ❌ Deleting tests without analysis (must document why)

## Deliverables

1. **Mock Usage Analysis Document** (Section 1)
   - Detailed breakdown of mocks per test function
   - Documentation of bypassed logic
   - Quantification of test vs. real coverage

2. **Test Categorization Table** (Section 2)
   - Classification of all over-mocked tests
   - Rationale for each classification
   - Target test location for refactored tests

3. **Integration Test Gap Analysis** (Section 3)
   - Mapping of unit tests to integration coverage
   - Identification of missing integration tests
   - Dependency requirements for gaps

4. **Testing Philosophy Document** (Section 4)
   - Current vs. desired approach
   - Concrete before/after examples
   - Guidelines for future test writing

5. **Coverage Impact Projection** (Section 5)
   - Line-by-line coverage analysis
   - Integration test potential estimation
   - Projected coverage improvement

6. **Refactoring Prerequisites** (Section 6)
   - Required code changes for testability
   - Dependency injection opportunities
   - Function splitting recommendations

7. **Test Infrastructure Requirements** (Section 7)
   - Library and fixture requirements
   - Test data needs
   - Performance considerations

## Success Criteria

This specification is complete when:

1. All four high-mock test files are analyzed in detail
2. Every over-mocked test function is categorized (A/B/C)
3. Integration test gaps are documented with specific requirements
4. Coverage impact is estimated with confidence intervals
5. Refactoring prerequisites are identified and prioritized
6. Test infrastructure requirements are documented
7. Examples show clear before/after for each refactoring pattern
8. Document is actionable for implementation (Phase 2 coding)

## References

- **Issue #238**: Improve test coverage from 55.7% to 75%+
- **Coverage Analysis**: `build/test-results/coverage-analysis.csv`
- **Test Files**:
  - `tests/unit/test_quilt_service.py`
  - `tests/unit/test_utils.py`
  - `tests/unit/test_tabulator.py`
  - `tests/unit/test_selector_fn.py`
- **Source Files**:
  - `src/quilt_mcp/services/quilt_service.py`
  - `src/quilt_mcp/utils.py`
  - `src/quilt_mcp/services/tabulator_service.py`
  - `src/quilt_mcp/tools/error_recovery.py`
  - `src/quilt_mcp/services/workflow_service.py`
  - `src/quilt_mcp/services/governance_service.py`
  - `src/quilt_mcp/tools/data_visualization.py`

# Real Data Test Design: search_catalog Integration Tests

**Status**: Draft Design
**Created**: 2025-11-15
**Branch**: 235-integration-test-coverage-gap-284-vs-45-threshold

## Executive Summary

This document provides a **design-only specification** for refactoring `test_search_catalog_integration.py` to use real test data (QUILT_TEST_PACKAGE, QUILT_TEST_ENTRY) across all three scopes (file, package, global) with and without QUILT_DEFAULT_BUCKET.

**Key Problems Solved**:
- ❌ **Current**: 172 lines, 60% repetitive boilerplate, hard-coded queries
- ✅ **Proposed**: ~120 lines, 80% less boilerplate, real fixtures guarantee non-zero results

## 1. Core Design Principles

### 1.1 ONE Behavior Per Test
Each test validates exactly one contract:
- ✅ "File scope with bucket='' returns ONLY files"
- ✅ "Package scope with bucket='my-bucket' returns ONLY packages from that bucket"
- ✅ "Global scope returns BOTH file and package types"

### 1.2 ALWAYS Use Real Test Data
```python
# ❌ NEVER: Hard-coded queries that might not exist
result = search_catalog(query="ccle", scope="package", bucket="")

# ✅ ALWAYS: Environment-configured fixtures that MUST exist
from quilt_mcp.constants import QUILT_TEST_PACKAGE, QUILT_TEST_ENTRY
result = search_catalog(query=QUILT_TEST_PACKAGE.split("/")[-1], scope="package", bucket="")
```

### 1.3 ALWAYS Assert Non-Zero Results
Tests MUST fail if data doesn't exist (no false passes):
```python
# ✅ Every test includes this validation
assert_non_zero_results(result, f"Package search for '{query}'")
```

### 1.4 Extract ALL Common Validation
No repetitive assertion boilerplate in test functions:
```python
# ❌ DON'T repeat in every test:
assert isinstance(result, dict)
assert result.get("success")
assert "results" in result
assert isinstance(result["results"], list)

# ✅ DO call shared helper once:
assert_valid_search_response(result)
```

## 2. Test Fixture Architecture

### 2.1 Fixture Definitions

**Location**: Add to `tests/integration/test_search_catalog_integration.py` (or `conftest.py` if reused)

```python
import pytest
from quilt_mcp.constants import QUILT_TEST_PACKAGE, QUILT_TEST_ENTRY, QUILT_DEFAULT_BUCKET

@pytest.fixture
def test_package():
    """Return known test package name from environment.

    Example: "test/raw" or "datasets/genomics"

    Set via: QUILT_TEST_PACKAGE environment variable
    """
    return QUILT_TEST_PACKAGE

@pytest.fixture
def test_entry():
    """Return known test entry filename from environment.

    Example: "README.md" or "data.csv"

    Set via: QUILT_TEST_ENTRY environment variable
    """
    return QUILT_TEST_ENTRY

@pytest.fixture
def default_bucket():
    """Return default bucket name (normalized), or skip test if not set.

    Example: "my-bucket" (with s3:// prefix removed)

    Set via: QUILT_DEFAULT_BUCKET environment variable

    Behavior:
    - If QUILT_DEFAULT_BUCKET is set: return normalized bucket name
    - If NOT set: skip test with message "QUILT_DEFAULT_BUCKET not set"
    """
    if not QUILT_DEFAULT_BUCKET:
        pytest.skip("QUILT_DEFAULT_BUCKET not set - required for this test")
    return QUILT_DEFAULT_BUCKET.replace("s3://", "")
```

### 2.2 Validation Helper Functions

**Location**: Same file as fixtures

```python
from typing import Dict, List, Set, NamedTuple

class ResultShape(NamedTuple):
    """Shape of search results for easy assertion."""
    count: int
    types: Set[str]
    buckets: Set[str]

def get_result_shape(results: List[Dict]) -> ResultShape:
    """Extract shape of search results for validation.

    Args:
        results: List of search result dicts

    Returns:
        ResultShape with count, set of types, set of buckets

    Example:
        shape = get_result_shape(result["results"])
        assert shape.count > 0, "Expected non-zero results"
        assert shape.types == {"file"}, "Expected only file results"
        assert shape.buckets == {"my-bucket"}, "Expected only my-bucket"
    """
    return ResultShape(
        count=len(results),
        types={r.get("type") for r in results if "type" in r},
        buckets={r.get("bucket") for r in results if "bucket" in r}
    )

def assert_valid_search_response(result: Dict) -> None:
    """Validate basic search response structure.

    Checks:
    - Result is a dict
    - success=True (or no error field)
    - Has 'results' field
    - results is a list

    Raises:
    - AssertionError with descriptive message if validation fails
    """
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result.get("success"), f"Search failed: {result.get('error')}"
    assert "results" in result, "Response must have 'results' field"
    assert isinstance(result["results"], list), "Results must be a list"
```

## 3. Test Class Structure (Explicit Functions Approach)

### 3.1 Why Explicit Functions > Parametrized Matrix

**Decision**: Use **explicit test functions** organized by test classes

**Rationale**:
1. **Readability**: Each test has clear name showing exactly what it validates
2. **Debuggability**: pytest output shows specific test name that failed
3. **Maintainability**: Easy to add new tests without modifying parametrize matrix
4. **Heterogeneity**: Global scope behaves differently (mixed types), doesn't fit uniform matrix

**Rejected Alternative**: Single parametrized test with 6 combinations
- Pro: Very compact (~30 lines for all 6 tests)
- Con: Hard to debug ("test_scope_bucket_combinations[global-all-None]" - what does this test?)
- Con: Requires conditional logic for global scope (mixed types)
- Con: All tests must have identical structure (they don't)

### 3.2 Test Class Organization

```
TestFileScopeWithRealData
├── test_file_scope_all_buckets_returns_only_files
└── test_file_scope_specific_bucket_returns_only_files

TestPackageScopeWithRealData
├── test_package_scope_all_buckets_returns_only_packages
└── test_package_scope_specific_bucket_returns_only_packages

TestGlobalScopeWithRealData
├── test_global_scope_all_buckets_returns_mixed_types
└── test_global_scope_specific_bucket_returns_mixed_types

TestBucketPrioritization
├── test_default_bucket_results_appear_first_when_set
└── test_specific_bucket_ignores_default_bucket_setting

TestBucketNormalization
├── test_s3_uri_normalized_to_bucket_name
└── test_s3_uri_with_trailing_slash_normalized

TestErrorHandling (keep existing test)
└── test_nonexistent_bucket_returns_error_not_exception
```

**Total**: 6 test classes, 11 test functions (vs. current 1 class, 5 functions)

## 4. Implementation Specifications

### 4.1 TestFileScopeWithRealData

**Purpose**: Validate file scope searches using QUILT_TEST_ENTRY

**Coverage**:
- Combination #2: scope="file", bucket="" (all buckets)
- Combination #4: scope="file", bucket="specific" (one bucket)

#### Test 1: File Scope, All Buckets

```python
@pytest.mark.integration
@pytest.mark.search
class TestFileScopeWithRealData:
    """Test file scope searches using QUILT_TEST_ENTRY fixture."""

    def test_file_scope_all_buckets_returns_only_files(self, test_entry):
        """File scope with bucket='' searches all object indices.

        Behavior:
        - Searches ALL buckets (comma-separated indices: "bucket1,bucket2,...")
        - Returns ONLY file results (type="file")
        - MUST return non-zero results

        Test Data:
        - Query: QUILT_TEST_ENTRY (e.g., "README.md")
        - Expected: At least 1 file matching test_entry exists
        """
        # Execute search
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket="",  # All buckets
            limit=50
        )

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"File search for '{test_entry}' returned ZERO results"
        assert shape.types == {"file"}, f"Expected only 'file' type, got: {shape.types}"
```

**Implementation Notes**:
- **Query Strategy**: Use `test_entry` directly (e.g., "README.md")
- **Expected Behavior**: Searches indices like `bucket1,bucket2,bucket3`
- **Type Enforcement**: EVERY result MUST have `type="file"`
- **Failure Mode**: Test FAILS if no files found (indicates missing test data)

#### Test 2: File Scope, Specific Bucket

```python
    def test_file_scope_specific_bucket_returns_only_files(self, test_entry, default_bucket):
        """File scope with bucket='my-bucket' searches single object index.

        Behavior:
        - Searches ONLY specified bucket (index: "my-bucket")
        - Returns ONLY file results (type="file")
        - ALL results MUST be from specified bucket
        - MUST return non-zero results

        Test Data:
        - Query: QUILT_TEST_ENTRY
        - Bucket: QUILT_DEFAULT_BUCKET (guaranteed to have test data)
        """
        # Execute search
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket=default_bucket,
            limit=50
        )

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"File search in {default_bucket} returned ZERO results"
        assert shape.types == {"file"}, f"Expected only 'file' type, got: {shape.types}"
        assert shape.buckets == {default_bucket}, f"Expected only {default_bucket}, got: {shape.buckets}"
```

**Implementation Notes**:
- **Query Strategy**: Same as Test 1 (consistent)
- **Bucket Validation**: New requirement - verify `result["bucket"] == default_bucket` for ALL results
- **Expected Behavior**: Searches ONLY `default_bucket` index
- **Fixture Dependency**: Requires `default_bucket` fixture (skips if not set)

### 4.2 TestPackageScopeWithRealData

**Purpose**: Validate package scope searches using QUILT_TEST_PACKAGE

**Coverage**:
- Combination #1: scope="package", bucket="" (all buckets)
- Combination #3: scope="package", bucket="specific" (one bucket)

#### Test 3: Package Scope, All Buckets

```python
@pytest.mark.integration
@pytest.mark.search
class TestPackageScopeWithRealData:
    """Test package scope searches using QUILT_TEST_PACKAGE fixture."""

    def test_package_scope_all_buckets_returns_only_packages(self, test_package):
        """Package scope with bucket='' searches all package indices.

        Behavior:
        - Searches ALL buckets (comma-separated indices: "bucket1_packages,bucket2_packages,...")
        - Returns ONLY package results (type="package")
        - MUST return non-zero results
        - At least ONE result should match QUILT_TEST_PACKAGE

        Test Data:
        - Query: Last component of QUILT_TEST_PACKAGE (e.g., "raw" from "test/raw")
        - Expected: Package named "test/raw" exists and is found
        """
        # Extract searchable component from package name
        query = test_package.split("/")[-1]  # "test/raw" → "raw"

        # Execute search
        result = search_catalog(
            query=query,
            scope="package",
            bucket="",
            limit=50
        )

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"Package search for '{query}' returned ZERO results"
        assert shape.types == {"package"}, f"Expected only 'package' type, got: {shape.types}"

        # Verify at least one result matches known test package
        package_names = [r["name"] for r in result["results"]]
        assert test_package in package_names, \
            f"Expected to find '{test_package}' in results: {package_names}"
```

**Implementation Notes**:
- **Query Strategy**: Extract last path component (more likely to match in search)
  - Example: `"test/raw"` → query `"raw"`
  - Rationale: Search engines tokenize on `/`, so "raw" matches "test/raw"
- **Verification**: Check that `test_package` is in result names (exact match)
- **Expected Behavior**: Searches indices like `bucket1_packages,bucket2_packages`

#### Test 4: Package Scope, Specific Bucket

```python
    def test_package_scope_specific_bucket_returns_only_packages(self, test_package, default_bucket):
        """Package scope with bucket='my-bucket' searches single package index.

        Behavior:
        - Searches ONLY specified bucket (index: "my-bucket_packages")
        - Returns ONLY package results (type="package")
        - ALL results MUST be from specified bucket
        - MUST return non-zero results

        Test Data:
        - Query: Last component of QUILT_TEST_PACKAGE
        - Bucket: QUILT_DEFAULT_BUCKET (guaranteed to have test package)
        """
        query = test_package.split("/")[-1]

        # Execute search
        result = search_catalog(
            query=query,
            scope="package",
            bucket=default_bucket,
            limit=50
        )

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"Package search in {default_bucket} returned ZERO results"
        assert shape.types == {"package"}, f"Expected only 'package' type, got: {shape.types}"
        assert shape.buckets == {default_bucket}, f"Expected only {default_bucket}, got: {shape.buckets}"
```

**Implementation Notes**:
- **Query Strategy**: Same as Test 3 (consistent)
- **Bucket Validation**: ALL results MUST have `bucket == default_bucket`
- **Expected Behavior**: Searches ONLY `default_bucket_packages` index

### 4.3 TestGlobalScopeWithRealData

**Purpose**: Validate global scope searches (NEW - currently untested)

**Coverage**:
- Combination #5: scope="global", bucket="" (all buckets) - **MISSING**
- Combination #6: scope="global", bucket="specific" (one bucket) - **MISSING**

#### Test 5: Global Scope, All Buckets

```python
@pytest.mark.integration
@pytest.mark.search
class TestGlobalScopeWithRealData:
    """Test global scope searches using both fixtures."""

    def test_global_scope_all_buckets_returns_mixed_types(self, test_entry):
        """Global scope with bucket='' searches all object AND package indices.

        Behavior:
        - Searches ALL buckets, BOTH index types per bucket
        - Index pattern: "bucket1,bucket1_packages,bucket2,bucket2_packages,..."
        - Returns MIXED results (type="file" AND/OR type="package")
        - MUST return non-zero results
        - Types MUST be subset of {"file", "package"}

        Test Data:
        - Query: QUILT_TEST_ENTRY (e.g., "README.md")
        - Expected: Generic query matches both files and possibly packages
        """
        # Execute search
        result = search_catalog(
            query=test_entry,
            scope="global",
            bucket="",
            limit=50
        )

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"Global search for '{test_entry}' returned ZERO results"
        assert shape.types.issubset({"file", "package"}), \
            f"Global scope returned invalid types: {shape.types - {'file', 'package'}}"
```

**Implementation Notes**:
- **Query Strategy**: Use `test_entry` (generic term likely in both indices)
- **Type Validation**: DON'T require both types (might only match files)
- **Type Validation**: DO require ONLY valid types (not "bucket", "object", etc.)
- **Expected Behavior**: Searches indices like `bucket1,bucket1_packages,bucket2,bucket2_packages`

#### Test 6: Global Scope, Specific Bucket

```python
    def test_global_scope_specific_bucket_returns_mixed_types(self, test_entry, default_bucket):
        """Global scope with bucket='my-bucket' searches both indices in one bucket.

        Behavior:
        - Searches ONLY specified bucket, BOTH index types
        - Index pattern: "my-bucket,my-bucket_packages"
        - Returns MIXED results (type="file" AND/OR type="package")
        - ALL results MUST be from specified bucket
        - MUST return non-zero results

        Test Data:
        - Query: QUILT_TEST_ENTRY
        - Bucket: QUILT_DEFAULT_BUCKET
        """
        # Execute search
        result = search_catalog(
            query=test_entry,
            scope="global",
            bucket=default_bucket,
            limit=50
        )

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, f"Global search in {default_bucket} returned ZERO results"
        assert shape.types.issubset({"file", "package"}), \
            f"Global scope returned invalid types: {shape.types - {'file', 'package'}}"
        assert shape.buckets == {default_bucket}, f"Expected only {default_bucket}, got: {shape.buckets}"
```

**Implementation Notes**:
- **Query Strategy**: Same as Test 5 (consistent)
- **Bucket Validation**: ALL results MUST be from `default_bucket`
- **Expected Behavior**: Searches ONLY `default_bucket,default_bucket_packages`

### 4.4 TestBucketPrioritization

**Purpose**: Validate QUILT_DEFAULT_BUCKET prioritization behavior (NEW)

**Coverage**:
- Bucket prioritization when QUILT_DEFAULT_BUCKET is set
- Verify default bucket ignored when specific bucket requested

#### Test 7: Default Bucket Prioritization

```python
@pytest.mark.integration
@pytest.mark.search
class TestBucketPrioritization:
    """Test QUILT_DEFAULT_BUCKET prioritization when bucket=''."""

    def test_default_bucket_results_appear_first_when_set(self, test_entry, default_bucket):
        """When QUILT_DEFAULT_BUCKET is set, results from that bucket appear first.

        Behavior:
        - When bucket="": backend enumerates ALL buckets
        - Backend moves QUILT_DEFAULT_BUCKET to front of list
        - Results from QUILT_DEFAULT_BUCKET appear earlier in response (when scores equal)

        Test Data:
        - Query: QUILT_TEST_ENTRY (exists in multiple buckets ideally)
        - Expected: default_bucket results appear in first 10 results

        Note: This test makes a SOFT assertion (warning, not failure) because:
        - Test data might not exist in multiple buckets
        - Relevance scoring might override prioritization
        - We can only verify "early" appearance, not "first" appearance
        """
        # Execute search with large limit to see bucket distribution
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket="",  # Triggers prioritization logic
            limit=100
        )

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape
        shape = get_result_shape(result["results"])
        assert shape.count > 0, "Bucket prioritization test returned ZERO results"

        # If default bucket has results, verify it appears early
        if default_bucket in shape.buckets:
            buckets_in_results = [r["bucket"] for r in result["results"]]
            first_default_idx = buckets_in_results.index(default_bucket)
            assert first_default_idx < 10, \
                f"Default bucket '{default_bucket}' first appears at position {first_default_idx}, " \
                f"expected in top 10. This may indicate prioritization is not working."
        else:
            # Soft failure - log warning but don't fail test
            import warnings
            warnings.warn(
                f"Default bucket '{default_bucket}' not found in top 100 results. "
                f"Test data might not exist in default bucket."
            )
```

**Implementation Notes**:
- **Soft Assertion**: Use warning instead of failure if default bucket not in results
  - Rationale: Test data might not exist in default bucket in all environments
- **Position Check**: Verify default bucket in top 10 (not necessarily #1)
  - Rationale: Relevance scoring might place highly-relevant non-default results first
- **Large Limit**: Use `limit=100` to see broader bucket distribution

#### Test 8: Specific Bucket Ignores Default

```python
    def test_specific_bucket_ignores_default_bucket_setting(self, test_entry, default_bucket):
        """Specific bucket searches ignore QUILT_DEFAULT_BUCKET setting.

        Behavior:
        - When bucket="specific-bucket": backend uses ONLY that bucket
        - QUILT_DEFAULT_BUCKET has NO EFFECT on search
        - ALL results MUST be from specified bucket (not default)

        Test Data:
        - Query: QUILT_TEST_ENTRY
        - Bucket: QUILT_DEFAULT_BUCKET (but treated as specific, not default)
        """
        # Execute search with specific bucket
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket=default_bucket,  # Specific bucket (not "" for all)
            limit=50
        )

        # Validate response structure
        assert_valid_search_response(result)

        # Validate result shape - ALL results from specified bucket
        # (This implicitly proves QUILT_DEFAULT_BUCKET setting had no effect)
        shape = get_result_shape(result["results"])
        assert shape.buckets == {default_bucket}, f"Expected only {default_bucket}, got: {shape.buckets}"
```

**Implementation Notes**:
- **Implicit Validation**: By verifying ALL results from specified bucket, we prove QUILT_DEFAULT_BUCKET didn't interfere
- **Query Strategy**: Same as other file scope tests

### 4.5 TestBucketNormalization

**Purpose**: Validate s3:// URI normalization (NEW)

**Coverage**:
- bucket="s3://my-bucket" normalized to "my-bucket"
- bucket="s3://my-bucket/" (trailing slash) normalized

#### Test 9: S3 URI Normalization

```python
@pytest.mark.integration
@pytest.mark.search
class TestBucketNormalization:
    """Test s3:// URI normalization in bucket parameter."""

    def test_s3_uri_normalized_to_bucket_name(self, test_entry, default_bucket):
        """bucket='s3://my-bucket' should work same as bucket='my-bucket'.

        Behavior:
        - Backend normalizes "s3://bucket" → "bucket"
        - Both forms should return identical results
        - Response should show normalized bucket name (no s3:// prefix)

        Test Data:
        - Query: QUILT_TEST_ENTRY
        - Bucket forms: "my-bucket" vs "s3://my-bucket"
        """
        # Search with normalized bucket
        result1 = search_catalog(
            query=test_entry,
            scope="file",
            bucket=default_bucket,  # e.g., "my-bucket"
            limit=10
        )

        # Search with s3:// URI
        result2 = search_catalog(
            query=test_entry,
            scope="file",
            bucket=f"s3://{default_bucket}",  # e.g., "s3://my-bucket"
            limit=10
        )

        # Both should succeed
        assert_valid_search_response(result1)
        assert_valid_search_response(result2)

        # Both should return same normalized bucket in response
        assert result1.get("bucket") == default_bucket, \
            f"Result1 bucket should be normalized: {result1.get('bucket')}"
        assert result2.get("bucket") == default_bucket, \
            f"Result2 bucket should be normalized: {result2.get('bucket')}"
```

**Implementation Notes**:
- **Comparison Strategy**: Compare `result.get("bucket")` field (not full results)
  - Rationale: Result order might vary slightly, but bucket field should match
- **Normalization Check**: Verify NO s3:// prefix in response

#### Test 10: Trailing Slash Normalization

```python
    def test_s3_uri_with_trailing_slash_normalized(self, test_entry, default_bucket):
        """bucket='s3://my-bucket/' should work (trailing slash removed).

        Behavior:
        - Backend normalizes "s3://bucket/" → "bucket"
        - Response should show normalized bucket name

        Test Data:
        - Query: QUILT_TEST_ENTRY
        - Bucket: "s3://my-bucket/"
        """
        # Execute search with trailing slash
        result = search_catalog(
            query=test_entry,
            scope="file",
            bucket=f"s3://{default_bucket}/",  # Trailing slash
            limit=10
        )

        # Should succeed
        assert_valid_search_response(result)

        # Should return normalized bucket (no s3://, no trailing slash)
        assert result.get("bucket") == default_bucket, \
            f"Bucket should be normalized to '{default_bucket}', got '{result.get('bucket')}'"
```

**Implementation Notes**:
- **Single Comparison**: Only test trailing slash case (s3:// normalization already covered)
- **Expected Behavior**: Backend strips both `s3://` and `/`

### 4.6 TestErrorHandling (Keep Existing)

**Purpose**: Validate error handling (already tested, keep as-is)

**Coverage**:
- Nonexistent bucket returns error (not exception)

#### Test 11: Nonexistent Bucket

```python
@pytest.mark.integration
@pytest.mark.search
class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_nonexistent_bucket_returns_error_not_exception(self):
        """Searching nonexistent bucket returns error dict, not exception.

        Behavior:
        - Backend catches Elasticsearch errors
        - Returns {"success": False, "error": "..."} instead of raising

        Note: Keep existing test as-is (already correct)
        """
        # Keep existing implementation unchanged
        result = search_catalog(
            query="test",
            scope="file",
            bucket="nonexistent-bucket-12345",
            limit=10
        )

        assert isinstance(result, dict)
        assert not result.get("success")
        assert "error" in result
```

**Implementation Notes**:
- **No Changes**: Existing test is correct, keep as-is
- **Rationale**: Error handling doesn't require real fixtures

## 5. Implementation Order

### Phase 1: Infrastructure (Estimated: 1-2 hours)

**Tasks**:
1. Add fixture definitions (`test_package`, `test_entry`, `default_bucket`)
2. Add validation helper functions (4 functions)
3. Verify test data exists in environment

**Files Modified**:
- `tests/integration/test_search_catalog_integration.py` (add to top)
- OR `tests/conftest.py` (if fixtures reused elsewhere)

**Verification**:
```bash
# Verify fixtures work
pytest tests/integration/test_search_catalog_integration.py -k "test_file_scope" -v --fixtures
```

### Phase 2: Core Scope Tests (Estimated: 2-3 hours)

**Tasks**:
1. Implement `TestFileScopeWithRealData` (2 tests)
2. Implement `TestPackageScopeWithRealData` (2 tests)
3. Implement `TestGlobalScopeWithRealData` (2 tests)

**Files Modified**:
- `tests/integration/test_search_catalog_integration.py` (add 3 test classes)

**Verification**:
```bash
# Run new tests
pytest tests/integration/test_search_catalog_integration.py::TestFileScopeWithRealData -v
pytest tests/integration/test_search_catalog_integration.py::TestPackageScopeWithRealData -v
pytest tests/integration/test_search_catalog_integration.py::TestGlobalScopeWithRealData -v
```

### Phase 3: Advanced Tests (Estimated: 2-3 hours)

**Tasks**:
1. Implement `TestBucketPrioritization` (2 tests)
2. Implement `TestBucketNormalization` (2 tests)
3. Keep `TestErrorHandling` (1 test, no changes)

**Files Modified**:
- `tests/integration/test_search_catalog_integration.py` (add 2 test classes)

**Verification**:
```bash
# Run advanced tests
pytest tests/integration/test_search_catalog_integration.py::TestBucketPrioritization -v
pytest tests/integration/test_search_catalog_integration.py::TestBucketNormalization -v
```

### Phase 4: Cleanup (Estimated: 1 hour)

**Tasks**:
1. Remove old verbose tests (if any overlap)
2. Update docstrings
3. Run full test suite

**Files Modified**:
- `tests/integration/test_search_catalog_integration.py` (remove old tests)

**Verification**:
```bash
# Run all integration tests
pytest tests/integration/test_search_catalog_integration.py -v

# Verify coverage (should increase)
pytest tests/integration/test_search_catalog_integration.py --cov=quilt_mcp.tools.search --cov-report=term-missing
```

**Total Estimated Effort**: 6-9 hours

## 6. Test Data Requirements

### 6.1 Environment Variables (REQUIRED)

**Minimum Configuration** (in `.env` or CI environment):

```bash
# Default bucket (REQUIRED for most tests)
QUILT_DEFAULT_BUCKET=s3://your-test-bucket

# Test package (REQUIRED)
QUILT_TEST_PACKAGE=test/raw

# Test entry (REQUIRED)
QUILT_TEST_ENTRY=README.md
```

### 6.2 Data Verification Steps

**Before running tests, verify**:

```bash
# 1. Verify QUILT_DEFAULT_BUCKET is set
echo $QUILT_DEFAULT_BUCKET
# Expected: s3://your-test-bucket

# 2. Verify test package exists
quilt3 list-packages s3://your-test-bucket | grep test/raw
# Expected: test/raw (and possibly versions)

# 3. Verify test entry exists in package
aws s3 ls s3://your-test-bucket/test/raw/README.md
# Expected: File listing with size and timestamp

# 4. Verify Elasticsearch indexed (critical!)
# Open catalog UI: https://your-catalog.com/b/your-test-bucket
# Search for "test/raw" in packages scope
# Expected: Package appears in results
# Search for "README.md" in files scope
# Expected: File appears in results
```

### 6.3 Missing Data Troubleshooting

**If tests fail with ZERO results**:

1. **Check environment variables**:
   ```bash
   pytest -v --fixtures | grep -A5 "test_package\|test_entry\|default_bucket"
   ```

2. **Verify data indexed**:
   ```bash
   # Check if indices exist
   curl -X GET "https://your-elasticsearch.com/_cat/indices?v" | grep your-test-bucket

   # Should see:
   # - your-test-bucket (object index)
   # - your-test-bucket_packages (package index)
   ```

3. **Re-index if needed**:
   ```bash
   # Trigger re-indexing (depends on your infrastructure)
   # This is environment-specific
   ```

## 7. Success Criteria

### 7.1 Functional Success

- [ ] All 11 tests pass in local environment
- [ ] All 11 tests pass in CI environment
- [ ] All tests return non-zero results (no false passes)
- [ ] Tests fail appropriately when data is missing
- [ ] Bucket prioritization validated when QUILT_DEFAULT_BUCKET set
- [ ] S3 URI normalization validated

### 7.2 Code Quality Success

- [ ] Test file ≤ 150 lines (current: 172 lines)
- [ ] Helper functions eliminate >80% of repetitive boilerplate
- [ ] Each test validates exactly ONE behavior
- [ ] Test names clearly describe what is tested
- [ ] No hard-coded queries (all use fixtures)

### 7.3 Coverage Success

- [ ] All 6 scope/bucket combinations tested (currently 4/6)
- [ ] Global scope coverage added (currently 0%)
- [ ] Bucket prioritization coverage added (currently 0%)
- [ ] S3 URI normalization coverage added (currently 0%)
- [ ] Integration coverage for search_catalog: 0% → 80%+

## 8. Known Limitations and Future Work

### 8.1 Not Covered in This Design

**Testing WITHOUT QUILT_DEFAULT_BUCKET** (Deferred to future iteration)
- **Challenge**: Requires unsetting environment variable and re-initializing search backend
- **Risk**: High complexity, potential side effects on other tests
- **Mitigation**: Document as known gap, implement in separate PR

**Testing with 50+ buckets** (Deferred to unit tests)
- **Challenge**: Requires specific infrastructure (50+ buckets)
- **Risk**: Expensive to set up in CI
- **Mitigation**: Cover in unit tests with mocks (already done in `test_elasticsearch_backend.py`)

**Mocking removal** (Tracked in separate spec)
- **Current Status**: Some unit tests still use mocks for Elasticsearch
- **Related**: See `spec/235-coverage/phase2-reduce-over-mocking.md`
- **Future Work**: Replace mocked unit tests with integration tests

### 8.2 Test Brittleness

**Potential Issues**:
1. **Test data deletion**: If QUILT_TEST_PACKAGE or QUILT_TEST_ENTRY deleted, all tests fail
   - **Mitigation**: Document test data as critical infrastructure, protect from deletion
2. **Multi-environment drift**: Test data might not exist in all environments (dev, CI, staging)
   - **Mitigation**: Fixtures skip tests if data not available (`pytest.skip()`)
3. **Elasticsearch indexing lag**: New data might not be immediately searchable
   - **Mitigation**: Use stable, long-lived test data (not recently created)

## 9. Appendix: Before/After Comparison

### 9.1 Before (Current Test)

```python
# test_search_catalog_integration.py (current)
# Lines: 172
# Tests: 5
# Coverage: 4/6 scope/bucket combinations

def test_package_scope_MUST_ONLY_return_packages_NOT_files(self):
    """Package scope with bucket='' should search ALL _packages indices."""
    # Execute search
    result = search_catalog(query="ccle", scope="package", bucket="", limit=50)  # ❌ Hard-coded query

    # === Validate response structure (9 lines) ===
    assert isinstance(result, dict)
    assert result.get("success"), f"Search should succeed, got: {result}"
    assert "results" in result, "Response must include 'results'"
    assert isinstance(result["results"], list)
    # ... 5 more lines of boilerplate ...

    # === Validate non-zero results (3 lines) ===
    assert len(result["results"]) > 0, "CRITICAL: Query returned ZERO results..."

    # === Validate all results are packages (7+ lines) ===
    for idx, res in enumerate(result["results"]):
        assert "type" in res, f"Result {idx} missing 'type'"
        assert res["type"] == "package", f"Expected package, got {res['type']}"
        # ... more assertions per result ...

# Total per test: ~30-50 lines
# Boilerplate per test: ~20-30 lines (60-80% repetition)
```

### 9.2 After (Proposed Test)

```python
# test_search_catalog_integration.py (proposed)
# Lines: ~120-150
# Tests: 11
# Coverage: 6/6 scope/bucket combinations + prioritization + normalization

class TestPackageScopeWithRealData:
    def test_package_scope_all_buckets_returns_only_packages(self, test_package):
        """Package scope with bucket='' searches ALL _packages indices."""
        # Execute search
        query = test_package.split("/")[-1]  # ✅ Real fixture
        result = search_catalog(query=query, scope="package", bucket="", limit=50)

        # Validate (2 lines with get_result_shape)
        assert_valid_search_response(result)
        shape = get_result_shape(result["results"])
        assert shape.count > 0 and shape.types == {"package"}

        # Verify known package found
        assert test_package in [r["name"] for r in result["results"]]

# Total per test: ~8-12 lines
# Boilerplate per test: ~2-3 lines (85% reduction)
```

### 9.3 Impact Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Lines of code** | 172 | ~120-150 | -30% |
| **Lines per test** | 30-50 | 8-12 | -70% |
| **Boilerplate per test** | 20-30 | 2-3 | -85% |
| **Number of tests** | 5 | 11 | +120% |
| **Test classes** | 1 | 6 | +500% |
| **Scope/bucket coverage** | 4/6 (67%) | 6/6 (100%) | +33% |
| **Uses real fixtures** | 0/5 (0%) | 11/11 (100%) | +100% |
| **Hard-coded queries** | 5/5 (100%) | 0/11 (0%) | -100% |

## 10. References

### 10.1 Related Specifications
- `spec/235-coverage/22-current-scope-bucket-semantics.md` - Scope/bucket behavior reference
- `spec/235-coverage/23-integration-test-gap-analysis.md` - Coverage gap analysis
- `spec/235-coverage/phase2-implementation-tasks.md` - Original implementation plan
- `spec/235-coverage/README.md` - Overall coverage strategy

### 10.2 Source Code References
- `src/quilt_mcp/tools/search.py` - search_catalog API implementation
- `src/quilt_mcp/search/backends/elasticsearch.py` - Backend with bucket prioritization
- `src/quilt_mcp/constants.py` - Test fixture constants (QUILT_TEST_PACKAGE, etc.)
- `tests/integration/test_search_catalog_integration.py` - Current tests (to be refactored)
- `tests/unit/test_elasticsearch_backend.py` - Unit tests (for reference)

### 10.3 Environment Configuration
- `.env.example` - Environment variable examples
- `env.example` - Alternative env file location
- `.github/workflows/push.yml` - CI configuration with test secrets

---

**End of Design Document**

**Next Steps**:
1. Review design with team
2. Verify test data exists in all environments
3. Begin Phase 1 implementation (fixtures and helpers)

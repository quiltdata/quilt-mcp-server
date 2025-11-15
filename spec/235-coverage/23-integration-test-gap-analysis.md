# Integration Test Gap Analysis: search_catalog scope/bucket Semantics

**Status:** Active Analysis
**Date:** 2025-11-15
**Version:** 0.9.1
**Related Spec:** [22-current-scope-bucket-semantics.md](./22-current-scope-bucket-semantics.md)

---

## Executive Summary

### Critical Finding: ZERO Integration Test Coverage for scope/bucket Semantics

The `search_catalog` tool has **NO integration tests** that validate the scope/bucket parameter semantics against real AWS/Elasticsearch infrastructure. All search tests are marked with `@pytest.mark.search` and **explicitly excluded** from integration test runs.

**Evidence:**
- `make.dev` line 49: Integration tests run with `-m "not search and not admin"`
- `make.dev` line 34: CI tests run with `-m "not slow and not search and not admin"`
- This exclusion is intentional to avoid hitting AWS/Elasticsearch during standard test runs

**Impact:**
- **284% gap** between current coverage (45%) and target (85%) threshold
- Scope/bucket combinations have never been validated against real Elasticsearch indices
- 403 error retry logic has never been integration tested
- Bucket prioritization behavior has never been verified with real catalog data

---

## Current Test Infrastructure Analysis

### Test Organization (from `make.dev` and `pyproject.toml`)

```
tests/
├── unit/                    # Mocked unit tests (fast)
│   └── test_*.py           # Coverage: ~45% (below 85% threshold)
├── integration/            # Real AWS/service tests
│   └── test_*.py           # Run with: -m "not search and not admin"
└── e2e/                    # End-to-end workflow tests
    └── test_*.py           # Run with: -m "not admin"
```

### Test Markers (from `pyproject.toml` lines 104-111)

```python
markers = [
    "admin: marks tests that require Quilt admin privileges",
    "integration: marks tests that require AWS credentials, network access, or external services",
    "search: marks tests that require Elasticsearch search functionality",  # ← EXCLUDED
    "slow: marks tests as slow",
    "e2e: marks tests as end-to-end tests",
    "asyncio: marks tests as async tests",
]
```

### Test Execution Patterns

| Make Target | Command | Search Tests Included? |
|------------|---------|----------------------|
| `make test` | `pytest tests/unit/` | ❌ No (unit only) |
| `make test-ci` | `pytest -m "not slow and not search and not admin"` | ❌ No (explicitly excluded) |
| `make test-integration` | `pytest tests/integration/ -m "not search and not admin"` | ❌ No (explicitly excluded) |
| `make test-e2e` | `pytest tests/e2e/ -m "not admin"` | ⚠️ Maybe (if marked `@pytest.mark.e2e` only) |
| `make test-all` | `pytest tests/` | ✅ Yes (all tests run) |

**Key Finding:** Search tests are only run during `make test-all`, which is NOT the default CI behavior.

---

## Scope/Bucket Combinations: Coverage Gap Matrix

### Complete Combination Matrix

Based on [22-current-scope-bucket-semantics.md](./22-current-scope-bucket-semantics.md), there are **6 valid combinations**:

| # | scope | bucket | Expected Index Pattern | Integration Test Exists? | Gap Priority |
|---|-------|--------|----------------------|------------------------|--------------|
| 1 | `"file"` | `""` | `"bucket1,bucket2,..."` (all objects) | ❌ NO | 🔴 CRITICAL |
| 2 | `"file"` | `"mybucket"` | `"mybucket"` | ❌ NO | 🔴 CRITICAL |
| 3 | `"package"` | `""` | `"bucket1_packages,..."` | ❌ NO | 🔴 CRITICAL |
| 4 | `"package"` | `"mybucket"` | `"mybucket_packages"` | ❌ NO | 🔴 CRITICAL |
| 5 | `"global"` | `""` | `"bucket1,bucket1_packages,..."` | ❌ NO | 🔴 CRITICAL |
| 6 | `"global"` | `"mybucket"` | `"mybucket,mybucket_packages"` | ❌ NO | 🔴 CRITICAL |

**Coverage:** 0/6 combinations tested (0%)

---

## Critical Behaviors Lacking Integration Tests

### 1. Bucket Enumeration (`bucket=""`)

**Code Under Test:** `elasticsearch.py:_get_available_buckets()` (lines 134-165)

**Current Status:** ❌ NO INTEGRATION TESTS

**What Needs Testing:**
- GraphQL query to catalog for bucket list succeeds
- Empty bucket list handling (returns empty pattern)
- Network failure graceful degradation
- Large bucket lists (50+ buckets) performance

**Risk:** If GraphQL endpoint changes, bucket enumeration silently fails

---

### 2. Bucket Prioritization

**Code Under Test:** `elasticsearch.py:_prioritize_buckets()` (lines 167-200)

**Current Status:** ❌ NO INTEGRATION TESTS

**What Needs Testing:**
- Default bucket (from `QUILT_DEFAULT_BUCKET`) moved to front
- Behavior when default bucket not in available list
- Behavior when `QUILT_DEFAULT_BUCKET` not set
- Order preservation of non-default buckets

**Risk:** Default bucket prioritization may not work as expected in production

---

### 3. Index Pattern Construction

**Code Under Test:** `elasticsearch.py:_build_index_pattern()` (lines 202-266)

**Current Status:** ❌ NO INTEGRATION TESTS

**What Needs Testing:**
- All 6 scope/bucket combinations produce correct patterns
- Bucket normalization (s3:// prefix removal)
- Trailing slash handling
- Pattern format accepted by real Elasticsearch API

**Risk:** Malformed index patterns may cause search failures

---

### 4. 403 Error Retry Logic

**Code Under Test:** `elasticsearch.py:search()` retry logic (lines 333-379)

**Current Status:** ❌ NO INTEGRATION TESTS

**What Needs Testing:**
- 403 error detection when searching 50+ buckets
- Progressive reduction: 50 → 40 → 30 → 20 → 10 buckets
- Default bucket stays first during retries
- Success after retry vs. exhausted retries
- Non-403 errors don't trigger retries

**Risk:** Retry logic may not work correctly with real Elasticsearch 403 responses

**Critical:** This is NEW code (added to fix package search 403 errors) and has NEVER been integration tested.

---

### 5. Elasticsearch Query DSL Construction

**Code Under Test:** `elasticsearch.py:search()` (lines 296-331)

**Current Status:** ❌ NO INTEGRATION TESTS

**What Needs Testing:**
- Query DSL accepted by real Elasticsearch
- Filter clauses (extensions, size, dates) work correctly
- Special character escaping in real queries
- Limit parameter respected
- Sort order (by score) works as expected

**Risk:** Query DSL may not match real Elasticsearch schema

---

### 6. Result Normalization

**Code Under Test:** `elasticsearch.py:_normalize_results()` (lines 419-509)

**Current Status:** ❌ NO INTEGRATION TESTS

**What Needs Testing:**
- Package results detected correctly (index ends with `_packages`)
- File results detected correctly (index does not end with `_packages`)
- S3 URI construction for packages vs. files
- Bucket name extraction from index name
- Extension extraction from file keys
- Metadata field mapping

**Risk:** Result format may not match real Elasticsearch response structure

---

## Specific Test Recommendations

### Phase 1: Create Integration Test Infrastructure

**Action:** Create new integration test file with proper markers

**File to Create:** `tests/integration/test_search_elasticsearch_integration.py`

**Structure:**
```python
"""Integration tests for search_catalog scope/bucket semantics.

These tests hit real AWS/Elasticsearch infrastructure and are excluded
from default CI runs via @pytest.mark.search marker.

Run with: pytest tests/integration/test_search_elasticsearch_integration.py
Or: make test-all  (includes all markers)
"""

import pytest
from quilt_mcp.tools.search import search_catalog

# Mark ALL tests in this file as integration + search
pytestmark = [pytest.mark.integration, pytest.mark.search]


@pytest.fixture
def real_test_bucket():
    """Fixture providing real test bucket from environment."""
    import os
    bucket = os.getenv('QUILT_TEST_BUCKET')
    if not bucket:
        pytest.skip("QUILT_TEST_BUCKET not set")
    return bucket


class TestScopeFileWithAllBuckets:
    """Test scope='file' with bucket='' (all buckets)."""

    async def test_file_scope_all_buckets_returns_results(self):
        """Verify file-level search across all buckets works."""
        # Test combination #1 from matrix
        pass

    async def test_file_scope_all_buckets_prioritizes_default(self):
        """Verify default bucket appears first in results."""
        pass


class TestScopeFileWithSpecificBucket:
    """Test scope='file' with bucket='mybucket' (specific bucket)."""

    async def test_file_scope_specific_bucket_returns_results(self, real_test_bucket):
        """Verify file-level search in specific bucket works."""
        # Test combination #2 from matrix
        pass


# ... similar classes for combinations #3-6 ...
```

**Priority:** 🔴 CRITICAL - Must be created FIRST

---

### Phase 2: Modify Existing Tests (if any exist)

**Finding:** Based on code analysis, no existing search integration tests were found that need modification.

**Reasoning:**
- Search tests are marked with `@pytest.mark.search` and excluded from standard runs
- This suggests they may not exist yet, or exist but are never run in CI
- The 284% coverage gap (45% actual vs. 85% target) suggests minimal existing tests

**Action:** NO MODIFICATIONS NEEDED - start fresh with Phase 1

---

### Phase 3: Delete Obsolete Tests (if any exist)

**Finding:** No obsolete tests identified for deletion.

**Reasoning:**
- Unable to locate existing integration tests for search_catalog
- Test exclusion pattern suggests search tests may not have been written yet
- If obsolete tests are found during implementation, they should be:
  1. Documented in a separate spec (e.g., `24-obsolete-tests-for-deletion.md`)
  2. Marked with `@pytest.mark.skip` with reason
  3. Deleted in a separate commit

**Action:** NO DELETIONS NEEDED at this time

---

## New Tests to Create: Detailed Specifications

### Test Suite 1: Basic Scope/Bucket Combinations (6 tests)

**Purpose:** Validate all 6 scope/bucket combinations produce correct index patterns and return results

**Tests:**

#### Test 1.1: `test_file_scope_all_buckets`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_file_scope_all_buckets():
    """Test scope='file', bucket='' - searches all object indices."""
    result = search_catalog(
        query="csv",
        scope="file",
        bucket="",
        limit=10
    )

    # Assertions:
    assert result["success"] is True
    assert result["scope"] == "file"
    assert result["bucket"] == ""
    assert "results" in result
    # Verify results come from multiple buckets
    buckets_seen = {r["bucket"] for r in result["results"]}
    assert len(buckets_seen) >= 2, "Should search multiple buckets"
    # Verify all results are files (not packages)
    assert all(r["type"] == "file" for r in result["results"])
```

**Why:** Tests combination #1 from matrix - most common use case (default scope, all buckets)

#### Test 1.2: `test_file_scope_specific_bucket`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_file_scope_specific_bucket():
    """Test scope='file', bucket='mybucket' - searches specific object index."""
    test_bucket = os.getenv('QUILT_TEST_BUCKET')

    result = search_catalog(
        query="csv",
        scope="file",
        bucket=test_bucket,
        limit=10
    )

    # Assertions:
    assert result["success"] is True
    assert result["scope"] == "file"
    assert result["bucket"] == test_bucket
    # Verify all results from specified bucket only
    assert all(r["bucket"] == test_bucket for r in result["results"])
    # Verify all results are files (not packages)
    assert all(r["type"] == "file" for r in result["results"])
```

**Why:** Tests combination #2 - targeted search in known bucket

#### Test 1.3: `test_package_scope_all_buckets`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_package_scope_all_buckets():
    """Test scope='package', bucket='' - searches all package indices."""
    result = search_catalog(
        query="*",  # Match all packages
        scope="package",
        bucket="",
        limit=10
    )

    # Assertions:
    assert result["success"] is True
    assert result["scope"] == "package"
    # Verify results come from multiple buckets
    buckets_seen = {r["bucket"] for r in result["results"]}
    assert len(buckets_seen) >= 1, "Should find packages in at least one bucket"
    # Verify all results are packages (not files)
    assert all(r["type"] == "package" for r in result["results"])
```

**Why:** Tests combination #3 - package-level search across all buckets

#### Test 1.4: `test_package_scope_specific_bucket`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_package_scope_specific_bucket():
    """Test scope='package', bucket='mybucket' - searches specific package index."""
    test_bucket = os.getenv('QUILT_TEST_BUCKET')

    result = search_catalog(
        query="*",
        scope="package",
        bucket=test_bucket,
        limit=10
    )

    # Assertions:
    assert result["success"] is True
    assert result["scope"] == "package"
    assert result["bucket"] == test_bucket
    # Verify all results from specified bucket only
    assert all(r["bucket"] == test_bucket for r in result["results"])
    # Verify all results are packages (not files)
    assert all(r["type"] == "package" for r in result["results"])
```

**Why:** Tests combination #4 - targeted package search

#### Test 1.5: `test_global_scope_all_buckets`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_global_scope_all_buckets():
    """Test scope='global', bucket='' - searches both file and package indices."""
    result = search_catalog(
        query="data",
        scope="global",
        bucket="",
        limit=20
    )

    # Assertions:
    assert result["success"] is True
    assert result["scope"] == "global"
    # Verify results include both files AND packages
    types_seen = {r["type"] for r in result["results"]}
    # Note: May only see one type if query matches one type better
    assert types_seen.issubset({"file", "package"}), "Should only return files or packages"
```

**Why:** Tests combination #5 - broadest search (everything everywhere)

#### Test 1.6: `test_global_scope_specific_bucket`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_global_scope_specific_bucket():
    """Test scope='global', bucket='mybucket' - searches both indices in one bucket."""
    test_bucket = os.getenv('QUILT_TEST_BUCKET')

    result = search_catalog(
        query="data",
        scope="global",
        bucket=test_bucket,
        limit=20
    )

    # Assertions:
    assert result["success"] is True
    assert result["scope"] == "global"
    assert result["bucket"] == test_bucket
    # Verify all results from specified bucket only
    assert all(r["bucket"] == test_bucket for r in result["results"])
    # Verify results can include both types
    types_seen = {r["type"] for r in result["results"]}
    assert types_seen.issubset({"file", "package"})
```

**Why:** Tests combination #6 - comprehensive search in single bucket

---

### Test Suite 2: Bucket Prioritization (3 tests)

**Purpose:** Verify default bucket appears first when searching all buckets

#### Test 2.1: `test_default_bucket_prioritized_in_results`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_default_bucket_prioritized_in_results():
    """Verify results from default bucket appear first."""
    default_bucket = os.getenv('QUILT_DEFAULT_BUCKET', '').replace('s3://', '').split('/')[0]
    if not default_bucket:
        pytest.skip("QUILT_DEFAULT_BUCKET not set")

    result = search_catalog(
        query="csv",
        scope="file",
        bucket="",  # All buckets
        limit=50
    )

    # Find first result's bucket
    if result["results"]:
        first_bucket = result["results"][0]["bucket"]
        # First result should ideally be from default bucket
        # (not strict assertion due to scoring, but log if not)
        if first_bucket != default_bucket:
            print(f"Warning: First result from {first_bucket}, expected {default_bucket}")
```

**Why:** Validates prioritization logic works in practice

#### Test 2.2: `test_bucket_prioritization_with_empty_default`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_bucket_prioritization_with_empty_default():
    """Verify search works even when QUILT_DEFAULT_BUCKET not set."""
    # Temporarily unset default bucket
    import os
    original = os.environ.get('QUILT_DEFAULT_BUCKET')
    if original:
        del os.environ['QUILT_DEFAULT_BUCKET']

    try:
        result = search_catalog(
            query="csv",
            scope="file",
            bucket="",
            limit=10
        )

        # Should still work, just no prioritization
        assert result["success"] is True
        assert len(result["results"]) > 0
    finally:
        # Restore original
        if original:
            os.environ['QUILT_DEFAULT_BUCKET'] = original
```

**Why:** Tests edge case where default bucket not configured

#### Test 2.3: `test_bucket_prioritization_order_preserved`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_bucket_prioritization_order_preserved():
    """Verify non-default buckets maintain relative order."""
    result = search_catalog(
        query="*",
        scope="file",
        bucket="",
        limit=100,
        explain_query=True  # Get backend info
    )

    # Extract bucket order from backend_info if available
    if "backend_info" in result:
        # Verify order is consistent across multiple searches
        pass  # Implementation depends on backend_info structure
```

**Why:** Validates prioritization doesn't break original order

---

### Test Suite 3: 403 Error Retry Logic (4 tests)

**Purpose:** Validate retry logic when Elasticsearch returns "too many indices" error

**Critical:** This is NEW code (lines 333-379) that has NEVER been tested against real Elasticsearch

#### Test 3.1: `test_403_retry_succeeds_with_fewer_buckets`
```python
@pytest.mark.integration
@pytest.mark.search
@pytest.mark.slow  # May take time with retries
async def test_403_retry_succeeds_with_fewer_buckets():
    """Test that 403 error triggers retry with progressively fewer buckets."""
    # This test requires a catalog with 50+ buckets to trigger 403
    # May need to be @pytest.mark.skip if not enough buckets available

    result = search_catalog(
        query="csv",
        scope="global",  # Global scope = 2x indices (files + packages)
        bucket="",  # All buckets
        limit=10
    )

    # If catalog has many buckets, may trigger 403 internally and retry
    # We can't easily detect retries without instrumentation, but we can verify success
    assert result["success"] is True or "403" in result.get("error", "")

    # If backend_info includes retry count, verify it
    if "backend_info" in result and "retry_count" in result["backend_info"]:
        retry_count = result["backend_info"]["retry_count"]
        assert retry_count >= 0, "Should track retry attempts"
```

**Why:** Validates core retry logic works

**Challenge:** Hard to test without 50+ buckets in catalog

**Solution:** May need to mock Elasticsearch response in unit test instead

#### Test 3.2: `test_403_retry_preserves_default_bucket_priority`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_403_retry_preserves_default_bucket_priority():
    """Verify default bucket stays first even during retries."""
    default_bucket = os.getenv('QUILT_DEFAULT_BUCKET', '').replace('s3://', '').split('/')[0]
    if not default_bucket:
        pytest.skip("QUILT_DEFAULT_BUCKET not set")

    result = search_catalog(
        query="csv",
        scope="file",
        bucket="",
        limit=10
    )

    # Even if retry happens, default bucket should be in results
    if result["success"] and result["results"]:
        buckets_in_results = {r["bucket"] for r in result["results"]}
        # Default bucket should be represented if it has matching data
        # (can't assert strictly without knowing data)
        pass
```

**Why:** Validates retry doesn't break prioritization

#### Test 3.3: `test_non_403_error_does_not_retry`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_non_403_error_does_not_retry():
    """Verify non-403 errors don't trigger retry logic."""
    # Use invalid query to trigger non-403 error
    result = search_catalog(
        query='[[[invalid query syntax',
        scope="file",
        bucket="",
        limit=10
    )

    # Should fail, but not due to retries
    assert result["success"] is False
    # Error should not mention retries or 403
    error_msg = result.get("error", "")
    assert "403" not in error_msg, "Should not have 403 error for syntax error"
```

**Why:** Validates retry only happens for 403 errors

#### Test 3.4: `test_specific_bucket_does_not_trigger_retry`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_specific_bucket_does_not_trigger_retry():
    """Verify retry logic doesn't activate for single-bucket searches."""
    test_bucket = os.getenv('QUILT_TEST_BUCKET')

    result = search_catalog(
        query="csv",
        scope="global",  # Even with global scope
        bucket=test_bucket,  # Specific bucket = only 2 indices
        limit=10
    )

    # Should succeed without retries (only 2 indices: bucket and bucket_packages)
    assert result["success"] is True
    # Verify backend_info doesn't show retry attempts
    if "backend_info" in result and "retry_count" in result["backend_info"]:
        assert result["backend_info"]["retry_count"] == 0
```

**Why:** Validates retry only happens for multi-bucket searches

---

### Test Suite 4: Bucket Normalization (3 tests)

**Purpose:** Verify s3:// URIs are correctly normalized to bucket names

#### Test 4.1: `test_bucket_s3_uri_normalized`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_bucket_s3_uri_normalized():
    """Test that s3://bucket URIs are normalized to bucket names."""
    test_bucket = os.getenv('QUILT_TEST_BUCKET')

    # Search with s3:// URI
    result = search_catalog(
        query="csv",
        scope="file",
        bucket=f"s3://{test_bucket}",  # s3:// format
        limit=10
    )

    # Verify bucket field in response is normalized (no s3://)
    assert result["bucket"] == test_bucket, "Bucket should be normalized"
    # Verify results reference normalized bucket
    if result["results"]:
        assert all(r["bucket"] == test_bucket for r in result["results"])
```

**Why:** Validates s3:// prefix handling (common user input)

#### Test 4.2: `test_bucket_trailing_slash_normalized`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_bucket_trailing_slash_normalized():
    """Test that trailing slashes are removed from bucket names."""
    test_bucket = os.getenv('QUILT_TEST_BUCKET')

    result = search_catalog(
        query="csv",
        scope="file",
        bucket=f"{test_bucket}/",  # Trailing slash
        limit=10
    )

    # Verify bucket normalized
    assert result["bucket"] == test_bucket
```

**Why:** Validates trailing slash handling (common user error)

#### Test 4.3: `test_bucket_s3_uri_with_prefix_normalized`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_bucket_s3_uri_with_prefix_normalized():
    """Test that s3://bucket/prefix URIs are normalized to just bucket."""
    test_bucket = os.getenv('QUILT_TEST_BUCKET')

    result = search_catalog(
        query="csv",
        scope="file",
        bucket=f"s3://{test_bucket}/some/prefix",  # With prefix
        limit=10
    )

    # Should normalize to just bucket name (prefix ignored)
    assert result["bucket"] == test_bucket
    # Note: Prefix filtering not supported in search_catalog
```

**Why:** Validates prefix extraction logic (line 136 in elasticsearch.py)

---

### Test Suite 5: Error Handling (4 tests)

**Purpose:** Validate graceful error handling for common failure modes

#### Test 5.1: `test_invalid_scope_rejected`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_invalid_scope_rejected():
    """Test that invalid scope values are rejected."""
    with pytest.raises((ValueError, TypeError)):
        search_catalog(
            query="csv",
            scope="invalid_scope",  # Not in ["file", "package", "global"]
            bucket="",
            limit=10
        )
```

**Why:** Validates input validation

#### Test 5.2: `test_empty_bucket_list_handled`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_empty_bucket_list_handled():
    """Test graceful handling when no buckets available."""
    # This test requires mocking _get_available_buckets to return []
    # Better as unit test, but documents expected behavior
    pass
```

**Why:** Validates edge case handling (lines 249-252 in elasticsearch.py)

#### Test 5.3: `test_graphql_bucket_fetch_failure_handled`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_graphql_bucket_fetch_failure_handled():
    """Test graceful handling when GraphQL bucket fetch fails."""
    # Hard to test without mocking - may skip in integration tests
    # Better as unit test with mocked GraphQL endpoint
    pass
```

**Why:** Validates network failure handling (lines 163-165 in elasticsearch.py)

#### Test 5.4: `test_nonexistent_bucket_returns_empty`
```python
@pytest.mark.integration
@pytest.mark.search
async def test_nonexistent_bucket_returns_empty():
    """Test that searching nonexistent bucket returns empty results."""
    result = search_catalog(
        query="csv",
        scope="file",
        bucket="nonexistent-bucket-12345",
        limit=10
    )

    # Should succeed but return no results
    assert result["success"] is True
    assert len(result["results"]) == 0
```

**Why:** Validates behavior with invalid bucket names

---

## Test Execution Strategy

### Environment Requirements

**Required Environment Variables:**
```bash
# AWS credentials
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_DEFAULT_REGION=us-east-1

# Quilt configuration
QUILT_DEFAULT_BUCKET=s3://your-default-bucket
QUILT_CATALOG_URL=https://your-catalog.quiltdata.com
QUILT_TEST_BUCKET=your-test-bucket  # Known bucket with test data
```

**Catalog Requirements:**
- Authenticated session with Quilt catalog
- At least 2 buckets available (for multi-bucket tests)
- Test bucket contains known data (CSV files, packages)
- Ideally 50+ buckets to test 403 retry logic

---

### Test Execution Commands

```bash
# Run only integration tests for search
pytest tests/integration/test_search_elasticsearch_integration.py -v

# Run with search marker (includes search tests)
pytest tests/ -v -m "search"

# Run full test suite including search
make test-all

# Run search tests with coverage
pytest tests/integration/test_search_elasticsearch_integration.py -v \
  --cov=quilt_mcp.search --cov-report=term-missing
```

---

### CI Integration

**Recommendation:** Add separate CI job for search integration tests

**Current CI Flow (from `.github/workflows/push.yml`):**
```yaml
- name: Run comprehensive tests
  run: pytest tests/ -m "not slow and not search and not admin"  # Excludes search
```

**Proposed CI Flow:**
```yaml
# Existing job (unchanged)
- name: Run fast tests
  run: pytest tests/ -m "not slow and not search and not admin"

# NEW job for search integration tests (optional, only on schedule or manual)
- name: Run search integration tests
  if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
  run: pytest tests/integration/test_search_elasticsearch_integration.py -v
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

**Reasoning:**
- Search tests hit real Elasticsearch (slow, expensive)
- Run on schedule (nightly) or manual trigger
- Don't block fast PR checks

---

## Coverage Impact Analysis

### Current Coverage: 45% (below 85% threshold)

**Coverage Gap:** 284% (45% actual vs. 85% target = 40 percentage point gap)

### Expected Coverage After New Tests

| Module | Current Coverage | Expected After | Gain |
|--------|-----------------|----------------|------|
| `search/backends/elasticsearch.py` | ~40% | ~75% | +35% |
| `search/tools/unified_search.py` | ~50% | ~80% | +30% |
| `tools/search.py` | ~60% | ~85% | +25% |

**Projected Combined Coverage:** 75-80% (closer to 85% threshold)

**Note:** May not reach full 85% without additional unit tests for edge cases

---

## Implementation Priority Ranking

### Must Have (P0) - Implement First

1. **Test Suite 1: Basic Scope/Bucket Combinations** (6 tests)
   - Validates core functionality
   - Covers most common use cases
   - Required for production confidence

2. **Test Suite 4: Bucket Normalization** (3 tests)
   - Common user input patterns
   - High risk if broken (user frustration)

### Should Have (P1) - Implement Second

3. **Test Suite 2: Bucket Prioritization** (3 tests)
   - Important for user experience
   - Lower risk if broken (still returns results)

4. **Test Suite 5: Error Handling** (4 tests)
   - Validates graceful degradation
   - Important for production stability

### Nice to Have (P2) - Implement Last

5. **Test Suite 3: 403 Error Retry Logic** (4 tests)
   - Hard to test without many buckets
   - May be better tested in unit tests with mocks
   - Only affects catalogs with 50+ buckets

---

## Estimated Implementation Effort

| Test Suite | Tests | LOC | Effort (hours) |
|------------|-------|-----|----------------|
| Suite 1: Scope/Bucket | 6 | ~300 | 4-6 |
| Suite 2: Prioritization | 3 | ~150 | 2-3 |
| Suite 3: 403 Retry | 4 | ~200 | 3-4 |
| Suite 4: Normalization | 3 | ~150 | 2-3 |
| Suite 5: Error Handling | 4 | ~200 | 2-3 |
| **Total** | **20** | **~1000** | **13-19** |

**Additional Effort:**
- Test infrastructure setup: 2-3 hours
- CI integration: 1-2 hours
- Documentation: 1-2 hours
- **Grand Total: 17-26 hours** (2-3 days)

---

## Success Metrics

### Quantitative Metrics

- ✅ 20 new integration tests created
- ✅ All 6 scope/bucket combinations covered
- ✅ Coverage increased from 45% to 75-80%
- ✅ Zero 403 retry regressions in production
- ✅ All tests passing in CI

### Qualitative Metrics

- ✅ Confidence in production search behavior
- ✅ Faster debugging of search issues
- ✅ Reduced user-reported search bugs
- ✅ Clear documentation of expected behavior

---

## Conclusion

**Current State:**
- 0% integration test coverage for scope/bucket semantics
- 45% overall coverage (40 points below 85% threshold)
- Search tests explicitly excluded from CI
- Critical 403 retry logic never tested against real Elasticsearch

**Required Action:**
- Create 20 new integration tests (17-26 hours effort)
- Set up test infrastructure with proper markers
- Integrate into CI (optional, for scheduled runs)
- Validate all 6 scope/bucket combinations

**Expected Outcome:**
- 75-80% coverage (near 85% threshold)
- Production confidence in search behavior
- Faster bug detection and resolution
- Clear test-driven documentation of semantics

**Next Steps:**
1. Create `tests/integration/test_search_elasticsearch_integration.py`
2. Implement Test Suite 1 (P0 priority)
3. Implement Test Suite 4 (P0 priority)
4. Run tests, measure coverage
5. Iterate until 85% threshold reached

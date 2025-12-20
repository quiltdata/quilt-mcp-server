# Implementation Changes for Simplified Search API

**Date:** 2025-01-14
**Status:** 📋 Implementation Plan
**Based On:** [20-simplified-search-api-spec.md](./20-simplified-search-api-spec.md)

---

## Executive Summary

This document identifies **what needs to change** to implement the simplified search API (spec 20). Focus is on file/function/test identification, not implementation details.

---

## 1. Parameter Changes

### 1.1 Function Signatures to Update

**File:** [src/quilt_mcp/tools/search.py](../../src/quilt_mcp/tools/search.py)

**Function:** `search_catalog()` (lines 27-137)

- **CHANGE:** `scope` parameter
  - Old: `Literal["global", "package", "bucket"]` (default `"bucket"`)
  - New: `Literal["global", "package", "file"]` (default `"file"`)
- **CHANGE:** `target` parameter → rename to `bucket`
  - Old: `target: str` (description mentions DEFAULT_BUCKET fallback)
  - New: `bucket: str` (empty string = all buckets)
- **KEEP:** `backend` parameter already correct
  - Current: `Literal["elasticsearch"]` (default `"elasticsearch"`)
  - Spec: Same ✅
- **KEEP:** All other parameters unchanged

**Function:** `search_explain()` (lines 291-352)

- **CHANGE:** `scope` parameter type (same as above)
- **CHANGE:** `target` → `bucket` parameter rename

**Function:** `search_suggest()` (lines 220-288)

- **NO CHANGES** (helper function, doesn't use scope/target)

---

### 1.2 Internal Search Functions

**File:** [src/quilt_mcp/search/tools/unified_search.py](../../src/quilt_mcp/search/tools/unified_search.py)

**Function:** `unified_search()` (lines 323-427)

- **CHANGE:** Update parameter names to match new API
  - `scope` type change
  - `target` → `bucket` rename
- **KEEP:** Logic structure (backend selection, result processing)

**Class:** `UnifiedSearchEngine` (lines 23-309)

- **Method:** `search()` (lines 40-189)
  - **CHANGE:** Parameter names/types
  - **REVIEW:** Scope handling logic (lines 143-147 currently handle `scope="bucket"` + DEFAULT_BUCKET fallback)

---

## 2. Result Structure Changes

### 2.1 SearchResult Model Updates

**File:** [src/quilt_mcp/models/responses.py](../../src/quilt_mcp/models/responses.py)

**Class:** `SearchResult` (lines 922-936)

**REQUIRED CHANGES:**

- **ADD:** `name: str` field (unified field for both files and packages)
- **ADD:** `bucket: str` field (extracted bucket name)
- **ADD:** `content_type: Optional[str]` field
- **ADD:** `extension: Optional[str]` field
- **ADD:** `content_preview: Optional[str]` field (when `include_content_preview=True`)
- **UPDATE:** `description` field (make non-optional with default)
- **KEEP:** All existing fields (backward compatible)

**Semantic Changes:**

- For **files**: `name` = logical_key (path within bucket)
- For **packages**: `name` = package_name (namespace/name format)
- `id` format:
  - Files: `s3://bucket/path/to/file`
  - Packages: `quilt+s3://bucket#package=namespace/name@hash`

### 2.2 Backend SearchResult Processing

**File:** [src/quilt_mcp/search/backends/base.py](../../src/quilt_mcp/search/backends/base.py)

**Class:** `SearchResult` (lines 29-48)

- **ADD:** Same fields as Pydantic model above
- **ENSURE:** Both file and package results populate all shared fields meaningfully

**File:** [src/quilt_mcp/search/tools/unified_search.py](../../src/quilt_mcp/search/tools/unified_search.py)

**Method:** `_process_backend_results()` (lines 191-230)

- **UPDATE:** Result dict construction to include new fields
- **ENSURE:** `name` field is set correctly based on type
- **ADD:** `bucket` extraction from `s3_uri`
- **ADD:** `content_type`, `extension`, `content_preview` population

---

## 3. Response Structure Changes

### 3.1 Success Response Updates

**File:** [src/quilt_mcp/models/responses.py](../../src/quilt_mcp/models/responses.py)

**Class:** `SearchCatalogSuccess` (find via grep - likely around line 950+)

- **CHANGE:** Field name `target` → `bucket`
- **KEEP:** All other response fields

**File:** [src/quilt_mcp/tools/search.py](../../src/quilt_mcp/tools/search.py)

**Function:** `search_catalog()` (lines 138-217)

- **UPDATE:** Response model instantiation (lines 189-201)
  - Change `target=` to `bucket=`

---

## 4. Validation Changes

### 4.1 Parameter Validation

**File:** [src/quilt_mcp/search/tools/unified_search.py](../../src/quilt_mcp/search/tools/unified_search.py) (or create new validator)

**ADD:** Validation logic (suggested location: before line 363)

```python
# Validate scope
assert scope in ["global", "package", "file"], "Invalid scope"

# Validate backend (already done, but ensure default)
if backend is None or backend == "":
    backend = "elasticsearch"
assert backend == "elasticsearch", "Only elasticsearch supported"

# Normalize bucket (extract from s3:// URI if needed)
if bucket.startswith("s3://"):
    bucket = bucket[5:].split("/")[0]

# Validate limit
assert 1 <= limit <= 1000, "Limit must be 1-1000"
```

### 4.2 Result Validation

#### DECISION: Trust backends + Pydantic (no runtime validation in code)

- NO validation in `_process_backend_results()` - trust backend results
- Rely on Pydantic model validation to catch structural issues
- BUT: Integration tests (using real AWS services) MUST validate all required fields are present and correct

---

## 5. Backend Implementation Changes

### 5.1 Elasticsearch Backend

**File:** [src/quilt_mcp/search/backends/elasticsearch.py](../../src/quilt_mcp/search/backends/elasticsearch.py)

**CHANGES NEEDED:**

- **UPDATE:** Scope handling to recognize `"file"` instead of `"bucket"`
- **ENSURE:** Result objects include new fields (`name`, `bucket`, `content_type`, `extension`)
- **ADD:** `bucket` extraction from S3 URIs
- **ADD:** `content_type` and `extension` from metadata

**QUESTION:** Does elasticsearch backend already populate these fields? Need to review actual response structure.

### 5.2 GraphQL Backend

**File:** [src/quilt_mcp/search/backends/graphql.py](../../src/quilt_mcp/search/backends/graphql.py)

#### DECISION: Disable GraphQL backend (leave as dead code)

- There is only ONE backend: Elasticsearch
- Keep `EnterpriseGraphQLBackend` class but never use it (dead code)
- Backend parameter validation ensures only "elasticsearch" is accepted
- Remove/disable any failing GraphQL tests

---

## 6. Tests to Update

### 6.1 Tests Using Old Parameter Names

**Files to grep for `scope="bucket"`:**

```bash
grep -r 'scope="bucket"' tests/
```

**Files to grep for `target=`:**

```bash
grep -r 'target=' tests/
```

**Expected files (from glob output):**

- [tests/test_search_scope_fixes.py](../../tests/test_search_scope_fixes.py)
- [tests/test_search_defaults.py](../../tests/test_search_defaults.py)
- [tests/e2e/test_unified_search.py](../../tests/e2e/test_unified_search.py)
- [tests/e2e/test_search_phase2.py](../../tests/e2e/test_search_phase2.py)
- [tests/e2e/test_search_phase3_errors.py](../../tests/e2e/test_search_phase3_errors.py)
- [tests/integration/test_elasticsearch_integration.py](../../tests/integration/test_elasticsearch_integration.py)
- [tests/test_elasticsearch_escaping.py](../../tests/test_elasticsearch_escaping.py)

**UPDATE:** All test calls to use new parameter names:

- `scope="bucket"` → `scope="file"`
- `target="..."` → `bucket="..."`

### 6.2 Tests to Delete (If Obsolete)

**CANDIDATE FILES FOR DELETION:**

1. **tests/test_search_scope_fixes.py**
   - Tests for "scope semantic fixes" (bucket vs catalog/global 403 fallback)
   - If scope semantics have changed, these tests may be obsolete
   - **REVIEW:** Check if any test logic should be preserved in new tests

2. **tests/e2e/test_search_phase2.py** and **tests/e2e/test_search_phase3_errors.py**
   - Phase-based tests suggest incremental implementation
   - **DECISION NEEDED:** Are these still relevant, or can they be consolidated?

**RECOMMENDATION:** Easier to **delete obsolete tests** and write fresh ones than to refactor extensively.

### 6.3 New Tests to Write

**Test file:** `tests/test_simplified_search_api.py` (NEW)

**Test coverage needed:**

- **Scope tests:**
  - `test_scope_file()` - verify only file results
  - `test_scope_package()` - verify only package results
  - `test_scope_global()` - verify mixed results
- **Bucket tests:**
  - `test_bucket_empty_searches_all()`
  - `test_bucket_specific_filters()`
  - `test_bucket_s3_uri_normalized()`
- **Backend tests:**
  - `test_backend_default()`
  - `test_backend_explicit()`
  - `test_backend_invalid_raises()` (graphql should error)
- **Result structure tests:**
  - `test_file_result_structure()` - verify all required fields
  - `test_package_result_structure()` - verify all required fields
  - `test_result_name_field()` - verify name semantics
  - `test_result_id_format()` - verify s3:// vs quilt+s3://

(See spec lines 511-617 for full test cases)

---

## 7. Documentation Updates

### 7.1 Docstrings to Update

**Files:**

- [src/quilt_mcp/tools/search.py](../../src/quilt_mcp/tools/search.py) - main docstrings
- [src/quilt_mcp/search/tools/unified_search.py](../../src/quilt_mcp/search/tools/unified_search.py) - internal docs
- [src/quilt_mcp/models/responses.py](../../src/quilt_mcp/models/responses.py) - model docstrings

**Changes:**

- Update all parameter descriptions
- Update examples showing `scope="bucket"` → `scope="file"`
- Update examples showing `target=` → `bucket=`
- Add examples showing new result structure

### 7.2 External Documentation

**DECISION NEEDED:** Are there markdown docs that need updating?

- Check `docs/` directory for search-related documentation
- Update any API reference docs
- Update migration guides

---

## 8. Backward Compatibility

### 8.1 Breaking Changes Summary

**BREAKING CHANGES:**

1. `scope="bucket"` → `scope="file"` (value change, not just rename)
2. `target` parameter → `bucket` parameter (name change)
3. `backend="graphql"` → No longer accepted (raises error)
4. Package `id` format change (parallel to file `s3://` format)

### 8.2 Migration Support

#### DECISION: Clean break with clear error messages

- NO migration helpers or deprecation warnings
- Invalid parameters will raise clear, descriptive errors
- This is MCP - the LLM can adapt to new API
- Simpler code, cleaner semantics

---

## 9. Implementation Dependencies

### 9.1 Order of Changes

**Suggested order:**

1. **Add new fields to SearchResult models** (non-breaking, additive)
2. **Update backends to populate new fields** (non-breaking)
3. **Update function signatures** (breaking - do all at once)
4. **Update tests** (after #3)
5. **Update documentation** (after #4)

### 9.2 Files That Must Change Together

**Atomic change set 1:** Parameter renames (must happen together)

- `src/quilt_mcp/tools/search.py`
- `src/quilt_mcp/search/tools/unified_search.py`
- `src/quilt_mcp/models/responses.py` (response models)

**Atomic change set 2:** Result structure (can be separate)

- `src/quilt_mcp/search/backends/base.py`
- `src/quilt_mcp/search/backends/elasticsearch.py`
- `src/quilt_mcp/models/responses.py` (SearchResult model)

---

## 10. Decisions Made

### 10.1 All Design Decisions Resolved

1. **Default Bucket Behavior:** ✅ BREAKING CHANGE
   - `bucket=""` = search ALL buckets (not DEFAULT_BUCKET)
   - Keep it clean and simple per spec
   - Remove DEFAULT_BUCKET fallback logic

2. **GraphQL Backend:** ✅ DISABLE (leave as dead code)
   - There is only ONE backend: Elasticsearch
   - Keep code but never use it
   - Remove/disable failing GraphQL tests

3. **Backward Compatibility:** ✅ Clean break with clear errors
   - No migration helpers or deprecation warnings
   - MCP/LLM can adapt to new API
   - Simpler, cleaner code

4. **Test Strategy:** ✅ Delete + rewrite fresh
   - Delete obsolete phase tests (phase2, phase3)
   - Delete scope_fixes tests
   - Write new `test_simplified_search_api.py` from scratch

5. **Result Validation:** ✅ Trust backends + Pydantic
   - No runtime validation in code
   - Pydantic handles model validation
   - Integration tests validate real AWS responses

### 10.2 Remaining Questions (Non-blocking)

1. **Package Result Fields:**
   - Spec says package `size` = manifest size (lines 201, 242-246)
   - Should `metadata.total_size` hold total package size?
   - **ACTION:** Review elasticsearch backend behavior during implementation

2. **External Documentation:**
   - Check if `docs/` directory has search-related markdown
   - **ACTION:** Grep for docs during implementation

---

## 11. Summary: Files to Change

### Core Implementation (Must Change)

1. `src/quilt_mcp/tools/search.py` - Function signatures
2. `src/quilt_mcp/search/tools/unified_search.py` - Internal search logic
3. `src/quilt_mcp/models/responses.py` - Request/response models
4. `src/quilt_mcp/search/backends/base.py` - SearchResult dataclass
5. `src/quilt_mcp/search/backends/elasticsearch.py` - Result population

### Tests (Must Update)

1. All 7 test files listed in section 6.1
2. **NEW:** `tests/test_simplified_search_api.py`

### Possible Deletions

1. `tests/test_search_scope_fixes.py` (review first)
2. `tests/e2e/test_search_phase2.py` (review first)
3. `tests/e2e/test_search_phase3_errors.py` (review first)
4. `src/quilt_mcp/search/backends/graphql.py` (if removing GraphQL)

### Documentation

1. All docstrings in changed files
2. Any markdown docs in `docs/` (need to check)

---

## 12. Next Steps

1. **DECISION:** Answer open questions (section 10)
2. **PLAN:** Choose implementation order (section 9.1)
3. **IMPLEMENT:** Core changes (section 11 - Core Implementation)
4. **TEST:** Write new tests, update existing (section 6)
5. **DOCUMENT:** Update all documentation (section 7)

---

**Status:** 📋 **Awaiting Decisions on Open Questions**

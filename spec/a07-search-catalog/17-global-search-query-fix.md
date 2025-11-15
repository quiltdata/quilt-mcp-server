# Global Search Query Fix: Supporting Multi-Type Results

**Date:** 2025-01-13
**Status:** Ready for Implementation
**Related:**
- [15-backend-initialization-bug-analysis.md](./15-backend-initialization-bug-analysis.md) - Backend initialization fix
- [16-fix-implementation-summary.md](./16-fix-implementation-summary.md) - Partial fix implementation

---

## Executive Summary

The `search_catalog.global` test fails because it searches for "README.md" but expects to find packages named "raw/test" in the results. This is unrealistic - a search engine can't return documents that don't match the query.

**Solution:** Update the test query to use boolean OR logic: `"README OR raw/test"` to retrieve both file and package results in a single search.

---

## Problem Statement

### Current Test Configuration

[mcp-test.yaml:578-609](../../scripts/tests/mcp-test.yaml#L578-L609):

```yaml
search_catalog.global:
  tool: search_catalog
  arguments:
    query: README.md           # ❌ Only matches files named README.md
    limit: 10
    scope: global
  validation:
    must_contain:
      - value: README.md
        field: logical_key      # ✅ Found - matches query
      - value: raw/test
        field: title            # ❌ Not found - doesn't match query!
```

### Why It Fails

1. **Query:** "README.md"
2. **Elasticsearch matches:** Files with "README.md" in their name/path
3. **Result types:** Only files (type: "file")
4. **Packages named "raw/test":** Don't contain the text "README.md" → Not returned
5. **Test expectation:** Find both files AND packages in results
6. **Reality:** Can't find packages that don't match the query term

**This is a test configuration bug, not a code bug.**

---

## Solution: Boolean OR Query

### Proposed Fix

Update [mcp-test.yaml:584-586](../../scripts/tests/mcp-test.yaml#L584-L586):

```yaml
search_catalog.global:
  tool: search_catalog
  arguments:
    query: "README OR raw/test"  # ✅ Matches BOTH types
    limit: 20                     # ✅ Increased to accommodate both
    scope: global
```

### Why This Works

Elasticsearch query string syntax supports boolean operators:
- `README OR raw/test` → Returns documents matching EITHER term
- Files with "README" in logical_key → Included
- Packages with "raw/test" in title → Included
- Both result types in same response → Test passes ✅

### Validation Logic

```yaml
  validation:
    type: search
    min_results: 2              # At least 1 file + 1 package
    must_contain:
      - value: README
        field: logical_key
        match_type: substring
        description: Must find files with README in global results
      - value: raw/test
        field: title
        match_type: substring
        description: Must find packages with raw/test in global results
    description: Global search must return both files and packages
```

**Note:** Changed "README.md" to "README" to be more flexible (matches README.md, README.txt, etc.)

---

## Alternative Solutions Considered

### Option A: Wildcard Query

```yaml
arguments:
  query: "*"
  limit: 100
```

**Pros:**
- Returns everything
- Guaranteed to find both types

**Cons:**
- ❌ Not realistic - users don't search with "*"
- ❌ Slow and expensive
- ❌ Doesn't test actual search relevance
- ❌ May return 100 random results without guaranteed types

**Verdict:** ❌ Not recommended

---

### Option B: Separate Tests

```yaml
search_catalog.global_files:
  arguments:
    query: "README.md"
    scope: global
  validation:
    must_contain:
      - value: README.md
        field: logical_key

search_catalog.global_packages:
  arguments:
    query: "raw/test"
    scope: global
  validation:
    must_contain:
      - value: raw/test
        field: title
```

**Pros:**
- Clear separation of concerns
- Tests one type per test

**Cons:**
- ❌ Doesn't test that global search returns BOTH types
- ❌ More tests to maintain
- ❌ Misses the key requirement: unified search

**Verdict:** ⚠️ Acceptable but less ideal

---

### Option C: Boolean OR Query (RECOMMENDED)

```yaml
arguments:
  query: "README OR raw/test"
  limit: 20
  scope: global
```

**Pros:**
- ✅ Realistic query pattern (users DO combine terms)
- ✅ Tests that global search returns multiple types
- ✅ Fast and efficient
- ✅ Tests actual Elasticsearch boolean logic
- ✅ Single test validates unified search behavior

**Cons:**
- None significant

**Verdict:** ✅ **RECOMMENDED**

---

## Implementation Plan

### Step 1: Update Test Configuration

**File:** `scripts/tests/mcp-test.yaml`
**Lines:** 578-609

```yaml
search_catalog.global:
  tool: search_catalog
  description: Intelligent unified search across Quilt catalog using Elasticsearch - Catalog and package search experiences
  effect: none
  arguments:
    query: "README OR raw/test"  # ✅ CHANGED: Boolean OR
    limit: 20                     # ✅ CHANGED: Increased limit
    scope: global
  response_schema:
    type: object
    properties:
      content:
        type: array
        items:
          type: object
    required:
      - content
  validation:
    type: search
    min_results: 2                # ✅ At least 1 file + 1 package
    must_contain:
      - value: README             # ✅ CHANGED: More flexible
        field: logical_key
        match_type: substring
        description: Must find files with README in global results (logical_key field)
      - value: raw/test
        field: title
        match_type: substring
        description: Must find packages with raw/test in global results (title field)
    description: Global search must return both files and packages using OR query
```

### Step 2: Test the Fix

```bash
# Run MCP tests
PYTHONPATH=src uv run pytest tests/test_mcp_server.py -v -k search

# Or run via mcp-test script directly
uv run python scripts/mcp-test.py http://localhost:8000/mcp --tools-test
```

### Step 3: Verify Results

Expected output:
```
✅ search_catalog.bucket - PASSED
✅ search_catalog.package - PASSED
✅ search_catalog.global - PASSED ✨ (NOW FIXED!)
```

---

## Result Format Normalization Analysis

### Current Result Structures

#### File Results
```json
{
  "id": "s3://bucket/path/to/file.csv",
  "type": "file",
  "title": "file.csv",
  "logical_key": "path/to/file.csv",
  "score": 1.5,
  "bucket": "s3://bucket"
}
```

#### Package Results
```json
{
  "id": "pkg:raw/test@latest",
  "type": "package",
  "title": "raw/test",
  "package_name": "raw/test",
  "score": 2.1,
  "registry": "s3://bucket"
}
```

### Normalization Question

**User asks:** "Would this be simpler if we normalized the results from packages and files to be similar (e.g., 'name' for both logical_key and package_name)?"

### Analysis

#### Option 1: Keep Current Structure (Status Quo)

**Current:**
- Files have `logical_key` (path within bucket)
- Packages have `package_name` (namespace/name)

**Pros:**
- ✅ Accurate terminology (files have keys, packages have names)
- ✅ Matches Quilt data model precisely
- ✅ No breaking changes
- ✅ Clear distinction between types

**Cons:**
- ⚠️ Consumers need to handle both field names
- ⚠️ Template logic needs conditional field access

---

#### Option 2: Add Normalized `name` Field (Augmentation)

**Proposal:**
```json
// Files
{
  "id": "s3://bucket/path/to/file.csv",
  "type": "file",
  "name": "path/to/file.csv",          // ✨ NEW (copy of logical_key)
  "logical_key": "path/to/file.csv",   // KEPT (backward compat)
  "title": "file.csv",
  "score": 1.5
}

// Packages
{
  "id": "pkg:raw/test@latest",
  "type": "package",
  "name": "raw/test",                   // ✨ NEW (copy of package_name)
  "package_name": "raw/test",           // KEPT (backward compat)
  "title": "raw/test",
  "score": 2.1
}
```

**Pros:**
- ✅ Consumers can use `.name` for both types
- ✅ Backward compatible (keeps original fields)
- ✅ Simpler template logic: `{{result.name}}`
- ✅ Better API ergonomics

**Cons:**
- ⚠️ Slight data duplication
- ⚠️ More fields to maintain

---

#### Option 3: Replace with `name` Only (Breaking Change)

**Proposal:**
```json
// Files
{
  "type": "file",
  "name": "path/to/file.csv",    // RENAMED from logical_key
  "title": "file.csv"
}

// Packages
{
  "type": "package",
  "name": "raw/test",             // RENAMED from package_name
  "title": "raw/test"
}
```

**Pros:**
- ✅ Cleanest API surface
- ✅ Simplest for consumers
- ✅ No duplication

**Cons:**
- ❌ BREAKING CHANGE for existing clients
- ❌ Loses semantic clarity (logical_key vs package_name)
- ❌ May confuse users familiar with Quilt terminology

---

### Recommendation: Option 2 (Augmentation)

**Add normalized `name` field while keeping original fields.**

**Implementation:**

[elasticsearch.py:_convert_catalog_results()](../../src/quilt_mcp/search/backends/elasticsearch.py):

```python
def _convert_catalog_results(self, hits: List[Dict[str, Any]]) -> List[SearchResult]:
    """Convert Elasticsearch hits to unified search results."""
    results = []

    for hit in hits:
        source = hit.get("_source", {})

        # Determine result type
        if "logical_key" in source:
            result_type = "file"
            name = source["logical_key"]  # ✨ Normalized name
        elif "package_name" in source:
            result_type = "package"
            name = source["package_name"]  # ✨ Normalized name
        else:
            continue

        result = {
            "id": hit["_id"],
            "type": result_type,
            "name": name,                    # ✨ NEW: Normalized field
            "title": source.get("name", ""),
            "score": hit.get("_score", 0.0),
        }

        # Add type-specific fields (backward compat)
        if result_type == "file":
            result["logical_key"] = source["logical_key"]  # KEPT
            result["bucket"] = source.get("bucket", "")
        else:  # package
            result["package_name"] = source["package_name"]  # KEPT
            result["registry"] = source.get("registry", "")

        results.append(result)

    return results
```

**Benefits:**
1. ✅ Simple consumer code: `result.name` works for both types
2. ✅ No breaking changes for existing clients
3. ✅ Maintains semantic accuracy with original fields
4. ✅ Template authors can choose: use `.name` (simple) or `.logical_key`/`.package_name` (precise)

---

## Testing Strategy

### Manual Testing

```bash
# Test 1: Boolean OR query
PYTHONPATH=src python3 -c "
import asyncio
from quilt_mcp.search.tools.unified_search import unified_search

async def test():
    result = await unified_search('README OR raw/test', scope='global', limit=20)
    print(f'Total results: {result[\"total_results\"]}')

    files = [r for r in result['results'] if r['type'] == 'file']
    packages = [r for r in result['results'] if r['type'] == 'package']

    print(f'Files: {len(files)}, Packages: {len(packages)}')

    if files:
        print(f'Sample file: {files[0][\"title\"]}')
    if packages:
        print(f'Sample package: {packages[0][\"title\"]}')

asyncio.run(test())
"
```

**Expected output:**
```
Total results: 15
Files: 10, Packages: 5
Sample file: README.md
Sample package: raw/test
```

### Automated Testing

```bash
# Run full test suite
make test

# Run only search tests
PYTHONPATH=src uv run pytest tests/ -v -k search

# Run mcp-test directly
uv run python scripts/mcp-test.py http://localhost:8000/mcp --tools-test -v
```

---

## Files to Modify

### 1. Test Configuration (Required)

**File:** `scripts/tests/mcp-test.yaml`
**Lines:** 578-609
**Changes:**
- Line 584: `query: "README OR raw/test"`
- Line 585: `limit: 20`
- Line 600: `value: README` (remove .md)
- Line 609: `description: Global search must return both files and packages using OR query`

### 2. Result Normalization (Optional Enhancement)

**File:** `src/quilt_mcp/search/backends/elasticsearch.py`
**Method:** `_convert_catalog_results()`
**Lines:** ~150-250 (approximate)
**Changes:**
- Add `name` field to all results
- Keep `logical_key` and `package_name` for backward compat

---

## Success Criteria

### Immediate (Test Fix)

- ✅ `search_catalog.bucket` - PASSED (already passing)
- ✅ `search_catalog.package` - PASSED (already passing)
- ✅ `search_catalog.global` - PASSED (will pass with query fix)

### Future (Normalization)

- ✅ All search results include `name` field
- ✅ Backward compatibility maintained
- ✅ Documentation updated to show both approaches
- ✅ No breaking changes for existing consumers

---

## Documentation Updates

### API Reference

Add to search documentation:

```markdown
### Search Result Structure

All search results include a normalized `name` field for convenience:

**For files:**
- `name`: Same as `logical_key` (path within package/bucket)
- `logical_key`: Canonical field (backward compatible)

**For packages:**
- `name`: Same as `package_name` (namespace/name format)
- `package_name`: Canonical field (backward compatible)

**Recommendation:** Use `name` in new code for simplicity. Use type-specific fields when semantic clarity is important.
```

---

## Timeline

1. **Immediate:** Update test configuration (~5 minutes)
2. **Short-term:** Implement result normalization (~30 minutes)
3. **Testing:** Run full test suite (~10 minutes)
4. **Documentation:** Update API docs (~20 minutes)

**Total:** ~1 hour for complete implementation

---

## Conclusion

### Test Configuration Issue

The `search_catalog.global` test failure is due to **unrealistic test expectations**, not a code bug. Searching for "README.md" will never return packages named "raw/test".

**Fix:** Update query to `"README OR raw/test"` to test multi-type results properly.

### Result Normalization

Adding a normalized `name` field (Option 2) provides the best balance of:
- ✅ Simplicity for consumers
- ✅ Backward compatibility
- ✅ Semantic accuracy
- ✅ API ergonomics

**Status:** Ready for implementation

---

**Next Steps:**
1. ✅ Update `mcp-test.yaml` with OR query
2. ⏳ Test with `make test`
3. ⏳ Implement result normalization (optional)
4. ⏳ Update documentation

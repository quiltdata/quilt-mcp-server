# Wildcard Escape Bug: Integration Test Failure Analysis

**Date**: 2025-11-15
**Issue**: Integration test `test_package_entry_handler_parses_real_documents` failing with 0 results
**Root Cause**: Over-aggressive query escaping breaking wildcard searches
**Fix**: Preserve `*` and `?` as wildcards in query escaping function

---

## Problem Statement

Integration test was failing with:
```
AssertionError: CRITICAL: No package ENTRY documents found in quilt-ernest-staging.
Cannot test PackageEntryScopeHandler parsing without real entry data.
```

However, the bucket **DID** have package entries in the `*_packages` index.

---

## Investigation Process

### Initial Misleading Error

The error message was useless:
> "CRITICAL: No package ENTRY documents found in quilt-ernest-staging"

This didn't tell us:
- ❌ What query was executed
- ❌ Which index was searched
- ❌ What Elasticsearch actually returned
- ❌ Why the query returned 0 results

### What We Discovered

1. **Added debug logging** to see the actual Elasticsearch request:
   ```python
   logger.info(f"🔍 Elasticsearch returned {len(hits)} hits (total: {total_count}) from index: {index_pattern}")
   logger.info(f"🔍 Query: {dsl_query}")
   ```

2. **Found the actual query being sent**:
   ```json
   {
     "from": 0,
     "size": 20,
     "query": {
       "query_string": {
         "query": "\\*"
       }
     }
   }
   ```

3. **The smoking gun**: Query string was `"\\*"` not `"*"`

4. **Verified with quilt3.search() directly**:
   ```python
   # This works - returns manifest documents
   q3.search('*', limit=5)

   # This works - returns entry documents
   dsl_query = {
       'query': {
           'bool': {
               'must': [
                   {'query_string': {'query': '*'}},  # NOT escaped!
                   {'exists': {'field': 'entry_pk'}}
               ]
           }
       }
   }
   q3.search(dsl_query, limit=5)
   ```

5. **Confirmed entries exist in the index**:
   ```python
   # Returns actual entry documents with entry_pk, entry_lk, entry_size, etc.
   result[0]['_source'] = {
       "entry_hash": {...},
       "entry_lk": "CORD19.ipynb",
       "entry_pk": "s3://ai2-semanticscholar-cord-19/2020-10-25/CORD19.ipynb",
       "entry_size": 467106
   }
   ```

---

## Root Cause Analysis

### The Bug

**File**: `src/quilt_mcp/search/backends/elasticsearch.py`
**Function**: `escape_elasticsearch_query()`

```python
# BEFORE (buggy)
special_chars = [
    '\\', '+', '-', '=', '>', '<', '!', '(', ')', '{', '}',
    '[', ']', '^', '"', '~',
    '*',  # ❌ This breaks wildcards!
    '?',  # ❌ This breaks single-char wildcards!
    ':', '/',
]
```

### What Was Happening

1. User passes query: `"*"` (match all)
2. Function escapes it: `"\\*"` (literal backslash-asterisk)
3. Elasticsearch interprets it as: "Find documents containing the string `\*`"
4. No documents contain that literal string
5. Result: 0 hits

### Why This Is Wrong

**Elasticsearch Query String Syntax:**
- `*` = wildcard (match zero or more characters)
- `?` = wildcard (match exactly one character)
- `\*` = literal asterisk character
- `\?` = literal question mark character

**Our use case:**
- We WANT wildcards to work
- Query `"*"` should mean "match all documents"
- Query `"*.csv"` should mean "match anything ending in .csv"
- Query `"data?"` should mean "match data followed by any single character"

**When escaping IS needed:**
- User searching for literal special characters in text
- Query `"team/dataset"` → `"team\/dataset"` (escape the slash)
- Query `"size>100"` → `"size\>100"` (escape the greater-than)

---

## The Fix

### Code Change

```python
# AFTER (fixed)
# NOTE: * and ? are INTENTIONALLY OMITTED to preserve wildcard functionality
special_chars = [
    '\\', '+', '-', '=', '>', '<', '!', '(', ')', '{', '}',
    '[', ']', '^', '"', '~', ':', '/',
    # ✅ * and ? removed - they remain as wildcards
]
```

### Updated Documentation

Added clear documentation to the function:

```python
"""Escape special characters in Elasticsearch query_string queries.

IMPORTANT: Wildcards (* and ?) are NOT escaped - they remain as wildcards.
Single * means "match all", ? means "match any single character".

Special characters that ARE escaped:
+ - = && || > < ! ( ) { } [ ] ^ " ~ : \ /

Examples:
    >>> escape_elasticsearch_query("*")
    '*'
    >>> escape_elasticsearch_query("*.csv")
    '*.csv'
"""
```

---

## Test Results

### Before Fix
```
FAILED tests/.../test_package_entry_handler_parses_real_documents
AssertionError: CRITICAL: No package ENTRY documents found
assert 0 > 0
```

### After Fix
```
PASSED tests/.../test_package_entry_handler_parses_real_documents [100%]
✅ All 12 results are ENTRY documents (no manifests)
✅ PackageEntryScopeHandler parsed ENTRY document: CORD19.ipynb
```

---

## Key Learnings

### 1. Error Messages Must Include Context

**BAD error message:**
```
"CRITICAL: No package ENTRY documents found in quilt-ernest-staging"
```

**GOOD error message would be:**
```
"CRITICAL: No package ENTRY documents found in quilt-ernest-staging

Query Details:
  - Index: quilt-ernest-staging_packages
  - Query: {'query_string': {'query': '\\*'}}
  - Total hits: 0
  - Response time: 347ms

Expected: Documents with entry_pk or entry_lk fields
Actual: No documents matched the query

Possible causes:
  1. Index has no entry documents (only manifests)
  2. Query syntax error (check escaping)
  3. Wrong index name
  4. Authentication/permission issue
```

### 2. Test Real Behavior First

When debugging search issues:
1. ✅ Test with the actual library API directly (`quilt3.search()`)
2. ✅ Verify data exists in the index
3. ✅ Compare working vs. broken queries
4. ❌ Don't trust error messages that lack context
5. ❌ Don't assume the test environment is broken

### 3. Wildcard Handling Is Nuanced

Different search systems handle wildcards differently:
- **SQL LIKE**: `%` = multi-char, `_` = single-char
- **Elasticsearch query_string**: `*` = multi-char, `?` = single-char
- **Elasticsearch wildcard query**: Same, but different query type
- **Elasticsearch match_all**: Separate query type entirely

When building search abstractions:
- Know when wildcards should work
- Know when they need escaping
- Document the behavior clearly
- Test both "match all" and "match pattern" queries

### 4. Integration Tests Reveal Real Issues

This bug wouldn't have been caught by unit tests because:
- Unit tests mock Elasticsearch responses
- Unit tests don't test query escaping against real ES
- Only integration tests revealed: "query returns 0 results when it should return many"

**Value of integration tests:**
- ✅ Found query escaping bug
- ✅ Verified correct index is being queried
- ✅ Confirmed entry documents exist and are parseable
- ✅ Validated end-to-end search flow

---

## Impact Analysis

### What Was Broken

**Wildcard searches returned 0 results:**
- `search(query="*", scope="packageEntry")` → 0 results ❌
- `search(query="*.csv", scope="file")` → 0 results ❌
- `search(query="data?", scope="global")` → 0 results ❌

**Regular text searches still worked:**
- `search(query="covid", scope="file")` → results ✅
- `search(query="notebook", scope="packageEntry")` → results ✅

### Who Was Affected

- **MCP tools** using wildcard queries (broken)
- **Direct quilt3.search()** calls (worked fine - bypass our escaping)
- **Integration tests** (correctly caught the bug)
- **End users** trying to browse "all files" or "all packages" (broken)

---

## Related Issues

### Package Entry vs Manifest Documents

While debugging this, we also learned:
- Package indices (`bucket_packages`) contain TWO types of documents:
  1. **Manifest documents**: `ptr_name`, `mnfst_name`, `ptr_last_modified`
  2. **Entry documents**: `entry_pk`, `entry_lk`, `entry_size`, `entry_hash`

- `quilt3.search("*")` by default returns manifests
- To get entries, need explicit filtering:
  ```python
  {
    'query': {
      'bool': {
        'must': [
          {'query_string': {'query': '*'}},
          {'exists': {'field': 'entry_pk'}}  # Filter for entries
        ]
      }
    }
  }
  ```

**Our current implementation:**
- `PackageEntryScopeHandler.parse_result()` filters out manifests (returns None)
- This is correct behavior - we only want entry documents in packageEntry scope
- If we want manifest documents, we'd need a separate `PackageManifestScopeHandler`

---

## Verification Checklist

- [x] Test passes with wildcard query `"*"`
- [x] Test passes with pattern query `"*.csv"`
- [x] Regular text queries still work
- [x] Slash escaping still works: `"team/dataset"` → `"team\/dataset"`
- [x] Operator escaping still works: `"size>100"` → `"size\>100"`
- [x] Documentation updated with wildcard behavior
- [x] Debug logging removed (not needed in production)

---

## Conclusion

A simple one-line fix (removing `*` and `?` from escape list) solved a critical bug that was:
- Breaking all wildcard searches
- Causing integration tests to fail
- Hidden by an unhelpful error message

The real value was in the investigation process:
1. Added proper logging to see actual queries
2. Tested with quilt3 API directly to verify data exists
3. Compared working vs broken query formats
4. Identified escaping as the root cause
5. Fixed and verified

**Time spent**: ~30 minutes of investigation, 2 minutes to fix, 10 minutes to document.

---

## Files Modified

1. **src/quilt_mcp/search/backends/elasticsearch.py**
   - `escape_elasticsearch_query()`: Removed `*` and `?` from escape list
   - Added documentation about wildcard preservation
   - Added examples showing wildcard behavior

2. **tests/integration/test_elasticsearch_index_discovery.py**
   - No changes needed - test passed after fix

3. **spec/a07-search-catalog/22-wildcard-escape-bug.md**
   - This document

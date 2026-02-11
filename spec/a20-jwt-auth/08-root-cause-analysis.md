# A20 JWT Auth: Platform Browse Failure - Root Cause Analysis

**Date:** 2026-02-10
**Status:** RESOLVED
**Severity:** High → Fixed

---

## Executive Summary

Platform backend `browse_content` operations were failing with "Internal Server Error" due to a **GraphQL query requesting `size` field on logical directory groupings**, which don't exist as actual objects in Quilt packages.

**Root Cause:** Packages contain flat logical keys (e.g., `data/file.csv`), not actual directories. The GraphQL query was requesting `size` for `PackageDir` objects, which are merely **visual groupings of file prefixes**, not real objects with computable sizes.

**Fix:** Remove `size` field from directory-related parts of the GraphQL query. Only request `size` for actual files (`PackageFile`).

---

## The Fundamental Misunderstanding

### What We Thought

"Packages contain directories that have sizes."

### The Reality

**Packages contain NO directories.** They contain:
- **Files** with logical keys like `data/experiment1/results.csv`
- **Logical key prefixes** like `data/` that the UI presents as "directories" for navigation

When you browse a package:
- `PackageFile`: An actual file object with size, hash, physical location
- `PackageDir`: A **logical grouping** based on "/" separators in file keys - NOT a real object

---

## Why the Query Failed

### Original GraphQL Query (BROKEN)

```graphql
query BrowseContent($bucket: String!, $name: String!, $path: String!) {
  package(bucket: $bucket, name: $name) {
    revision(hashOrTag: "latest") {
      dir(path: $path) {
        path
        size              # ❌ Requesting size on logical grouping
        children {
          __typename
          ... on PackageFile { path size physicalKey }
          ... on PackageDir { path size }   # ❌ Directories don't have size!
        }
      }
    }
  }
}
```

**Problem:**
- `PackageDir` objects are **synthetic** - they're computed on-the-fly by grouping file prefixes
- They have **no inherent size** - computing it would require recursively summing all children
- The GraphQL server likely fails when trying to compute/return a size for something that doesn't exist

---

## The Fix

### Fixed GraphQL Query (WORKING)

```graphql
query BrowseContent($bucket: String!, $name: String!, $path: String!) {
  package(bucket: $bucket, name: $name) {
    revision(hashOrTag: "latest") {
      dir(path: $path) {
        path              # ✅ Just the path
        children {
          __typename
          ... on PackageFile { path size physicalKey }  # ✅ Files have size
          ... on PackageDir { path }                     # ✅ Dirs are just prefixes
        }
      }
    }
  }
}
```

**Changes:**
- ❌ Removed `size` from `dir(path: $path)`
- ❌ Removed `size` from `PackageDir` fragment
- ✅ Kept `size` only for `PackageFile` (actual files with size)

---

## Test Results

### Before Fix

```bash
TEST_BACKEND_MODE=platform uv run pytest tests/e2e/backend/test_simple_browse.py
❌ FAILED - GraphQL query failed: Internal Server Error
```

### After Fix

```bash
TEST_BACKEND_MODE=platform uv run pytest tests/e2e/backend/test_simple_browse.py
✅ PASSED in 5.37s
```

---

## What "Browsing a Directory" Actually Means

### Question: What does it mean to "browse a directory" in a package?

**Answer:** It's a **metaphor**. You're not browsing a real directory. You're:

1. **Querying logical keys** at a prefix level
2. **Grouping by prefix** to show what "looks like" subdirectories
3. **Filtering files** whose keys start with that prefix

### Example

**Package contains:**
```
data/experiment1/results.csv    (file, 1024 bytes)
data/experiment1/plot.png       (file, 2048 bytes)
data/experiment2/output.txt     (file, 512 bytes)
```

**Browse at path="":**
```
data/   (PackageDir - logical grouping, NO size)
```

**Browse at path="data/":**
```
experiment1/  (PackageDir - logical grouping, NO size)
experiment2/  (PackageDir - logical grouping, NO size)
```

**Browse at path="data/experiment1/":**
```
results.csv   (PackageFile, size=1024)
plot.png      (PackageFile, size=2048)
```

---

## Why We Were Even Trying to Get Directory Sizes

### Context

The platform backend's `browse_content()` method was attempting to mirror the quilt3 backend's behavior. However:

1. **Quilt3 backend** uses the Python SDK, which may compute sizes differently (or not at all for logical groupings)
2. **Platform backend** uses GraphQL API, which explicitly models `PackageDir` as separate from `PackageFile`
3. **GraphQL schema** makes the distinction clear: directories don't have intrinsic size

### Lesson Learned

**Don't request attributes that don't semantically exist.** Just because a field is available in the GraphQL schema doesn't mean it should be requested - especially for derived/synthetic objects like `PackageDir`.

---

## Impact on E2E Tests

### Current Status

**Simple browse test:** ✅ PASSES
```bash
TEST_BACKEND_MODE=platform uv run pytest tests/e2e/backend/test_simple_browse.py
✅ 1 passed in 5.37s
```

**Package lifecycle test:** ⚠️ Different issue
```bash
TEST_BACKEND_MODE=platform uv run pytest tests/e2e/backend/integration/test_package_lifecycle.py
❌ FAILED - Expected file file1.csv not found in browse results: ['test_package_lifecycle']
```

**Note:** The lifecycle test failure is **unrelated to the GraphQL size issue**. It's about test expectations:
- Test expects files at root level
- Files are actually nested under `test_package_lifecycle/{timestamp}/`
- Browse at path="" correctly returns top-level prefix `test_package_lifecycle`
- Test needs adjustment to browse deeper path or check for prefix

---

## Files Changed

### src/quilt_mcp/backends/platform_backend.py

**Lines 240-260** (browse_content method):
- Removed `size` from dir query
- Removed `size` from PackageDir fragment

**Lines 757-778** (_backend_browse_package_content method):
- Removed `size` from dir query
- Removed `size` from PackageDir fragment

---

## Related Issues

1. **Search syntax errors** - Different issue, not addressed by this fix
2. **Package lifecycle test expectations** - Test design issue, not GraphQL schema issue
3. **60s timeout for packageConstruct** - Successfully resolved in parallel with this fix

---

## Conclusion

**The fix was simple once we understood the core issue:**

> **Packages don't have directories. Directories are logical groupings. Logical groupings don't have size. Don't request size for non-existent objects.**

This aligns with the Quilt data model where packages are:
- ✅ Collections of files with logical keys
- ❌ NOT hierarchical directory structures with directory objects

---

## References

- [07-platform-browse-failure.md](./07-platform-browse-failure.md) - Detailed investigation that led to this fix
- [Platform Backend Source](../../src/quilt_mcp/backends/platform_backend.py) - Implementation
- [Simple Browse Test](../../tests/e2e/backend/test_simple_browse.py) - Verification test

---

**Document Status:** Complete root cause analysis with verified fix

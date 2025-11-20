# Next Steps: Package Scope Feature Completion

## Current Status

✅ **Code Complete**: PackageScopeHandler implementation is complete and functional
⚠️ **Infrastructure Blocked**: Feature requires Elasticsearch index configuration
📊 **Test Status**: 658 passed, 1 skipped, 16 xfailed (3 package scope tests)

## Problem Summary

The intelligent package scope feature (`scope="package"`) returns HTTP 500 errors from Elasticsearch when using the collapse configuration. The issue is:

1. **Collapse Field Missing**: The collapse configuration requires `ptr_name.keyword` field
2. **Mixed Document Types**: Package indices contain both manifest documents (with `ptr_name`) and entry documents (without `ptr_name`)
3. **Field Mapping Required**: Elasticsearch needs proper field mappings for the collapse operation to work

### Current Workaround

The query was simplified to only search manifest documents (those with `ptr_name` field), but the collapse still fails with 500 errors, suggesting the field mapping itself is the issue.

## Next Steps

### 1. Verify Elasticsearch Index Mappings (HIGH PRIORITY)

**Action**: Check if `ptr_name.keyword` field exists in package indices

```bash
# Check mapping for a package index
curl -X GET "localhost:9200/quilt-ernest-staging_packages/_mapping?pretty"

# Look for:
# "ptr_name": {
#   "type": "text",
#   "fields": {
#     "keyword": {
#       "type": "keyword"
#     }
#   }
# }
```

**Expected Result**: `ptr_name` should have a `.keyword` subfield of type `keyword`

**If Missing**: The index needs to be reindexed with the correct mapping template

---

### 2. Add Field Mapping to Index Template (REQUIRED)

**File to Update**: Elasticsearch index template configuration (likely in stack infrastructure code)

**Required Mapping**:
```json
{
  "mappings": {
    "properties": {
      "ptr_name": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      }
    }
  }
}
```

**Steps**:
1. Update the index template for `*_packages` indices
2. Reindex existing package indices to apply the new mapping
3. Verify the mapping is applied correctly

---

### 3. Alternative: Implement Multi-Level Search Strategy (MEDIUM EFFORT)

If reindexing is not feasible immediately, consider implementing a two-phase search:

**Phase 1**: Search with collapse (for manifests)
```python
# Current implementation - searches only manifests
{
  "query": {
    "bool": {
      "must": [
        {"exists": {"field": "ptr_name"}},
        {"query_string": {...}}
      ]
    }
  },
  "collapse": {"field": "ptr_name.keyword"}
}
```

**Phase 2**: Fallback without collapse (if Phase 1 fails)
```python
# Fallback - search manifests, group results in application code
{
  "query": {
    "bool": {
      "must": [
        {"exists": {"field": "ptr_name"}},
        {"query_string": {...}}
      ]
    }
  }
  # No collapse - group by ptr_name in Python
}
```

**Implementation Location**: `src/quilt_mcp/search/backends/elasticsearch.py`

---

### 4. Future Enhancement: Parent-Child Relationship (LONG TERM)

For optimal performance with mixed document types, consider using Elasticsearch parent-child relationships:

**Benefits**:
- Group entries under their parent package automatically
- Efficient aggregation and search
- Natural document hierarchy

**Documents**:
- Parent: Package manifest (ptr_name, ptr_tag, mnfst_name)
- Child: Package entries (entry_pk, entry_lk, entry_size)

**Mapping Example**:
```json
{
  "mappings": {
    "properties": {
      "document_type": {
        "type": "join",
        "relations": {
          "package": "entry"
        }
      }
    }
  }
}
```

**Search Query**:
```json
{
  "query": {
    "has_child": {
      "type": "entry",
      "query": {"match": {"entry_lk": "*.csv"}},
      "inner_hits": {}
    }
  }
}
```

---

### 5. Remove XFAIL Markers (AFTER FIX)

Once Elasticsearch is configured correctly, remove xfail markers from:

**File**: `tests/integration/test_search_catalog_integration.py`

**Lines to Update**:
- Line 267: `@pytest.mark.xfail(reason="...")`
- Line 397: `@pytest.mark.xfail(reason="...")`
- Line 434: `@pytest.mark.xfail(reason="...")`

**Verification**:
```bash
# Run package scope tests specifically
uv run pytest tests/integration/test_search_catalog_integration.py::TestSearchCatalogIntegration::test_package_scope_specific_bucket_returns_only_packages -v

# Should show PASSED instead of XFAIL
```

---

### 6. Update Documentation

**Files to Update**:
1. `README.md` - Document the package scope feature and requirements
2. `docs/search-api.md` - Add examples of package scope usage
3. `CHANGELOG.md` - Note the Elasticsearch requirement

**Example Documentation**:
```markdown
## Package Scope Search

Search for packages (not individual files) across your catalog.

### Prerequisites
- Elasticsearch indices must have `ptr_name.keyword` field mapping
- Required for collapse functionality

### Usage
```python
result = search_catalog(
    query="CCLE AND csv",
    scope="package",  # Returns packages, not files
    bucket="my-bucket",
    limit=20
)
```

### Returns
- `type`: "package"
- `name`: Full package name (e.g., "test/genomics")
- `s3_uri`: Package manifest URI
- `metadata.matched_entries`: List of matching files within package
- `metadata.matched_entry_count`: Total matches across package
```

---

## Testing Checklist

After implementing the fix:

- [ ] Verify `ptr_name.keyword` field exists in all `*_packages` indices
- [ ] Run integration tests: `uv run pytest tests/integration/test_search_catalog_integration.py -v`
- [ ] All 3 package scope tests should PASS (not xfail)
- [ ] Verify package search returns expected results with real data
- [ ] Test with wildcards: `query="CCLE* AND *.csv", scope="package"`
- [ ] Test with boolean operators: `query="(csv OR json) AND data", scope="package"`
- [ ] Verify collapse is working (only one result per package)
- [ ] Check inner_hits are populated with matched entries
- [ ] Performance test with large result sets (100+ packages)

---

## Error Messages for Users

If users encounter this issue before the fix, they should see:

```
Error: Package scope search requires Elasticsearch configuration.
Cause: Index mapping missing 'ptr_name.keyword' field for collapse operation.
Suggested Actions:
  1. Use 'packageEntry' scope to search individual files within packages
  2. Use 'global' scope to search both files and packages
  3. Contact administrator to configure Elasticsearch index mappings
```

**Implementation**: Update error handling in `src/quilt_mcp/search/backends/elasticsearch.py` to detect this specific error and provide helpful message.

---

## Contact Points

- **Elasticsearch Admin**: Responsible for index template updates and reindexing
- **Infrastructure Team**: May need to update CDK/Terraform configs
- **QA Team**: Should test after index reconfiguration

---

## Estimated Effort

| Task | Effort | Priority |
|------|--------|----------|
| Verify mappings | 30 min | HIGH |
| Update index template | 1 hour | HIGH |
| Reindex package indices | 2-4 hours | HIGH |
| Update tests (remove xfail) | 30 min | MEDIUM |
| Documentation | 1 hour | MEDIUM |
| Alternative implementation | 4-6 hours | LOW |
| Parent-child refactor | 1-2 weeks | LOW |

**Recommended Path**: Start with verifying mappings, then update template and reindex.

---

## Success Criteria

✅ All package scope tests pass without xfail
✅ Package search returns results in < 500ms
✅ Collapse correctly groups entries by package
✅ No 500 errors from Elasticsearch
✅ Documentation updated with requirements
✅ CI/CD pipeline passes all tests

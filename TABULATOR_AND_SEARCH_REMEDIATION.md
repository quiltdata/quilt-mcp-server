# Tabulator and Search Remediation Analysis

**Date**: October 9, 2025  
**Version**: v0.6.73  
**Issue**: Bucket filtering not working in package search; Tabulator DataFusion errors persist

## Issues Identified

### 1. Bucket Filter Not Working in Package Search

**Problem**: When searching for packages with `filters: {bucket: "nextflowtower"}`, the results show packages from wrong buckets (e.g., "cellxgene-913524946226-us-east-1").

**Root Cause**:
- The search tool wrapper passes `filters: {bucket: "nextflowtower"}` (singular)
- The GraphQL backend's `_search_packages_global` expects `filters: {buckets: ["nextflowtower"]}` (plural, as a list)
- The filter parameter name mismatch causes the bucket filter to be ignored

**Location**: 
- `src/quilt_mcp/search/backends/graphql.py` line 486-490
- `src/quilt_mcp/tools/search.py` line 742

**Current Code** (graphql.py:486-490):
```python
# Extract bucket filter if provided
buckets = []
if filters and "buckets" in filters:
    buckets = filters.get("buckets", [])
    if isinstance(buckets, str):
        buckets = [buckets]
```

**Fix Required**:
```python
# Extract bucket filter if provided (support both 'bucket' and 'buckets')
buckets = []
if filters:
    if "buckets" in filters:
        buckets = filters.get("buckets", [])
        if isinstance(buckets, str):
            buckets = [buckets]
    elif "bucket" in filters:
        # Support singular 'bucket' parameter
        bucket = filters.get("bucket")
        if isinstance(bucket, str):
            buckets = [bucket]
        elif isinstance(bucket, list):
            buckets = bucket
```

### 2. Tabulator DataFusion Metadata Error

**Problem**: The "sail" table in the `nextflowtower` database consistently returns:
```
GENERIC_USER_ERROR: Encountered an exception from your LambdaFunction 
executed in context[retrieving meta-data] with message[Query failed: 
INVALID_FUNCTION_ARGUMENT: undefined group option]
```

**Root Cause**:
- The Tabulator Lambda (last updated 6 months ago) uses an older version of DataFusion
- The underlying Parquet files in the `nextflowtower` bucket use a newer encoding that includes "group" options in the metadata
- The old DataFusion version doesn't recognize these metadata fields, causing it to fail during metadata retrieval (before query execution even begins)

**Why This Persists**:
- Recreating the table doesn't help because it's not a table configuration issue
- The problem is in the Parquet file encoding vs. the DataFusion version mismatch
- The Lambda needs to be updated to a newer DataFusion version that supports the metadata format

**Location**: 
- AWS Lambda: `sales-prod-TabulatorLambda-yXUridthb6qT`
- S3 Bucket: `nextflowtower`
- Database: `nextflowtower`
- Table: `sail`

### 3. AI Analysis Errors in Chat Logs

**Problem**: The AI in the chat logs made several incorrect statements:
1. Claimed to find the "sail-nextflow" table when it was actually "sail"
2. Searched for packages in "nextflowtower" but analyzed results from "cellxgene-913524946226-us-east-1"
3. Did not notice the bucket mismatch in search results

**Root Cause**:
- Bucket filter not working (Issue #1 above) caused the AI to receive irrelevant search results
- AI proceeded with analysis without validating the bucket names in the results
- AI did not have adequate prompting to verify search results match the requested filters

## Recommended Fixes

### Priority 1: Fix Bucket Filtering in Package Search

**File**: `src/quilt_mcp/search/backends/graphql.py`  
**Function**: `_search_packages_global` (line 480)

**Change**:
```python
async def _search_packages_global(
    self, query: str, filters: Optional[Dict[str, Any]], limit: int, offset: int = 0
) -> PackageSearchResponse:
    """Search packages globally using GraphQL searchPackages with pagination support."""

    # Extract bucket filter if provided (support both 'bucket' and 'buckets')
    buckets = []
    if filters:
        if "buckets" in filters:
            buckets = filters.get("buckets", [])
            if isinstance(buckets, str):
                buckets = [buckets]
        elif "bucket" in filters:
            # Support singular 'bucket' parameter for consistency with frontend
            bucket = filters.get("bucket")
            if isinstance(bucket, str):
                buckets = [bucket]
            elif isinstance(bucket, list):
                buckets = bucket

    graphql_query = """
    query SearchPackages($searchString: String!, $order: SearchResultOrder!, $latestOnly: Boolean!, $buckets: [String!]!) {
        searchPackages(buckets: $buckets, searchString: $searchString, latestOnly: $latestOnly) {
            ... on PackagesSearchResultSet {
                total
                stats {
                    size { min max }
                    entries { min max }
                }
                firstPage(order: $order) {
                    cursor
                    hits {
                        id
                        score
                        bucket
                        name
                        pointer
                        hash
                        size
                        modified
                        totalEntriesCount
                        comment
                        workflow
                    }
                }
            }
            ... on EmptySearchResultSet {
                _
            }
        }
    }
    """

    variables = {
        "searchString": query if query and query != "*" else "",
        "order": "BEST_MATCH",
        "latestOnly": False,
        "buckets": buckets,  # Now correctly populated
    }
    
    # ... rest of function unchanged
```

**Test**: 
```python
# Should now correctly filter to nextflowtower bucket
search(
    action="unified_search",
    params={
        "query": "*",
        "scope": "catalog",
        "search_type": "packages",
        "filters": {"bucket": "nextflowtower"}
    }
)
```

### Priority 2: Update Tabulator Lambda

**Recommendation**: Contact Quilt support to update the Tabulator Lambda to a newer DataFusion version.

**Workaround** (until Lambda is updated):
1. Use direct Athena queries instead of Tabulator:
   ```sql
   -- Create an Athena external table pointing to the same data
   CREATE EXTERNAL TABLE nextflowtower_sail (
       Name STRING,
       Length INT,
       EffectiveLength FLOAT,
       TPM FLOAT,
       NumReads FLOAT
   )
   STORED AS PARQUET
   LOCATION 's3://nextflowtower/path/to/data/';
   
   -- Then query via Athena
   SELECT * FROM nextflowtower_sail LIMIT 10;
   ```

2. Alternatively, export the table configuration and recreate it in a bucket with compatible Parquet encoding.

**Contact**: Quilt support at support@quiltdata.com
- Lambda: `sales-prod-TabulatorLambda-yXUridthb6qT`
- Region: `us-east-1`
- Account: `850787717197`
- Issue: DataFusion version needs update to support newer Parquet metadata format

### Priority 3: Improve AI Search Result Validation

**File**: `src/quilt_mcp/tools/search.py`  
**Function**: `unified_search` docstring

**Enhancement**: Add to docstring:
```
    Important Notes:
        - Always verify that returned results match the requested bucket/scope filters
        - If results show unexpected buckets, check if the bucket filter is working correctly
        - For bucket-scoped searches, all results should have matching bucket names
```

## Testing Checklist

### Bucket Filtering Tests

- [ ] Test package search with `filters: {bucket: "nextflowtower"}`
- [ ] Verify all results have `bucket: "nextflowtower"`
- [ ] Test with multiple buckets: `filters: {buckets: ["bucket1", "bucket2"]}`
- [ ] Test backward compatibility with `filters: {buckets: ["nextflowtower"]}`
- [ ] Test object search with bucket filter
- [ ] Test unified search with bucket filter

### Tabulator Tests

- [ ] Verify "sail" table still returns DataFusion error (expected until Lambda updated)
- [ ] Test Athena workaround query
- [ ] Test other Tabulator tables in different buckets (should work if Parquet encoding compatible)
- [ ] After Lambda update: re-test "sail" table

### Integration Tests

- [ ] Test full search workflow via browser on demo.quiltdata.com
- [ ] Test AI analysis of search results (should now correctly identify bucket mismatches)
- [ ] Test Tabulator table listing
- [ ] Test admin tool with various actions

## Deployment Plan

1. **Immediate** (can deploy now):
   - Fix bucket filtering in `graphql.py`
   - Add unit tests for bucket filtering
   - Update integration tests

2. **Short-term** (requires Quilt support):
   - Contact Quilt support for Lambda update
   - Implement Athena workaround for urgent queries
   - Document Tabulator limitations in user-facing docs

3. **Medium-term** (after Lambda update):
   - Re-test all Tabulator tables
   - Remove workaround documentation
   - Add regression tests for Parquet encoding compatibility

## Impact Analysis

### Bucket Filtering Fix
- **Severity**: High - search results are incorrect
- **User Impact**: High - users cannot reliably search within specific buckets
- **Fix Complexity**: Low - single function change
- **Test Complexity**: Low - existing test infrastructure
- **Deployment Risk**: Low - backward compatible change

### Tabulator DataFusion Error
- **Severity**: Medium - specific table affected, others may work
- **User Impact**: Medium - users cannot query this specific table via Tabulator
- **Fix Complexity**: Medium - requires AWS Lambda update by Quilt team
- **Workaround Available**: Yes - direct Athena queries
- **Deployment Risk**: N/A - external dependency

## Next Steps

1. **Fix and test bucket filtering** (Est: 2 hours)
   - Implement change in `graphql.py`
   - Add unit tests
   - Run integration tests
   - Update CLAUDE.md with learning

2. **Deploy v0.6.74** (Est: 30 min)
   - Build Docker image
   - Push to ECR
   - Update ECS task

3. **Contact Quilt support** (Est: 15 min)
   - Send email with Lambda details
   - Include error messages and diagnosis
   - Request Lambda update timeline

4. **Document workaround** (Est: 30 min)
   - Add Athena query examples to docs
   - Update Tabulator tool docstring
   - Add to CLAUDE.md

## Conclusion

The bucket filtering issue is a straightforward fix that should restore correct search functionality. The Tabulator DataFusion error requires external support but has a viable workaround. Both issues are well-understood and have clear remediation paths.


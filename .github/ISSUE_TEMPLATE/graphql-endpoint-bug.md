---
name: 🐛 GraphQL Endpoint Internal Server Error
about: Demo catalog GraphQL endpoint has server-side errors on firstPage queries
title: 'GraphQL Bug: Internal Server Error on searchPackages.firstPage queries'
labels: ['bug', 'graphql', 'demo-catalog', 'server-side']
assignees: []
---

## 🐛 Bug Description

The demo catalog GraphQL endpoint (`https://demo-registry.quiltdata.com/graphql`) returns "Internal Server Error" when executing `searchPackages` queries that include `firstPage` field requests.

## 🔍 Error Details

### GraphQL Error Response
```json
{
  "data": null,
  "errors": [
    {
      "locations": [
        {
          "column": 13,
          "line": 6
        }
      ],
      "message": "Internal Server Error",
      "path": [
        "searchPackages",
        "firstPage"
      ]
    }
  ]
}
```

### HTTP Response
- **Status Code**: 200 (GraphQL errors are returned as 200 with error payload)
- **Content-Type**: application/json
- **Server**: nginx

## 🧪 Reproduction Steps

1. **Authentication**: Ensure logged in with `quilt3 login` to demo catalog
2. **Execute Query**:
   ```graphql
   query TestSearchPackages {
       searchPackages(buckets: [], searchString: "genomics") {
           ... on PackagesSearchResultSet {
               total
               firstPage(size: 2) {
                   hits {
                       name
                       score
                   }
               }
           }
       }
   }
   ```
3. **Observe**: Query returns Internal Server Error on firstPage field

## ✅ What Works

### Working Queries
- ✅ **`bucketConfigs`**: `query { bucketConfigs { name } }` → 74 buckets
- ✅ **`searchPackages` (total only)**: Returns total count (11,496 packages)
- ✅ **Authentication**: Bearer token authentication working correctly

### Working Code Pattern
```python
from quilt_mcp.tools.graphql import catalog_graphql_query

# This works:
result = catalog_graphql_query('query { searchPackages(buckets: [], searchString: "genomics") { ... on PackagesSearchResultSet { total } } }', {})
# Returns: {"success": True, "data": {"searchPackages": {"total": 11496}}}

# This fails:
result = catalog_graphql_query('query { searchPackages(...) { ... firstPage { hits { name } } } }', {})
# Returns: {"success": False, "errors": [{"message": "Internal Server Error", "path": ["searchPackages", "firstPage"]}]}
```

## ❌ What Fails

### Failing Queries
- ❌ **`searchPackages.firstPage`**: Internal Server Error
- ❌ **Schema Introspection**: `__schema` queries timeout/fail
- ❌ **Complex Object Queries**: `objects` queries with results timeout

## 🔧 Current Workaround

Our unified search architecture handles this gracefully:

1. **Health Check**: Uses working `bucketConfigs` query
2. **Package Count**: Uses `searchPackages` total for package discovery
3. **Fallback**: Uses Elasticsearch + S3 for actual result retrieval
4. **Error Handling**: Detailed error reporting with GraphQL error unpacking

## 🎯 Impact Assessment

### Current Impact
- **Minimal**: System continues to function with Elasticsearch + S3 backends
- **Performance**: Sub-second search responses maintained
- **Functionality**: All search capabilities available through alternative backends

### Missing Capabilities (When GraphQL Fixed)
- **Rich Package Metadata**: Package relationships, workflow info, match locations
- **User Metadata Filtering**: Custom metadata predicates with type safety
- **Advanced Package Search**: Detailed package results with scores and metadata

## 🏥 Health Check Status

### Backend Availability
- **Elasticsearch**: ✅ Available (primary search backend)
- **GraphQL**: ⚠️ Partially available (metadata queries work, result queries fail)
- **S3**: ✅ Available (reliable fallback)

### System Resilience
- ✅ **Graceful Degradation**: Continues with available backends
- ✅ **Error Reporting**: Clear indication of GraphQL issues
- ✅ **Performance**: No impact on overall search performance

## 🔬 Technical Analysis

### Server-Side Issue
- **Location**: Demo catalog GraphQL resolver for `SearchHitPackage` results
- **Scope**: Affects `firstPage` field on `PackagesSearchResultSet`
- **Severity**: Medium (workarounds available, core functionality intact)

### Client-Side Verification
- ✅ **Authentication**: Proper bearer token in requests
- ✅ **Query Syntax**: Valid GraphQL syntax (simple queries work)
- ✅ **Error Handling**: Proper error detection and reporting
- ✅ **Fallback Logic**: Appropriate degradation to working backends

## 🛠️ Proposed Resolution

### Server-Side (Quilt Team)
1. **Investigate**: Check demo catalog GraphQL resolver for `SearchHitPackage.firstPage`
2. **Debug**: Review server logs for Internal Server Error details
3. **Fix**: Resolve server-side issue with package result pagination
4. **Test**: Verify `firstPage` queries return proper results

### Client-Side (Our Implementation)
- ✅ **Already Implemented**: Graceful error handling and fallback
- ✅ **Already Implemented**: Detailed error reporting for troubleshooting
- ✅ **Ready**: Will automatically use full GraphQL capabilities when fixed

## 🧪 Testing Instructions

### Verify Bug Still Exists
```bash
# Test the failing query
python -c "
from quilt_mcp.tools.graphql import catalog_graphql_query
result = catalog_graphql_query('query { searchPackages(buckets: [], searchString: \"test\") { ... on PackagesSearchResultSet { firstPage(size: 1) { hits { name } } } } }', {})
print(f'Success: {result.get(\"success\", False)}')
if not result.get('success'):
    print(f'Error: {result.get(\"errors\", result.get(\"error\", \"Unknown\"))}')
"
```

### Verify Workaround Works
```bash
# Test our unified search still works
python -c "
import asyncio
from quilt_mcp.search.tools.unified_search import unified_search
result = asyncio.run(unified_search('genomics packages', limit=3))
print(f'Unified search works: {result[\"success\"]}')
print(f'Results: {len(result.get(\"results\", []))}')
"
```

## 📋 Environment Details

- **Catalog**: demo.quiltdata.com
- **Registry**: demo-registry.quiltdata.com  
- **GraphQL Endpoint**: demo-registry.quiltdata.com/graphql
- **Authentication**: quilt3 bearer token (working)
- **User Agent**: quilt-python/6.3.1

## 🎯 Priority

**Medium Priority**: 
- System continues to function with excellent performance
- Affects demo environment primarily
- Enterprise environments may not have this issue
- Workarounds are robust and production-ready

---

**Related Implementation**: `feature/unified-search-architecture` branch
**Workaround Status**: ✅ Complete and tested
**Enterprise Readiness**: ✅ Ready for deployment



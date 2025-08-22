# Search Architecture Troubleshooting

## GraphQL Backend Issues

### Symptom: GraphQL Backend Shows "Error" Status

The GraphQL backend may show as unavailable with error messages like:
- `"GraphQL request failed: 'message'"`
- `"GraphQL access check failed: 'message'"`

### Common Causes & Solutions

#### 1. Demo Catalog GraphQL Limitations
**Issue**: Demo catalogs may not have full GraphQL endpoints enabled
**Solution**: This is expected behavior. The system gracefully falls back to Elasticsearch + S3

#### 2. Enterprise Catalog Authentication
**Issue**: Enterprise GraphQL requires proper authentication tokens
**Solution**: Ensure you're logged in with `quilt3 login` and have proper permissions

#### 3. Network/Connectivity Issues
**Issue**: GraphQL endpoint may be temporarily unavailable
**Solution**: The system automatically falls back to available backends

### Verification Steps

1. **Check Authentication**:
   ```python
   import quilt3
   print(f"Logged in: {quilt3.logged_in()}")
   session = quilt3.session.get_session()
   print(f"Has auth header: {'Authorization' in session.headers}")
   ```

2. **Test Working GraphQL Tool**:
   ```python
   from quilt_mcp.tools.buckets import bucket_objects_search_graphql
   result = bucket_objects_search_graphql('bucket-name', {}, first=1)
   print(f"Working tool success: {result.get('success', False)}")
   ```

3. **Check Backend Status**:
   ```python
   from quilt_mcp.search.tools.unified_search import get_search_engine
   engine = get_search_engine()
   backends = [(b.backend_type.value, b.status.value) for b in engine.registry._backends.values()]
   print(f"Backend status: {backends}")
   ```

### Expected Behavior

#### Demo/Community Catalogs
- **Elasticsearch**: ✅ Available (primary search)
- **GraphQL**: ⚠️ Unavailable (expected)
- **S3**: ✅ Available (fallback)
- **Result**: Full functionality with 2-backend coverage

#### Enterprise Catalogs  
- **Elasticsearch**: ✅ Available (fast search)
- **GraphQL**: ✅ Available (rich metadata)
- **S3**: ✅ Available (fallback)
- **Result**: Full functionality with 3-backend coverage

## Performance Troubleshooting

### Slow Search Responses

1. **Check Backend Performance**:
   ```python
   result = await unified_search("your query", explain_query=True)
   backend_status = result["backend_status"]
   for backend, status in backend_status.items():
       print(f"{backend}: {status['query_time_ms']}ms")
   ```

2. **Optimize Query**:
   - Add file extension filters: `"CSV files"` vs `"files"`
   - Use specific scope: `scope="bucket"` vs `scope="global"`
   - Limit results: `limit=10` vs `limit=100`

3. **Backend Selection**:
   - Force fast backend: `backends=["elasticsearch"]`
   - Skip slow backends: `backends=["elasticsearch", "s3"]`

### No Results Found

1. **Check Query Classification**:
   ```python
   from quilt_mcp.search.core.query_parser import parse_query
   analysis = parse_query("your query")
   print(f"Detected type: {analysis.query_type.value}")
   print(f"Keywords: {analysis.keywords}")
   ```

2. **Try Alternative Queries**:
   ```python
   suggestions = search_suggest("your partial query")
   print(f"Suggestions: {suggestions['suggestions']['query_completions']}")
   ```

3. **Check Backend Availability**:
   - Elasticsearch down → Try S3: `backends=["s3"]`
   - All backends down → Check authentication and network

## Integration Issues

### Tool Not Found in MCP Server

If unified search tools aren't available in the MCP server:

1. **Check Registration**: Ensure tools are registered in `app/quilt_mcp/tools/__init__.py`
2. **Import Path**: Verify `from quilt_mcp.search import unified_search` works
3. **Module Loading**: Check for import errors in search modules

### Async Function Issues

The search tools are async. Ensure proper usage:

```python
# Correct usage
import asyncio
result = await unified_search("query")

# Or for non-async contexts
result = asyncio.run(unified_search("query"))
```

## Best Practices

### Query Optimization
- **Be Specific**: `"CSV files in genomics packages"` vs `"data"`
- **Use Filters**: Include size, date, or type constraints
- **Scope Appropriately**: Use `bucket` or `package` scope when possible

### Error Handling
- **Check Success**: Always verify `result["success"]` before using results
- **Handle Fallbacks**: System continues with available backends
- **Monitor Performance**: Use `explain_query=True` for optimization

### Enterprise Features
- **User Metadata**: Use GraphQL for custom metadata filtering
- **Relationships**: Leverage package dependency queries
- **Analytics**: Use GraphQL statistics and faceting capabilities

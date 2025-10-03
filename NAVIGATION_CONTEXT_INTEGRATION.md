# Navigation Context Integration 🧭

## Overview

The frontend provides **navigation context** via the MCP client that tells us:
- Current bucket user is viewing
- Current package (if viewing a package)  
- Current package hash/version
- Current file path (if viewing a file)

This context is **automatically available** when tools are called from the frontend!

---

## How It Works

### Frontend → MCP Client

```javascript
// Frontend sends navigation context with tool calls
await mcpClient.callTool('search', {
  action: 'unified_search',
  params: {
    query: 'csv files',
    // Navigation context is passed automatically or explicitly
    _context: {
      bucket: 'quilt-sandbox-bucket',
      package: 'demo-team/visualization-showcase',
      hash: '4bb163860a05c57b496f01f5f824854f5ae720a9cc0516ed99cab4ca88b252f4',
      path: 'data/measurements.csv'
    }
  }
});
```

### MCP Server (Backend)

Tools can access navigation context to:
- Default search scope to current bucket
- Create browsing sessions for current package
- Generate links to current package files
- Provide context-aware results

---

## Use Cases

### 1. Smart Search Defaults ✅

**User is viewing**: `quilt-sandbox-bucket/demo-team/viz-showcase`  
**User asks**: "find CSV files"  

**Without context**:
```python
# Searches globally across all buckets
search.unified_search(query="csv files")
```

**With context**:
```python
# Automatically scopes to current package
search.unified_search(
    query="csv files",
    scope="package",  # inferred from context
    target="demo-team/viz-showcase"  # from context
)
```

### 2. Automatic Browsing Sessions ✅

**User is viewing**: Package file browser  
**User asks**: "show me the README"

**With context**:
```python
# Automatically create browsing session for current package
session = catalog_create_browsing_session(
    bucket=context['bucket'],  # from navigation
    package_name=context['package'],  # from navigation  
    package_hash=context['hash'],  # from navigation
    ...
)
url = catalog_browse_file(session_id, path="README.md", ...)
```

### 3. Context-Aware File Operations ✅

**User is viewing**: `s3://quilt-sandbox-bucket/data/raw/`  
**User asks**: "upload this CSV"

**With context**:
```python
# Default upload location from current path
buckets.objects_put(
    bucket=context['bucket'],  # from navigation
    objects=[{
        'key': f"{context['path']}/new_file.csv",  # contextual path
        'text': csv_content
    }]
)
```

---

## Implementation Strategy

### Phase 1: Extract Navigation Context

Add helper function to extract context from tool parameters:

```python
# src/quilt_mcp/runtime/context_helpers.py

def get_navigation_context(params: Dict[str, Any]) -> Dict[str, Any]:
    """Extract navigation context from tool parameters.
    
    The frontend may pass context in various ways:
    - _context key in params
    - Direct bucket/package params
    - HTTP headers (X-Quilt-Context)
    
    Returns:
        Dict with keys: bucket, package, hash, path
    """
    context = {}
    
    # Check for explicit _context parameter
    if '_context' in params:
        context.update(params['_context'])
    
    # Check for direct parameters
    if 'bucket' in params:
        context['bucket'] = params['bucket']
    if 'package' in params:
        context['package'] = params['package']
    if 'hash' in params:
        context['hash'] = params['hash']
    if 'path' in params:
        context['path'] = params['path']
    
    return context
```

### Phase 2: Update Search Tool

```python
# src/quilt_mcp/tools/search.py

async def unified_search(
    query: str,
    scope: str = "global",
    target: str = "",
    **params
) -> Dict[str, Any]:
    """Unified search with navigation context awareness."""
    
    # Extract navigation context
    nav_context = get_navigation_context(params)
    
    # Auto-scope if context available and scope not specified
    if not target and nav_context.get('bucket'):
        if nav_context.get('package') and scope == "global":
            # User is in a package - search within package
            scope = "package"
            target = f"{nav_context['bucket']}/{nav_context['package']}"
        elif scope == "global":
            # User is in a bucket - search within bucket
            scope = "bucket"
            target = nav_context['bucket']
    
    # Continue with search...
    return await _unified_search(query, scope, target, ...)
```

### Phase 3: Update Bucket Tools

```python
# src/quilt_mcp/tools/buckets.py

def bucket_object_link(
    path: str,
    **params
) -> Dict[str, Any]:
    """Generate presigned URL for file using navigation context."""
    
    # Extract navigation context
    nav_context = get_navigation_context(params)
    
    # Require package context for browsing session
    if not nav_context.get('package'):
        return {
            'error': 'Package context required. Navigate to a package first.'
        }
    
    # Create browsing session for current package
    session = catalog_create_browsing_session(
        bucket=nav_context['bucket'],
        package_name=nav_context['package'],
        package_hash=nav_context['hash'],
        ...
    )
    
    # Get presigned URL
    url = catalog_browse_file(
        session_id=session['id'],
        path=path,
        ...
    )
    
    return {'url': url, 'expires': session['expires']}
```

---

## Benefits

✅ **Smart Defaults**: Tools use current page context  
✅ **Less Typing**: Users don't need to specify bucket/package  
✅ **Better UX**: Actions apply to what user is viewing  
✅ **Browsing Sessions Work**: Package context enables file access  
✅ **Context-Aware Search**: Results relevant to current view  

---

## Frontend Integration

### Option 1: Automatic Context Injection

Frontend MCP client automatically adds navigation context to all tool calls:

```javascript
class QuiltMCPClient {
  async callTool(tool, params) {
    // Inject current navigation context
    const enrichedParams = {
      ...params,
      _context: this.getCurrentNavigationContext()
    };
    
    return await this.mcp.callTool(tool, enrichedParams);
  }
  
  getCurrentNavigationContext() {
    // Get from router or redux store
    const location = window.location.pathname;
    // Parse: /b/bucket/packages/name/tree/hash/path
    return {
      bucket: extractBucket(location),
      package: extractPackage(location),
      hash: extractHash(location),
      path: extractPath(location)
    };
  }
}
```

### Option 2: Explicit Context Parameter

Frontend can explicitly pass context when needed:

```javascript
// User clicks "Search within this package"
await mcpClient.callTool('search', {
  action: 'unified_search',
  params: {
    query: userQuery,
    _context: {
      bucket: currentBucket,
      package: currentPackage,
      hash: currentHash
    }
  }
});
```

---

## Migration Path

### Stage 1: Add Context Helpers ✅
- Create `get_navigation_context()` helper
- Make it safe (fallback to empty dict)
- No breaking changes

### Stage 2: Update Search Tool ✅
- Add context awareness to `unified_search`
- Use context for smart scope defaults
- Still allow explicit params to override

### Stage 3: Update Bucket Tools 🔄
- Implement `bucket_object_link` with browsing sessions
- Use navigation context for package info
- Return user-friendly errors if context missing

### Stage 4: Update Other Tools 📋
- Packaging tools can use context
- Governance tools can use context
- Visualization tools can use context

---

## Examples

### Example 1: Search CSV Files

**User viewing**: `quilt-sandbox-bucket`

```javascript
// Frontend call
search.unified_search({
  query: "*.csv",
  _context: { bucket: "quilt-sandbox-bucket" }
});

// Backend auto-scopes to bucket
// Returns CSV files from quilt-sandbox-bucket only
```

### Example 2: Get File Link

**User viewing**: `demo-team/viz-showcase @ hash:4bb1638...`

```javascript
// Frontend call
buckets.object_link({
  path: "data/measurements.csv",
  _context: {
    bucket: "quilt-sandbox-bucket",
    package: "demo-team/viz-showcase",
    hash: "4bb163860a05c57b496f01f5f824854f5ae720a9cc0516ed99cab4ca88b252f4"
  }
});

// Backend creates browsing session
// Returns presigned URL for measurements.csv
```

### Example 3: Create Package

**User viewing**: `quilt-sandbox-bucket`

```javascript
// Frontend call
packaging.create({
  name: "my-new-package",
  files: ["s3://quilt-sandbox-bucket/data/file1.csv"],
  _context: { bucket: "quilt-sandbox-bucket" }
});

// Backend infers registry from context
// Creates package in quilt-sandbox-bucket
```

---

## Security Considerations

✅ **Always validate context**: Don't trust client-provided context blindly  
✅ **Check JWT permissions**: Ensure user has access to context bucket/package  
✅ **Audit logging**: Log context usage for security audits  
✅ **Fallback gracefully**: If context invalid, return helpful error  

---

## Next Steps

1. ✅ **DONE**: Document navigation context approach
2. 🔄 **TODO**: Add `get_navigation_context()` helper
3. 🔄 **TODO**: Update search tool to use context
4. 🔄 **TODO**: Implement bucket tools with browsing sessions + context
5. 🔄 **TODO**: Test with frontend navigation context
6. 🔄 **TODO**: Update other tools to leverage context

---

## Conclusion

Navigation context makes MCP tools **context-aware** and **intelligent**:

- Search knows what you're viewing
- File operations default to current location  
- Browsing sessions work automatically with package context
- Users get better, more relevant results

This solves the "how do we know which package?" problem! 🎉


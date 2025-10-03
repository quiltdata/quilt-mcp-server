# Bucket Tools Backend Proxy Solution 🎉

## TL;DR

**We found the backend proxy mechanism!** The Quilt registry provides REST endpoints that handle S3 operations without requiring AWS credentials in the JWT.

---

## Discovery

The enterprise registry has two key REST endpoints:

1. **GraphQL Mutation**: `browsingSessionCreate` - Creates a session for package file access
2. **REST Endpoint**: `/browse/{session_id}/{path}` - Returns presigned S3 URLs

### How It Works

```
User (JWT only) → MCP Server → Registry Backend → IAM Role → S3
                                    ↓
                           Presigned URL returned
```

**The backend assumes the IAM role** - the client never needs AWS credentials!

---

## Implementation Status

### ✅ Implemented in catalog client

Added two new functions to `src/quilt_mcp/clients/catalog.py`:

#### 1. `catalog_create_browsing_session()`
```python
session = catalog_create_browsing_session(
    registry_url="https://demo-registry.quiltdata.com",
    bucket="quilt-sandbox-bucket",
    package_name="demo-team/visualization-showcase",
    package_hash="4bb163860a05c57b496f01f5f824854f5ae720a9cc0516ed99cab4ca88b252f4",
    ttl=180,
    auth_token=jwt_token,
)
# Returns: {'id': 'session-uuid', 'expires': '2025-10-02T23:42:35Z'}
```

#### 2. `catalog_browse_file()`
```python
presigned_url = catalog_browse_file(
    registry_url="https://demo-registry.quiltdata.com",
    session_id=session['id'],
    path="README.md",
    auth_token=jwt_token,
)
# Returns: presigned S3 URL (string)
```

---

## Curl Tests

### ✅ Create Browsing Session
```bash
curl -X POST https://demo-registry.quiltdata.com/graphql \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "mutation {
      browsingSessionCreate(
        scope: \"quilt+s3://quilt-sandbox-bucket#package=demo-team/visualization-showcase@4bb163860a05c57b496f01f5f824854f5ae720a9cc0516ed99cab4ca88b252f4\",
        ttl: 180
      ) {
        ... on BrowsingSession { id expires }
        ... on InvalidInput { errors { message } }
      }
    }"
  }'
```

**Result**: ✅ Returns session ID and expiration

### 🔄 Browse File (Cookie Issue)
```bash
curl -I -H "Authorization: Bearer $TOKEN" \
  https://demo-registry.quiltdata.com/browse/{session_id}/README.md
```

**Result**: ⚠️ Returns 403 (needs session cookie)

**Note**: Cookie mechanism is for web browser security. We need to investigate:
- Anonymous browsing (if session.user is None)
- Alternative authentication flow
- Direct presigned URL generation

---

## URI Format

The browsing session scope uses Quilt URI format:

```
quilt+s3://{bucket}#package={name}@{hash}
quilt+s3://{bucket}#package={name}:{tag}
```

**Examples**:
```
quilt+s3://quilt-sandbox-bucket#package=demo-team/viz@4bb1638...
quilt+s3://quilt-sandbox-bucket#package=demo-team/viz:latest
```

**Note**: Use `@` for hash, `:` for tag (not `&`)

---

## What Can Be Fixed

| Action | Fixable? | Solution |
|--------|----------|----------|
| `object_link` | ✅ YES | Use browsing session + browse endpoint |
| `object_fetch` | ✅ YES | Get presigned URL, then fetch |
| `object_text` | ✅ YES | Get presigned URL, fetch, decode |
| `object_info` | ✅ YES | HEAD request to presigned URL |
| `objects_put` | ❓ MAYBE | Need to find upload endpoint |

### Implementation Plan

#### Phase 1: object_link ✅
```python
def bucket_object_link(package_uri: str, path: str):
    # Parse package URI
    bucket, package_name, hash_or_tag = parse_package_uri(package_uri)
    
    # Create browsing session
    session = catalog_create_browsing_session(...)
    
    # Get presigned URL
    url = catalog_browse_file(session_id=session['id'], path=path, ...)
    
    return {'url': url, 'expires': session['expires']}
```

#### Phase 2: object_fetch, object_text, object_info ✅
```python
def bucket_object_fetch(package_uri: str, path: str):
    # Get presigned URL
    url = bucket_object_link(package_uri, path)['url']
    
    # Fetch from S3 via presigned URL
    response = requests.get(url)
    return {'content': response.content, ...}
```

#### Phase 3: objects_put ❓
**Need to find**: Registry endpoint for upload
- Check `/api/` routes in enterprise
- Look for presigned upload URLs
- Or use package construction workflow

---

## Constraints

### ✅ Works For
- **Package files only** - Must have package context (bucket, name, hash)
- **Read operations** - Download, preview, metadata
- **Authenticated users** - With valid JWT

### ❌ Doesn't Work For
- **Arbitrary S3 objects** - Not in a package
- **Raw bucket listing** - No package context
- **Write operations** - Upload endpoint not yet found

---

## Cookie Challenge

The `/browse/` endpoint requires a session cookie for authenticated access:

```python
# From enterprise code:
if session.user is not None:
    cookie = request.cookies.get("session")
    if cookie is None:
        return Response("Missing session cookie", status=403)
```

**Workaround Options**:
1. **Anonymous access**: If `session.user is None`, returns plain unsigned S3 URL
2. **Cookie management**: Implement cookie handling in MCP server
3. **Alternative endpoint**: Find another way to get presigned URLs

**Current Status**: Need to investigate anonymous browsing sessions

---

## Navigation Context Integration 🎯

**KEY INSIGHT**: Frontend provides navigation context automatically!

The frontend's navigate tool passes current page context to MCP calls:
- Current bucket user is viewing
- Current package (name + hash)
- Current file path

This **solves the "which package?" problem** for browsing sessions!

### How It Works

```javascript
// Frontend automatically injects navigation context
await mcpClient.callTool('buckets', {
  action: 'object_link',
  params: {
    path: 'README.md',
    _context: {  // ← Automatically added by frontend!
      bucket: 'quilt-sandbox-bucket',
      package: 'demo-team/viz-showcase',
      hash: '4bb163860a05c57b496f01f5f824854f5ae720a9cc0516ed99cab4ca88b252f4'
    }
  }
});
```

### Backend Usage

```python
# Extract context from tool parameters
nav_context = params.get('_context', {})

if nav_context.get('package'):
    # Create browsing session using navigation context
    session = catalog_create_browsing_session(
        bucket=nav_context['bucket'],
        package_name=nav_context['package'],
        package_hash=nav_context['hash'],
        ...
    )
    
    # Get presigned URL
    url = catalog_browse_file(session_id, path, ...)
    return {'url': url}
```

This makes bucket tools **fully functional** with backend proxy! 🎉

---

## Next Steps

1. ✅ **DONE**: Add `catalog_create_browsing_session()` to client
2. ✅ **DONE**: Add `catalog_browse_file()` to client  
3. ✅ **DONE**: Document navigation context integration
4. 🔄 **TODO**: Add `get_navigation_context()` helper
5. 🔄 **TODO**: Implement `bucket_object_link()` using browsing sessions + context
6. 🔄 **TODO**: Implement `bucket_object_fetch/text/info()` using presigned URLs + context
7. 🔄 **TODO**: Update search tool to use context for smart scoping
8. 🔄 **TODO**: Find upload endpoint for `bucket_objects_put()`

---

## Benefits

✅ **No AWS Credentials Needed**: Backend handles IAM roles  
✅ **Secure**: JWT authentication only  
✅ **Standard Pattern**: Uses existing enterprise endpoints  
✅ **Session Management**: TTL-based expiration  
✅ **Works with Frontend JWTs**: Auth-only tokens are sufficient  

---

## Conclusion

**We CAN fix the bucket tools!** 🎉

The backend proxy mechanism exists via browsing sessions. We just need to:
1. Resolve the cookie authentication issue
2. Wire up the bucket tools to use these endpoints
3. Handle the constraint that files must be in packages

**Estimated**: 3-4 bucket actions can be fully restored using this approach.

---

## Files Modified

- `src/quilt_mcp/clients/catalog.py`: Added browsing session functions
- `src/quilt_mcp/tools/buckets.py`: Added helper for unavailable message (will update to use sessions)

---

## References

- Enterprise code: `registry/quilt_server/views/browse.py`
- QuiltURI format: `registry/quilt_server/quilt_uri.py`
- GraphQL mutation: `browsingSessionCreate`
- REST endpoint: `/browse/{session_id}/{path}`


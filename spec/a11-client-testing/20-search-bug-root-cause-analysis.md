# Search Bug Root Cause Analysis

**Date:** 2026-01-30
**Branch:** a11-jwt-client
**Investigator:** AI Analysis
**Bug:** search_catalog returns 0 results in HTTP+JWT mode but works in stdio mode

## Executive Summary

I successfully reproduced the search bug and identified the **root cause**: The search backend checks for a local quilt3 session, but JWT authentication only stores catalog credentials in runtime metadata without properly configuring quilt3's authenticated session.

### Key Finding

**The Bug:** `search_catalog` works in stdio mode (where local `~/.quilt/quilt3` session exists) but fails in HTTP+JWT stateless mode with error: **"No quilt3 session configured"**

**Root Cause:** The `JWTAuthService._configure_quilt3_session()` method calls `quilt3.config(catalog_url)` which only sets the catalog URL, but **never authenticates** quilt3 with the catalog token extracted from the JWT.

---

## Reproduction Success

### Test Script Fixes

Fixed the reproduction script [reproduce_search_bug.py](../../scripts/tests/reproduce_search_bug.py) to:

1. Handle Server-Sent Events (SSE) responses correctly
2. Extract and include MCP session IDs in subsequent requests
3. Provide detailed error responses

### Reproduction Output

```
================================================================================
STEP 3: Initializing MCP Session with Catalog JWT
================================================================================
✅ MCP session initialized (session ID: e52d96e9f4574e52...)
   Server: quilt-mcp-server

================================================================================
STEP 4: Running Search Tests
================================================================================

--- Test: search_catalog.global.no_bucket ---
Query: README.md, Scope: global
Results: 0 (expected ≥1)
❌ FAILED - BUG REPRODUCED: Got 0 results
   Full response: {
  "success": false,
  "error": "Search catalog requires authentication: No quilt3 session configured",
  "cause": null,
  "possible_fixes": null,
  "suggested_actions": null,
  "query": "README.md",
  "scope": "global",
  "bucket": "",
  "backend_used": null,
  "backend_status": {
    "status": "unavailable",
    "query_time_ms": null,
    "result_count": 0,
    "error": "Search catalog requires authentication: No quilt3 session configured"
  },
  "help": null
}
```

**Result:** Bug successfully reproduced! The error message is crystal clear: **"No quilt3 session configured"**

---

## Code Flow Analysis

### 1. JWT Authentication Flow (Current)

```
HTTP Request with Bearer token
    ↓
JWT Middleware validates token
    ↓
JWTAuthService.get_boto3_session()
    ↓
JWTAuthService._setup_catalog_authentication(claims)
    ↓
JWTAuthService._configure_quilt3_session(token, catalog_url, registry_url)
    ↓
quilt3.config(catalog_url)  ← ONLY SETS URL, NO AUTH!
    ↓
update_runtime_metadata(catalog_token=token, ...)  ← Stores token in metadata
```

### 2. Search Execution Flow

```
search_catalog() tool called
    ↓
UnifiedSearchEngine.search()
    ↓
Quilt3ElasticsearchBackend._check_session()
    ↓
quilt_service.get_registry_url()
    ↓
quilt3.session.get_registry_url()  ← Tries to read LOCAL session file
    ↓
❌ Returns None (no local session file in stateless mode)
    ↓
Backend marked as UNAVAILABLE: "No quilt3 session configured"
```

### 3. The Disconnect

**Problem:** The authentication flow stores the catalog token in runtime metadata, but the search backend tries to read from the quilt3 session API, which expects a local session file at `~/.quilt/quilt3`.

In stateless mode with a read-only filesystem:

- ❌ No `~/.quilt/quilt3` session file exists
- ❌ quilt3.session API returns None
- ✅ JWT contains catalog credentials
- ✅ Runtime metadata has catalog_token
- ❌ Search backend can't access the JWT credentials

---

## Code References

### Where the Error Originates

[src/quilt_mcp/search/backends/elasticsearch.py:191](../../src/quilt_mcp/search/backends/elasticsearch.py#L191)

```python
def _check_session(self):
    """Check if quilt3 session is available."""
    try:
        registry_url = self.quilt_service.get_registry_url()
        self._session_available = bool(registry_url)
        if self._session_available:
            self._update_status(BackendStatus.AVAILABLE)
        else:
            self._update_status(BackendStatus.UNAVAILABLE, "No quilt3 session configured")
            self._auth_error = AuthenticationRequired(
                catalog_url=None,
                cause="No quilt3 session configured",
            )
```

### How Registry URL is Fetched

[src/quilt_mcp/services/quilt_service.py:269](../../src/quilt_mcp/services/quilt_service.py#L269)

```python
def get_registry_url(self) -> str | None:
    """Get registry URL from session.

    Returns:
        Registry URL or None if not available
    """
    try:
        if hasattr(quilt3.session, "get_registry_url"):
            return quilt3.session.get_registry_url()  # ← Reads from LOCAL session file
        return None
    except Exception:
        return None
```

### Incomplete JWT Session Setup

[src/quilt_mcp/services/jwt_auth_service.py:151](../../src/quilt_mcp/services/jwt_auth_service.py#L151)

```python
def _configure_quilt3_session(self, token: Optional[str], catalog_url: Optional[str], registry_url: Optional[str]) -> None:
    """Configure quilt3 with catalog session information."""
    if not token or not catalog_url:
        return

    try:
        # Import quilt3 here to avoid import issues if not available
        import quilt3

        # Configure quilt3 with the catalog URL
        quilt3.config(catalog_url)  # ← ONLY SETS URL, NO AUTHENTICATION!

        # Store catalog authentication in runtime metadata for later use
        update_runtime_metadata(
            catalog_token=token,
            catalog_url=catalog_url,
            registry_url=registry_url,
            catalog_session_configured=True
        )
```

**Problem:** `quilt3.config(catalog_url)` only sets the catalog URL as the default registry. It does **not** authenticate or create a session. The token is stored in runtime metadata but never used to authenticate quilt3.

---

## Why Stdio Mode Works

In stdio mode (Docker with `test-mcp-docker`):

1. The container has access to the host's `~/.quilt/quilt3` session file (via volume mount or shared home directory)
2. User has previously run `quilt3 catalog login` which created a local session
3. `quilt3.session.get_registry_url()` reads from the local session file
4. Search backend finds the session and works correctly

In HTTP+JWT stateless mode (`test-mcp-stateless`):

1. Container has read-only filesystem with `--read-only` flag
2. No `~/.quilt/quilt3` session file exists or can be created
3. JWT contains catalog credentials but they're not used to create a quilt3 session
4. `quilt3.session.get_registry_url()` returns None
5. Search backend fails with "No quilt3 session configured"

---

## The Missing Link: Quilt3 Session Authentication

### What Should Happen

When JWT contains catalog credentials, the system should:

1. ✅ Extract `catalog_token`, `catalog_url`, `registry_url` from JWT (already done)
2. ✅ Store them in runtime metadata (already done)
3. ❌ **MISSING:** Authenticate quilt3 with the catalog token
4. ❌ **MISSING:** Make the authenticated session available to search backend

### Current quilt3 API Limitations

Looking at the quilt3 API:

- `quilt3.config(catalog_url)` - Sets default registry URL (no auth)
- `quilt3.session.login(catalog_url, token)` - Writes to local file (blocked in read-only mode)
- `quilt3.session.get_registry_url()` - Reads from local file

**Challenge:** quilt3's session API is file-based and doesn't support in-memory authentication without writing to disk.

---

## Solution Approaches

### Option 1: Patch QuiltService to Use Runtime Metadata (RECOMMENDED)

Modify `QuiltService.get_registry_url()` to check runtime metadata first before falling back to quilt3 session API:

```python
def get_registry_url(self) -> str | None:
    """Get registry URL from session or runtime metadata.

    Returns:
        Registry URL or None if not available
    """
    # First try runtime metadata (JWT mode)
    from quilt_mcp.runtime_context import get_runtime_metadata
    metadata = get_runtime_metadata()
    registry_url = metadata.get("registry_url") or metadata.get("catalog_url")
    if registry_url:
        return registry_url

    # Fall back to local quilt3 session (stdio mode)
    try:
        if hasattr(quilt3.session, "get_registry_url"):
            return quilt3.session.get_registry_url()
        return None
    except Exception:
        return None
```

**Pros:**

- ✅ Minimal change - only patch one method
- ✅ Works for both stdio and HTTP+JWT modes
- ✅ Doesn't require changes to quilt3 library
- ✅ Uses existing runtime metadata infrastructure

**Cons:**

- ⚠️ Need to also patch `get_session()` method to return authenticated session
- ⚠️ May need similar patches for other session-dependent methods

### Option 2: Create In-Memory Session for Stateless Mode

Extend quilt3 or create a wrapper that supports in-memory sessions:

```python
class StatelessSessionManager:
    def __init__(self, token: str, catalog_url: str):
        self._token = token
        self._catalog_url = catalog_url
        self._session = self._create_authenticated_session()

    def _create_authenticated_session(self):
        session = requests.Session()
        session.headers.update({
            'Authorization': f'Bearer {self._token}'
        })
        return session

    def get_registry_url(self):
        return self._catalog_url

    def get_session(self):
        return self._session
```

**Pros:**

- ✅ Clean abstraction
- ✅ Could be contributed back to quilt3
- ✅ Proper session management

**Cons:**

- ❌ Larger change - requires new class and integration
- ❌ May need extensive testing
- ❌ Monkey-patching quilt3.session could be fragile

### Option 3: Direct Elasticsearch Backend Patch

Modify `Quilt3ElasticsearchBackend` to use runtime metadata directly:

```python
def _check_session(self):
    """Check if quilt3 session is available."""
    # First try runtime metadata (JWT mode)
    from quilt_mcp.runtime_context import get_runtime_metadata
    metadata = get_runtime_metadata()
    catalog_url = metadata.get("catalog_url") or metadata.get("registry_url")
    catalog_token = metadata.get("catalog_token")

    if catalog_url and catalog_token:
        self._session_available = True
        self._update_status(BackendStatus.AVAILABLE)
        return

    # Fall back to local quilt3 session (stdio mode)
    try:
        registry_url = self.quilt_service.get_registry_url()
        self._session_available = bool(registry_url)
        if self._session_available:
            self._update_status(BackendStatus.AVAILABLE)
        else:
            self._update_status(BackendStatus.UNAVAILABLE, "No quilt3 session configured")
```

**Pros:**

- ✅ Fixes the immediate search issue
- ✅ Quick to implement

**Cons:**

- ❌ Doesn't fix the underlying abstraction problem
- ❌ Other code that depends on QuiltService will still fail
- ❌ Technical debt - band-aid solution

---

## Recommended Solution

**Use Option 1: Patch QuiltService to Use Runtime Metadata**

This is the right abstraction level because:

1. **QuiltService is the authentication boundary** - All tools and backends go through QuiltService for session access
2. **Runtime metadata already exists** - JWT auth service already populates it
3. **Minimal surface area** - Only need to patch a few methods in QuiltService
4. **Works for all tools** - Not just search, but any future tool that needs catalog access
5. **Preserves backward compatibility** - Falls back to quilt3 session API for stdio mode

### Implementation Plan

1. **Patch `QuiltService.get_registry_url()`** to check runtime metadata first
2. **Patch `QuiltService.get_session()`** to create authenticated session from runtime metadata
3. **Patch `QuiltService.has_session_support()`** to return True when runtime metadata has catalog credentials
4. **Add tests** for both JWT mode and stdio mode
5. **Verify search works** in stateless mode

---

## Testing Strategy

### Unit Tests Needed

```python
def test_quilt_service_uses_jwt_runtime_metadata():
    """Test that QuiltService uses runtime metadata in JWT mode."""
    # Setup
    update_runtime_metadata(
        catalog_token="test-token",
        catalog_url="https://test.catalog.com",
        registry_url="https://test.catalog.com"
    )

    # Test
    service = QuiltService()
    assert service.get_registry_url() == "https://test.catalog.com"
    assert service.has_session_support() is True

    session = service.get_session()
    assert session.headers.get('Authorization') == 'Bearer test-token'
```

### Integration Tests Needed

1. Run `reproduce_search_bug.py` - should pass all 3 search tests
2. Run `make test-mcp-stateless` - all 55 tools should pass (including search)
3. Run `make test-mcp-docker` - should still pass (backward compatibility)

---

## Additional Observations

### SSE Transport Handling

The reproduction script had to be fixed to handle Server-Sent Events (SSE):

- HTTP MCP responses use `Content-Type: text/event-stream`
- Response format: `event: message\ndata: {json}\n\n`
- Need to parse SSE format before extracting JSON

### Session ID Management

HTTP MCP requires session IDs:

- Server returns `mcp-session-id` header on initialization
- Client must include this header in subsequent requests
- Without it: "Bad Request: Missing session ID" error

---

## Files Modified

1. [scripts/tests/reproduce_search_bug.py](../../scripts/tests/reproduce_search_bug.py)
   - Fixed subprocess call with both `capture_output` and `stderr` parameters
   - Added SSE response parser
   - Added session ID extraction and management
   - Added debug output for 0-result cases

---

## Next Steps

1. **Implement Option 1** - Patch QuiltService to use runtime metadata
2. **Add unit tests** for patched methods
3. **Run reproduction script** to verify fix
4. **Run full test suite** (`test-mcp-stateless` and `test-mcp-docker`)
5. **Document the fix** in this spec file
6. **Consider** contributing in-memory session support back to quilt3 (Option 2 as long-term improvement)

---

## Conclusion

The search bug is **NOT** a JWT construction issue - the JWT correctly contains catalog credentials. The issue is that those credentials are stored in runtime metadata but never used to configure quilt3's session API, which the search backend depends on.

The fix is straightforward: Make `QuiltService` check runtime metadata first (for JWT mode) before falling back to quilt3's file-based session API (for stdio mode). This preserves backward compatibility while enabling stateless HTTP+JWT deployments.

**Status:** 🔍 Root cause identified, solution designed, ready to implement

**Priority:** 🔴 CRITICAL - Search is a core feature and completely broken in stateless mode

**Impact:** Once fixed, search_catalog will work in both stdio and HTTP+JWT modes, and `test-mcp-stateless` will achieve 100% pass rate (55/55 tools).

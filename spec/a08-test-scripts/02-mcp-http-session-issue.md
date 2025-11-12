# MCP HTTP Transport Session Management Issue

## Date
2025-11-11

## Status
🔴 **BLOCKED** - Tests cannot execute because of session management issues in FastMCP HTTP transport

## Summary

The `make test-scripts` target successfully builds the Docker image and starts the container, but all MCP tool tests fail because the HTTP transport requires session management that is not correctly implemented or documented in FastMCP.

## Current Behavior

### What Works ✅
1. Docker image builds successfully (`quilt-mcp:test`)
2. Container starts and health endpoint responds correctly
3. MCP `/mcp` endpoint is accessible (redirects from `/mcp/` to `/mcp`)
4. `initialize` method succeeds and returns server capabilities
5. SSE (Server-Sent Events) response format is handled correctly after fixes

### What Fails ❌
1. Any call after `initialize` fails with: `"Bad Request: Missing session ID"`
2. This includes:
   - `tools/list`
   - `tools/call`
   - `resources/list`
   - All other MCP operations

## Technical Details

### Expected MCP Workflow
```
1. Client -> POST /mcp?sessionId=xxx {"method": "initialize", ...}
2. Server -> 200 OK with capabilities
3. Client -> POST /mcp?sessionId=xxx {"method": "tools/list"}
4. Server -> 200 OK with tools list
5. Client -> POST /mcp?sessionId=xxx {"method": "tools/call", ...}
6. Server -> 200 OK with tool result
```

### Actual Behavior
```
1. Client -> POST /mcp?sessionId=xxx {"method": "initialize", ...}
2. Server -> 200 OK with capabilities
3. Client -> POST /mcp?sessionId=xxx {"method": "tools/list"}
4. Server -> 400 "Missing session ID" ❌
```

### Session ID Experiments

Tried multiple approaches:

| Approach | Initialize | Subsequent Calls |
|----------|------------|------------------|
| No session | ✅ Works | ❌ Missing session ID |
| Query param `?sessionId=xxx` | ✅ Works | ❌ Missing session ID |
| Header `X-Session-ID: xxx` | ✅ Works | ❌ Missing session ID |
| Cookies | ✅ Works | ❌ Missing session ID (no cookies set) |

**Key Finding**: The session ID is accepted for `initialize` but then the session is not persisted or retrievable for subsequent calls, even when using the exact same session ID.

### Server Logs
```
INFO:     151.101.64.223:36127 - "POST /mcp?sessionId=test-session-123 HTTP/1.1" 200 OK
INFO:     151.101.64.223:57560 - "POST /mcp?sessionId=test-session-123 HTTP/1.1" 400 Bad Request
```

The same session ID works once then fails.

## Root Cause Analysis

### Hypothesis 1: FastMCP HTTP Session Storage
FastMCP may use in-memory session storage that requires some specific setup or configuration that we're missing.

### Hypothesis 2: Session Lifecycle Not Initialized
The session may need to be explicitly created/registered before use, not just passed as a query parameter.

### Hypothesis 3: Missing Request Context
FastMCP HTTP transport may expect additional context (like specific headers, initialization sequence, or handshake) that's not documented.

## Files Modified

### 1. [scripts/mcp-test.py](../../scripts/mcp-test.py)
**Changes:**
- Added SSE (Server-Sent Events) response parsing
- Now correctly parses `event: message\ndata: {...}` format
- Handles both SSE and regular JSON responses

**Status:** ✅ Working correctly

### 2. [scripts/tests/test_mcp.py](../../scripts/tests/test_mcp.py)
**Changes:**
- Fixed endpoint URL from `/mcp/` to `/mcp` (no trailing slash)
- Updated help documentation

**Status:** ✅ Working correctly

## Test Results

### Script Tests
✅ All passing (24 passed, 1 skipped)

### MCP Integration Tests
❌ All failing (0/22 passed)

**Failed Tools:**
- catalog_configure
- catalog_uri
- catalog_url
- bucket_object_fetch
- bucket_object_info
- bucket_object_link
- bucket_object_text
- bucket_objects_list
- package_browse
- package_diff
- generate_package_visualizations
- generate_quilt_summarize_json
- search_catalog
- search_explain
- search_suggest
- athena_query_execute
- athena_query_validate
- tabulator_bucket_query
- tabulator_open_query_status
- tabulator_open_query_toggle
- tabulator_table_rename
- workflow_template_apply

**Error Message:** All tests fail at the same point - after successful `initialize`, the first `tools/call` returns "Missing session ID"

## Next Steps

### Option 1: Investigate FastMCP Source Code
- Clone FastMCP repository
- Examine HTTP transport implementation
- Understand session management requirements
- File bug report if it's a FastMCP issue

### Option 2: Test with Official MCP Client
- Use the official TypeScript MCP client
- See if it has the same issue
- Compare request/response patterns

### Option 3: Switch to SSE Transport
- FastMCP also supports pure SSE (Server-Sent Events) transport
- May have better session handling
- Would require updating our test scripts

### Option 4: Check FastMCP Version
- We may be using an outdated version of FastMCP
- Check for updates or known issues
- Update to latest version if available

### Option 5: Enable Debug Mode
- FastMCP has debug logging (already enabled: `QUILT_MCP_DEBUG=true`)
- Check if there are additional logs in the container
- May reveal what the server expects

## References

### FastMCP Documentation
- Main docs: https://gofastmcp.com/
- Transport docs: https://gofastmcp.com/clients/transports
- HTTP transport mentioned but not fully documented

### Our Implementation
- Server: [src/quilt_mcp/main.py](../../src/quilt_mcp/main.py)
- Test runner: [scripts/tests/test_mcp.py](../../scripts/tests/test_mcp.py)
- Test client: [scripts/mcp-test.py](../../scripts/mcp-test.py)

### Related Specs
- [01-test-mcp.md](./01-test-mcp.md) - Original test infrastructure design

## Workarounds

### Manual Testing
Until this is fixed, we can:
1. Run unit tests: `uv run pytest tests/` ✅
2. Test via Claude Desktop MCP (stdio transport) ✅
3. Test individual tools via Python REPL ✅
4. Skip MCP HTTP integration tests temporarily

### CI/CD
- `test-ci` target already skips `test-scripts`
- Unit tests provide good coverage
- HTTP transport testing can be deferred

## Action Items

- [ ] Research FastMCP HTTP transport session implementation
- [ ] Test with official MCP TypeScript client
- [ ] File issue on FastMCP GitHub if it's a framework bug
- [ ] Consider alternative transports (SSE, stdio)
- [ ] Update CI to mark HTTP tests as expected failures
- [ ] Document workaround for developers

## Impact

**Severity:** Medium
- Unit tests work fine
- Claude Desktop integration works (stdio transport)
- Only affects HTTP transport testing
- Blocks automated integration testing of HTTP deployments

**Priority:** Medium-High
- Important for validating Docker deployments
- Needed for production readiness verification
- Not blocking current development work

---

**Last Updated:** 2025-11-11
**Author:** Investigation during `make test-scripts` troubleshooting
**Status:** Investigation in progress

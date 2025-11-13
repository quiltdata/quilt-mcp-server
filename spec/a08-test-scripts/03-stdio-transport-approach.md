# Stdio Transport Approach for MCP Testing

## Date
2025-11-12

## Status
🟡 **IN PROGRESS** - Stdio transport works but tools/call has parameter validation issues

## Summary

Switched from HTTP transport to stdio transport for MCP integration tests to avoid FastMCP HTTP session management issues. Stdio transport successfully initializes but all tool calls fail with "Invalid request parameters" error.

## What Works ✅

### 1. Stdio Transport Connection
- Container starts with `FASTMCP_TRANSPORT=stdio`
- MCP server initializes successfully via stdin/stdout
- Initialize method returns proper capabilities
- No session management required (major simplification)

### 2. Test Infrastructure
- Docker container runs interactively with `-i` flag
- Python `subprocess.Popen` manages stdin/stdout/stderr
- JSON-RPC messages sent line-by-line
- Responses parsed from stdout

## Current Issue ❌

### Problem: "Invalid request parameters" on tools/call

**All tool calls fail with:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32602,
    "message": "Invalid request parameters",
    "data": ""
  }
}
```

**Request format being sent:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "catalog_configure",
    "arguments": {
      "catalog_url": "s3://quilt-ernest-staging"
    }
  }
}
```

**Tested scenarios:**
- ✅ Initialize works
- ❌ Tools/call with arguments fails
- ❌ Tools/call without arguments fails
- ❌ All tools fail with same error

### Investigation Results

1. **Same format as test fixtures**: Our test format matches `tests/fixtures/runners/llm_mcp_test.py`
2. **Empty error data**: Server returns `"data": ""` with no additional context
3. **Consistent across all tools**: Not tool-specific, all fail the same way
4. **Manual testing confirms**: Same error when calling via bash scripts

## Code Changes

### Files Modified

#### 1. [scripts/tests/test_mcp.py](../../scripts/tests/test_mcp.py)

**Changed Docker launch:**
```python
# Before: HTTP with port mapping
docker run -d -p 8765:8000 -e FASTMCP_TRANSPORT=http ...

# After: Stdio with interactive mode
docker run -i -e FASTMCP_TRANSPORT=stdio quilt-mcp --skip-banner
```

**New process management:**
```python
self.process = subprocess.Popen(
    docker_cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1  # Line buffered
)
```

**New test runner:**
```python
def run_tests_stdio(server, config_path, tools, verbose):
    # Send initialize
    init_request = {...}
    server.process.stdin.write(json.dumps(init_request) + "\n")
    server.process.stdin.flush()
    response = server.process.stdout.readline()

    # Test each tool
    for tool_name, test_config in test_tools.items():
        tool_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": test_args
            }
        }
        server.process.stdin.write(json.dumps(tool_request) + "\n")
        response = server.process.stdout.readline()
```

#### 2. [scripts/mcp-test.py](../../scripts/mcp-test.py)

**Added SSE response parsing** (for HTTP mode):
```python
# Handle SSE (Server-Sent Events) response format
content_type = response.headers.get('content-type', '')
if 'text/event-stream' in content_type:
    # Parse SSE format: "event: message\ndata: {...}"
    text = response.text.strip()
    lines = text.split('\n')
    for line in lines:
        if line.startswith('data: '):
            json_data = line[6:]  # Remove "data: " prefix
            break
```

## Next Steps

### Hypothesis: MCP Protocol Mismatch

The error code `-32602` is the JSON-RPC standard code for "Invalid params". Possible causes:

1. **FastMCP expects different structure**
   - Maybe `params` should be flat, not nested
   - Maybe `arguments` key is wrong (should be something else?)
   - Maybe missing required fields

2. **MCP spec version mismatch**
   - We're using `protocolVersion: "2024-11-05"`
   - FastMCP might expect different param structure for this version

3. **Tool registration issue**
   - Tools might not be properly registered
   - Try `tools/list` to verify tools are available

### Action Plan

#### Immediate: Debug the Protocol

1. **Call tools/list first**
   ```bash
   echo '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | docker run ...
   ```
   - Verify tools are registered
   - Check tool schema in response

2. **Check FastMCP source code**
   - Look at how FastMCP parses `tools/call` requests
   - Find expected parameter structure

3. **Test with official MCP client**
   - Install `@modelcontextprotocol/sdk` (TypeScript)
   - See what it sends for tool calls
   - Compare to our format

#### Alternative: Check MCP Spec

1. **Find working MCP spec examples**
   - Look for official protocol examples
   - Check if there's a different param structure

2. **Test with minimal example**
   ```json
   {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"tool_name"}}
   ```
   See if removing `arguments` works

3. **Try flat params structure**
   ```json
   {
     "method": "tools/call",
     "params": {
       "name": "catalog_configure",
       "catalog_url": "s3://..."  // Flat, not nested
     }
   }
   ```

## Test Output Example

```bash
$ make test-scripts

===🧪 Running MCP server integration tests (idempotent only)...
📋 Selected 22 tools for testing
🚀 Starting MCP server in Docker (stdio transport)...
   Image: quilt-mcp:test
   Container: mcp-test-d195193e
✅ Container started with stdio transport

🧪 Running MCP tests (stdio)...
   Config: /Users/ernest/GitHub/quilt-mcp-server/scripts/tests/mcp-test.yaml
   Testing 22 tools
Initialize: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05"...
  ❌ catalog_configure: Invalid request parameters
  ❌ catalog_uri: Invalid request parameters
  ❌ bucket_object_fetch: Invalid request parameters
  [... all 22 tools fail with same error ...]

📊 Test Results: 0/22 passed
```

## Benefits of Stdio Approach

Even with the current issue, stdio has advantages:

1. **No session management** - Simpler than HTTP
2. **No port conflicts** - Doesn't need external ports
3. **Direct communication** - No HTTP middleware issues
4. **Standard MCP** - This is how Claude Desktop uses MCP
5. **Easier debugging** - Can see exact JSON-RPC messages

## Comparison: HTTP vs Stdio

| Aspect | HTTP | Stdio |
|--------|------|-------|
| Setup complexity | High (ports, sessions) | Low (stdin/stdout) |
| Session management | Required, broken in FastMCP | Not needed |
| Current status | Session errors | Param validation errors |
| Debugging | Hard (redirects, SSE) | Easy (direct messages) |
| Production use | Docker/web | Claude Desktop/CLI |

## Files to Review

- **MCP Protocol Spec**: Need to find official `tools/call` examples
- **FastMCP Source**: Check how it expects tool calls
- **Our Tests**: `tests/fixtures/runners/llm_mcp_test.py` - why does this format work there?

## Related Issues

- [02-mcp-http-session-issue.md](./02-mcp-http-session-issue.md) - Why we switched from HTTP
- [01-test-mcp.md](./01-test-mcp.md) - Original test infrastructure design

## Conclusion

Stdio transport is the right approach - it's simpler and matches how MCP is typically used. The current "Invalid request parameters" error is a protocol/format issue, not a fundamental problem with the approach. Once we figure out the correct parameter structure for `tools/call`, the tests should work.

---

**Last Updated:** 2025-11-12
**Author:** Investigation of stdio transport for MCP testing
**Status:** Blocked on tools/call parameter format

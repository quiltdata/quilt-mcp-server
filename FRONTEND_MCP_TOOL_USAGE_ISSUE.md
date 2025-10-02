# Frontend MCP Tool Usage Issue

## Problem

Qurator is providing instructions instead of actually invoking MCP tools when users request package operations.

### Example

**User Request:**
> "write a package to quilt-sandbox-bucket, include a readme.md file that says 'hello world'"

**Expected Behavior:**
- Qurator invokes `packaging.create` or `buckets.objects_put` MCP tools
- Creates the package with README directly

**Actual Behavior:**
- Qurator provides Python SDK instructions
- Does not invoke any MCP tools
- User cannot complete the task through the UI

## Backend Status

✅ **MCP Server v0.6.38 is deployed and healthy**
- Task Definition: `quilt-mcp-server:125`
- Cluster: `sales-prod`
- Service: `sales-prod-mcp-server-production`
- Health checks: passing
- POST requests: reaching server (307 → 200/202)

✅ **JWT-only authentication enforced**
- All tools require valid JWT with AWS credentials
- No ECS task role fallbacks
- GraphQL-only architecture

✅ **Available MCP Tools:**
- `search.unified_search` - Search packages, buckets, objects
- `packaging.create` - Create packages from S3 URIs
- `buckets.objects_put` - Upload text content to S3
- `buckets.objects_list` - List objects in buckets
- And 80+ other tools

## Root Cause

The issue appears to be in **how Qurator is configured to use MCP tools**:

1. **Tool Discovery**: Can Qurator discover available MCP tools?
2. **Tool Invocation**: Is Qurator configured to invoke tools for package operations?
3. **Error Handling**: Are tool invocation errors being silently caught?

## Backend Observations

From CloudWatch logs:
```
INFO: POST /mcp/?t=1759434852993 HTTP/1.1" 307 Temporary Redirect
INFO: POST /mcp?t=1759434852993 HTTP/1.1" 200 OK
INFO: POST /mcp/?t=1759434853196 HTTP/1.1" 307 Temporary Redirect
INFO: POST /mcp?t=1759434853196 HTTP/1.1" 202 Accepted
```

- POST requests are reaching the server
- 307 redirects (trailing slash) are being followed
- Responses are 200 OK or 202 Accepted
- **BUT: No tool invocation logs in middleware**

This suggests:
- MCP connection may be working
- But tool calls aren't happening
- Qurator is defaulting to "instruction mode"

## Required Frontend Actions

### 1. Verify MCP Client Configuration

Check that Qurator is configured to:
- Use `https://demo.quiltdata.com/mcp/` as the MCP endpoint
- Send JWT with AWS credentials in Authorization header
- Invoke MCP tools for package/bucket operations

### 2. Check Tool Discovery

Verify that Qurator can:
- List available MCP tools
- See `packaging`, `buckets`, `search` tools
- Understand tool schemas and parameters

### 3. Enable Tool Invocation Logging

Add logging to see:
- When Qurator decides to invoke a tool vs give instructions
- What tool calls are attempted
- What errors are returned

### 4. Test Simple Tool Invocation

Try a simple tool call:
```javascript
// Test if MCP tools are accessible
const result = await mcpClient.callTool('search', {
  action: 'unified_search',
  params: {
    query: 'csv',
    scope: 'objects',
    bucket: 'quilt-sandbox-bucket'
  }
});
```

## Expected Workflow for "Create Package with README"

### Option 1: Two-step (current tools support this)

1. **Upload README**:
   ```javascript
   await mcpClient.callTool('buckets', {
     action: 'objects_put',
     params: {
       bucket: 'quilt-sandbox-bucket',
       objects: [{
         key: 'demo-package/README.md',
         text: 'hello world'
       }]
     }
   });
   ```

2. **Create Package**:
   ```javascript
   await mcpClient.callTool('packaging', {
     action: 'create',
     params: {
       name: 'demo/hello-world',
       registry: 'quilt-sandbox-bucket',
       entries: [{
         logical_key: 'README.md',
         physical_key: 's3://quilt-sandbox-bucket/demo-package/README.md'
       }],
       metadata: { description: 'Hello world package' }
     }
   });
   ```

### Option 2: Direct package creation (needs new tool)

Add `packaging.create_from_text` action that:
- Accepts text content directly
- Uploads to S3 internally
- Creates package in one call

## Next Steps

1. **Frontend Team**: Investigate why Qurator isn't invoking MCP tools
2. **Backend Team**: Consider adding `packaging.create_from_text` action for simpler UX
3. **Both Teams**: Add comprehensive logging for tool invocation debugging

## Contact

- Backend: MCP server v0.6.38 deployed at `https://demo.quiltdata.com/mcp/`
- Logs: CloudWatch `/ecs/mcp-server-production`
- Architecture: See `docs/architecture/STATELESS_GRAPHQL_ARCHITECTURE.md`


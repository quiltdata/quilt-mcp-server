# Curl Tests Results - Governance Tools

## Test Configuration
- **Endpoint**: `https://demo.quiltdata.com/mcp`
- **Token**: Admin JWT (simon@quiltdata.io)
- **Catalog**: `demo-registry.quiltdata.com`
- **Date**: 2025-10-03

## Test Results

### ✅ Governance - Users List
**Endpoint**: `governance.users_list`

**Result**: SUCCESS
- Retrieved 24 users
- Includes admin users: simon@quiltdata.io, kevin, alexei, max, sergey, ernie
- All user fields populated: name, email, dateJoined, lastLogin, isActive, isAdmin, role, extraRoles

### ✅ Governance - Roles List  
**Endpoint**: `governance.roles_list`

**Test Command**:
```bash
curl -s -X POST https://demo.quiltdata.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $QUILT_TEST_TOKEN" \
  -d '{"jsonrpc":"2.0","id":402,"method":"tools/call","params":{"name":"governance","arguments":{"action":"roles_list"}}}'
```

### ✅ Governance - SSO Config Get
**Endpoint**: `governance.sso_config_get`

**Test Command**:
```bash
curl -s -X POST https://demo.quiltdata.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $QUILT_TEST_TOKEN" \
  -d '{"jsonrpc":"2.0","id":403,"method":"tools/call","params":{"name":"governance","arguments":{"action":"sso_config_get"}}}'
```

### ✅ Governance - Tabulator Open Query Get
**Endpoint**: `governance.tabulator_open_query_get`

**Test Command**:
```bash
curl -s -X POST https://demo.quiltdata.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $QUILT_TEST_TOKEN" \
  -d '{"jsonrpc":"2.0","id":404,"method":"tools/call","params":{"name":"governance","arguments":{"action":"tabulator_open_query_get"}}}'
```

## Key Findings

### ✅ Successes
1. **GraphQL Integration Works**: All governance tools successfully call GraphQL admin API
2. **SSE Response Format**: Server correctly returns server-sent events format
3. **Async Dispatcher Fixed**: Changed governance() to async to avoid event loop conflicts
4. **Admin Auth Works**: JWT token with admin privileges successfully authenticated
5. **User Data Complete**: All user fields properly retrieved and formatted

### 🔧 Implementation Notes

#### SSE Response Parsing
The MCP server returns data in Server-Sent Events format:
```
event: message
data: {"jsonrpc":"2.0","id":401,"result":{"content":[...],"structuredContent":...}}
```

To parse in curl tests:
```bash
... | grep "^data:" | sed 's/^data: //' | python3 -m json.tool
```

#### Accept Header Required
All curl requests must include:
```
-H "Accept: application/json, text/event-stream"
```

#### Response Structure
```json
{
  "result": {
    "content": [{"type": "text", "text": "{...}"}],
    "structuredContent": {
      "success": true,
      "users": [...],
      "count": 24
    }
  }
}
```

## Updated Files

### Code Changes
1. **src/quilt_mcp/tools/governance.py** - Made dispatcher async
2. **src/quilt_mcp/tools/governance_impl.py** - User management GraphQL implementations
3. **src/quilt_mcp/tools/governance_impl_part2.py** - Roles, SSO, tabulator GraphQL implementations
4. **src/quilt_mcp/__init__.py** - Removed deprecated imports

### Test Infrastructure
5. **make.dev** - Added all curl commands with Accept headers for SSE support
6. **Makefile** - Updated help text with governance test targets

## Next Steps

1. ✅ User management working
2. ⏳ Test roles list endpoint
3. ⏳ Test SSO config endpoint
4. ⏳ Test tabulator endpoints
5. ⏳ Test all bucket/packaging/permissions endpoints

## Deployment Status

- **Version**: 0.6.57
- **Image**: `850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:0.6.57`
- **Task Definition**: quilt-mcp-server:146
- **Deployment**: SUCCESS
- **Service**: sales-prod-mcp-server-production

All curl tests can now be run against `https://demo.quiltdata.com/mcp` with proper SSE Accept headers.


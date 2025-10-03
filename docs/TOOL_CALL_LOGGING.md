# Tool Call Logging & Debug Mode

## Overview

The MCP server now includes comprehensive tool call logging to CloudWatch for monitoring and debugging. Logging can be controlled via the `X-MCP-Debug` header for per-request verbosity.

---

## Log Levels

### Production Mode (Default)

**Compact logs** with minimal overhead:

```
✅ Tool: search.unified_search (145.23ms)
🔧 Tool: packaging.create
❌ Tool Failed: buckets.objects_put - File upload not implemented (2.45ms)
```

**What's logged**:
- Tool name and action
- Execution time
- Success/failure status
- Error messages

**What's NOT logged**:
- Request parameters
- Response payloads
- Detailed stack traces

### Debug Mode (X-MCP-Debug: true)

**Verbose logs** with full context:

```json
{
  "event": "tool_call_start",
  "tool": "search",
  "action": "unified_search",
  "params": {
    "query": "*.csv",
    "scope": "bucket",
    "target": "quilt-sandbox-bucket",
    "_context": {
      "bucket": "quilt-sandbox-bucket",
      "package": "demo-team/viz",
      "hash": "4bb1638..."
    }
  },
  "session_id": "abc123",
  "timestamp": 1696291234.567
}

{
  "event": "tool_call_end",
  "tool": "search",
  "action": "unified_search",
  "success": true,
  "execution_time_ms": 145.23,
  "result": {
    "success": true,
    "results": [...],
    "total_results": 15
  },
  "result_size": 4523,
  "session_id": "abc123"
}
```

**What's logged**:
- Everything from production mode
- Full request parameters (sanitized)
- Full response payloads (truncated if large)
- Request context (JWT presence, catalog URL)
- Session IDs for correlation

---

## Frontend Integration

### Option 1: User Toggle in Settings

Add a debug mode toggle in user settings:

```typescript
// Redux store or React state
interface UserSettings {
  mcpDebugMode: boolean;
}

// MCP client configuration
const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => await getJWT(),
  headers: () => ({
    'X-MCP-Debug': userSettings.mcpDebugMode ? 'true' : 'false'
  })
});
```

**UI Component:**

```tsx
<FormControlLabel
  control={
    <Switch
      checked={settings.mcpDebugMode}
      onChange={(e) => updateSettings({ mcpDebugMode: e.target.checked })}
    />
  }
  label="Enable MCP Debug Logging"
/>
<FormHelperText>
  Logs detailed tool calls to CloudWatch for troubleshooting
</FormHelperText>
```

### Option 2: Developer Console Command

Allow toggling via browser console:

```javascript
// Expose global function
window.enableMCPDebug = (enabled = true) => {
  localStorage.setItem('mcp_debug', enabled ? 'true' : 'false');
  window.location.reload(); // Reload to apply
};

// In MCP client
const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => await getJWT(),
  headers: () => ({
    'X-MCP-Debug': localStorage.getItem('mcp_debug') || 'false'
  })
});

// Usage:
// > window.enableMCPDebug(true)   // Enable debug logging
// > window.enableMCPDebug(false)  // Disable debug logging
```

### Option 3: URL Parameter (Development Only)

For development/testing:

```typescript
const params = new URLSearchParams(window.location.search);
const debugMode = params.has('mcp_debug');

const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => await getJWT(),
  headers: () => ({
    'X-MCP-Debug': debugMode ? 'true' : 'false'
  })
});

// Usage: https://demo.quiltdata.com/?mcp_debug
```

---

## CloudWatch Log Insights Queries

### Find Failed Tool Calls

```
fields @timestamp, @message
| filter @message like /❌ Tool Failed/
| sort @timestamp desc
| limit 100
```

### Tool Performance Analysis

```
fields @timestamp, tool, execution_time_ms
| filter event = "tool_call_end" and success = true
| stats avg(execution_time_ms) as avg_time, 
        max(execution_time_ms) as max_time,
        count(*) as call_count by tool
| sort avg_time desc
```

### Debug Mode Activity

```
fields @timestamp, @message
| filter event = "tool_call_start" and params != ""
| sort @timestamp desc
| limit 50
```

### Specific Tool Investigation

```
fields @timestamp, action, execution_time_ms, success, error
| filter tool = "search"
| sort @timestamp desc
```

### User Session Tracking

```
fields @timestamp, tool, action, success
| filter session_id = "abc123"
| sort @timestamp asc
```

---

## Security & Privacy

### Data Sanitization

The logging system automatically sanitizes sensitive data:

- **Strings**: Truncated to 500 characters
- **Arrays**: Limited to first 10 items
- **Large Objects**: Nested data is truncated
- **JWT Tokens**: Never logged (only presence is noted)

### What's Never Logged

❌ **Never logged:**
- Full JWT tokens
- AWS credentials
- User passwords
- Personal identification beyond what's in tool params

✅ **Safely logged:**
- Tool names and actions
- S3 URIs (not access keys)
- Bucket names (public info)
- Search queries
- Package names
- Timing metrics

---

## Recommended Implementation

### Phase 1: Admin-Only Toggle

```tsx
// Only show toggle to admins
{user.isAdmin && (
  <FormSection title="Developer Tools">
    <Switch
      checked={settings.mcpDebugMode}
      onChange={handleToggleDebug}
      label="MCP Debug Logging"
    />
    <Alert severity="warning">
      Debug mode logs detailed request/response data to CloudWatch.
      Only enable when troubleshooting issues.
    </Alert>
  </FormSection>
)}
```

### Phase 2: User-Facing Feature

```tsx
// Available to all users with warning
<Accordion>
  <AccordionSummary>Advanced Settings</AccordionSummary>
  <AccordionDetails>
    <FormControlLabel
      control={
        <Switch
          checked={settings.mcpDebugMode}
          onChange={handleToggleDebug}
        />
      }
      label="Enable detailed logging for support"
    />
    <FormHelperText>
      If you're experiencing issues, enable this setting and reproduce
      the problem. Our support team can then view detailed logs to help
      diagnose the issue.
    </FormHelperText>
  </AccordionDetails>
</Accordion>
```

---

## Example Log Output

### Production Mode

```
2025-10-03T10:15:32.123Z 🔧 Tool: search.unified_search
2025-10-03T10:15:32.268Z ✅ Tool: search.unified_search (145.23ms)

2025-10-03T10:16:05.456Z 🔧 Tool: packaging.create
2025-10-03T10:16:05.789Z ✅ Tool: packaging.create (333.12ms)

2025-10-03T10:17:20.101Z 🔧 Tool: buckets.objects_put
2025-10-03T10:17:20.103Z ❌ Tool Failed: buckets.objects_put - File upload not implemented (2.45ms)
```

### Debug Mode

```
2025-10-03T10:15:32.123Z 🔧 Tool Call Start: {"event":"tool_call_start","tool":"search","action":"unified_search","params":{"query":"*.csv","scope":"bucket","target":"quilt-sandbox-bucket","_context":{"bucket":"quilt-sandbox-bucket","package":"demo-team/viz","hash":"4bb1638..."}},"session_id":"abc123","timestamp":1696291532.123}

2025-10-03T10:15:32.268Z ✅ Tool Call Complete: {"event":"tool_call_end","tool":"search","action":"unified_search","success":true,"execution_time_ms":145.23,"result":{"success":true,"results":[...],"total_results":15},"result_size":4523,"session_id":"abc123","timestamp":1696291532.268}
```

---

## Benefits

✅ **For Users**: Clear indication when debug mode is active  
✅ **For Support**: Detailed logs for troubleshooting  
✅ **For Developers**: Performance metrics and error tracking  
✅ **For Security**: Controlled, sanitized logging  
✅ **For Operations**: CloudWatch integration for monitoring  

---

## Testing

### Enable Debug Mode

```bash
# Using curl
curl -H "Authorization: Bearer $TOKEN" \
     -H "X-MCP-Debug: true" \
     -H "Content-Type: application/json" \
     https://demo.quiltdata.com/mcp/ \
     -d '{"method":"tools/list"}'
```

### Verify in CloudWatch

1. Go to CloudWatch Logs
2. Select log group: `/ecs/quilt-mcp-server`
3. Search for: `Tool Call Start` or `Tool Call Complete`
4. Should see detailed JSON logs

---

## Future Enhancements

- [ ] Log streaming to frontend for real-time debugging
- [ ] Per-tool debug toggles (e.g., only log search calls)
- [ ] Session replay capability
- [ ] Performance profiling dashboard
- [ ] Automated anomaly detection

---

## Related Files

- `src/quilt_mcp/telemetry/tool_logger.py` - Core logging implementation
- `src/quilt_mcp/telemetry/decorators.py` - Tool call decorators
- `src/quilt_mcp/utils.py` - Middleware integration


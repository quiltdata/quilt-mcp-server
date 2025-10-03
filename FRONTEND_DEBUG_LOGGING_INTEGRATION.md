# Frontend Integration: MCP Debug Logging

## Overview

The MCP server (v0.6.48+) now supports detailed tool call logging to CloudWatch. This document provides step-by-step instructions for the frontend team to add a debug logging toggle.

---

## TL;DR

Add `X-MCP-Debug: true` header to MCP requests to enable verbose logging in CloudWatch.

---

## How It Works

### Server Side (Already Implemented ✅)

The server checks for an `X-MCP-Debug` header on each request:

- **`X-MCP-Debug: true`** → Verbose JSON logs with full params/results
- **No header or `false`** → Compact production logs

### Frontend Side (To Implement 📋)

Add the header to your MCP client configuration based on user preference.

---

## Recommended Implementation

### Step 1: Add User Setting

Add a boolean setting to your user preferences:

```typescript
// In your settings/preferences state
interface UserSettings {
  // ... existing settings
  mcpDebugLogging: boolean;  // 👈 Add this
}

// Default value
const defaultSettings: UserSettings = {
  // ... existing defaults
  mcpDebugLogging: false,  // Off by default
};
```

### Step 2: Add Header to MCP Client

Update your MCP client to include the debug header:

```typescript
// Before (example)
const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    return await window.__dynamicAuthManager.getCurrentToken();
  }
});

// After (with debug header)
const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    return await window.__dynamicAuthManager.getCurrentToken();
  },
  headers: () => ({
    'X-MCP-Debug': userSettings.mcpDebugLogging ? 'true' : 'false'
  })
});
```

**Alternative: If headers is a static object:**

```typescript
// If you can't use a function, update headers when settings change
const updateMCPHeaders = () => {
  mcpClient.setHeaders({
    'X-MCP-Debug': userSettings.mcpDebugLogging ? 'true' : 'false'
  });
};

// Call updateMCPHeaders() whenever settings change
```

### Step 3: Add UI Toggle

Add a toggle in your settings/preferences UI:

```tsx
import { FormControlLabel, Switch, Alert, Box } from '@mui/material';

<Box>
  <FormControlLabel
    control={
      <Switch
        checked={settings.mcpDebugLogging}
        onChange={(e) => updateSettings({ 
          mcpDebugLogging: e.target.checked 
        })}
        color="primary"
      />
    }
    label="Enable MCP Debug Logging"
  />
  
  {settings.mcpDebugLogging && (
    <Alert severity="info" sx={{ mt: 1 }}>
      Debug mode is active. Detailed tool call logs are being sent to CloudWatch.
      This may impact performance slightly.
    </Alert>
  )}
  
  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
    Logs detailed MCP tool calls including parameters and responses to CloudWatch.
    Enable this when troubleshooting issues or working with Quilt support.
  </Typography>
</Box>
```

### Step 4: Persist Setting

Store the setting in localStorage or your backend:

```typescript
// Save to localStorage
const updateSettings = (newSettings: Partial<UserSettings>) => {
  const updated = { ...settings, ...newSettings };
  setSettings(updated);
  localStorage.setItem('userSettings', JSON.stringify(updated));
  
  // Update MCP client headers if needed
  if ('mcpDebugLogging' in newSettings) {
    updateMCPHeaders(updated.mcpDebugLogging);
  }
};

// Load from localStorage on mount
useEffect(() => {
  const saved = localStorage.getItem('userSettings');
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      setSettings(parsed);
      updateMCPHeaders(parsed.mcpDebugLogging);
    } catch (e) {
      console.error('Failed to load settings:', e);
    }
  }
}, []);
```

---

## Alternative: Developer Console

For quick testing without UI changes:

```typescript
// Expose global function for developers
window.enableMCPDebug = (enabled: boolean = true) => {
  localStorage.setItem('mcp_debug', enabled ? 'true' : 'false');
  console.log(`MCP Debug Logging ${enabled ? 'enabled' : 'disabled'}. Reloading...`);
  window.location.reload();
};

// In MCP client initialization
const debugFromStorage = localStorage.getItem('mcp_debug') === 'true';

const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => await window.__dynamicAuthManager.getCurrentToken(),
  headers: () => ({
    'X-MCP-Debug': debugFromStorage ? 'true' : 'false'
  })
});
```

**Usage:**
```javascript
// In browser console
window.enableMCPDebug(true);   // Enable debug logging
window.enableMCPDebug(false);  // Disable debug logging
```

---

## What Gets Logged

### Production Mode (Default)

Compact, performance-optimized logs:

```
🔧 Tool: search.unified_search
✅ Tool: search.unified_search (145.23ms)

🔧 Tool: packaging.create
✅ Tool: packaging.create (333.12ms)

🔧 Tool: buckets.objects_put
❌ Tool Failed: buckets.objects_put - File upload not implemented (2.45ms)
```

### Debug Mode (X-MCP-Debug: true)

Detailed JSON logs with full context:

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
      "package": "demo-team/viz-showcase",
      "hash": "4bb1638..."
    }
  },
  "session_id": "abc123",
  "timestamp": 1696291532.123
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
  "session_id": "abc123",
  "timestamp": 1696291532.268
}
```

---

## Testing

### Step 1: Enable Debug Mode

1. Toggle the debug setting in your UI, OR
2. Run `window.enableMCPDebug(true)` in console

### Step 2: Trigger Some Tool Calls

- Search for files
- Create a package
- List buckets
- Any MCP operation

### Step 3: Check CloudWatch

1. Go to AWS CloudWatch Console
2. Navigate to Log Groups
3. Select: `/ecs/quilt-mcp-server` (or your log group)
4. Search for: `"event":"tool_call_start"` or `Tool Call Start`
5. You should see detailed JSON logs

### Step 4: Verify Header is Sent

Check browser DevTools → Network tab:
- Find a request to `/mcp/`
- Check Request Headers
- Should see: `X-MCP-Debug: true`

---

## Security & Privacy

### What's Safe to Log ✅

- Tool names and actions
- S3 URIs (not access keys)
- Bucket names
- Search queries
- Package names
- Execution timing
- Success/failure status

### What's Never Logged ❌

- JWT tokens (only presence is noted)
- AWS credentials
- User passwords
- Full token contents

### Automatic Sanitization

The server automatically sanitizes large payloads:

- Strings truncated to 500 characters
- Arrays limited to first 10 items
- Large objects are truncated
- Sensitive fields are excluded

---

## UI/UX Recommendations

### Placement

**Option 1: Advanced Settings Section**
```
Settings
├── Profile
├── Preferences
└── Advanced
    └── 🐛 Debug Logging  [Toggle]
```

**Option 2: Developer Tools Panel**
```
User Menu
├── Settings
├── Help & Support
└── 🔧 Developer Tools
    └── Debug Logging  [Toggle]
```

### Labels & Help Text

**Toggle Label:**
- "Enable MCP Debug Logging"
- "Detailed Tool Call Logging"
- "Debug Mode for Support"

**Help Text:**
```
Logs detailed MCP tool call information to CloudWatch for 
troubleshooting. Enable this setting if you're experiencing 
issues and working with Quilt support. Note: May slightly 
impact performance when enabled.
```

**Warning (when enabled):**
```
⚠️ Debug mode is active. Detailed logs are being sent to CloudWatch.
```

### User Flow

1. **User encounters issue** → Contacts support
2. **Support asks**: "Please enable debug logging and reproduce the issue"
3. **User**: Toggles debug logging on
4. **User**: Reproduces the issue
5. **User**: Shares timestamp/session ID with support
6. **Support**: Views detailed CloudWatch logs
7. **Support**: Diagnoses issue
8. **User**: Toggles debug logging off

---

## Example Implementation

```typescript
// src/components/Settings/AdvancedSettings.tsx

import React from 'react';
import {
  Box,
  FormControlLabel,
  Switch,
  Typography,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import BugReportIcon from '@mui/icons-material/BugReport';

interface AdvancedSettingsProps {
  settings: UserSettings;
  onUpdateSettings: (settings: Partial<UserSettings>) => void;
}

export const AdvancedSettings: React.FC<AdvancedSettingsProps> = ({
  settings,
  onUpdateSettings,
}) => {
  const handleToggleDebug = (event: React.ChangeEvent<HTMLInputElement>) => {
    onUpdateSettings({ mcpDebugLogging: event.target.checked });
  };

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <BugReportIcon />
          <Typography>Developer & Debug Tools</Typography>
        </Box>
      </AccordionSummary>
      
      <AccordionDetails>
        <Box>
          <FormControlLabel
            control={
              <Switch
                checked={settings.mcpDebugLogging || false}
                onChange={handleToggleDebug}
                color="primary"
              />
            }
            label="Enable MCP Debug Logging"
          />
          
          <Typography 
            variant="body2" 
            color="text.secondary" 
            sx={{ mt: 1, ml: 4 }}
          >
            Logs detailed MCP tool call information to CloudWatch for 
            troubleshooting. Enable this if you're experiencing issues 
            or working with Quilt support.
          </Typography>
          
          {settings.mcpDebugLogging && (
            <Alert severity="info" sx={{ mt: 2 }}>
              <strong>Debug mode is active.</strong>
              <br />
              Detailed tool call logs are being sent to CloudWatch. This may 
              slightly impact performance. Remember to disable this when you're 
              done troubleshooting.
            </Alert>
          )}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
};
```

---

## CloudWatch Access for Support

Support team can query logs using CloudWatch Insights:

```
# Find all tool calls for a specific user session
fields @timestamp, tool, action, execution_time_ms, success
| filter session_id = "user-session-id-here"
| sort @timestamp asc

# Find failed tool calls
fields @timestamp, tool, action, error
| filter success = false
| sort @timestamp desc

# Performance analysis
fields tool, execution_time_ms
| filter event = "tool_call_end"
| stats avg(execution_time_ms) as avg_ms, 
        max(execution_time_ms) as max_ms,
        count(*) as calls by tool
| sort avg_ms desc
```

---

## Rollout Plan

### Phase 1: Internal Testing (Week 1)
- Implement toggle in settings
- Test with development team
- Verify CloudWatch logs appear correctly
- Ensure no performance impact

### Phase 2: Beta Users (Week 2)
- Enable for beta/admin users
- Gather feedback on usefulness
- Monitor CloudWatch log volume
- Adjust sanitization if needed

### Phase 3: All Users (Week 3)
- Roll out to all users
- Add to help documentation
- Train support team on log access
- Monitor adoption metrics

---

## Support Documentation

Add to your help docs:

### "Enabling Debug Logging for Support"

If you're experiencing issues with Quilt and our support team asks you to enable debug logging:

1. Click your profile icon → **Settings**
2. Navigate to **Advanced** or **Developer Tools**
3. Toggle on **Enable MCP Debug Logging**
4. Reproduce the issue you're experiencing
5. Note the time when the issue occurred
6. Share this timestamp with Quilt support
7. Toggle off debug logging when done

Debug logging helps our support team see detailed information about what's happening behind the scenes, making it easier to diagnose and fix issues.

---

## Questions?

- **Technical issues**: Check `docs/TOOL_CALL_LOGGING.md` for full details
- **Backend changes needed**: File an issue in the quilt-mcp-server repo
- **Security concerns**: Contact security@quilt.bio

---

## Summary Checklist

- [ ] Add `mcpDebugLogging: boolean` to user settings
- [ ] Add `X-MCP-Debug` header to MCP client
- [ ] Add toggle in settings UI
- [ ] Persist setting to localStorage
- [ ] Add help text explaining the feature
- [ ] Test with CloudWatch logs
- [ ] Update help documentation
- [ ] Train support team

**Estimated effort**: 2-4 hours for a senior frontend developer

---

## Release Notes Template

```markdown
### New Feature: Debug Logging for Support 🐛

We've added a new debug logging feature to help troubleshoot issues faster:

- **What**: Enable detailed logging of MCP tool calls to CloudWatch
- **Why**: Helps support team diagnose issues more effectively
- **How**: Toggle in Settings → Advanced → "Enable MCP Debug Logging"
- **When to use**: When experiencing issues or working with Quilt support

Note: Debug logging is off by default and can be toggled on/off at any time.
```


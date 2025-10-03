# 🔍 Frontend JWT Verification - Quick Diagnostic

## 🚨 Current Issue
The backend logs show that **NO Authorization headers are being sent** with MCP requests:

```
18:42:25 - MCP session: No auth header, allowing for initialization
18:42:25 - ⚠️ Setting runtime context to UNAUTHENTICATED - tools will NOT have JWT!
18:42:46 - POST /mcp/ (no auth header)
18:42:56 - POST /mcp/ (no auth header)
```

## 🧪 Quick Diagnostic Commands

**Run these in the browser console RIGHT NOW:**

### 1. Check if JWT tokens are being generated:
```javascript
// Check token generation
const token = await window.__dynamicAuthManager?.getCurrentToken();
console.log('🔍 JWT Token Check:');
console.log('  Token exists:', !!token);
console.log('  Token length:', token?.length || 0);
console.log('  Token preview:', token?.substring(0, 50) + '...' || 'NONE');
```

### 2. Monitor ALL MCP requests:
```javascript
// Monitor MCP requests to see if Authorization headers are sent
let reqNum = 0;
const origFetch = window.fetch;
window.fetch = async (...args) => {
  const [url, opts] = args;
  if (url.includes('/mcp/')) {
    reqNum++;
    console.log(`📡 MCP Request #${reqNum}:`, {
      time: new Date().toISOString(),
      hasAuth: !!opts?.headers?.Authorization,
      authLength: opts?.headers?.Authorization?.length || 0,
      authPreview: opts?.headers?.Authorization?.substring(0, 30) || 'NONE'
    });
  }
  return origFetch(...args);
};
console.log('✅ Monitoring enabled - now try a bucket operation');
```

### 3. Test the MCP client configuration:
```javascript
// Check MCP client configuration
console.log('🔍 MCP Client Check:');
console.log('  Client exists:', !!window.__mcpClient);
console.log('  getToken function:', typeof window.__mcpClient?.getToken);
console.log('  Client config:', window.__mcpClient?.config);
```

## 🎯 Expected Results

### If Working Correctly:
```
🔍 JWT Token Check:
  Token exists: true
  Token length: 4084
  Token preview: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6...

📡 MCP Request #1: { hasAuth: false, authLength: 0 }  ✅ (init)
📡 MCP Request #2: { hasAuth: true, authLength: 4084 }  ✅ (tool call)
📡 MCP Request #3: { hasAuth: true, authLength: 4084 }  ✅ (tool call)
```

### If Still Broken:
```
🔍 JWT Token Check:
  Token exists: false  ❌
  Token length: 0
  Token preview: NONE

📡 MCP Request #1: { hasAuth: false, authLength: 0 }  ✅ (init)
📡 MCP Request #2: { hasAuth: false, authLength: 0 }  ❌ (tool call - NO JWT!)
📡 MCP Request #3: { hasAuth: false, authLength: 0 }  ❌ (tool call - NO JWT!)
```

## 🔧 Common Issues & Fixes

### Issue 1: Token Generation Failing
**Symptom**: `Token exists: false`
**Fix**: Check DynamicAuthManager configuration:
```javascript
console.log('DynamicAuthManager state:', {
  exists: !!window.__dynamicAuthManager,
  isInitialized: window.__dynamicAuthManager?.isInitialized,
  hasTokenGenerator: !!window.__dynamicAuthManager?.tokenGenerator,
  secret: window.__dynamicAuthManager?.tokenGenerator?.signingSecret?.substring(0, 20) + '...',
  secretLength: window.__dynamicAuthManager?.tokenGenerator?.signingSecret?.length
});
```

### Issue 2: MCP Client Not Using getToken
**Symptom**: `getToken function: undefined`
**Fix**: Ensure MCP client is configured with getToken function:
```javascript
// The MCP client should be configured like this:
const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    // This function should be called for every request after init
    const token = await window.__dynamicAuthManager.getCurrentToken();
    return token;
  }
});
```

### Issue 3: getToken Always Returns Null
**Symptom**: `hasAuth: false` for all requests after init
**Fix**: Check the getToken logic:
```javascript
// The getToken function should NOT return null after the first request
let requestCount = 0;
const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    requestCount++;
    console.log(`getToken called for request #${requestCount}`);
    
    if (requestCount === 1) {
      console.log('Skipping token for init request');
      return null; // Only for init
    }
    
    const token = await window.__dynamicAuthManager.getCurrentToken();
    console.log(`Token for request #${requestCount}:`, token ? 'EXISTS' : 'NULL');
    return token; // For all other requests
  }
});
```

## 🚀 Quick Test

After running the diagnostic commands, try this test:

```javascript
// Test bucket access
setTimeout(async () => {
  console.log('\n🧪 Testing bucket access...');
  
  try {
    const result = await window.__mcpClient.callTool({
      name: 'bucket_objects_list',
      arguments: { bucket: 's3://quilt-sandbox-bucket', max_keys: 3 }
    });
    
    if (result.error) {
      console.error('❌ Test failed:', result.error);
    } else {
      console.log('✅ Test passed! Got', result.objects?.length || 0, 'objects');
    }
  } catch (error) {
    console.error('❌ Test error:', error);
  }
}, 2000);
```

## 📋 Next Steps

1. **Run the diagnostic commands** above
2. **Check the console output** to see what's happening
3. **Share the results** so we can identify the specific issue
4. **Apply the appropriate fix** based on the diagnostic results

The backend is ready and waiting - we just need to identify why the frontend isn't sending JWT tokens! 🎯













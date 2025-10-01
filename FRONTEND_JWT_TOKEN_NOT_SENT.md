# 🚨 CRITICAL: Frontend Not Sending JWT Tokens After Init

## 🐛 Current Problem

The frontend successfully fixed the "chicken-and-egg" problem by not sending JWT during initialization, but **overcorrected** - now they're **not sending JWT tokens AT ALL**.

### Backend Logs Confirm:
```
16:33:14 - MCP session d3a9571b55434f719b803c1f935a5712: No auth header, allowing for initialization
16:33:14 - ⚠️  Setting runtime context to UNAUTHENTICATED - tools will NOT have JWT!
16:33:37 - (tool call - still no JWT!)
16:34:09 - (tool call - still no JWT!)
16:34:13 - (tool call - still no JWT!)
```

**Result**: Session is UNAUTHENTICATED → No bucket access → All tools fail with "Access denied"

---

## ✅ Expected Behavior

### Request Flow (Correct):
1. **First request (init)**: NO Authorization header → Session created as UNAUTHENTICATED
2. **Second request (tool call)**: **WITH Authorization: Bearer <token>** → Session updated with JWT
3. **Third+ requests**: Reuse cached JWT session → Full bucket access

### Current Flow (WRONG):
1. **First request (init)**: NO Authorization header → Session created as UNAUTHENTICATED ✅
2. **Second request (tool call)**: NO Authorization header → Session stays UNAUTHENTICATED ❌
3. **Third+ requests**: Reuse UNAUTHENTICATED session → No bucket access ❌

---

## 🔧 The Fix

### Problem Code (Current):
```javascript
// MCP Client initialization
const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    // Don't send token during init
    if (!mcpClient.isInitialized) {
      return null;  // ✅ Correct for init
    }
    // After init, send token
    return await window.__dynamicAuthManager.getCurrentToken();
    // ❌ BUT THIS IS NEVER BEING CALLED!
  }
})
```

**The bug**: The `getToken` function is defined correctly, but it's **not being called** for subsequent requests, OR it's returning `null` even after initialization.

### Solution 1: Ensure getToken is Called for Every Request

**Check if the MCP client is actually calling `getToken` for every request:**

```javascript
// Add logging to verify function is being called
const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    console.log('🔍 getToken called, isInitialized:', mcpClient.isInitialized);
    
    if (!mcpClient.isInitialized) {
      console.log('⏭️  Skipping token (not initialized yet)');
      return null;
    }
    
    const token = await window.__dynamicAuthManager.getCurrentToken();
    console.log('✅ Returning token, length:', token?.length || 0);
    return token;
  }
})
```

**Expected console output:**
```
🔍 getToken called, isInitialized: false
⏭️  Skipping token (not initialized yet)
... (MCP initializes) ...
🔍 getToken called, isInitialized: true
✅ Returning token, length: 4084
🔍 getToken called, isInitialized: true
✅ Returning token, length: 4084
```

### Solution 2: Fix the isInitialized Check

**If `isInitialized` is always `false`, the check is wrong:**

```javascript
// Option A: Use a flag that's set after initialization
let sessionEstablished = false;

const initMCP = async () => {
  const client = new MCPClient({
    url: '/mcp/',
    getToken: async () => {
      if (!sessionEstablished) {
        console.log('⏭️  Init phase - no token');
        return null;
      }
      console.log('✅ Sending JWT token');
      return await window.__dynamicAuthManager.getCurrentToken();
    }
  });
  
  await client.initialize();
  sessionEstablished = true;  // ✅ Set flag AFTER init
  console.log('✅ MCP session established, will send tokens now');
  
  return client;
};

// Option B: Check for session ID instead
const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    // If we don't have a session ID yet, we're initializing
    if (!mcpClient.sessionId) {
      return null;
    }
    return await window.__dynamicAuthManager.getCurrentToken();
  }
});

// Option C: Use request count
let requestCount = 0;

const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    requestCount++;
    console.log('Request #', requestCount);
    
    // First request is always init (no token)
    if (requestCount === 1) {
      return null;
    }
    
    // All subsequent requests should have token
    return await window.__dynamicAuthManager.getCurrentToken();
  }
});
```

### Solution 3: Verify Token is Actually Generated

**The token generator might be failing silently:**

```javascript
const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    if (!sessionEstablished) {
      return null;
    }
    
    try {
      const token = await window.__dynamicAuthManager.getCurrentToken();
      
      if (!token) {
        console.error('❌ getCurrentToken returned null/undefined!');
        // Debug why
        console.log('DynamicAuthManager state:', {
          isInitialized: window.__dynamicAuthManager.isInitialized,
          hasTokenGenerator: !!window.__dynamicAuthManager.tokenGenerator,
          hasSecret: !!window.__dynamicAuthManager.tokenGenerator?.signingSecret,
          secretLength: window.__dynamicAuthManager.tokenGenerator?.signingSecret?.length
        });
        return null;
      }
      
      console.log('✅ Token generated, length:', token.length);
      return token;
      
    } catch (error) {
      console.error('❌ Error getting token:', error);
      return null;
    }
  }
});
```

---

## 🧪 Testing & Verification

### Test 1: Verify getToken is Called
**Open browser DevTools console and refresh the page.**

**Expected output:**
```
🔍 getToken called, isInitialized: false
⏭️  Skipping token (not initialized yet)
✅ MCP session established
🔍 getToken called, isInitialized: true
✅ Returning token, length: 4084
```

**If you see:**
- No "getToken called" logs → `getToken` is not being invoked
- All "isInitialized: false" → The initialization flag is not being set
- "token length: 0" or "null" → Token generation is failing

### Test 2: Check Network Requests
**Open DevTools → Network tab → Filter by "mcp"**

**Look at request headers:**

**First request (init):**
```
POST /mcp/?t=1759250000000
Headers:
  (no Authorization header) ✅ Correct
```

**Second request (tool call):**
```
POST /mcp/?t=1759250005000
Headers:
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImZyb250... ✅ Should be here!
```

**If the Authorization header is MISSING** in request #2+, that's the bug!

### Test 3: Check Backend Logs
**Run this to see what the backend receives:**

```bash
aws logs tail /ecs/mcp-server-production --region us-east-1 --since 2m --format short | grep "Session.*JWT\|auth header"
```

**Expected after fix:**
```
MCP session abc123: No auth header, allowing for initialization
Session abc123: New JWT token detected, re-authenticating
✅ Session abc123 updated with new JWT
Using cached JWT auth for session abc123
```

**Current (WRONG):**
```
MCP session abc123: No auth header, allowing for initialization
(no more auth logs - all requests have no auth header)
```

---

## 🔍 Debugging Steps

### Step 1: Add Comprehensive Logging
```javascript
// Wrap the entire MCP client creation with logging
console.log('='.repeat(80));
console.log('🔧 INITIALIZING MCP CLIENT');
console.log('='.repeat(80));

let requestNumber = 0;

const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    requestNumber++;
    console.log(`\n📞 Request #${requestNumber}: getToken called`);
    console.log('  isInitialized:', mcpClient.isInitialized);
    console.log('  sessionId:', mcpClient.sessionId);
    
    // Check if we should send token
    const shouldSendToken = mcpClient.isInitialized || requestNumber > 1;
    console.log('  shouldSendToken:', shouldSendToken);
    
    if (!shouldSendToken) {
      console.log('  ⏭️  Returning null (init phase)');
      return null;
    }
    
    // Try to get token
    console.log('  🔄 Getting token from DynamicAuthManager...');
    const token = await window.__dynamicAuthManager.getCurrentToken();
    
    if (!token) {
      console.error('  ❌ Token is null/undefined!');
      console.log('  DynamicAuthManager:', {
        exists: !!window.__dynamicAuthManager,
        isInitialized: window.__dynamicAuthManager?.isInitialized,
        hasTokenGenerator: !!window.__dynamicAuthManager?.tokenGenerator
      });
      return null;
    }
    
    console.log('  ✅ Token obtained, length:', token.length);
    console.log('  Token preview:', token.substring(0, 50) + '...');
    return token;
  }
});

console.log('✅ MCP Client created');
console.log('='.repeat(80));
```

### Step 2: Test Token Generation Independently
```javascript
// Test token generation BEFORE MCP client
console.log('Testing token generation...');
const testToken = await window.__dynamicAuthManager.getCurrentToken();
console.log('Token:', testToken ? 'Generated ✅' : 'Failed ❌');
console.log('Length:', testToken?.length || 0);

if (testToken) {
  // Decode to verify
  const parts = testToken.split('.');
  const payload = JSON.parse(atob(parts[1]));
  console.log('Payload:', {
    iss: payload.iss,
    aud: payload.aud,
    buckets: payload.buckets?.length,
    permissions: payload.permissions?.length
  });
}
```

### Step 3: Monitor All MCP Requests
```javascript
// Add request interceptor to log all MCP requests
const originalFetch = window.fetch;
window.fetch = async (...args) => {
  const [url, options] = args;
  
  if (url.includes('/mcp/')) {
    console.log('🌐 MCP Request:', {
      url,
      method: options?.method,
      hasAuthHeader: !!options?.headers?.Authorization,
      authHeaderPreview: options?.headers?.Authorization?.substring(0, 30)
    });
  }
  
  return originalFetch(...args);
};
```

---

## 📋 Checklist for Frontend Team

### Before Making Changes:
- [ ] Add logging to `getToken` function
- [ ] Verify `getToken` is actually being called for each request
- [ ] Check that `isInitialized` or equivalent flag is being set correctly
- [ ] Verify `getCurrentToken()` is returning a valid token

### Implementation:
- [ ] Fix the condition that determines when to send tokens
- [ ] Ensure tokens are sent for ALL requests AFTER initialization
- [ ] Keep NOT sending tokens during initialization (first request only)

### After Changes:
- [ ] Hard refresh browser (Cmd/Ctrl + Shift + R)
- [ ] Check console logs show tokens being sent
- [ ] Check Network tab shows Authorization headers (except first request)
- [ ] Test bucket access - should work now
- [ ] Verify backend logs show "Session updated with new JWT"

---

## 🎯 Success Criteria

After the fix, you should see:

### In Browser Console:
```
🔍 Request #1: getToken called
  shouldSendToken: false
  ⏭️  Returning null (init phase)
  
🔍 Request #2: getToken called
  shouldSendToken: true
  🔄 Getting token from DynamicAuthManager...
  ✅ Token obtained, length: 4084
  
🔍 Request #3: getToken called
  shouldSendToken: true
  ✅ Token obtained, length: 4084
```

### In Network Tab:
```
Request 1: POST /mcp/?t=xxx
  Headers: (no Authorization) ✅
  
Request 2: POST /mcp/?t=xxx
  Headers: Authorization: Bearer eyJhbGci... ✅
  
Request 3: POST /mcp/?t=xxx
  Headers: Authorization: Bearer eyJhbGci... ✅
```

### In Backend Logs:
```
MCP session abc123: No auth header, allowing for initialization
Session abc123: New JWT token detected, re-authenticating
✅ Session abc123 updated with new JWT
Using cached JWT auth for session abc123
```

### In MCP Tools:
```javascript
const result = await window.__mcpClient.callTool({
  name: 'bucket_objects_list',
  arguments: { bucket: 's3://quilt-sandbox-bucket' }
})
// Should return bucket objects, not "Access denied"
```

---

## 🚀 Quick Test Command

Run this in browser console after implementing the fix:

```javascript
// Clear everything and test
localStorage.clear();
location.reload();

// After page loads:
(async () => {
  console.log('Testing MCP authentication flow...');
  
  // Wait for initialization
  await new Promise(r => setTimeout(r, 2000));
  
  // Test tool call
  const result = await window.__mcpClient.callTool({
    name: 'bucket_objects_list',
    arguments: { bucket: 's3://quilt-sandbox-bucket', max_keys: 5 }
  });
  
  if (result.error) {
    console.error('❌ FAILED:', result.error);
  } else {
    console.log('✅ SUCCESS! Got', result.objects?.length || 0, 'objects');
  }
})();
```

**Expected output:**
```
Testing MCP authentication flow...
✅ SUCCESS! Got 5 objects
```

---

**TL;DR**: The frontend is correctly NOT sending JWT during init, but then NEVER sends JWT for subsequent requests. Fix: Ensure `getToken()` returns tokens for all requests AFTER the first one. 🎯










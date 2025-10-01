# 🚨 URGENT: Frontend MUST Send JWT Tokens - Confirmed Issue

## 📊 Latest Evidence (17:05 UTC - 2 minutes ago)

### Backend Logs Show:
```
17:05 - MCP session 4ebe14aee9e04fd2a394b3d1684ea764: No auth header, allowing for initialization
17:05 - ⚠️  Setting runtime context to UNAUTHENTICATED - tools will NOT have JWT!
17:05 - (tool calls using UNAUTHENTICATED session)
17:05 - S3 access falls back to ecsTaskRole → Permission denied for s3:PutObject
```

### What This Means:
1. ✅ Frontend correctly NOT sending JWT during init (Request #1)
2. ❌ **Frontend also NOT sending JWT for tool calls** (Requests #2, #3, #4...)
3. ❌ Backend has NO JWT credentials → Falls back to ECS task IAM role
4. ❌ ECS task role has minimal permissions → Can't write to S3

---

## ⚠️ The Problem in Detail

### Request Flow (CURRENT - BROKEN):
```
Request #1 (init):
  Frontend → No Authorization header
  Backend → Creates UNAUTHENTICATED session
  Result → ✅ Init succeeds

Request #2 (tool call - bucket_objects_list):
  Frontend → No Authorization header  ← PROBLEM!
  Backend → Uses UNAUTHENTICATED session
  Backend → Falls back to ecsTaskRole
  Result → ❌ "Access denied" (ecsTaskRole has no permissions)

Request #3 (tool call - bucket_objects_put):
  Frontend → No Authorization header  ← PROBLEM!
  Backend → Uses UNAUTHENTICATED session
  Backend → Falls back to ecsTaskRole
  Result → ❌ "Not authorized for s3:PutObject"
```

### Request Flow (EXPECTED - CORRECT):
```
Request #1 (init):
  Frontend → No Authorization header
  Backend → Creates UNAUTHENTICATED session
  Result → ✅ Init succeeds

Request #2 (tool call - bucket_objects_list):
  Frontend → Authorization: Bearer eyJhbGci...  ← MUST ADD THIS!
  Backend → Detects new JWT → Re-authenticates
  Backend → Updates session with JWT credentials
  Backend → Uses JWT-derived AWS credentials
  Result → ✅ Full bucket access

Request #3+ (tool calls):
  Frontend → Authorization: Bearer eyJhbGci...
  Backend → Uses cached JWT session
  Backend → Uses JWT-derived AWS credentials
  Result → ✅ Full bucket access (read AND write)
```

---

## ✅ THE FIX (CRITICAL - MUST IMPLEMENT NOW)

### Current Frontend Code (BROKEN):
```javascript
// This is what's happening now - getToken returns null for ALL requests
const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    // This condition is ALWAYS true, so it NEVER sends tokens
    if (!mcpClient.isInitialized) {
      return null;
    }
    // This line is NEVER reached
    return await window.__dynamicAuthManager.getCurrentToken();
  }
})
```

### Fixed Frontend Code (USE THIS):
```javascript
// Track requests to know when to send tokens
let mcpRequestCount = 0;

const mcpClient = new MCPClient({
  url: '/mcp/',
  getToken: async () => {
    mcpRequestCount++;
    
    // Log for debugging
    console.log(`🔍 MCP Request #${mcpRequestCount} - getToken called`);
    
    // ONLY skip token for the FIRST request (initialization)
    if (mcpRequestCount === 1) {
      console.log('⏭️  Skipping token for init (request #1)');
      return null;
    }
    
    // For ALL other requests, send the JWT token
    console.log('✅ Sending JWT token for request #' + mcpRequestCount);
    const token = await window.__dynamicAuthManager.getCurrentToken();
    
    if (!token) {
      console.error('❌ ERROR: getCurrentToken returned null!');
      console.log('DynamicAuthManager state:', window.__dynamicAuthManager);
    } else {
      console.log('✅ Token length:', token.length);
    }
    
    return token;
  }
});

console.log('✅ MCP Client created with request counter');
```

---

## 🧪 Immediate Test (Run in Browser Console)

### Step 1: Add Request Monitoring
```javascript
// Monitor all fetch requests to /mcp/
let requestNum = 0;
const origFetch = window.fetch;
window.fetch = async (...args) => {
  const [url, opts] = args;
  if (url.includes('/mcp/')) {
    requestNum++;
    const hasAuth = !!opts?.headers?.Authorization;
    const authPreview = opts?.headers?.Authorization?.substring(0, 50);
    
    console.log(`📡 MCP Request #${requestNum}:`, {
      hasAuth,
      authPreview: hasAuth ? authPreview + '...' : 'NONE'
    });
    
    if (requestNum > 1 && !hasAuth) {
      console.error(`❌ ERROR: Request #${requestNum} has NO Authorization header!`);
      console.error('Frontend is NOT sending JWT tokens!');
    }
  }
  return origFetch(...args);
};

console.log('✅ Request monitoring enabled - refresh page now');
```

### Step 2: Refresh Page and Check Output

**Current (BROKEN) Output:**
```
📡 MCP Request #1: { hasAuth: false, authPreview: 'NONE' }  ✅ Correct
📡 MCP Request #2: { hasAuth: false, authPreview: 'NONE' }  ❌ ERROR!
❌ ERROR: Request #2 has NO Authorization header!
Frontend is NOT sending JWT tokens!
```

**Expected (CORRECT) Output:**
```
📡 MCP Request #1: { hasAuth: false, authPreview: 'NONE' }  ✅
📡 MCP Request #2: { hasAuth: true, authPreview: 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImtpZCI...' }  ✅
📡 MCP Request #3: { hasAuth: true, authPreview: 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImtpZCI...' }  ✅
```

---

## 🎯 Why This Causes the ecsTaskRole Error

### Without JWT:
```
Session: UNAUTHENTICATED
↓
No JWT credentials available
↓
Backend falls back to default AWS credentials
↓
Uses ECS task's IAM role (arn:aws:sts::850787717197:assumed-role/ecsTaskRole/...)
↓
ecsTaskRole has MINIMAL permissions (no s3:PutObject)
↓
Error: "Not authorized for s3:PutObject"
```

### With JWT:
```
Session: AUTHENTICATED (JWT)
↓
JWT contains AWS credentials (from role: ReadWriteQuiltV2-sales-prod)
↓
Backend uses JWT-derived AWS credentials
↓
ReadWriteQuiltV2-sales-prod has FULL bucket permissions
↓
Success: Read AND write access to all authorized buckets
```

---

## 📋 Implementation Checklist

### Before Implementing:
- [ ] Verify `getCurrentToken()` returns a valid token
  ```javascript
  const token = await window.__dynamicAuthManager.getCurrentToken();
  console.log('Token:', !!token, 'Length:', token?.length);
  // Should show: Token: true Length: 4000+
  ```

- [ ] Check JWT secret is correct (33 chars)
  ```javascript
  const secret = window.__dynamicAuthManager?.tokenGenerator?.signingSecret;
  console.log('Secret:', secret, 'Length:', secret?.length);
  // Should show: Secret: QuiltMCPJWTSecret2025ProductionV1 Length: 33
  ```

### Implementation:
- [ ] Modify `getToken` function to use request counter
- [ ] Ensure `return null` ONLY for request #1
- [ ] Ensure `return token` for ALL requests #2+
- [ ] Add console logging for debugging
- [ ] Deploy the change

### After Deployment:
- [ ] Hard refresh browser (Cmd/Ctrl + Shift + R)
- [ ] Check console logs show tokens being sent
- [ ] Check Network tab shows Authorization headers (except request #1)
- [ ] Test bucket access - should work for both read AND write
- [ ] Verify NO more ecsTaskRole errors

---

## 🚀 Verification Commands

### Test Bucket Access After Fix:
```javascript
// Clear everything
localStorage.clear();
location.reload();

// After reload (wait 2 seconds):
setTimeout(async () => {
  console.log('Testing bucket access with JWT...');
  
  // Test read
  const listResult = await window.__mcpClient.callTool({
    name: 'bucket_objects_list',
    arguments: { bucket: 's3://quilt-sandbox-bucket', max_keys: 5 }
  });
  
  console.log('Read test:', listResult.objects?.length > 0 ? '✅ SUCCESS' : '❌ FAILED');
  
  // Test write (if supported)
  const writeResult = await window.__mcpClient.callTool({
    name: 'bucket_access_check',
    arguments: { bucket_name: 'quilt-sandbox-bucket', operations: ['write'] }
  });
  
  console.log('Write test:', writeResult.access_summary?.can_write ? '✅ SUCCESS' : '❌ FAILED');
}, 2000);
```

**Expected Output:**
```
Testing bucket access with JWT...
Read test: ✅ SUCCESS
Write test: ✅ SUCCESS
```

### Check Backend Logs:
```bash
aws logs tail /ecs/mcp-server-production --region us-east-1 --since 2m --format short | grep -E "Session.*JWT|Updated with new JWT"
```

**Expected Output:**
```
MCP session abc123: No auth header, allowing for initialization
Session abc123: New JWT token detected, re-authenticating
✅ Session abc123 updated with new JWT
Using cached JWT auth for session abc123
```

---

## ⚠️ Critical Points

1. **The backend is READY** - It correctly handles JWT when received
2. **The frontend is NOT sending JWT** - Authorization headers are missing
3. **This causes IAM fallback** - Backend uses ecsTaskRole (which has no permissions)
4. **The fix is simple** - Send Authorization headers for requests #2+

---

## 🎯 Success Criteria

After implementing the fix:

- ✅ Request #1: No Authorization header
- ✅ Request #2+: **WITH Authorization: Bearer <token>**
- ✅ Backend logs: "Session updated with new JWT"
- ✅ Bucket access works (read AND write)
- ✅ **NO MORE ecsTaskRole errors**
- ✅ Tools use JWT credentials (not ECS task role)

---

**BOTTOM LINE**: The frontend MUST add `Authorization: Bearer <token>` headers to ALL MCP requests EXCEPT the first one. This is the ONLY thing blocking full bucket access! 🚀










# CRITICAL: Frontend MCP Client Not Sending Authorization Header

## 🚨 Problem Identified

**CloudWatch Logs Show:**
```
MCP session 266db5d2804a46748dc9b78e2d4f08bb: No auth header, allowing for initialization
MCP session 266db5d2804a46748dc9b78e2d4f08bb: No auth header, allowing for initialization
MCP session 266db5d2804a46748dc9b78e2d4f08bb: No auth header, allowing for initialization
```

**Diagnosis:** The frontend MCP Client is **NOT sending the Authorization header** on tool requests.

**Result:** All requests are unauthenticated → Tools fall back to IAM role → No write access

---

## 🔍 Root Cause

The MCP Client in `Client.ts` needs to send the `Authorization: Bearer <token>` header on **EVERY request**, not just the first one.

### Current Behavior (Wrong):
```
Request 1 (init): No Authorization header
Request 2 (tool): No Authorization header  ❌
Request 3 (tool): No Authorization header  ❌
```

### Expected Behavior (Correct):
```
Request 1 (init): No Authorization header (OK for protocol handshake)
Request 2 (tool): Authorization: Bearer <jwt>  ✅
Request 3 (tool): Authorization: Bearer <jwt>  ✅
```

---

## 🔧 Fix Required in Frontend

### Location: `catalog/app/components/Assistant/MCP/Client.ts`

### Issue 1: Headers Not Persisted

The `getRequestHeaders()` method gets the token, but it might not be called for every request.

**Find this pattern:**
```typescript
private async getRequestHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: this.getAcceptHeader(),
    'Cache-Control': 'no-cache',
    'mcp-protocol-version': MCP_PROTOCOL_VERSION,
  }

  if (this.sessionId) {
    headers['mcp-session-id'] = this.sessionId
  }

  // Primary Authentication: Bearer Token (Redux or OAuth)
  const accessToken = await this.getAccessToken()
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
    // ... logging ...
  }
  
  return headers
}
```

**Ensure this method is called for EVERY request:**

```typescript
// In the request method
async request(method: string, params: any) {
  const headers = await this.getRequestHeaders()  // ✅ Get fresh headers every time
  
  const response = await fetch(this.endpoint, {
    method: 'POST',
    headers: headers,  // ✅ Use headers with Authorization
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: generateId(),
      method: method,
      params: params
    })
  })
  
  return response.json()
}
```

### Issue 2: Token Not Available

The `getAccessToken()` method might be returning `null` or `undefined`.

**Add debugging:**
```typescript
const accessToken = await this.getAccessToken()
console.log('🔍 MCP Request Headers:', {
  method,
  hasAccessToken: !!accessToken,
  tokenLength: accessToken?.length,
  sessionId: this.sessionId,
  headers: Object.keys(headers)
})

if (!accessToken) {
  console.error('❌ No access token available for MCP request!')
  console.error('  - Check tokenGetter is configured')
  console.error('  - Check DynamicAuthManager.getCurrentToken()')
}
```

### Issue 3: Headers Not Included in Fetch

**Verify the fetch call includes headers:**
```typescript
const response = await fetch(this.endpoint, {
  method: 'POST',
  headers: await this.getRequestHeaders(),  // ✅ Must be here
  body: JSON.stringify(request)
})
```

---

## 🧪 Verification Commands

### Run in Browser Console:

**Test 1: Check if headers are being generated:**
```javascript
const client = window.__mcpClient
const headers = await client.getRequestHeaders()
console.log('MCP Headers:', headers)
console.log('Has Authorization:', !!headers.Authorization)
```

**Expected:**
```javascript
{
  'Content-Type': 'application/json',
  'mcp-protocol-version': '2024-11-05',
  'mcp-session-id': '266db5d2804a46748dc9b78e2d4f08bb',
  'Authorization': 'Bearer eyJhbGc...'  // ✅ Must be present
}
```

**Test 2: Intercept fetch to see what's sent:**
```javascript
const originalFetch = window.fetch
window.fetch = function(...args) {
  const [url, options] = args
  if (url.includes('/mcp')) {
    console.log('🔍 MCP Fetch:', {
      url,
      method: options?.method,
      headers: options?.headers,
      hasAuth: !!(options?.headers?.Authorization || options?.headers?.authorization)
    })
    
    if (!options?.headers?.Authorization && !options?.headers?.authorization) {
      console.error('❌ MCP request without Authorization header!')
      console.trace()
    }
  }
  return originalFetch.apply(this, args)
}
console.log('✅ Fetch interceptor installed')
```

Then ask Qurator to use an MCP tool and watch the console.

---

## 🎯 Expected Fix

### Before (Broken):
```javascript
🔍 MCP Fetch: {
  url: 'https://demo.quiltdata.com/mcp',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'mcp-session-id': '266db5d2804a46748dc9b78e2d4f08bb'
  },
  hasAuth: false  // ❌
}
```

### After (Fixed):
```javascript
🔍 MCP Fetch: {
  url: 'https://demo.quiltdata.com/mcp',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'mcp-session-id': '266db5d2804a46748dc9b78e2d4f08bb',
    'Authorization': 'Bearer eyJhbGc...'
  },
  hasAuth: true  // ✅
}
```

---

## 📋 Quick Checklist for Frontend

### In `Client.ts`:

- [ ] `getRequestHeaders()` is async and awaits the token
- [ ] `getAccessToken()` successfully returns a token (not null)
- [ ] Headers include `Authorization: Bearer <token>`
- [ ] Every request calls `getRequestHeaders()` to get fresh headers
- [ ] Fetch calls include the headers object

### Common Issues:

**Issue 1: Token getter returns null**
```typescript
// Check DynamicAuthManager
const token = await window.__dynamicAuthManager.getCurrentToken()
if (!token) {
  console.error('DynamicAuthManager returning null token!')
}
```

**Issue 2: Headers not awaited**
```typescript
// WRONG:
const headers = this.getRequestHeaders()  // ❌ Missing await

// RIGHT:
const headers = await this.getRequestHeaders()  // ✅
```

**Issue 3: Headers not passed to fetch**
```typescript
// WRONG:
fetch(url, { method: 'POST', body: ... })  // ❌ No headers

// RIGHT:
fetch(url, { 
  method: 'POST',
  headers: await this.getRequestHeaders(),  // ✅
  body: ...
})
```

---

## 🧪 Test After Fix

After fixing the Client.ts:

1. **Install fetch interceptor** (browser console)
2. **Ask Qurator** to list objects in a bucket
3. **Check console** - should show `hasAuth: true`
4. **Check CloudWatch** - should show:
   ```
   INFO: MCP request: session=abc123 has_auth=True
   INFO: Session abc123: JWT authenticated for user testuser (buckets=32, permissions=24)
   ```

---

## 🎯 Bottom Line

**MCP Server:** ✅ Working perfectly (session auth, SSM secret, diagnostics)  
**Frontend Client:** ❌ Not sending Authorization header on requests  
**Fix:** Update `Client.ts` to include Authorization header on ALL requests

Once the frontend sends the header, everything will work! 🚀

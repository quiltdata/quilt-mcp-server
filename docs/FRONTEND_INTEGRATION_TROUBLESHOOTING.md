# Frontend Integration Troubleshooting Guide

> **For backend deployment**, see [JWT_AUTHENTICATION.md](developer/JWT_AUTHENTICATION.md)
> **For architecture details**, see [JWT_ARCHITECTURE.md](JWT_ARCHITECTURE.md)

## Overview

This guide helps troubleshoot frontend MCP Client integration issues with the Quilt MCP Server's JWT authentication.

## Common Issues

### Issue 1: MCP Client Not Sending Authorization Header

**Symptoms:**
- CloudWatch logs show: "No auth header, allowing for initialization" on every request
- Tools fail with "No write access" or fall back to IAM role
- 401 Unauthorized responses

**Diagnosis:**

```javascript
// Browser console - intercept requests
const originalFetch = window.fetch
window.fetch = function(...args) {
  const [url, options] = args
  if (url.includes('/mcp')) {
    console.log('🔍 MCP Request:', {
      url,
      method: options?.method,
      hasAuth: !!(options?.headers?.Authorization || options?.headers?.authorization),
      headers: options?.headers
    })

    if (!options?.headers?.Authorization) {
      console.error('❌ Missing Authorization header!')
    }
  }
  return originalFetch.apply(this, args)
}
console.log('✅ Fetch interceptor installed')
```

**Root Causes:**

1. **Headers not generated on every request**
   ```typescript
   // WRONG: Headers generated once
   const headers = await this.getRequestHeaders()
   this.headers = headers  // ❌ Cached

   // RIGHT: Fresh headers per request
   async request(method, params) {
     const headers = await this.getRequestHeaders()  // ✅ Fresh
     return fetch(url, { headers, ... })
   }
   ```

2. **Token getter returns null**
   ```javascript
   // Check token availability
   const token = await window.__dynamicAuthManager.getCurrentToken()
   if (!token) {
     console.error('❌ DynamicAuthManager returning null!')
   }
   ```

3. **Headers not passed to fetch**
   ```typescript
   // WRONG:
   fetch(url, { method: 'POST', body: ... })  // ❌ No headers

   // RIGHT:
   fetch(url, {
     headers: await this.getRequestHeaders(),  // ✅
     method: 'POST',
     body: ...
   })
   ```

**Fix:**

In `Client.ts`, ensure `getRequestHeaders()` is called and awaited for every request:

```typescript
async request(method: string, params: any) {
  const headers = await this.getRequestHeaders()  // ✅ Get fresh headers

  const response = await fetch(this.endpoint, {
    method: 'POST',
    headers: headers,  // ✅ Include Authorization
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

### Issue 2: MCP Server URL Not Configured

**Symptoms:**
- Console shows "MCP Server URL: undefined"
- 401 errors on requests to `/mcp/?t=...`

**Diagnosis:**

```javascript
// Browser console
const client = window.__mcpClient
console.log('MCP Config:', {
  endpoint: client?.endpoint,
  hasTokenGetter: !!client?.tokenGetter,
  configUrl: quiltConfig?.mcp?.serverUrl
})
```

**Fix:**

Ensure MCP Client is initialized with endpoint:

```typescript
// In MCPContextProvider.tsx
const mcpClient = new MCPClient({
  endpoint: 'https://demo.quiltdata.com/mcp',  // ✅ Must be set
  tokenGetter: async () => {
    return await dynamicAuthManager.getCurrentToken()
  }
})
```

**Configuration:**

```json
{
  "mcp": {
    "serverUrl": "https://demo.quiltdata.com/mcp",
    "enhancedJwt": {
      "signingSecret": "quilt-sales-prod-mcp-jwt-secret-2025-enhanced-tokens-v2",
      "keyId": "frontend-enhanced"
    }
  }
}
```

### Issue 3: JWT Signature Verification Fails

**Symptoms:**
- Console: "JWT token could not be verified"
- Backend logs: "Signature verification failed"

**Diagnosis:**

```javascript
// Browser console - compare secrets
const tokenGen = window.__dynamicAuthManager?.tokenGenerator
const secret = tokenGen?.signingSecret

console.log('Frontend Secret:', {
  length: secret?.length,
  first10: secret?.substring(0, 10),
  last10: secret?.substring(secret.length - 10),
  hasWhitespace: secret !== secret?.trim()
})
```

**Expected:**
- Secret: `quilt-sales-prod-mcp-jwt-secret-2025-enhanced-tokens-v2`
- Length: **55 characters**
- No whitespace, no special characters

**Fix:**

Ensure frontend and backend secrets match **exactly** (case-sensitive, no extra spaces):

```javascript
// Verify in browser console
const expectedSecret = 'quilt-sales-prod-mcp-jwt-secret-2025-enhanced-tokens-v2'
const actualSecret = window.__dynamicAuthManager?.tokenGenerator?.signingSecret

console.log('Secrets match:', expectedSecret === actualSecret)
```

### Issue 4: Bucket Format Error

**Symptoms:**
- Error: "Cannot use 'in' operator to search for 'name' in cellpainting-gallery"

**Root Cause:**

Code checks `'name' in bucket` where `bucket` is a string, not an object.

**Fix:**

```javascript
// WRONG:
buckets.forEach((bucket) => {
  if ('name' in bucket) {  // ❌ Crashes on strings
    bucketName = bucket.name
  }
})

// RIGHT:
buckets.forEach((bucket) => {
  const bucketName = typeof bucket === 'string' ? bucket : bucket?.name  // ✅
  if (bucketName) {
    // ... use bucketName
  }
})

// OR use the helper:
const extractBucketNames = (buckets) => {
  if (!Array.isArray(buckets)) return []
  return buckets
    .map((bucket) => {
      if (typeof bucket === 'string') return bucket.trim()
      if (bucket?.name) return bucket.name.trim()
      return null
    })
    .filter(name => name && name.length > 0)
}

const bucketNames = extractBucketNames(freshBuckets)
```

### Issue 5: Token Not Enhanced

**Symptoms:**
- Enhanced token identical to original token
- Console: "⚠️ EnhancedTokenGenerator: Missing signing secret"

**Diagnosis:**

```javascript
// Browser console
const tokenGen = window.__dynamicAuthManager?.tokenGenerator
console.log('TokenGen Config:', {
  hasSecret: !!tokenGen?.signingSecret,
  secretLength: tokenGen?.signingSecret?.length,
  kid: tokenGen?.signingKeyId
})
```

**Fix:**

Ensure `EnhancedTokenGenerator` receives the secret during initialization:

```javascript
// In initialization code
const enhancedTokenGenerator = new EnhancedTokenGenerator({
  signingSecret: quiltConfig?.mcp?.enhancedJwt?.signingSecret,  // ✅ Pass config
  signingKeyId: 'frontend-enhanced',
  mcpServerUrl: quiltConfig?.mcp?.serverUrl
})
```

Add defensive checks in constructor:

```javascript
constructor({ signingSecret, signingKeyId }) {
  this.signingSecret =
    signingSecret ||
    process.env.MCP_ENHANCED_JWT_SECRET ||
    quiltConfig?.mcp?.enhancedJwt?.signingSecret

  if (!this.signingSecret) {
    console.error('❌ EnhancedTokenGenerator: Missing signing secret!')
    console.error('   Check: quiltConfig.mcp.enhancedJwt.signingSecret')
  }
}
```

## Comprehensive Diagnostic Script

Run this in the browser console for complete diagnostics:

```javascript
console.log('='.repeat(80))
console.log('MCP CLIENT DIAGNOSTICS')
console.log('='.repeat(80))

// 1. Configuration
console.log('\n1. CONFIGURATION:')
console.log('   Server URL:', quiltConfig?.mcp?.serverUrl)
console.log('   JWT Secret length:', quiltConfig?.mcp?.enhancedJwt?.signingSecret?.length)
console.log('   JWT Kid:', quiltConfig?.mcp?.enhancedJwt?.keyId)

// 2. MCP Client
console.log('\n2. MCP CLIENT:')
const client = window.__mcpClient
console.log('   Exists:', !!client)
console.log('   Endpoint:', client?.endpoint)
console.log('   Has token getter:', !!client?.tokenGetter)
console.log('   Session ID:', client?.sessionId)

// 3. Auth Manager
console.log('\n3. AUTH MANAGER:')
const manager = window.__dynamicAuthManager
console.log('   Exists:', !!manager)
console.log('   Token generator:', !!manager?.tokenGenerator)
console.log('   Secret length:', manager?.tokenGenerator?.signingSecret?.length)

// 4. Token Generation
console.log('\n4. TOKEN GENERATION:')
const token = await manager?.getCurrentToken()
console.log('   Token exists:', !!token)
console.log('   Token length:', token?.length)

// 5. Token Getter
console.log('\n5. TOKEN GETTER:')
if (client?.tokenGetter) {
  const gotToken = await client.tokenGetter()
  console.log('   Returns token:', !!gotToken)
  console.log('   Length:', gotToken?.length)
} else {
  console.log('   ❌ Not configured!')
}

// 6. Bucket Discovery
console.log('\n6. BUCKET DISCOVERY:')
const buckets = await manager?.getCurrentBuckets()
console.log('   Count:', buckets?.length)
console.log('   First bucket type:', typeof buckets?.[0])
console.log('   Has sandbox:', buckets?.includes('quilt-sandbox-bucket'))

// 7. Request Headers
console.log('\n7. REQUEST HEADERS:')
if (client?.getRequestHeaders) {
  const headers = await client.getRequestHeaders()
  console.log('   Has Authorization:', !!headers?.Authorization)
  console.log('   Has session ID:', !!headers?.['mcp-session-id'])
}

console.log('\n' + '='.repeat(80))
```

## Expected Results

After fixes, diagnostics should show:

```javascript
1. CONFIGURATION:
   Server URL: https://demo.quiltdata.com/mcp  ✅
   JWT Secret length: 55  ✅
   JWT Kid: frontend-enhanced  ✅

2. MCP CLIENT:
   Exists: true  ✅
   Endpoint: https://demo.quiltdata.com/mcp  ✅
   Has token getter: true  ✅
   Session ID: 266db5d2804a46748dc9b78e2d4f08bb  ✅

3. AUTH MANAGER:
   Exists: true  ✅
   Token generator: true  ✅
   Secret length: 55  ✅

4. TOKEN GENERATION:
   Token exists: true  ✅
   Token length: 1500+  ✅

5. TOKEN GETTER:
   Returns token: true  ✅
   Length: 1500+  ✅

6. BUCKET DISCOVERY:
   Count: 32  ✅
   First bucket type: string  ✅
   Has sandbox: true  ✅

7. REQUEST HEADERS:
   Has Authorization: true  ✅
   Has session ID: true  ✅
```

## Checklist

### Configuration
- [ ] `quiltConfig.mcp.serverUrl` = `https://demo.quiltdata.com/mcp`
- [ ] `quiltConfig.mcp.enhancedJwt.signingSecret` = 55 char secret
- [ ] `quiltConfig.mcp.enhancedJwt.keyId` = `frontend-enhanced`

### MCP Client
- [ ] Client initialized with endpoint
- [ ] Token getter configured and returns token
- [ ] `getRequestHeaders()` called on every request
- [ ] Headers include `Authorization: Bearer <token>`

### Auth Manager
- [ ] `DynamicAuthManager` initialized
- [ ] `EnhancedTokenGenerator` receives signing secret
- [ ] `getCurrentToken()` returns valid JWT
- [ ] `getCurrentBuckets()` returns array of strings

### Code Patterns
- [ ] No `'name' in bucket` checks without type checking
- [ ] All fetch calls include headers
- [ ] Headers are fresh (not cached)
- [ ] Buckets are normalized to strings before use

## Quick Fixes

### Find and Fix `'name' in bucket` Error

```bash
cd catalog/app/services
grep -rn "'name' in" .
```

Replace with safe pattern:

```javascript
const bucketName = typeof bucket === 'string' ? bucket : bucket?.name
```

### Add Request Logging

```typescript
// In Client.ts request method
console.log('🔍 MCP Request:', {
  method,
  endpoint: this.endpoint,
  hasAuth: !!headers?.Authorization,
  sessionId: headers?.['mcp-session-id']
})
```

### Verify Backend Logs

```bash
aws logs tail /ecs/mcp-server-production --follow --region us-east-1
```

Look for:
```
INFO: Session abc123: JWT authenticated for user testuser (buckets=32, permissions=24)
INFO: ✅ Using JWT-based S3 client for bucket_objects_list
```

## Success Criteria

JWT authentication works when:

✅ MCP Client sends `Authorization: Bearer` header on all tool requests
✅ Backend logs show "JWT authenticated" messages
✅ Tools use JWT-derived credentials (not IAM role)
✅ Bucket operations succeed with write access
✅ No "signature verification failed" errors

## References

- **JWT Architecture**: [JWT_ARCHITECTURE.md](JWT_ARCHITECTURE.md)
- **Deployment Guide**: [developer/JWT_AUTHENTICATION.md](developer/JWT_AUTHENTICATION.md)
- **MCP Client**: `catalog/app/components/Assistant/MCP/Client.ts`
- **Auth Manager**: `catalog/app/services/DynamicAuthManager.js`

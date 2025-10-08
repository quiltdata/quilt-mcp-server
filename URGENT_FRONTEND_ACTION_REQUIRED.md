# 🚨 URGENT: Frontend Token Still Using Old Secret

## ⚠️ Critical Issue
Even after browser refresh, the frontend is **STILL sending tokens signed with the OLD secret (55 chars)**.

Backend logs confirm:
```
JWT validation failed: Signature verification failed (secret_length=33, kid=frontend-enhanced)
```

## 🔍 Root Cause
The frontend's `DynamicAuthManager` is either:
1. **Using the old secret** from configuration
2. **Caching old tokens** in memory/localStorage
3. **Not regenerating tokens** after browser refresh

## ✅ IMMEDIATE ACTIONS REQUIRED

### Step 1: Verify Secret Configuration
**Run this in browser console:**
```javascript
// Check current secret
const secret = window.QUILT_CATALOG_CONFIG?.mcpEnhancedJwtSecret
console.log('Frontend Secret:', secret)
console.log('Secret Length:', secret?.length)
console.log('Expected:', 'QuiltMCPJWTSecret2025ProductionV1')
console.log('Match:', secret === 'QuiltMCPJWTSecret2025ProductionV1')
```

**Expected Output:**
```
Frontend Secret: QuiltMCPJWTSecret2025ProductionV1
Secret Length: 33
Expected: QuiltMCPJWTSecret2025ProductionV1
Match: true
```

### Step 2: Force Complete Token Refresh
**Run this in browser console:**
```javascript
// Clear localStorage
localStorage.clear()

// Clear DynamicAuthManager cache
if (window.__dynamicAuthManager) {
  // Force refresh
  await window.__dynamicAuthManager.refreshAllData()
  console.log('✅ DynamicAuthManager refreshed')
}

// Generate new token
const token = await window.__dynamicAuthManager?.getCurrentToken()
console.log('New Token Length:', token?.length)

// Decode and check
const payload = JSON.parse(atob(token.split('.')[1]))
console.log('Token Issued:', new Date(payload.iat * 1000))
console.log('Should be within last few seconds!')
```

### Step 3: Verify Token Signature
**Test if new token validates:**
```javascript
// Test token generation
const manager = window.__dynamicAuthManager
const secret = manager?.tokenGenerator?.signingSecret

console.log('Token Generator Secret:', secret)
console.log('Secret Length:', secret?.length)

// If secret is STILL 55 chars, the config wasn't updated!
if (secret?.length === 55) {
  console.error('❌ PROBLEM: Frontend still using OLD secret!')
  console.error('Expected: QuiltMCPJWTSecret2025ProductionV1 (33 chars)')
  console.error('Actual:', secret)
}
```

## 🔧 Fixes Based on Findings

### If Secret is Wrong (Still 55 chars):
**The frontend configuration wasn't updated. Deploy Rev 95+ with new secret:**

```javascript
// In Config.ts or environment config:
mcpEnhancedJwtSecret: "QuiltMCPJWTSecret2025ProductionV1"  // 33 chars
mcpEnhancedJwtKid: "frontend-enhanced"
```

**Then deploy new frontend build.**

### If Secret is Correct But Token Still Old:
**The token generator is caching. Force regeneration:**

```javascript
// In DynamicAuthManager or EnhancedTokenGenerator:
// Add cache-busting logic
generateEnhancedToken: async ({ originalToken, roles, buckets }) => {
  // DON'T cache - regenerate every time during initial rollout
  const token = jwt.sign(
    {
      ...payload,
      iat: Math.floor(Date.now() / 1000),  // Force new timestamp
      jti: generateUniqueId()  // Force new token ID
    },
    this.signingSecret,
    { algorithm: 'HS256', headers: { kid: this.signingKeyId } }
  )
  return token
}
```

### If localStorage is Caching Old Tokens:
**Clear it on page load:**

```javascript
// In App initialization or main.ts:
if (localStorage.getItem('mcp_jwt_token')) {
  // Clear old cached tokens
  localStorage.removeItem('mcp_jwt_token')
  localStorage.removeItem('enhanced_jwt_cache')
  localStorage.removeItem('auth_token_cache')
  console.log('✅ Cleared old JWT caches')
}
```

## 🧪 Test After Fix

### 1. Hard Refresh Browser
- **Windows/Linux**: `Ctrl + Shift + R`
- **Mac**: `Cmd + Shift + R`
- **Or use Incognito/Private mode**

### 2. Verify New Token
```javascript
const token = await window.__dynamicAuthManager.getCurrentToken()
const parts = token.split('.')
const payload = JSON.parse(atob(parts[1]))

console.log('Token Info:', {
  issued: new Date(payload.iat * 1000),
  expires: new Date(payload.exp * 1000),
  buckets: payload.buckets?.length,
  permissions: payload.permissions?.length
})

// Token should be VERY recent (within last 5 seconds)
const age = Date.now() / 1000 - payload.iat
console.log('Token age (seconds):', age)
// Should be < 10 seconds
```

### 3. Test MCP Connection
```javascript
// Should work without 401 errors
const result = await window.__mcpClient.callTool({
  name: 'bucket_objects_list',
  arguments: { bucket: 's3://quilt-sandbox-bucket' }
})
console.log('✅ Success!', result)
```

## 📊 Expected vs Actual

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Frontend Secret | 33 chars | ? | ❓ |
| Backend Secret | 33 chars | ✅ | ✅ |
| Token Signature | Valid | ❌ Fails | ❌ |
| MCP Tools | Work | ❌ 401 | ❌ |

## 🎯 Success Criteria

After fix, you should see:
- ✅ Frontend secret: `QuiltMCPJWTSecret2025ProductionV1` (33 chars)
- ✅ Backend validates tokens successfully
- ✅ No "Signature verification failed" errors
- ✅ MCP tools work without 401 errors
- ✅ Bucket access works

## 🔍 Debugging Commands

### Check Frontend Config
```javascript
console.log('Config:', {
  mcpUrl: window.QUILT_CATALOG_CONFIG?.mcpUrl,
  mcpEnabled: window.QUILT_CATALOG_CONFIG?.mcpEnabled,
  jwtSecret: window.QUILT_CATALOG_CONFIG?.mcpEnhancedJwtSecret,
  jwtKid: window.QUILT_CATALOG_CONFIG?.mcpEnhancedJwtKid
})
```

### Check Token Generator
```javascript
console.log('Token Generator:', {
  secret: window.__dynamicAuthManager?.tokenGenerator?.signingSecret,
  secretLength: window.__dynamicAuthManager?.tokenGenerator?.signingSecret?.length,
  kid: window.__dynamicAuthManager?.tokenGenerator?.signingKeyId
})
```

### Check Cached Tokens
```javascript
// Check localStorage for any cached tokens
Object.keys(localStorage).filter(k => 
  k.includes('token') || k.includes('jwt') || k.includes('auth')
).forEach(k => {
  console.log(k, localStorage.getItem(k)?.substring(0, 50) + '...')
})
```

## 🚀 Next Steps

1. **Verify secret** in frontend config
2. **Clear all caches** (localStorage, sessionStorage, browser cache)
3. **Hard refresh** browser or use incognito mode
4. **Test token generation** - should be < 10 seconds old
5. **Test MCP tools** - should work without 401

---

**The backend is ready and waiting. The frontend just needs to use the correct secret!** 🎯














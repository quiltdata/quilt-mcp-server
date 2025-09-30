# Frontend Team: JWT Integration Bug Fixes

## ✅ Configuration Status

Your JWT configuration is **CORRECT** and matches the MCP server:
- `MCP_ENHANCED_JWT_KID`: `frontend-enhanced` ✅
- `MCP_ENHANCED_JWT_SECRET`: `quilt-sales-prod-mcp-jwt-secret-2025-enhanced-tokens-v2` ✅

The MCP server is deployed and healthy. The test failures are due to **code bugs** that need fixing.

---

## 🐛 Bug #1: CRITICAL - Bucket Format Error

**Test Failure:**
```
❌ Get Current Buckets
Test failed: Cannot use 'in' operator to search for 'name' in cellpainting-gallery
```

### The Problem
Somewhere in your code, you're checking `'name' in bucket` where `bucket` is a **string** (`"cellpainting-gallery"`), not an object.

### Where to Look
Run this command in your `catalog/app/services/` directory:
```bash
grep -rn "'name' in" .
grep -rn '"name" in' .
```

### The Fix
**Find this pattern:**
```javascript
buckets.forEach((bucket) => {
  if ('name' in bucket) {           // ❌ CRASHES when bucket is a string
    bucketName = bucket.name
  }
})
```

**Replace with:**
```javascript
buckets.forEach((bucket) => {
  const bucketName = typeof bucket === 'string' ? bucket : bucket?.name  // ✅ SAFE
  if (bucketName) {
    // ... rest of your code
  }
})
```

**OR** use the helper function you already have:
```javascript
// You already have this in DynamicAuthManager.js - USE IT!
const extractBucketNames = (buckets) => {
  if (!Array.isArray(buckets)) return []
  return buckets
    .map((bucket) => {
      if (typeof bucket === 'string') return bucket.trim()
      if (bucket && typeof bucket.name === 'string') return bucket.name.trim()
      return null
    })
    .filter((name) => typeof name === 'string' && name.length > 0)
}

// Then always normalize buckets before processing:
const bucketNames = extractBucketNames(freshBuckets)
```

---

## 🐛 Bug #2: Token Not Being Enhanced

**Test Failure:**
```
❌ Enhanced Token Generator
Test failed: Enhanced token is identical to original token
```

### The Problem
Even though your config is correct, the `EnhancedTokenGenerator` isn't receiving it during initialization.

### Where to Check
1. Open browser DevTools console
2. Look for this warning:
   ```
   ⚠️ EnhancedTokenGenerator: Missing signing secret, returning original token
   ```

### Verify Configuration Access

In `EnhancedTokenGenerator.js`, check that the constructor can access the config:

```javascript
constructor({ signingSecret, signingKeyId, mcpServerUrl }) {
  console.log('🔍 EnhancedTokenGenerator constructor called with:', {
    hasSigningSecret: !!signingSecret,
    hasSigningKeyId: !!signingKeyId,
    envSecret: process.env.MCP_ENHANCED_JWT_SECRET,
    configSecret: quiltConfig?.mcp?.enhancedJwt?.signingSecret
  })

  this.signingSecret = 
    signingSecret || 
    process.env.MCP_ENHANCED_JWT_SECRET ||
    (typeof quiltConfig !== 'undefined' && quiltConfig?.mcp?.enhancedJwt?.signingSecret)
  
  this.signingKeyId = 
    signingKeyId || 
    'frontend-enhanced'
  
  if (!this.signingSecret) {
    console.error('❌ EnhancedTokenGenerator: Missing signing secret!')
  } else {
    console.log('✅ EnhancedTokenGenerator: Signing secret configured')
  }
}
```

### How EnhancedTokenGenerator is Initialized

Check where you create the instance - it should receive the config:

```javascript
// In DynamicAuthManager.js or wherever you initialize it
const enhancedTokenGenerator = new EnhancedTokenGenerator({
  signingSecret: quiltConfig?.mcp?.enhancedJwt?.signingSecret,  // Must pass this!
  signingKeyId: quiltConfig?.mcp?.enhancedJwt?.keyId || 'frontend-enhanced',
  mcpServerUrl: quiltConfig?.mcp?.serverUrl
})
```

---

## 🐛 Bug #3: Bucket Discovery Issues

**Test Failures:**
```
❌ Permission Validation
Test failed: quilt-sandbox-bucket not found in discovered buckets

❌ Bucket Discovery Validation
Test failed: Expected buckets not found in discovery
```

### The Problem
The buckets aren't being discovered or returned correctly.

### Debug in Browser Console

Run these commands:
```javascript
// 1. Check what getCurrentBuckets returns
const manager = window.__dynamicAuthManager
const buckets = await manager.getCurrentBuckets()
console.log('Discovered buckets:', buckets)
console.log('Bucket count:', buckets.length)
console.log('Has quilt-sandbox-bucket:', buckets.includes('quilt-sandbox-bucket'))

// 2. Check the GraphQL response
const query = `query { bucketConfigs { name title } }`
const response = await fetch('https://demo.quiltdata.com/graphql', {
  method: 'POST',
  headers: { 
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${await manager.getOriginalToken()}`
  },
  body: JSON.stringify({ query })
})
const data = await response.json()
console.log('GraphQL buckets:', data.data?.bucketConfigs)

// 3. Check AWSBucketDiscoveryService
const awsService = manager.awsBucketDiscovery || new AWSBucketDiscoveryService()
const roleBuckets = awsService.getBucketsForRole('ReadWriteQuiltV2-sales-prod')
console.log('Role mapping buckets:', roleBuckets)
```

### Expected Results
```javascript
Discovered buckets: ["cellpainting-gallery", "quilt-sandbox-bucket", ...] // 32 buckets
Bucket count: 32
Has quilt-sandbox-bucket: true
GraphQL buckets: [{name: "cellpainting-gallery", ...}, ...] // 32+ buckets
Role mapping buckets: ["cellpainting-gallery", "quilt-sandbox-bucket", ...] // 32 buckets
```

### If GraphQL Returns Objects
The GraphQL endpoint returns:
```javascript
[
  { name: "cellpainting-gallery", title: "Cell Painting Gallery" },
  { name: "quilt-sandbox-bucket", title: "Quilt Sandbox" },
  ...
]
```

Make sure to extract just the names:
```javascript
const bucketNames = graphqlBuckets.map(b => b.name)
```

---

## 🔧 Immediate Action Items

### Priority 1: Fix the `'name' in bucket` Error
This is **CRASHING** your tests. Find and fix it immediately:

```bash
cd catalog/app/services
grep -n "'name' in" *.js
```

Look for the exact line and replace with the safe pattern.

### Priority 2: Add Debug Logging
Add this to `DynamicAuthManager.js` in `getCurrentBuckets()`:

```javascript
async getCurrentBuckets() {
  try {
    if (!this.isInitialized) await this.initialize()
    
    const originalToken = await this.getOriginalToken()
    if (!originalToken) {
      console.warn('❌ getCurrentBuckets: No original token available')
      return []
    }
    
    const userRoles = this.getUserRolesFromState()
    console.log('🔍 getCurrentBuckets: User roles:', userRoles)
    
    const freshBuckets = await this.awsBucketDiscovery.getAccessibleBuckets({
      token: originalToken,
      roles: userRoles,
    })
    console.log('🔍 getCurrentBuckets: Fresh buckets type:', typeof freshBuckets[0])
    console.log('🔍 getCurrentBuckets: First bucket:', freshBuckets[0])
    
    const bucketNames = extractBucketNames(freshBuckets)
    console.log('✅ getCurrentBuckets: Extracted bucket names:', bucketNames.length)
    
    this.currentBuckets = bucketNames
    return bucketNames
  } catch (error) {
    console.error('❌ Error getting current buckets:', error)
    return []
  }
}
```

### Priority 3: Verify Token Enhancement
Add this to `EnhancedTokenGenerator.js` in `generateEnhancedToken()`:

```javascript
async generateEnhancedToken({ originalToken, roles = [], buckets = [] }) {
  console.log('🔍 generateEnhancedToken called:', {
    hasOriginalToken: !!originalToken,
    hasSigningSecret: !!this.signingSecret,
    signingSecretLength: this.signingSecret?.length,
    rolesCount: roles.length,
    bucketsCount: buckets.length
  })
  
  if (!this.signingSecret) {
    console.error('❌ Cannot enhance token: Missing signing secret!')
    console.error('❌ Check: process.env.MCP_ENHANCED_JWT_SECRET')
    console.error('❌ Check: quiltConfig?.mcp?.enhancedJwt?.signingSecret')
    return originalToken  // This is why token isn't enhanced!
  }
  
  // ... rest of enhancement logic
}
```

---

## 🧪 Test Commands After Fixes

Run these in **browser console** after applying fixes:

```javascript
// Test 1: Verify token enhancement works
const manager = window.__dynamicAuthManager
const token = await manager.getOriginalToken()
const enhanced = await manager.tokenGenerator.generateEnhancedToken({
  originalToken: token,
  roles: manager.getUserRolesFromState(),
  buckets: await manager.getCurrentBuckets()
})

const origPayload = JSON.parse(atob(token.split('.')[1]))
const enhPayload = JSON.parse(atob(enhanced.split('.')[1]))

console.log('🔍 Token Comparison:', {
  original_has_buckets: !!origPayload.buckets,
  enhanced_has_buckets: !!enhPayload.buckets,
  enhanced_has_compressed_buckets: !!enhPayload.b,
  enhanced_has_permissions: !!enhPayload.permissions,
  enhanced_has_compressed_perms: !!enhPayload.p,
  tokens_are_different: token !== enhanced
})

// Test 2: Verify bucket discovery
const buckets = await manager.getCurrentBuckets()
console.log('🔍 Bucket Discovery:', {
  count: buckets.length,
  first_bucket_type: typeof buckets[0],
  has_sandbox: buckets.includes('quilt-sandbox-bucket'),
  sample_buckets: buckets.slice(0, 5)
})
```

**Expected output:**
```javascript
{
  original_has_buckets: false,  // Original token doesn't have buckets
  enhanced_has_buckets: true,   // Enhanced token DOES have buckets
  enhanced_has_compressed_buckets: true,  // Has 'b' field
  enhanced_has_permissions: true,
  enhanced_has_compressed_perms: true,  // Has 'p' field
  tokens_are_different: true    // Tokens should be DIFFERENT!
}

{
  count: 32,
  first_bucket_type: "string",  // Should be string, not object!
  has_sandbox: true,
  sample_buckets: ["cellpainting-gallery", "quilt-sandbox-bucket", ...]
}
```

---

## 📋 Action Plan

1. **Fix `'name' in bucket` error** (5 min)
   - Search for the pattern
   - Replace with safe type checking
   
2. **Add debug logging** (10 min)
   - Add to getCurrentBuckets
   - Add to generateEnhancedToken
   
3. **Test in browser** (5 min)
   - Run the test commands above
   - Share the output with me

4. **Re-run your test suite** (2 min)
   - All tests should pass after fixing Bug #1

---

## 🆘 If Still Failing

Share these outputs from browser console:

```javascript
// Command 1: Check signing secret
console.log('Config check:', {
  envSecret: process.env.MCP_ENHANCED_JWT_SECRET,
  configSecret: quiltConfig?.mcp?.enhancedJwt?.signingSecret,
  hasQuiltConfig: typeof quiltConfig !== 'undefined'
})

// Command 2: Check bucket format
const manager = window.__dynamicAuthManager
const buckets = await manager.getCurrentBuckets()
console.log('Bucket format check:', {
  bucketsArray: Array.isArray(buckets),
  firstBucketType: typeof buckets[0],
  firstBucket: buckets[0],
  allBuckets: buckets
})

// Command 3: Check token enhancement
const tokenGen = manager.tokenGenerator
console.log('TokenGen check:', {
  hasSigningSecret: !!tokenGen.signingSecret,
  secretLength: tokenGen.signingSecret?.length,
  kidValue: tokenGen.signingKeyId
})
```

Send me the output and I'll provide the exact fix! 🚀

---

## 📊 Summary

**MCP Server:** ✅ Deployed, healthy, configured correctly  
**JWT Config:** ✅ Matches between frontend and MCP server  
**Root Cause:** Frontend code bugs (not configuration)  
**Priority:** Fix `'name' in bucket` error first (it's crashing tests)  
**ETA:** 15-20 minutes to fix all issues

Ready to debug when you send the console output! 🎯

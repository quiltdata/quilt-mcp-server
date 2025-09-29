# Frontend JWT Integration Fixes

## Issues Detected from Test Results

The MCP server is now deployed with enhanced JWT support (version `0.6.13-jwt-auth-20250929-184230`), but there are three integration issues to fix on the frontend.

---

## Issue 1: Bucket Format Error ❌

**Test Failed:**
```
Get Current Buckets
Test failed: Cannot use 'in' operator to search for 'name' in cellpainting-gallery
```

### Root Cause
Code is checking `'name' in bucket` where `bucket` is a string, not an object.

### Fix Required
Find the code that uses `'name' in bucket` (likely in `DynamicAuthManager.js` or `EnhancedTokenGenerator.js`) and replace it:

**Before:**
```javascript
buckets.forEach((bucket) => {
  if ('name' in bucket) {  // ❌ This fails when bucket is a string
    bucketName = bucket.name
  }
})
```

**After:**
```javascript
buckets.forEach((bucket) => {
  // ✅ Handle both string and object formats
  const bucketName = typeof bucket === 'string' ? bucket : bucket?.name
  if (bucketName) {
    // ... use bucketName
  }
})
```

**Or use the existing helper:**
```javascript
// The normalizeBucketNames function already handles this correctly:
const normalizeBucketNames = (buckets) => {
  if (!Array.isArray(buckets)) return []
  const seen = new Set()
  const names = []
  buckets.forEach((bucket) => {
    let name = null
    if (typeof bucket === 'string') {
      name = bucket.trim()
    } else if (bucket && typeof bucket.name === 'string') {
      name = bucket.name.trim()
    }
    if (name && !seen.has(name)) {
      seen.add(name)
      names.push(name)
    }
  })
  return names
}

// Use it wherever you process buckets:
const bucketNames = normalizeBucketNames(buckets)
```

**Search Command:**
```bash
# Find the problematic line in catalog/app/services/
grep -n "'name' in" catalog/app/services/*.js
# or
grep -n '"name" in' catalog/app/services/*.js
```

---

## Issue 2: Token Not Being Enhanced ❌

**Test Failed:**
```
Enhanced Token Generator
Test failed: Enhanced token is identical to original token
```

### Root Cause
`EnhancedTokenGenerator` is missing the JWT signing secret configuration.

### Fix Required

**Step 1: Check Current Configuration**
Look for console warnings in browser DevTools:
```
⚠️ EnhancedTokenGenerator: Missing signing secret, returning original token
```

**Step 2: Add Configuration**

Update `catalog/config.json.tmpl` or the appropriate config file:

```javascript
{
  "mcp": {
    "enhancedJwt": {
      "signingSecret": "${MCP_ENHANCED_JWT_SECRET}",
      "keyId": "frontend-enhanced"
    }
  }
}
```

**Step 3: Set Environment Variable**

For the frontend deployment, ensure this environment variable is set:

```bash
# Should match the MCP server's secret
MCP_ENHANCED_JWT_SECRET=<your-secret-here>
```

**Step 4: Verify in Code**

In `EnhancedTokenGenerator.js`, ensure initialization uses the config:

```javascript
constructor({ signingSecret, signingKeyId }) {
  this.signingSecret = signingSecret || 
                       process.env.MCP_ENHANCED_JWT_SECRET ||
                       (typeof quiltConfig !== 'undefined' && 
                        quiltConfig?.mcp?.enhancedJwt?.signingSecret)
  this.signingKeyId = signingKeyId || 'frontend-enhanced'
  
  if (!this.signingSecret) {
    console.warn('⚠️ EnhancedTokenGenerator: Missing signing secret')
  }
}
```

---

## Issue 3: Bucket Discovery Validation ❌

**Test Failed:**
```
Permission Validation
Test failed: quilt-sandbox-bucket not found in discovered buckets
```

### Root Cause
The bucket names in the role mapping don't match what the MCP server returns, OR the MCP server isn't being called correctly.

### Fix Required

**Step 1: Verify Role-to-Bucket Mapping**

In `AWSBucketDiscoveryService.js`, ensure the role mapping includes all expected buckets:

```javascript
getBucketsForRole(roleName) {
  const roleBucketMap = {
    'ReadWriteQuiltV2-sales-prod': [
      'quilt-sandbox-bucket',       // ✅ Must be exact match
      'cellpainting-gallery',       // ✅ Must be exact match
      'quilt-sales-raw',
      'quilt-sales-staging',
      'quilt-demos',
      // ... add all 32 buckets for this role
    ],
    'ReadQuiltV2-sales-prod': [
      'quilt-sandbox-bucket',
      'quilt-sales-raw',
      'quilt-sales-staging',
    ],
  }
  
  return roleBucketMap[roleName] || []
}
```

**Step 2: Verify MCP Server Returns Buckets**

Test the MCP server endpoint directly:

```javascript
// In browser console
const response = await fetch('https://demo.quiltdata.com/mcp/tools/list_available_resources', {
  headers: {
    'Authorization': `Bearer ${await quiltConfig.mcpClient.getToken()}`
  }
})
const data = await response.json()
console.log('MCP returned buckets:', data.writable_buckets)
console.log('MCP returned readable:', data.readable_buckets)
```

**Step 3: Check extractBucketNames Usage**

Ensure the `extractBucketNames` function is used consistently:

```javascript
// Already defined in DynamicAuthManager.js
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

// Use it whenever processing bucket arrays from MCP server:
const freshBuckets = await this.awsBucketDiscovery.getAccessibleBuckets({...})
const bucketNames = extractBucketNames(freshBuckets)  // ✅ Always use this
```

---

## Verification Steps

After applying the fixes, run these tests:

### Test 1: Check Token Enhancement
```javascript
// In browser console
const manager = window.__dynamicAuthManager
const token = await manager.getOriginalToken()
const payload = JSON.parse(atob(token.split('.')[1]))

console.log('Token has enhanced fields:', {
  hasCompressedBuckets: !!payload.b,
  hasExpandedBuckets: !!payload.buckets,
  hasCompressedPerms: !!payload.p,
  hasExpandedPerms: !!payload.permissions,
  bucketCount: (payload.buckets || []).length,
  permCount: (payload.permissions || []).length
})
```

Expected output:
```javascript
{
  hasCompressedBuckets: true,
  hasExpandedBuckets: true,
  hasCompressedPerms: true,
  hasExpandedPerms: true,
  bucketCount: 32,  // or however many buckets the user has
  permCount: 8      // or however many permissions
}
```

### Test 2: Check Bucket Discovery
```javascript
// In browser console
const buckets = await manager.getCurrentBuckets()
console.log('Bucket count:', buckets.length)
console.log('Has quilt-sandbox-bucket:', buckets.includes('quilt-sandbox-bucket'))
console.log('First 5 buckets:', buckets.slice(0, 5))
```

Expected output:
```javascript
Bucket count: 32
Has quilt-sandbox-bucket: true
First 5 buckets: ['cellpainting-gallery', 'quilt-sandbox-bucket', ...]
```

### Test 3: MCP Integration Test
Run the frontend's MCP integration tests again:
```
✅ Get Current Buckets - Should pass
✅ Enhanced Token Generator - Should pass  
✅ Permission Validation - Should pass
```

---

## Configuration Checklist

Ensure these are set in the **frontend deployment**:

- [ ] `MCP_ENHANCED_JWT_SECRET` environment variable (must match MCP server)
- [ ] `MCP_ENHANCED_JWT_KID=frontend-enhanced`
- [ ] MCP server URL: `https://demo.quiltdata.com/mcp`
- [ ] Bucket names in `AWSBucketDiscoveryService` match exactly

Ensure these are set in the **MCP server deployment** (already done ✅):

- [x] `MCP_ENHANCED_JWT_SECRET` - configured
- [x] `MCP_ENHANCED_JWT_KID=frontend-enhanced` - configured
- [x] Container deployed and healthy
- [x] JWT decoder with compression support

---

## Quick Wins

### Immediate Fix #1: Handle Both Bucket Formats
Add this helper at the top of any file processing buckets:

```javascript
const ensureBucketString = (bucket) => {
  return typeof bucket === 'string' ? bucket : bucket?.name || ''
}

// Then use it everywhere:
buckets.map(ensureBucketString).filter(Boolean)
```

### Immediate Fix #2: Add Defensive Checks
```javascript
// Before checking 'name' in bucket:
if (bucket && typeof bucket === 'object' && 'name' in bucket) {
  // Use bucket.name
} else if (typeof bucket === 'string') {
  // Use bucket directly
}
```

---

## Testing the MCP Server

I've created a diagnostic script. You can run it to verify the MCP server is working:

```bash
# Get a JWT token from the frontend (from browser console):
# const token = await quiltConfig.mcpClient.getToken()
# console.log(token)

# Then test the MCP server:
QUILT_ACCESS_TOKEN=<paste-token-here> \
MCP_SERVER_URL=https://demo.quiltdata.com/mcp \
python scripts/test_mcp_endpoints.py
```

---

## Questions to Answer

To help further debug, please provide:

1. **Where exactly does the `'name' in bucket` error occur?**
   - File name and line number
   - Function name
   - Stack trace if available

2. **What does the browser console show for EnhancedTokenGenerator?**
   - Any warnings about missing signing secret?
   - Token enhancement logs?

3. **What buckets does the frontend think the user has access to?**
   ```javascript
   // Run in browser console:
   const buckets = await window.__dynamicAuthManager.getCurrentBuckets()
   console.log(buckets)
   ```

4. **Does the JWT payload include buckets?**
   ```javascript
   // Run in browser console:
   const token = await quiltConfig.mcpClient.getToken()
   const payload = JSON.parse(atob(token.split('.')[1]))
   console.log('Buckets in JWT:', payload.buckets || payload.b)
   ```

---

## MCP Server Status

✅ **Container deployed successfully:**
- Version: `0.6.13-jwt-auth-20250929-184230`
- Health: HEALTHY
- Task: revision 69
- Endpoint: `https://demo.quiltdata.com/mcp`

The MCP server is ready and waiting for properly formatted requests!

Send me the answers to the questions above and I'll provide specific code fixes for the frontend. 🚀

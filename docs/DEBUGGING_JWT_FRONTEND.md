# Debugging JWT Frontend Integration Issues

This guide helps diagnose and fix JWT authentication issues between the Quilt frontend and MCP server.

## Current Issues (from Test Results)

### 1. Bucket Format Error
**Error:**
```
❌ Get Current Buckets
Test failed: Cannot use 'in' operator to search for 'name' in cellpainting-gallery
```

**Diagnosis:**
- The error occurs when code tries `'name' in bucket` where `bucket` is a string
- Frontend's `AWSBucketDiscoveryService.discoverBucketsFromRoles()` returns strings: `["bucket-name"]`
- MCP server's `list_available_resources` returns objects: `[{name: "bucket-name", permission_level: "..."}]`
- The `extractBucketNames()` function handles both formats, but somewhere else code expects objects

**Fix Options:**

**Option A - Update Frontend Code:**
Check where the frontend code is using `'name' in bucket` and change it to handle both formats:
```javascript
// Instead of:
if ('name' in bucket) {  // This fails on strings
  bucketName = bucket.name
}

// Use:
const bucketName = typeof bucket === 'string' ? bucket : bucket.name
```

**Option B - Standardize MCP Response:**
Update the MCP server to always return just bucket name strings when the frontend expects them.

### 2. Token Not Enhanced
**Error:**
```
❌ Enhanced Token Generator
Test failed: Enhanced token is identical to original token
```

**Diagnosis:**
The `EnhancedTokenGenerator` requires configuration to enhance tokens.

**Fix:**
Check frontend configuration for:

```javascript
// In catalog/config.json or environment
{
  "mcp": {
    "enhancedJwt": {
      "signingSecret": "your-jwt-secret-here",  // Must match MCP server
      "keyId": "frontend-enhanced"               // Must match MCP server
    }
  }
}
```

**Verification:**
1. Check browser console for: `⚠️ EnhancedTokenGenerator: Missing signing secret`
2. Verify environment variables:
   - `MCP_ENHANCED_JWT_SECRET` - should be set
   - `MCP_ENHANCED_JWT_KID` - should be "frontend-enhanced"

### 3. Bucket Discovery Validation Fails
**Error:**
```
❌ Permission Validation
Test failed: quilt-sandbox-bucket not found in discovered buckets
```

**Diagnosis:**
The MCP server isn't returning expected buckets, OR the bucket names don't match.

**Common Causes:**
1. JWT doesn't include bucket in claims
2. Bucket discovery returns different names (e.g., with/without prefixes)
3. Role mapping incomplete

**Fix:**
1. Check JWT payload includes buckets:
```javascript
// Decode the JWT and check:
const payload = JSON.parse(atob(token.split('.')[1]))
console.log('Buckets in JWT:', payload.buckets || payload.b)
```

2. Verify role-to-bucket mapping in frontend:
```javascript
// In AWSBucketDiscoveryService.js
const roleBucketMap = {
  'ReadWriteQuiltV2-sales-prod': [
    'quilt-sandbox-bucket',  // Must match MCP server bucket names
    'cellpainting-gallery',
    // ... etc
  ]
}
```

3. Check MCP server logs for bucket discovery:
```bash
aws logs tail /ecs/mcp-server-production --since 10m --region us-east-1 | grep bucket
```

## Debugging Workflow

### Step 1: Verify MCP Server is Responding

```bash
# Test health endpoint
curl https://demo.quiltdata.com/mcp/healthz

# Expected: {"status": "ok", ...}
```

### Step 2: Check JWT Token Structure

```javascript
// In browser console
const token = await quiltConfig.mcpClient.getToken()
const payload = JSON.parse(atob(token.split('.')[1]))

console.log('JWT Claims:', {
  buckets: payload.buckets || payload.b,
  permissions: payload.permissions || payload.p,
  roles: payload.roles || payload.r,
  exp: new Date(payload.exp * 1000),
  iss: payload.iss,
  aud: payload.aud
})
```

### Step 3: Test Bucket Discovery Directly

```javascript
// In browser console on Quilt frontend
const manager = window.__dynamicAuthManager
if (manager) {
  const buckets = await manager.getCurrentBuckets()
  console.log('Discovered buckets:', buckets)
}
```

### Step 4: Verify Enhanced Token Generation

```javascript
// In browser console
const tokenGen = window.__enhancedTokenGenerator
if (tokenGen) {
  const originalToken = await tokenGen.getOriginalToken()
  const enhanced = await tokenGen.generateEnhancedToken({
    originalToken,
    roles: ['ReadWriteQuiltV2-sales-prod'],
    buckets: ['quilt-sandbox-bucket']
  })
  
  // Decode both tokens and compare
  const origPayload = JSON.parse(atob(originalToken.split('.')[1]))
  const enhPayload = JSON.parse(atob(enhanced.split('.')[1]))
  
  console.log('Original buckets:', origPayload.buckets)
  console.log('Enhanced buckets:', enhPayload.buckets || enhPayload.b)
  console.log('Tokens match?', originalToken === enhanced)
}
```

### Step 5: Check MCP Server Environment

```bash
# Get the task definition
aws ecs describe-task-definition \
  --task-definition quilt-mcp-server \
  --region us-east-1 \
  --query 'taskDefinition.containerDefinitions[0].environment' \
  | grep -E "JWT_SECRET|JWT_KID|MCP_ENHANCED"

# Expected:
# MCP_ENHANCED_JWT_SECRET: <secret-value>
# MCP_ENHANCED_JWT_KID: frontend-enhanced
```

## Common Fixes

### Fix 1: Bucket Format Mismatch

**Update MCP server to return simple bucket lists:**

```python
# In src/quilt_mcp/tools/unified_package.py
def list_available_resources() -> Dict[str, Any]:
    # ... existing code ...
    
    # Change from:
    writable_buckets.append({
        "name": bucket_info["name"],
        "permission_level": bucket_info["permission_level"],
        ...
    })
    
    # To:
    writable_buckets.append(bucket_info["name"])
```

### Fix 2: Enable Token Enhancement

**Frontend configuration:**

```javascript
// In catalog/app/services/EnhancedTokenGenerator.js initialization
const enhancedTokenGenerator = new EnhancedTokenGenerator({
  signingSecret: process.env.MCP_ENHANCED_JWT_SECRET || 
                 config.mcp?.enhancedJwt?.signingSecret,
  signingKeyId: 'frontend-enhanced'
})
```

### Fix 3: Standardize Bucket Names

**Ensure consistency:**

1. Frontend role mapping uses exact bucket names
2. MCP server returns exact bucket names (no prefixes/suffixes)
3. JWT payload includes exact bucket names

**Check bucket name consistency:**
```bash
# In frontend code
console.log('Frontend bucket names:', 
  AWSBucketDiscoveryService.getBucketsForRole('ReadWriteQuiltV2-sales-prod'))

# In MCP server logs
# Should match exactly
```

## Test Suite Fixes

### Update Frontend Tests

```javascript
// In catalog/app/services/__tests__/DynamicAuthManager.test.js

describe('Get Current Buckets', () => {
  it('should handle both string and object bucket formats', async () => {
    const buckets = await manager.getCurrentBuckets()
    
    // Accept both formats
    buckets.forEach(bucket => {
      const name = typeof bucket === 'string' ? bucket : bucket.name
      expect(typeof name).toBe('string')
      expect(name.length).toBeGreaterThan(0)
    })
  })
})
```

## Next Steps

1. **Run diagnostic script:**
   ```bash
   cd quilt-mcp-server
   QUILT_ACCESS_TOKEN=<your-token> python scripts/test_mcp_endpoints.py
   ```

2. **Check CloudWatch logs:**
   ```bash
   aws logs tail /ecs/mcp-server-production --follow --region us-east-1
   ```

3. **Test in browser console:**
   - Open Quilt frontend
   - Open browser DevTools
   - Run Step 2-4 from Debugging Workflow above

4. **Compare JWT payloads:**
   - Get token from frontend
   - Decode and check bucket format
   - Verify it matches what MCP server expects

## Environment Checklist

### Frontend (catalog)
- [ ] `MCP_ENHANCED_JWT_SECRET` is set
- [ ] `MCP_ENHANCED_JWT_KID` is "frontend-enhanced"
- [ ] MCP server URL is correct in config
- [ ] Bucket names in role mapping match MCP server

### MCP Server (ECS)
- [ ] `MCP_ENHANCED_JWT_SECRET` matches frontend
- [ ] `MCP_ENHANCED_JWT_KID` is "frontend-enhanced"
- [ ] Service is healthy and responding
- [ ] JWT decoder handles compressed claims

### AWS/Permissions
- [ ] ECS task role can access buckets
- [ ] Security groups allow frontend → MCP traffic
- [ ] Load balancer health checks passing

## Additional Resources

- [JWT_AUTHENTICATION.md](./developer/JWT_AUTHENTICATION.md) - JWT implementation guide
- [MCP Server Logs](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group//ecs/mcp-server-production)
- [ECS Service](https://console.aws.amazon.com/ecs/v2/clusters/sales-prod/services/sales-prod-mcp-server-production/)

## Contact

If issues persist, provide:
1. JWT payload (sanitized)
2. CloudWatch logs from last 5 minutes
3. Browser console errors
4. Test results from diagnostic script

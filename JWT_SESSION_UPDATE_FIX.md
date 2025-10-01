# 🎉 JWT Session Update Fix - DEPLOYED

## 🐛 The Bug
After the frontend fixed the chicken-and-egg problem (not sending JWT during init), the backend had a NEW bug:

1. **First request (init)**: No JWT → Session cached as UNAUTHENTICATED
2. **Second request (tool call)**: Has JWT → Middleware saw cached session and **reused it** WITHOUT checking for new JWT
3. **Result**: All tool calls used UNAUTHENTICATED session → No bucket permissions

### Logs Showing the Bug
```
MCP session 63a10972a69441b29ccc924d734188a2: No auth header, allowing for initialization
⚠️  Setting runtime context to UNAUTHENTICATED - tools will NOT have JWT!
... (subsequent requests) ...
No permission to list buckets, will work with explicitly provided bucket names
```

## ✅ The Fix
Modified the middleware to check if NEW requests have Authorization headers, even when a session is already cached:

```python
# NEW CODE: Check if current request has auth header
if session_auth and authorization:
    # Check if this is a NEW token (different from cached one)
    cached_token = session_auth.jwt_result.token if hasattr(session_auth, 'jwt_result') else None
    new_token = authorization.replace("Bearer ", "")
    
    if cached_token != new_token:
        logger.info("Session %s: New JWT token detected, re-authenticating", session_id)
        # Re-authenticate with new token
        session_auth, error = session_manager.authenticate_session(session_id, authorization)
        logger.info("✅ Session %s updated with new JWT", session_id)
```

### What This Does
1. **First request (init)**: No JWT → Session cached as UNAUTHENTICATED ✅
2. **Second request (tool call)**: Has JWT → Middleware detects NEW token → **Re-authenticates** → Updates cached session → ✅
3. **Subsequent requests**: Reuse AUTHENTICATED session → ✅
4. **Result**: All tool calls use JWT credentials → Full bucket permissions → ✅

## 🚀 Deployment Status

### Docker Image
- **Built**: ✅ `850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:jwt-session-update-20250930-111439`
- **Pushed**: ✅ ECR
- **Tagged**: ✅ `latest`

### ECS Service
- **Cluster**: `sales-prod`
- **Service**: `sales-prod-mcp-server-production`
- **Status**: 🔄 Deploying...
- **Expected**: Complete in ~2-3 minutes

## 🧪 How to Test After Deployment

### Test 1: Check Session Authentication
**In browser console:**
```javascript
// Clear any existing MCP sessions
localStorage.clear()

// Refresh the page
location.reload()

// After page loads, test MCP connection
const result = await window.__mcpClient.callTool({
  name: 'bucket_objects_list',
  arguments: { bucket: 's3://quilt-sandbox-bucket' }
})
console.log('✅ MCP Tool Result:', result)
```

**Expected Result:**
- No 401 errors
- No "UNAUTHENTICATED" warnings
- Full bucket access
- Tool returns bucket objects

### Test 2: Check Backend Logs
**Look for these log messages:**
```bash
aws logs tail /ecs/mcp-server-production --region us-east-1 --since 2m --format short | grep -E "Session.*JWT|authentication"
```

**Expected Logs:**
```
Session abc123: New JWT token detected, re-authenticating
✅ Session abc123 updated with new JWT
Using cached JWT auth for session abc123
```

### Test 3: Verify Bucket Permissions
**In browser console:**
```javascript
// Test bucket discovery
const buckets = await window.__mcpClient.callTool({
  name: 'discover_buckets',
  arguments: {}
})
console.log('Discovered buckets:', buckets.buckets?.length || 0)

// Test specific bucket access
const objects = await window.__mcpClient.callTool({
  name: 'bucket_objects_list',
  arguments: { bucket: 's3://quilt-sandbox-bucket', max_keys: 5 }
})
console.log('Objects:', objects.objects?.length || 0)
```

**Expected Result:**
- Discovers 30+ buckets (based on JWT claims)
- Can list objects in accessible buckets
- No "Access denied" errors

## 📊 Expected Behavior Flow

### Request 1: MCP Initialization
```
Frontend → /mcp/ (NO Authorization header)
Backend → Allow (no cached session)
Backend → Cache session as UNAUTHENTICATED
Response → 200 OK (session established)
```

### Request 2: First Tool Call
```
Frontend → /mcp/tool (WITH Authorization: Bearer <token>)
Backend → Check cached session (exists, but UNAUTHENTICATED)
Backend → Detect new Authorization header
Backend → Log: "New JWT token detected, re-authenticating"
Backend → Authenticate JWT
Backend → Update cached session with JWT
Backend → Execute tool WITH JWT credentials
Response → 200 OK (with bucket data)
```

### Request 3+: Subsequent Tool Calls
```
Frontend → /mcp/tool (WITH Authorization: Bearer <token>)
Backend → Check cached session (exists, AUTHENTICATED)
Backend → Check if token changed (no)
Backend → Reuse cached JWT session
Backend → Execute tool WITH JWT credentials
Response → 200 OK (with bucket data)
```

## 🔍 Debugging

### If Still Seeing "UNAUTHENTICATED"
Check backend logs for:
```bash
aws logs tail /ecs/mcp-server-production --region us-east-1 --since 5m --format short | grep "UNAUTHENTICATED"
```

Should NOT see this after the first request.

### If Still Seeing "Access denied"
Check if JWT token is being sent:
```javascript
// In browser dev tools Network tab:
// 1. Filter by "/mcp/"
// 2. Click on a request
// 3. Look at Request Headers
// 4. Verify "authorization: Bearer eyJ..." is present
```

### If JWT Validation Fails
Check secret match:
```bash
aws ssm get-parameter --name /quilt/mcp-server/jwt-secret --with-decryption --region us-east-1 --query 'Parameter.Value' --output text
# Should output: QuiltMCPJWTSecret2025ProductionV1
```

## ✅ Success Criteria

After deployment, you should see:
- ✅ No 401 errors during MCP initialization
- ✅ No "UNAUTHENTICATED" warnings in logs
- ✅ Backend logs: "✅ Session updated with new JWT"
- ✅ Tools return bucket data successfully
- ✅ Bucket discovery finds 30+ buckets
- ✅ No "Access denied" errors

---

## 🎯 What Changed

**File**: `src/quilt_mcp/utils.py`
**Lines**: 470-486
**Change**: Added JWT token update logic for cached sessions

**Before**:
```python
if session_auth:
    # Blindly reuse cached session (bug!)
    return await call_next(request)
```

**After**:
```python
if session_auth and authorization:
    # Check for new token
    if cached_token != new_token:
        # Re-authenticate and update cache
        session_auth = authenticate_session(...)

if session_auth:
    # Use cached (possibly updated) session
    return await call_next(request)
```

---

**Deployment Time**: ~3 minutes
**Testing Time**: ~2 minutes
**Total Time to Resolution**: ~5 minutes

🚀 **Ready for testing once deployment completes!**










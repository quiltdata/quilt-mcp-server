# JWT DevTools Troubleshooting Guide

This guide explains how to use the JWT diagnostic tools in the Qurator DevTools section to troubleshoot authentication issues.

## 🛠️ Available Diagnostic Tools

The MCP server now includes three JWT diagnostic tools accessible through Qurator's DevTools:

### 1. `jwt_diagnostics`
Provides comprehensive JWT authentication state inspection.

**Usage:**
```
Ask Qurator: "Run jwt_diagnostics"
```

**Returns:**
- Runtime environment (web-jwt, desktop-stdio, etc.)
- Current auth state and scheme
- Session cache statistics
- Bearer service configuration
- JWT claims details (buckets, permissions, roles)
- Recommendations for fixing issues

### 2. `validate_jwt_token`
Validates a JWT token and shows detailed information.

**Usage:**
```
Ask Qurator: "Validate my JWT token"
# Or with a specific token:
Ask Qurator: "Run validate_jwt_token with token eyJhbGc..."
```

**Returns:**
- Token header (algorithm, kid)
- Unverified payload contents
- Validation result (pass/fail)
- Detailed error information if validation fails
- Configuration comparison (frontend vs backend)
- Specific recommendations for fixing mismatches

### 3. `session_diagnostics`
Inspects the session cache state.

**Usage:**
```
Ask Qurator: "Show session diagnostics"
# Or for a specific session:
Ask Qurator: "Run session_diagnostics with session_id <session-id>"
```

**Returns:**
- All active sessions
- Session creation and last-used timestamps
- Session age and idle time
- User information per session
- Buckets and permissions per session

---

## 🧪 Testing Workflow

### Test 1: Verify JWT Authentication is Working

**Ask Qurator:**
```
Run jwt_diagnostics
```

**Expected Output (✅ Working):**
```json
{
  "success": true,
  "diagnostics": {
    "runtime_environment": "web-jwt",
    "has_auth_state": true,
    "auth_scheme": "jwt",
    "jwt_details": {
      "user_id": "8795f0cc-8deb-40dd-9132-13357c983984",
      "username": "user@example.com",
      "buckets_count": 32,
      "permissions_count": 24,
      "roles": ["ReadWriteQuiltV2-sales-prod"]
    }
  },
  "summary": "Environment: web-jwt | Authentication: Active | Auth Scheme: jwt | User: user@example.com | Buckets: 32 | Permissions: 24"
}
```

**Problem Output (❌ IAM Fallback):**
```json
{
  "diagnostics": {
    "runtime_environment": "web-unauthenticated",
    "has_auth_state": false,
    "auth_scheme": null
  },
  "summary": "Environment: web-unauthenticated | Authentication: None"
}
```

### Test 2: Validate Token Signature

**Ask Qurator:**
```
Validate my JWT token
```

**Expected Output (✅ Valid):**
```json
{
  "success": true,
  "validation": "passed",
  "validated_claims": {
    "user_id": "...",
    "buckets": ["quilt-sandbox-bucket", ...],
    "permissions": ["s3:GetObject", ...]
  },
  "message": "JWT token is valid and can be used for authentication"
}
```

**Problem Output (❌ Invalid Secret):**
```json
{
  "success": false,
  "validation": "failed",
  "error": "Signature verification failed",
  "bearer_service_config": {
    "secret_configured": true,
    "secret_length": 31,
    "expected_kid": "frontend-enhanced",
    "token_kid": "frontend-enhanced",
    "kid_matches": true
  },
  "recommendations": [
    "Verify JWT secret matches between frontend and backend",
    "Check that token hasn't expired"
  ]
}
```

### Test 3: Check Session Cache

**Ask Qurator:**
```
Show session diagnostics
```

**Expected Output (✅ Cached):**
```json
{
  "success": true,
  "all_sessions": true,
  "stats": {
    "total_sessions": 1,
    "session_ids": ["2ae361e1d98f4d0a8decdc4fbaa509c7"],
    "session_timeout": 3600
  },
  "message": "Currently tracking 1 active sessions"
}
```

---

## 🔍 Common Issues and Solutions

### Issue 1: "IAM role" Instead of JWT

**Symptoms:**
- Qurator says "authenticated through an IAM role"
- `jwt_diagnostics` shows `has_auth_state: false`
- No buckets with write access visible

**Diagnosis:**
```
Run jwt_diagnostics
```

Look for:
- `runtime_environment`: Should be `"web-jwt"`, not `"web-unauthenticated"`
- `has_auth_state`: Should be `true`
- `auth_scheme`: Should be `"jwt"`

**Solution:**
1. Check that frontend is sending Authorization header
2. Verify JWT secret matches between frontend and backend
3. Check CloudWatch logs for authentication errors

### Issue 2: Signature Verification Failed

**Symptoms:**
- Error: "JWT token could not be verified"
- 401 Unauthorized responses

**Diagnosis:**
```
Validate my JWT token
```

Look for:
- `validation`: `"failed"`
- `secret_length`: Should be 55, not 31
- `kid_matches`: Should be `true`

**Solution:**
1. Verify frontend JWT secret:
   ```javascript
   // Browser console
   const tokenGen = window.__dynamicAuthManager?.tokenGenerator
   console.log('Secret:', tokenGen?.signingSecret)
   ```

2. Verify backend JWT secret:
   ```bash
   aws ecs describe-task-definition \
     --task-definition quilt-mcp-server \
     --region us-east-1 \
     --query 'taskDefinition.containerDefinitions[0].environment[?name==`MCP_ENHANCED_JWT_SECRET`]'
   ```

3. Ensure they match **exactly** (case-sensitive, no extra spaces)

### Issue 3: Session Not Cached

**Symptoms:**
- JWT validation happens on every request (slow)
- Logs show repeated "JWT authentication successful"

**Diagnosis:**
```
Show session diagnostics
```

Look for:
- `total_sessions`: Should be > 0 if you've used tools
- `session_ids`: Should show your current session

**Solution:**
1. Check that `mcp-session-id` header is being sent
2. Verify session manager is initialized
3. Check for session expiration

### Issue 4: No Buckets/Permissions in JWT

**Symptoms:**
- Qurator says "no buckets with write access"
- Tools fail with permission denied

**Diagnosis:**
```
Run jwt_diagnostics
```

Look at `jwt_details`:
- `buckets_count`: Should be > 0 (e.g., 32 for ReadWriteQuiltV2-sales-prod)
- `permissions_count`: Should be > 0 (e.g., 24 for write access)
- `roles`: Should show your role

**Solution:**
1. Check frontend token generation:
   ```javascript
   const token = await window.__dynamicAuthManager.getCurrentToken()
   const payload = JSON.parse(atob(token.split('.')[1]))
   console.log('Buckets:', payload.buckets)
   console.log('Permissions:', payload.permissions)
   ```

2. Verify `AWSBucketDiscoveryService` includes all expected buckets
3. Check role mappings in frontend code

---

## 📊 DevTools Integration

### Running Diagnostics Through Qurator

Once deployed, you can ask Qurator:

**Quick Health Check:**
```
Check my JWT authentication status
```
→ Runs `jwt_diagnostics`

**Validate Token:**
```
Validate my JWT token
```
→ Runs `validate_jwt_token`

**Check Sessions:**
```
How many MCP sessions are active?
```
→ Runs `session_diagnostics`

### Viewing Results

The diagnostic tools return structured JSON that Qurator will interpret and explain in natural language.

**Example Interaction:**
```
You: Check my JWT authentication status

Qurator: ✅ Your JWT authentication is working correctly! You're authenticated as 
user@example.com with access to 32 buckets and 24 AWS permissions through the 
ReadWriteQuiltV2-sales-prod role. Your session is cached and active.
```

---

## 🧪 Browser Console Testing

You can also test directly in the browser console:

### Get Current Token
```javascript
const token = await window.__dynamicAuthManager.getCurrentToken()
console.log('Token length:', token.length)
```

### Decode Token
```javascript
const payload = JSON.parse(atob(token.split('.')[1]))
console.log('JWT Payload:', {
  user: payload.sub,
  buckets: payload.buckets.length,
  permissions: payload.permissions.length,
  roles: payload.roles,
  expires: new Date(payload.exp * 1000)
})
```

### Test MCP Request with Token
```javascript
const response = await fetch('https://demo.quiltdata.com/mcp/tools/jwt_diagnostics', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    jsonrpc: '2.0',
    id: 'test-1',
    method: 'tools/call',
    params: {
      name: 'jwt_diagnostics',
      arguments: {}
    }
  })
})
const data = await response.json()
console.log('Diagnostics:', data)
```

---

## 📝 CloudWatch Logs to Watch

### Successful JWT Flow
```
INFO: MCP request: method=POST path=/mcp session=abc123 has_auth=True
INFO: Session abc123: JWT authenticated for user testuser (buckets=32, permissions=24)
INFO: Cached auth for session abc123
INFO: Using cached JWT auth for session abc123
INFO: Bucket tool bucket_objects_list: JWT auth check result: authorized=True
INFO: ✅ Using JWT-based S3 client for bucket_objects_list
```

### Failed JWT Flow
```
ERROR: Session abc123 authentication failed: JWT token could not be verified
ERROR: JWT validation failed: Signature verification failed (secret_length=31, kid=frontend-enhanced)
WARNING: JWT authorization failed for bucket_objects_list: JWT authentication required
```

---

## 🎯 Pre-Deployment Checklist

Before deploying JWT authentication changes:

- [ ] Run unit tests: `uv run pytest tests/unit/test_session_auth.py -v`
- [ ] Run JWT tests: `uv run pytest tests/unit/test_jwt_decompression.py -v`
- [ ] Verify JWT secret matches frontend (55 chars)
- [ ] Test token validation locally with `scripts/test_jwt_validation.py`
- [ ] Check task definition has correct secret
- [ ] Deploy with session auth enabled
- [ ] Test in DevTools after deployment
- [ ] Monitor CloudWatch logs for auth success messages

---

## 🚀 Deployment Validation

After deploying, validate in this order:

1. **Health Check:**
   ```bash
   curl https://demo.quiltdata.com/mcp/healthz
   ```

2. **Session Init (No Auth):**
   Browser should successfully establish MCP session

3. **JWT Diagnostics (With Auth):**
   Ask Qurator to "Check my JWT authentication status"

4. **Bucket Access (With Auth):**
   Ask Qurator to "List objects in quilt-sandbox-bucket"

5. **CloudWatch Logs:**
   Should show session caching and JWT success messages

---

## 📞 Troubleshooting Support

If you encounter issues:

1. **Run all three diagnostic tools** and save the output
2. **Check CloudWatch logs** for the last 5 minutes
3. **Get browser console output** from the fetch interceptor
4. **Provide:**
   - Diagnostic tool outputs
   - CloudWatch log excerpt
   - Browser console errors
   - Expected vs actual behavior

This information will help quickly identify and fix the issue.

---

## ✅ Success Criteria

JWT authentication is working correctly when:

- ✅ `jwt_diagnostics` shows `auth_scheme: "jwt"`
- ✅ `validate_jwt_token` shows `validation: "passed"`
- ✅ `session_diagnostics` shows cached sessions
- ✅ CloudWatch shows "Using cached JWT auth for session"
- ✅ Tools use JWT-derived S3 clients, not IAM role
- ✅ Qurator can access buckets listed in JWT claims

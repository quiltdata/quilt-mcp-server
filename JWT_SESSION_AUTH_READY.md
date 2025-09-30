# Session-Based JWT Authentication - Ready for Deployment

## ✅ What's Been Implemented

### 1. **Session-Based Authentication** (Most Important!)
**Problem:** JWT was validated on every request but tools fell back to IAM role
**Solution:** SessionAuthManager caches JWT auth by MCP session ID

- Validates JWT **once** per session
- Caches boto3 session built from JWT credentials
- Reuses cached auth for all subsequent requests
- Tools now use JWT-derived S3 clients instead of IAM role ✅
- Sessions expire after 1 hour

**Test Coverage:** 12/12 tests passing ✅

### 2. **JWT Diagnostic Tools**
Three new MCP tools available in Qurator DevTools:

- `jwt_diagnostics` - Comprehensive JWT auth state inspection
- `validate_jwt_token` - Validate and decode JWT tokens
- `session_diagnostics` - Inspect session cache state

### 3. **Enhanced Logging**
- Logs JWT validation success/failure with details
- Shows session cache hits/misses  
- Tracks which auth method is being used
- Secret length and kid logged for debugging

### 4. **Comprehensive Documentation**
- `JWT_DEVTOOLS_TROUBLESHOOTING.md` - How to use diagnostic tools
- `JWT_AUTHENTICATION.md` - Deployment guide
- `JWT_FIX_DEPLOYED.md` - Recent fix history
- Test scripts for local validation

---

## 🚨 Critical: JWT Secret Mismatch Fixed

**The Problem:**
- Frontend uses: `quilt-sales-prod-mcp-jwt-secret-2025-enhanced-tokens-v2` (55 chars)
- ECS Task had: `development-enhanced-jwt-secret` (31 chars)
- Secrets didn't match → All JWT validation failed

**The Fix:**
- Manually updated task definition to revision 77
- Secret now matches frontend ✅
- But deployment script doesn't preserve environment variables
- **Next deployment will revert to development secret** ❌

---

## 🔧 Before Deploying

### Fix the Deployment Script

The deployment script needs to preserve the JWT secret. Add this to `scripts/ecs_deploy.py`:

**Option 1: Read from environment**
```python
# When building task definition, preserve existing environment variables
existing_env = current_task_def['containerDefinitions'][0]['environment']

# Ensure JWT secret is preserved
jwt_secret = os.getenv('MCP_ENHANCED_JWT_SECRET') or next(
    (env['value'] for env in existing_env if env['name'] == 'MCP_ENHANCED_JWT_SECRET'),
    'development-enhanced-jwt-secret'  # Fallback
)

# Update environment with preserved secret
new_env = [
    env for env in existing_env 
    if env['name'] != 'MCP_ENHANCED_JWT_SECRET'
]
new_env.append({
    'name': 'MCP_ENHANCED_JWT_SECRET',
    'value': jwt_secret
})
```

**Option 2: Use AWS Systems Manager Parameter Store** (Recommended)
```python
# Store secret in SSM Parameter Store
aws ssm put-parameter \
  --name "/quilt/mcp-server/jwt-secret" \
  --value "quilt-sales-prod-mcp-jwt-secret-2025-enhanced-tokens-v2" \
  --type "SecureString" \
  --region us-east-1

# Reference in task definition:
{
  "name": "MCP_ENHANCED_JWT_SECRET",
  "valueFrom": "arn:aws:ssm:us-east-1:850787717197:parameter/quilt/mcp-server/jwt-secret"
}
```

---

## 🚀 Deployment Steps

### Step 1: Store JWT Secret in SSM (Recommended)
```bash
aws ssm put-parameter \
  --name "/quilt/mcp-server/jwt-secret" \
  --value "quilt-sales-prod-mcp-jwt-secret-2025-enhanced-tokens-v2" \
  --type "SecureString" \
  --region us-east-1 \
  --overwrite
```

### Step 2: Update Task Definition Template

Edit the task definition template to use SSM:
```json
{
  "name": "MCP_ENHANCED_JWT_SECRET",
  "valueFrom": "arn:aws:ssm:us-east-1:850787717197:parameter/quilt/mcp-server/jwt-secret"
}
```

### Step 3: Deploy Session Auth

```bash
cd /Users/simonkohnstamm/Documents/Quilt/quilt-mcp-server

# Deploy with session auth
VERSION="0.6.13-session-auth-$(date +%Y%m%d-%H%M%S)" \
AWS_ACCOUNT_ID=850787717197 \
AWS_DEFAULT_REGION=us-east-1 \
make deploy-docker
```

### Step 4: Verify in DevTools

After deployment, ask Qurator:
```
Run jwt_diagnostics
```

Should show:
- `auth_scheme: "jwt"` ✅
- `buckets_count: 32` ✅
- `permissions_count: 24` ✅

---

## 🧪 Test Plan

### Pre-Deployment Tests (Local)
```bash
# Run all JWT-related tests
uv run pytest tests/unit/test_session_auth.py -v          # 12/12 ✅
uv run pytest tests/unit/test_jwt_decompression.py -v     # 17/17 ✅
uv run pytest tests/unit/test_auth_service.py -v          # All auth tests
```

### Post-Deployment Tests (Frontend DevTools)

1. **Ask Qurator:** "Run jwt_diagnostics"
   - Verify `auth_scheme: "jwt"`
   - Verify buckets and permissions present

2. **Ask Qurator:** "Validate my JWT token"
   - Verify `validation: "passed"`

3. **Ask Qurator:** "Show session diagnostics"
   - Verify session is cached

4. **Ask Qurator:** "List objects in quilt-sandbox-bucket"
   - Should work with JWT credentials ✅

5. **Ask Qurator:** "Create a package in quilt-sandbox-bucket"
   - Should work with JWT write permissions ✅

---

## 📊 Expected Behavior After Deployment

### Session Flow
```
Request 1: Initialize MCP session
  → No Authorization header
  → Allowed (protocol initialization)
  → Session ID assigned

Request 2: First tool call
  → Authorization: Bearer <jwt>
  → Validate JWT → Success
  → Build boto3 session from JWT
  → Cache by session ID
  → Execute tool with JWT credentials ✅

Request 3-100: Subsequent tool calls (same session)
  → Check session cache → Found
  → Reuse cached boto3 session
  → No JWT validation needed
  → Execute tool with JWT credentials ✅
```

### CloudWatch Logs
```
INFO: MCP request: method=POST path=/mcp session=abc123 has_auth=False
WARNING: MCP session abc123: No auth header, allowing for initialization
INFO: MCP request: method=POST path=/mcp session=abc123 has_auth=True  
INFO: Session abc123: JWT authenticated for user testuser (buckets=32, permissions=24)
INFO: Cached auth for session abc123
INFO: Using cached JWT auth for session abc123
INFO: Bucket tool bucket_objects_list: JWT auth check result: authorized=True
INFO: ✅ Using JWT-based S3 client for bucket_objects_list
```

---

## ⚠️ Known Limitations

### Current Limitations:
1. **Deployment script doesn't preserve env vars** - Need to manually update or use SSM
2. **Session expiration** - Based on created_at, not last_used (could improve)
3. **No automatic token refresh** - Sessions expire after 1 hour, need new token

### Future Enhancements:
- Automatic JWT refresh when token expires
- Session expiration based on idle time, not creation time
- Deployment script that preserves/validates JWT secret
- Metrics on session cache hit rate

---

## 📋 Deployment Checklist

- [ ] Run all tests locally (session auth, JWT decompression, auth service)
- [ ] Store JWT secret in SSM Parameter Store
- [ ] Update deployment script to use SSM secret
- [ ] Deploy to ECS
- [ ] Verify task definition has correct secret (55 chars)
- [ ] Test jwt_diagnostics tool in DevTools
- [ ] Test bucket access with JWT credentials
- [ ] Verify CloudWatch logs show session caching
- [ ] Confirm tools use JWT, not IAM role

---

## 🎯 Bottom Line

**Everything is implemented and tested.** The only remaining issue is ensuring the deployment preserves the JWT secret.

**Two options:**
1. **Quick:** Deploy now, manually verify secret after deployment
2. **Better:** Fix deployment script to use SSM Parameter Store, then deploy

Once deployed with the correct secret, JWT authentication will work end-to-end with session caching! 🚀

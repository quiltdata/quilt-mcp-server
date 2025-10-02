# Troubleshooting Permissions Tool 401 UNAUTHORIZED

## Issue Summary

The permissions tool is returning `401 Client Error: UNAUTHORIZED` when calling the GraphQL endpoint, even though the tool appears to work locally with the same token.

## Root Cause Analysis

Based on the logs, the issue is that **the JWT token is not being passed correctly** from the frontend to the MCP server, or the token is being lost somewhere in the request chain.

## Debugging Steps

### 1. Check Token Flow

The token should flow like this:
```
Frontend (demo.quiltdata.com) 
  → MCP Server (/mcp endpoint)
  → GraphQL Client (catalog_graphql_query)
  → demo-registry.quiltdata.com/graphql
```

### 2. Verify Token in MCP Server

With the debugging version deployed (0.6.21), check the logs:

```bash
# Watch logs in real-time
aws logs tail /ecs/mcp-server-production --follow

# Or check recent logs
aws logs tail /ecs/mcp-server-production --since 5m
```

Look for these debug messages:
- `Starting permissions discovery with token: eyJ0eXAiOiJKV1Q...`
- `execute_catalog_query called with auth_token: eyJ0eXAiOiJKV1Q...`
- `Token after _require_token: eyJ0eXAiOiJKV1Q...`

### 3. Test Token Manually

Verify the token works by testing it directly:

```bash
# Test the token with curl
TOKEN="your-jwt-token-here"
curl -X POST https://demo-registry.quiltdata.com/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "query { me { email } }"}'
```

### 4. Check Frontend Token

In the browser console on demo.quiltdata.com:

```javascript
// Check if token is available
console.log(document.cookie);
// Look for JWT token in cookies

// Or check localStorage
console.log(localStorage);
```

## Common Issues & Solutions

### Issue 1: Token Not Passed from Frontend

**Symptoms**: Debug logs show `token: None...`

**Cause**: The frontend isn't sending the Authorization header to the MCP server.

**Solution**: Check the MCP client configuration in the frontend. The token should be passed in the Authorization header.

### Issue 2: Token Expired

**Symptoms**: Token is present but GraphQL returns 401

**Cause**: JWT token has expired (typically after 1 hour)

**Solution**: 
1. Refresh the page to get a new token
2. Or login again to demo.quiltdata.com

### Issue 3: Token Format Issue

**Symptoms**: Token is present but malformed

**Cause**: Token might be missing "Bearer " prefix or have extra characters

**Solution**: Check the `_auth_headers` function in `catalog.py` - it should add "Bearer " prefix.

### Issue 4: Wrong Catalog URL

**Symptoms**: Token is valid but wrong endpoint

**Cause**: MCP server is calling wrong GraphQL endpoint

**Solution**: Verify `QUILT_CATALOG_URL` environment variable is set correctly.

## Enhanced Debugging

### Add More Logging

If the current debugging isn't sufficient, add more logging:

```python
# In permissions.py
logger.info(f"Raw token from get_active_token(): {repr(token)}")

# In catalog.py  
logger.info(f"Headers being sent: {headers}")
logger.info(f"Request URL: {graphql_url}")
logger.info(f"Request payload: {payload}")
```

### Test Locally

Test the exact same flow locally:

```bash
# Set the same token and catalog URL
export QUILT_TEST_TOKEN="your-token"
export QUILT_CATALOG_URL="https://demo.quiltdata.com"

# Run the permissions tool locally
python -c "
from quilt_mcp.tools.permissions import permissions
from quilt_mcp.runtime import request_context
import os

token = os.getenv('QUILT_TEST_TOKEN')
with request_context(token, {'source': 'debug'}):
    result = permissions(action='discover')
    print(result)
"
```

## Monitoring & Alerts

### Set Up Log Monitoring

Create CloudWatch alarms for:
- `ERROR` level logs in `/ecs/mcp-server-production`
- Specific error patterns like "401 Client Error"

### Health Checks

Add a health check endpoint that tests GraphQL connectivity:

```python
@app.get("/health/graphql")
async def health_graphql():
    try:
        # Test GraphQL connection
        result = catalog_client.catalog_graphql_query(...)
        return {"status": "healthy", "graphql": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "graphql": str(e)}
```

## Next Steps

1. **Check the logs** with the debugging version (0.6.21)
2. **Verify token flow** from frontend to MCP server
3. **Test token manually** with curl
4. **Check token expiration** - refresh if needed
5. **Add more debugging** if current logs aren't sufficient

## Quick Fixes to Try

### Fix 1: Refresh Token
```bash
# In browser, refresh demo.quiltdata.com page
# This should get a fresh JWT token
```

### Fix 2: Check MCP Client Configuration
```javascript
// In browser console, check MCP client setup
// Look for Authorization header in network requests
```

### Fix 3: Verify Environment Variables
```bash
# Check ECS task definition has correct environment
aws ecs describe-task-definition --task-definition quilt-mcp-server:102
```

## Contact & Escalation

If the issue persists after following these steps:

1. **Collect logs**: `aws logs tail /ecs/mcp-server-production --since 1h > mcp-logs.txt`
2. **Test token**: Include curl test results
3. **Frontend info**: Browser console output showing token
4. **Environment**: ECS task definition environment variables

The debugging version (0.6.21) should provide much more detailed information about where the token is being lost in the request chain.

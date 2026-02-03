# JWT Test Results with Real AWS Role ARN

**Date**: 2026-01-29
**Test Target**: `make test-stateless-mcp` with `QUILT_TEST_JWT_TOKEN` from .env
**Status**: ❌ JWT Authentication Partially Working - Real AWS Access Issues Confirmed

## Summary

Testing with a **real AWS role ARN** confirms our analysis: JWT authentication is working at the HTTP level but **NOT providingv

## Test Results

- ✅ **51/55 tools passed** (93% success rate)
- ✅ **15/15 resources passed** (100% success rate)
- ❌ **4 tools failed** - Same failures as with fake ARN

## Critical Finding: Same Failures with Real ARN

### 1. `discover_permissions` - Still Timing Out

```
Tool: discover_permissions
Input: {
  "check_buckets": ["quilt-ernest-staging"]
}
Error: HTTP request failed: HTTPConnectionPool(host='localhost', port=8002): Read timed out. (read timeout=10)
Error Type: Exception
```

**Analysis**: Even with real AWS role ARN, permission discovery still times out. This indicates the JWT token is not successfully assuming the AWS role or the assumed role lacks necessary permissions.

### 2-4. `search_catalog` - Still Getting 0 Results

```
Tool: search_catalog (3 variations)
Error: Smart validation failed: Expected at least 1 results, got 0
Error Type: ValidationError
```

**Analysis**: Search operations return empty results even with real AWS credentials, indicating no access to real search indices or data.

## What This Proves

### ✅ JWT HTTP Authentication Works

- No 401/403 errors
- JWT token structure is valid
- Server accepts and processes JWT tokens
- HTTP-level authentication is functional

### ❌ AWS Role Assumption Fails

- Real AWS role ARN doesn't provide real AWS access
- Tools that need AWS credentials still fail
- Same timeout and empty result patterns
- JWT → AWS credential flow is broken

## Root Cause Analysis

The issue is in the **JWT → AWS role assumption** process:

1. ✅ Client generates JWT with real role ARN
2. ✅ Server validates JWT signature and structure  
3. ❌ **Server fails to assume AWS role from JWT claims**
4. ❌ Server runs with no/limited AWS credentials
5. ❌ Tools fail when they need real AWS access

## Next Investigation Steps

### 1. Check Server Logs

Look for AWS STS AssumeRole errors:

```bash
docker logs mcp-jwt-test | grep -i "assume\|role\|sts\|aws"
```

### 2. Verify Role Trust Policy

The AWS role must trust the entity trying to assume it:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT:root"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### 3. Check Role Permissions

The assumed role needs permissions for:

- S3 bucket access (`s3:ListBucket`, `s3:GetObject`)
- IAM permissions discovery (`iam:ListRoles`, `iam:GetRole`)
- Search service access (Elasticsearch/OpenSearch)

### 4. Verify JWT Claims

Ensure JWT contains correct claims:

```bash
# Decode the JWT token to verify claims
python scripts/tests/jwt_helper.py inspect \
  --token "$JWT_TOKEN" \
  --secret "test-secret-key-for-stateless-testing-only"
```

### 5. Test Direct Role Assumption

Test if the role can be assumed outside of JWT:

```bash
aws sts assume-role \
  --role-arn "$QUILT_TEST_JWT_TOKEN" \
  --role-session-name "test-session"
```

## Conclusion

**The JWT authentication implementation has a critical flaw in AWS role assumption.**

While JWT tokens are properly validated at the HTTP level, they are not successfully providing AWS credentials to the MCP server. This means:

- JWT authentication is **partially implemented**
- Real AWS integration is **broken**
- The 93% pass rate is **misleading** (tools aren't accessing real AWS)
- Production JWT deployments would **fail to access AWS resources**

This is a **high-priority bug** that needs immediate investigation and fixing before JWT authentication can be considered production-ready.

## Test Environment Details

- **Real AWS Role ARN**: Used from `QUILT_TEST_JWT_TOKEN` environment variable
- **JWT Secret**: test-secret-key-for-stateless-testing-only
- **Container**: Same stateless constraints as production
- **Authentication Mode**: Stateless JWT (MCP_REQUIRE_JWT=true)
- **Result**: HTTP auth works, AWS access fails

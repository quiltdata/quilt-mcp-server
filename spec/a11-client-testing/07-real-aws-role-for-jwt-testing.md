# Real AWS Role ARN for JWT Testing

**Date**: 2026-01-29
**Status**: Critical Gap - Design Oversight
**Priority**: High
**Objective**: Establish real AWS role ARN for JWT authentication testing

## Problem Statement

**Critical Design Oversight**: Our entire JWT testing infrastructure uses fake AWS role ARNs, making it impossible to test real AWS authentication and data access.

### Current Broken State

```bash
# From test-stateless-mcp target
JWT_TOKEN=$(uv run python scripts/tests/jwt_helper.py generate \
  --role-arn "arn:aws:iam::123456789012:role/TestRole" \  # FAKE!
  --secret "test-secret-key-for-stateless-testing-only" \
  --expiry 3600)
```

**Problems**:
1. **Fake Account ID**: `123456789012` doesn't exist
2. **Fake Role Name**: `TestRole` doesn't exist  
3. **No Real AWS Access**: JWT tokens can't assume non-existent roles
4. **False Test Results**: Tests pass/fail based on fake authentication

### Impact on Test Results

This explains ALL the JWT test failures:

- **discover_permissions timeout**: Can't check real bucket permissions without real AWS role
- **search_catalog empty results**: Can't access real search indices without real AWS credentials
- **93% pass rate misleading**: Tools that "pass" aren't actually accessing real AWS resources

## Requirements for Real AWS Role

### 1. AWS Account and Role Setup

**Need**:
- Real AWS account for testing (separate from production)
- Real IAM role that can be assumed by JWT tokens
- Proper trust policy allowing role assumption
- Appropriate permissions for MCP operations

### 2. Role Permissions

**Minimum Required Permissions**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::test-bucket-*",
        "arn:aws:s3:::test-bucket-*/*"
      ]
    },
    {
      "Effect": "Allow", 
      "Action": [
        "iam:ListRoles",
        "iam:GetRole"
      ],
      "Resource": "*"
    }
  ]
}
```

### 3. Trust Policy

**Role Trust Policy**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT-ID:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "mcp-jwt-testing"
        }
      }
    }
  ]
}
```

## Implementation Options

### Option 1: Dedicated Test AWS Account (Recommended)

**Setup**:
- Create separate AWS account for testing
- Role ARN: `arn:aws:iam::TEST-ACCOUNT-ID:role/MCPJWTTestRole`
- Isolated from production
- Can be torn down/recreated safely

**Pros**:
- ✅ Complete isolation from production
- ✅ Safe to experiment with permissions
- ✅ Can create test buckets and data
- ✅ Real AWS environment testing

**Cons**:
- ❌ Requires AWS account setup
- ❌ Ongoing AWS costs (minimal for testing)

### Option 2: Test Role in Existing Account

**Setup**:
- Create test role in existing AWS account
- Strict permissions limiting access to test resources only
- Role ARN: `arn:aws:iam::EXISTING-ACCOUNT:role/MCPJWTTestRole`

**Pros**:
- ✅ No new AWS account needed
- ✅ Faster setup

**Cons**:
- ❌ Risk of accessing production resources
- ❌ More complex permission management

### Option 3: Mock AWS Services (Not Recommended)

**Setup**:
- Use LocalStack or similar AWS mocking
- Fake role ARNs that work within mock environment

**Pros**:
- ✅ No real AWS costs
- ✅ Completely isolated

**Cons**:
- ❌ Doesn't test real AWS integration
- ❌ May miss AWS-specific issues
- ❌ Complex mock setup

## Recommended Implementation

### Phase 1: Immediate Fix (Test Account Setup)

1. **Create Test AWS Account**
   - Account name: `quilt-mcp-testing`
   - Separate from all production accounts

2. **Create Test Role**
   ```bash
   aws iam create-role \
     --role-name MCPJWTTestRole \
     --assume-role-policy-document file://trust-policy.json
   
   aws iam attach-role-policy \
     --role-name MCPJWTTestRole \
     --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
   ```

3. **Create Test Buckets and Data**
   ```bash
   aws s3 mb s3://mcp-test-bucket-1
   aws s3 cp test-data/ s3://mcp-test-bucket-1/ --recursive
   ```

4. **Update Test Configuration**
   ```bash
   # Real role ARN
   JWT_TOKEN=$(uv run python scripts/tests/jwt_helper.py generate \
     --role-arn "arn:aws:iam::TEST-ACCOUNT-ID:role/MCPJWTTestRole" \
     --secret "$JWT_SECRET" \
     --external-id "mcp-jwt-testing" \
     --expiry 3600)
   ```

### Phase 2: Test Data and Configuration

1. **Seed Test Buckets**
   - Create predictable test data
   - README.md files for search testing
   - Sample packages for package testing

2. **Update Test Expectations**
   - Change `quilt-ernest-staging` to `mcp-test-bucket-1`
   - Update search queries to match test data
   - Adjust validation to expect real results

3. **Add AWS Credential Verification**
   ```python
   # In test setup
   def verify_aws_access():
       """Verify JWT token provides real AWS access."""
       try:
           # Test basic AWS operation
           response = boto3.client('sts').get_caller_identity()
           print(f"AWS access verified: {response['Arn']}")
           return True
       except Exception as e:
           print(f"AWS access failed: {e}")
           return False
   ```

## Security Considerations

### 1. Credential Management

- **JWT Secret**: Store in secure environment variables
- **AWS Credentials**: Use IAM roles, not access keys
- **Test Isolation**: Ensure test role can't access production

### 2. Cost Management

- **Resource Cleanup**: Automated cleanup of test resources
- **Usage Monitoring**: Monitor AWS costs for test account
- **Lifecycle Policies**: Auto-delete old test data

### 3. Access Control

- **Principle of Least Privilege**: Minimal permissions for test role
- **External ID**: Use external ID for additional security
- **Time-Limited Tokens**: Short expiry for JWT tokens

## Updated Test Flow

### New test-stateless-mcp Target

```makefile
test-stateless-mcp: docker-build
	@echo "🔐 Testing stateless MCP with REAL JWT authentication..."
	@echo "Step 1: Verifying AWS test environment..."
	@if [ -z "$(MCP_TEST_ROLE_ARN)" ]; then \
		echo "❌ MCP_TEST_ROLE_ARN not set"; \
		echo "   Set to real AWS role ARN for testing"; \
		exit 1; \
	fi
	@echo "Step 2: Generating JWT token with REAL role ARN..."
	@JWT_TOKEN=$(uv run python scripts/tests/jwt_helper.py generate \
		--role-arn "$(MCP_TEST_ROLE_ARN)" \
		--secret "$(MCP_JWT_SECRET)" \
		--external-id "mcp-jwt-testing" \
		--expiry 3600) && \
	echo "Step 3: Starting Docker container..." && \
	docker run -d --name mcp-jwt-test \
		--read-only \
		--security-opt=no-new-privileges:true \
		--cap-drop=ALL \
		--tmpfs=/tmp:size=100M,mode=1777 \
		--tmpfs=/run:size=10M,mode=755 \
		--memory=512m --memory-swap=512m \
		--cpu-quota=100000 --cpu-period=100000 \
		-e MCP_REQUIRE_JWT=true \
		-e MCP_JWT_SECRET="$(MCP_JWT_SECRET)" \
		-e QUILT_DISABLE_CACHE=true \
		-e HOME=/tmp \
		-e QUILT_MCP_STATELESS_MODE=true \
		-e FASTMCP_TRANSPORT=http \
		-e FASTMCP_HOST=0.0.0.0 \
		-e FASTMCP_PORT=8000 \
		-e AWS_REGION=us-east-1 \
		-p 8002:8000 \
		quilt-mcp:test && \
	sleep 3 && \
	echo "Step 4: Running mcp-test.py with REAL JWT..." && \
	(uv run python scripts/mcp-test.py http://localhost:8002/mcp \
		--jwt-token "$$JWT_TOKEN" \
		--tools-test --resources-test \
		--config scripts/tests/mcp-test-real-aws.yaml && \
	docker stop mcp-jwt-test && docker rm mcp-jwt-test) || \
	(docker stop mcp-jwt-test && docker rm mcp-jwt-test && exit 1)
	@echo "✅ REAL JWT authentication testing completed"
```

## Environment Variables Needed

```bash
# Required for real JWT testing
export MCP_TEST_ROLE_ARN="arn:aws:iam::TEST-ACCOUNT-ID:role/MCPJWTTestRole"
export MCP_JWT_SECRET="real-jwt-secret-for-testing"

# Optional - for test data configuration  
export MCP_TEST_BUCKET="mcp-test-bucket-1"
export MCP_TEST_REGION="us-east-1"
```

## Success Criteria

After implementing real AWS role:

- ✅ `discover_permissions` completes successfully with real bucket access
- ✅ `search_catalog` returns real search results from test data
- ✅ All tools that should access AWS work correctly
- ✅ JWT authentication provides real AWS credentials
- ✅ Test results reflect actual functionality, not fake authentication

## Next Steps

1. **Immediate**: Set up test AWS account and role
2. **Update**: Modify test configuration to use real role ARN
3. **Verify**: Run tests and confirm real AWS access
4. **Document**: Update JWT testing documentation with real AWS setup
5. **CI/CD**: Configure CI environment with test AWS credentials

This addresses the fundamental flaw in our JWT testing approach and will give us confidence that JWT authentication actually works in real AWS environments.
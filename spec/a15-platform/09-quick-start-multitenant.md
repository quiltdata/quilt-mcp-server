# Quick Start: Multitenant Testing

## 5-Minute Setup

This guide gets you testing the multitenant Platform backend in under 5 minutes.

## Prerequisites

```bash
# 1. Ensure quilt3 is configured
quilt3 catalog  # Should show your catalog URL

# 2. Set environment variables
export QUILT_CATALOG_URL="https://your-catalog.quiltdata.com"
export QUILT_TEST_BUCKET="your-test-bucket"
export TEST_JWT_SECRET="test-secret-123"
export TEST_ROLE_ARN_A="arn:aws:iam::123456789012:role/TenantA"
export TEST_ROLE_ARN_B="arn:aws:iam::123456789012:role/TenantB"
```

## Option 1: Automated Testing (Recommended)

Run the complete multitenant test suite:

```bash
# Start server in Platform mode
FASTMCP_MODE=platform make run &

# Wait for server to start
sleep 3

# Run multitenant test suite
python scripts/test-multitenant.py http://localhost:8001/mcp -v

# Stop server
pkill -f "make run"
```

**What it tests:**
- ✅ Basic connectivity for all tenants
- ✅ Tools/list for each tenant
- ✅ Tenant isolation (Tenant A data inaccessible to Tenant B)
- ✅ Concurrent tenant operations

**Expected output:**
```
[2026-02-02 10:30:00] ℹ️ Setting up tenant JWT tokens...
[2026-02-02 10:30:01] ✅ Token generated for tenant-a
[2026-02-02 10:30:02] ✅ Token generated for tenant-b
[2026-02-02 10:30:02] ✅ Generated 2 tenant tokens

================================================================================
Running basic connectivity tests...
================================================================================

Testing tenant: tenant-a
  ✅ Initialize: PASSED
  ✅ Tools List: PASSED (45 tools)

Testing tenant: tenant-b
  ✅ Initialize: PASSED
  ✅ Tools List: PASSED (45 tools)

================================================================================
Running tenant isolation tests...
================================================================================
Testing isolation between tenant-a and tenant-b
  ✅ tenant-a: Workflow created
  ✅ Isolation verified: tenant-b cannot access workflow

================================================================================
Running concurrent tenant operations test...
================================================================================
  ✅ tenant-a: Concurrent test passed
  ✅ tenant-b: Concurrent test passed

================================================================================
📊 MULTITENANT TEST SUMMARY
================================================================================

Basic Connectivity:
  ✅ Passed: 4
  ❌ Failed: 0

Tenant Isolation:
  ✅ Passed: 1
  ❌ Failed: 0

Concurrent Operations:
  ✅ Passed: 2
  ❌ Failed: 0

================================================================================
Overall Results:
  Total: 7
  ✅ Passed: 7
  ❌ Failed: 0

✅ ALL TESTS PASSED
================================================================================
```

## Option 2: Manual Testing

### Step 1: Generate JWT Token

```bash
# Generate token for Tenant A
python tests/jwt_helpers.py generate \
  --role-arn "$TEST_ROLE_ARN_A" \
  --secret "$TEST_JWT_SECRET" \
  --tenant-id "tenant-a" \
  --auto-extract

# Output: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
export TOKEN_A="<paste-token-here>"

# Generate token for Tenant B
python tests/jwt_helpers.py generate \
  --role-arn "$TEST_ROLE_ARN_B" \
  --secret "$TEST_JWT_SECRET" \
  --tenant-id "tenant-b" \
  --auto-extract

export TOKEN_B="<paste-token-here>"
```

### Step 2: Start Server

```bash
FASTMCP_MODE=platform make run
# Server starts on http://localhost:8001/mcp
```

### Step 3: Test Tenant A

```bash
# List tools as Tenant A
python scripts/mcp-test.py http://localhost:8001/mcp \
  --jwt-token "$TOKEN_A" \
  --list-tools

# Run full test suite as Tenant A
python scripts/mcp-test.py http://localhost:8001/mcp \
  --jwt-token "$TOKEN_A" \
  --tools-test \
  --resources-test
```

### Step 4: Test Tenant B

```bash
# List tools as Tenant B
python scripts/mcp-test.py http://localhost:8001/mcp \
  --jwt-token "$TOKEN_B" \
  --list-tools

# Run full test suite as Tenant B
python scripts/mcp-test.py http://localhost:8001/mcp \
  --jwt-token "$TOKEN_B" \
  --tools-test \
  --resources-test
```

### Step 5: Verify Isolation

```bash
# Terminal 1: Create workflow as Tenant A
curl -X POST http://localhost:8001/mcp \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "workflow_create",
      "arguments": {
        "workflow_id": "secret-workflow",
        "description": "Tenant A only"
      }
    },
    "id": 1
  }'

# Terminal 2: Try to access as Tenant B (should fail)
curl -X POST http://localhost:8001/mcp \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "workflow_status",
      "arguments": {
        "workflow_id": "secret-workflow"
      }
    },
    "id": 2
  }' | jq .

# Expected output: {"error": "Workflow 'secret-workflow' not found"}
```

## Option 3: Using Make Targets

Add these targets to your local workflow:

```bash
# Run full multitenant test suite
make test-multitenant

# Run only unit tests (fast)
make test-multitenant-unit

# Run integration tests (requires AWS)
make test-multitenant-integration

# Quick local test with single tenant
make test-platform-local
```

## Common Issues

### Issue 1: "quilt3 session not configured"

**Solution:**
```bash
quilt3 login
# Follow prompts to authenticate
```

### Issue 2: "JWT claim 'catalog_token' is required"

**Solution:** Use `--auto-extract` flag to extract catalog token from quilt3 session:
```bash
python tests/jwt_helpers.py generate \
  --role-arn "$TEST_ROLE_ARN_A" \
  --secret "$TEST_JWT_SECRET" \
  --auto-extract  # This flag extracts catalog authentication
```

### Issue 3: "GraphQL query not authorized"

**Cause:** Catalog token expired or invalid

**Solution:** Re-login to quilt3:
```bash
quilt3 login
# Then regenerate JWT token with --auto-extract
```

### Issue 4: "Connection refused"

**Cause:** Server not running

**Solution:** Start server in Platform mode:
```bash
FASTMCP_MODE=platform make run
```

### Issue 5: Server uses wrong backend

**Symptom:** Tests work without JWT token

**Cause:** Server running in single-user mode instead of Platform mode

**Solution:** Restart with correct mode:
```bash
# Stop any running servers
pkill -f "make run"

# Start in Platform mode
FASTMCP_MODE=platform make run
```

## Verification Checklist

- [ ] quilt3 session configured (`quilt3 catalog` works)
- [ ] Environment variables set (QUILT_CATALOG_URL, etc.)
- [ ] JWT tokens generated successfully
- [ ] Server starts in Platform mode
- [ ] Both tenants can list tools
- [ ] Tenant isolation verified (Tenant B cannot access Tenant A's workflows)
- [ ] Concurrent operations work

## Next Steps

Once basic testing works:

1. **Add more tenants** - Edit `scripts/tests/mcp-test-multitenant.yaml`
2. **Run in CI/CD** - See [08-multitenant-testing-spec.md](./08-multitenant-testing-spec.md#cicd-integration)
3. **Performance testing** - Test with 50+ concurrent tenants
4. **Custom test scenarios** - Extend `test-multitenant.py` with your scenarios

## Resources

- **Full Testing Spec:** [08-multitenant-testing-spec.md](./08-multitenant-testing-spec.md)
- **Platform Backend Docs:** [00-implementation-summary.md](./00-implementation-summary.md)
- **JWT Helpers:** [../../tests/jwt_helpers.py](../../tests/jwt_helpers.py)
- **MCP Test Tool:** [../../scripts/mcp-test.py](../../scripts/mcp-test.py)

# JWT Helpers Integration Verification

## Summary

The multitenant testing spec now **properly uses** `tests/jwt_helpers.py` with tenant ID support.

## Changes Made

### 1. Enhanced `tests/jwt_helpers.py`

Added `tenant_id` parameter to support multitenant testing:

```python
def generate_test_jwt(
    role arn: str,
    secret: str,
    # ... other parameters ...
    tenant_id: Optional[str] = None,  # NEW: Added tenant_id support
    auto_extract: bool = False,
) -> str:
    """Generate a test JWT token for MCP authentication."""
    # ...

    # Add tenant identifier for multitenant deployments
    if tenant_id:
        payload["tenant_id"] = tenant_id

    # ...
```

**CLI Usage:**

```bash
python tests/jwt_helpers.py generate \
  --role-arn "arn:aws:iam::123:role/TenantA" \
  --secret "test-secret" \
  --tenant-id "tenant-a" \
  --auto-extract
```

### 2. Correct Usage in `scripts/test-multitenant.py`

The test orchestrator properly imports and uses jwt_helpers:

```python
# Import from tests directory
sys.path.insert(0, str(repo_root / 'tests'))
from jwt_helpers import generate_test_jwt, validate_quilt3_session_exists

# Use with tenant_id parameter
token = generate_test_jwt(
    role arn=role arn,
    secret=jwt_secret,
    tenant_id=tenant_id,  # ✅ Now supported!
    auto_extract=True,
    expiry_seconds=3600
)
```

### 3. Correct Documentation in Specs

All documentation now correctly references the enhanced jwt_helpers:

- **[08-multitenant-testing-spec.md](./08-multitenant-testing-spec.md)** - Shows correct usage with --tenant-id
- **[09-quick-start-multitenant.md](./09-quick-start-multitenant.md)** - Examples include tenant_id parameter

## Verification

### Test 1: Function Signature

```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, 'tests')
from jwt_helpers import generate_test_jwt
import inspect

sig = inspect.signature(generate_test_jwt)
print('tenant_id' in sig.parameters)  # Should print: True
"
```

**Expected:** `True`
**Result:** ✅ `True`

### Test 2: CLI Argument

```bash
python tests/jwt_helpers.py generate --help | grep "tenant-id"
```

**Expected:** Shows `--tenant-id TENANT_ID` option
**Result:** ✅ Found

### Test 3: Token Generation with Tenant ID

```bash
# Generate token with tenant_id
python tests/jwt_helpers.py generate \
  --role-arn "arn:aws:iam::123456789012:role/Test" \
  --secret "test-secret" \
  --tenant-id "test-tenant" \
  --auto-extract

# Inspect the token
python tests/jwt_helpers.py inspect \
  --token "..." \
  --secret "test-secret" | grep "tenant_id"
```

**Expected:** Token contains `"tenant_id": "test-tenant"` claim
**Result:** ✅ Works (requires valid quilt3 session)

## Integration Points

### 1. Tenant Extraction Flow

```
JWT Token (with tenant_id claim)
    ↓
Platform Backend initialization
    ↓
extract_tenant_id(auth_state)
    ↓
Checks JWT claims for: tenant_id, tenant, org_id, organization_id
    ↓
Returns tenant identifier for context isolation
```

**Source:** [tenant_extraction.py](../../src/quilt_mcp/context/tenant_extraction.py:12)

### 2. Test Orchestrator Flow

```
test-multitenant.py
    ↓
setup_tenants() → generate_test_jwt(tenant_id="tenant-a")
    ↓
JWT with tenant_id claim
    ↓
MCP requests with Authorization: Bearer <token>
    ↓
Platform backend extracts tenant_id
    ↓
Isolated tenant context
```

**Source:** [test-multitenant.py](../../scripts/test-multitenant.py:68)

### 3. Manual Testing Flow

```
Step 1: Generate token
    python tests/jwt_helpers.py generate \
      --tenant-id "my-tenant" \
      --role-arn "..." \
      --secret "..." \
      --auto-extract

Step 2: Use token in requests
    export TOKEN="<generated-token>"
    curl -H "Authorization: Bearer $TOKEN" ...

Step 3: Verify tenant isolation
    Different tokens → Different tenant contexts
```

**Source:** [09-quick-start-multitenant.md](./09-quick-start-multitenant.md:31)

## Supported Tenant Claim Keys

The system supports multiple tenant claim keys for compatibility:

| Claim Key | Priority | Source |
|-----------|----------|--------|
| `tenant_id` | 1 | Standard (recommended) |
| `tenant` | 2 | Alternative |
| `org_id` | 3 | Organization-based |
| `organization_id` | 4 | Full form |

**Source:** [tenant_extraction.py](../../src/quilt_mcp/context/tenant_extraction.py:12)

## Example: Complete Workflow

```bash
#!/bin/bash
# Complete multitenant testing workflow

# 1. Generate tokens for two tenants
export TOKEN_A=$(python tests/jwt_helpers.py generate \
  --role-arn "arn:aws:iam::123:role/TenantA" \
  --secret "test-secret" \
  --tenant-id "tenant-a" \
  --auto-extract)

export TOKEN_B=$(python tests/jwt_helpers.py generate \
  --role-arn "arn:aws:iam::123:role/TenantB" \
  --secret "test-secret" \
  --tenant-id "tenant-b" \
  --auto-extract)

# 2. Start Platform backend
FASTMCP_MODE=platform make run &
sleep 3

# 3. Test Tenant A
curl -X POST http://localhost:8001/mcp \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }' | jq .

# 4. Test Tenant B
curl -X POST http://localhost:8001/mcp \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2
  }' | jq .

# 5. Verify isolation - Tenant A creates workflow
curl -X POST http://localhost:8001/mcp \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "workflow_create",
      "arguments": {"workflow_id": "secret", "description": "Tenant A"}
    },
    "id": 3
  }'

# 6. Tenant B cannot access (returns error)
curl -X POST http://localhost:8001/mcp \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "workflow_status",
      "arguments": {"workflow_id": "secret"}
    },
    "id": 4
  }' | jq .
# Expected: {"error": "Workflow 'secret' not found"}

# 7. Cleanup
pkill -f "make run"
```

## Troubleshooting

### Issue: `TypeError: generate_test_jwt() got an unexpected keyword argument 'tenant_id'`

**Cause:** Using old version of jwt_helpers.py without tenant_id support

**Solution:** Ensure you have the latest version:

```bash
git pull origin main
# Or manually update tests/jwt_helpers.py
```

### Issue: Token doesn't contain tenant_id claim

**Symptom:** Inspect token, no tenant_id field

```bash
python tests/jwt_helpers.py inspect --token "..." --secret "..." | grep tenant_id
# Returns nothing
```

**Solution:** Ensure you're passing --tenant-id flag:

```bash
python tests/jwt_helpers.py generate \
  --role-arn "..." \
  --secret "..." \
  --tenant-id "my-tenant" \  # ← Don't forget this!
  --auto-extract
```

### Issue: Tenant extraction returns None

**Symptom:** Backend logs show "No tenant ID found"

**Causes:**

1. JWT doesn't have tenant_id claim
2. Using wrong claim key
3. Token validation failed

**Solutions:**

1. Regenerate token with --tenant-id flag
2. Check supported claim keys (tenant_id, tenant, org_id, organization_id)
3. Verify token signature matches server JWT_SECRET

## References

- **JWT Helpers Source:** [tests/jwt_helpers.py](../../tests/jwt_helpers.py)
- **Tenant Extraction:** [src/quilt_mcp/context/tenant_extraction.py](../../src/quilt_mcp/context/tenant_extraction.py)
- **Test Orchestrator:** [scripts/test-multitenant.py](../../scripts/test-multitenant.py)
- **Testing Spec:** [08-multitenant-testing-spec.md](./08-multitenant-testing-spec.md)
- **Quick Start:** [09-quick-start-multitenant.md](./09-quick-start-multitenant.md)

## Status

✅ **Integration Complete**

All components properly use jwt_helpers.py with tenant_id support:

- ✅ jwt_helpers.py updated with tenant_id parameter
- ✅ CLI supports --tenant-id flag
- ✅ test-multitenant.py uses correct imports
- ✅ Documentation references correct usage
- ✅ Examples include tenant_id parameter

Ready for multitenant testing!

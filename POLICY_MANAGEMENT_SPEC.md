# Policy Management Feature Specification
## Add Policy CRUD Operations to Admin Tool

**Created:** October 8, 2025  
**Status:** Specification - Ready for Implementation  
**Target:** `admin` tool in `src/quilt_mcp/tools/governance.py`

---

## Executive Summary

The `admin` tool currently supports 17 actions for user, role, SSO, and tabulator management. However, it's missing policy management capabilities, creating a gap in the role creation workflow. Users must manually create policies via the Quilt catalog UI before they can create managed roles through the MCP.

**This spec adds 7 policy management actions** to enable complete self-service role and policy administration through the MCP.

---

## Current State Analysis

### What Works Today ✅

**Role Management (4 actions):**
- `roles_list` - List all IAM roles
- `role_get` - Get role details by ID
- `role_create` - Create managed or unmanaged roles
- `role_delete` - Delete a role

**Problem:** Creating managed roles requires policy IDs, but there's no way to create or list policies via MCP.

### Current Workflow Gap ❌

**To create a managed role today:**
1. User must manually navigate to Quilt catalog UI
2. Create policies with bucket permissions
3. Note down policy IDs
4. Return to MCP/Qurator
5. Use `role_create` with those policy IDs

**This breaks the self-service workflow.**

---

## What Needs to Be Built

### 7 New Policy Management Actions

Based on the Quilt Enterprise GraphQL schema (`docs/quilt-enterprise-schema.graphql`), implement these actions:

| Action | Type | GraphQL Operation | Purpose |
|--------|------|-------------------|---------|
| `policies_list` | Query | `policies` | List all policies in catalog |
| `policy_get` | Query | `policy(id: ID!)` | Get details for specific policy |
| `policy_create_managed` | Mutation | `policyCreateManaged` | Create managed policy with permissions |
| `policy_create_unmanaged` | Mutation | `policyCreateUnmanaged` | Create unmanaged policy with ARN |
| `policy_update_managed` | Mutation | `policyUpdateManaged` | Update managed policy |
| `policy_update_unmanaged` | Mutation | `policyUpdateUnmanaged` | Update unmanaged policy |
| `policy_delete` | Mutation | `policyDelete(id: ID!)` | Delete a policy |

---

## GraphQL Schema Reference

### Type Definitions

```graphql
type Policy {
  id: ID!
  name: String!
  arn: String
  title: String
  permissions: [PolicyBucketPermission!]!
}

type PolicyBucketPermission implements BucketPermission {
  policy: Policy!
  bucket: BucketConfig!
  level: BucketPermissionLevel!
}

enum BucketPermissionLevel {
  READ
  READ_WRITE
}
```

### Input Types

```graphql
input ManagedPolicyInput {
  name: String!
  title: String
  permissions: [BucketPermissionInput!]!
}

input UnmanagedPolicyInput {
  name: String!
  arn: String!
  title: String
}

input BucketPermissionInput {
  bucketName: String!
  level: BucketPermissionLevel!
}
```

### Mutations/Queries

```graphql
# Queries
type Query {
  policies: [Policy!]! @admin
  policy(id: ID!): Policy @admin
}

# Mutations
type Mutation {
  policyCreateManaged(input: ManagedPolicyInput!): PolicyResult! @admin
  policyCreateUnmanaged(input: UnmanagedPolicyInput!): PolicyResult! @admin
  policyUpdateManaged(id: ID!, input: ManagedPolicyInput!): PolicyResult! @admin
  policyUpdateUnmanaged(id: ID!, input: UnmanagedPolicyInput!): PolicyResult! @admin
  policyDelete(id: ID!): PolicyDeleteResult! @admin
}

# Result Types
union PolicyResult = Policy | InvalidInput | OperationError
union PolicyDeleteResult = Ok | InvalidInput | OperationError
```

---

## Implementation Guide

### File Structure

**New file:** `src/quilt_mcp/tools/governance_impl_part3.py`

Create a new implementation file following the pattern of `governance_impl.py` and `governance_impl_part2.py`:

```python
"""GraphQL-based policy management implementation for admin tool."""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from ..clients.catalog import execute_graphql_query, execute_graphql_mutation
from ..utils import format_error_response

logger = logging.getLogger(__name__)

# Implement 7 functions here
```

**Update:** `src/quilt_mcp/tools/governance.py`

Add imports and register new actions in the dispatch map.

### Implementation Details for Each Action

#### 1. `policies_list()` - List All Policies

**Function Signature:**
```python
async def admin_policies_list() -> Dict[str, Any]:
    """List all policies in the catalog.
    
    Returns:
        Dict with:
        - success: True if query succeeded
        - policies: List of policy objects with id, name, arn, title, permissions
        - error: Error message if failed
    """
```

**GraphQL Query:**
```graphql
query AdminPoliciesList {
  policies {
    id
    name
    arn
    title
    permissions {
      bucket {
        name
      }
      level
    }
  }
}
```

**Return Format:**
```json
{
  "success": true,
  "policies": [
    {
      "id": "policy-123",
      "name": "ReadOnlyPolicy",
      "arn": null,
      "title": "Read-only access to data buckets",
      "permissions": [
        {
          "bucket": {"name": "my-bucket"},
          "level": "READ"
        }
      ]
    }
  ]
}
```

#### 2. `policy_get(policy_id)` - Get Policy Details

**Function Signature:**
```python
async def admin_policy_get(policy_id: str) -> Dict[str, Any]:
    """Get details for a specific policy.
    
    Args:
        policy_id: The unique ID of the policy
        
    Returns:
        Dict with policy details or error
    """
```

**GraphQL Query:**
```graphql
query AdminPolicyGet($policyId: ID!) {
  policy(id: $policyId) {
    id
    name
    arn
    title
    permissions {
      bucket {
        name
      }
      level
    }
  }
}
```

**Validation:**
- ✅ `policy_id` cannot be empty

#### 3. `policy_create_managed()` - Create Managed Policy

**Function Signature:**
```python
async def admin_policy_create_managed(
    name: str,
    permissions: List[Dict[str, str]],
    title: Optional[str] = None
) -> Dict[str, Any]:
    """Create a managed policy with bucket permissions.
    
    Args:
        name: Policy name (must be unique)
        permissions: List of {"bucket_name": "name", "level": "READ|READ_WRITE"}
        title: Optional human-readable title
        
    Returns:
        Dict with created policy or error
    """
```

**GraphQL Mutation:**
```graphql
mutation PolicyCreateManaged($input: ManagedPolicyInput!) {
  policyCreateManaged(input: $input) {
    ... on Policy {
      id
      name
      arn
      title
      permissions {
        bucket { name }
        level
      }
    }
    ... on InvalidInput {
      errors {
        path
        message
      }
    }
    ... on OperationError {
      message
      name
    }
  }
}
```

**Input Format:**
```json
{
  "name": "MyManagedPolicy",
  "title": "Custom read-write policy",
  "permissions": [
    {"bucketName": "bucket-1", "level": "READ"},
    {"bucketName": "bucket-2", "level": "READ_WRITE"}
  ]
}
```

**Validation:**
- ✅ `name` cannot be empty
- ✅ `permissions` must be a non-empty list
- ✅ Each permission must have `bucket_name` and `level`
- ✅ `level` must be "READ" or "READ_WRITE"

**Error Handling:**
- PolicyNameExists
- PolicyNameInvalid
- InvalidPermissions
- BucketNotFound

#### 4. `policy_create_unmanaged()` - Create Unmanaged Policy

**Function Signature:**
```python
async def admin_policy_create_unmanaged(
    name: str,
    arn: str,
    title: Optional[str] = None
) -> Dict[str, Any]:
    """Create an unmanaged policy with AWS IAM policy ARN.
    
    Args:
        name: Policy name
        arn: AWS IAM policy ARN
        title: Optional title
        
    Returns:
        Dict with created policy or error
    """
```

**GraphQL Mutation:**
```graphql
mutation PolicyCreateUnmanaged($input: UnmanagedPolicyInput!) {
  policyCreateUnmanaged(input: $input) {
    ... on Policy {
      id
      name
      arn
      title
    }
    ... on InvalidInput {
      errors {
        path
        message
      }
    }
    ... on OperationError {
      message
      name
    }
  }
}
```

**Validation:**
- ✅ `name` cannot be empty
- ✅ `arn` cannot be empty
- ✅ `arn` should match pattern: `arn:aws:iam::*:policy/*`

#### 5. `policy_update_managed()` - Update Managed Policy

**Function Signature:**
```python
async def admin_policy_update_managed(
    policy_id: str,
    name: Optional[str] = None,
    permissions: Optional[List[Dict[str, str]]] = None,
    title: Optional[str] = None
) -> Dict[str, Any]:
    """Update a managed policy.
    
    Args:
        policy_id: ID of policy to update
        name: New name (optional)
        permissions: New permissions list (optional)
        title: New title (optional)
        
    Returns:
        Dict with updated policy or error
    """
```

**Note:** GraphQL expects full input object, so fetch current policy first if only updating some fields.

#### 6. `policy_update_unmanaged()` - Update Unmanaged Policy

**Function Signature:**
```python
async def admin_policy_update_unmanaged(
    policy_id: str,
    name: Optional[str] = None,
    arn: Optional[str] = None,
    title: Optional[str] = None
) -> Dict[str, Any]:
    """Update an unmanaged policy.
    
    Args:
        policy_id: ID of policy to update
        name: New name (optional)
        arn: New ARN (optional)
        title: New title (optional)
        
    Returns:
        Dict with updated policy or error
    """
```

#### 7. `policy_delete()` - Delete Policy

**Function Signature:**
```python
async def admin_policy_delete(policy_id: str) -> Dict[str, Any]:
    """Delete a policy.
    
    Args:
        policy_id: ID of policy to delete
        
    Returns:
        Dict with success status or error
    """
```

**GraphQL Mutation:**
```graphql
mutation PolicyDelete($policyId: ID!) {
  policyDelete(id: $policyId) {
    ... on Ok {
      ok
    }
    ... on InvalidInput {
      errors {
        path
        message
      }
    }
    ... on OperationError {
      message
      name
    }
  }
}
```

**Validation:**
- ✅ `policy_id` cannot be empty

**Note:** Should check if policy is in use by any roles before deleting.

---

## Integration with Existing Code

### 1. Update `governance.py` Main Wrapper

Add to the `admin()` function:

**In docstring (line 57-75):**
```python
Available actions:
    # ... existing actions ...
    - policies_list: List all policies in the catalog
    - policy_get: Get details about a specific policy
    - policy_create_managed: Create a managed policy with bucket permissions
    - policy_create_unmanaged: Create an unmanaged policy with IAM ARN
    - policy_update_managed: Update a managed policy
    - policy_update_unmanaged: Update an unmanaged policy
    - policy_delete: Delete a policy
```

**In discovery mode (line 114-133):**
```python
"actions": [
    # ... existing actions ...
    "policies_list",
    "policy_get",
    "policy_create_managed",
    "policy_create_unmanaged",
    "policy_update_managed",
    "policy_update_unmanaged",
    "policy_delete",
],
```

**In dispatch_map (line 137-156):**
```python
dispatch_map = {
    # ... existing mappings ...
    "policies_list": admin_policies_list,
    "policy_get": admin_policy_get,
    "policy_create_managed": admin_policy_create_managed,
    "policy_create_unmanaged": admin_policy_create_unmanaged,
    "policy_update_managed": admin_policy_update_managed,
    "policy_update_unmanaged": admin_policy_update_unmanaged,
    "policy_delete": admin_policy_delete,
}
```

### 2. Update Tool Count

- Current: "11 tools" in UI
- After: Still "11 tools" (admin is one tool, just more actions)
- But update action count from 17 to **24 actions**

---

## Testing Requirements

### Unit Tests

Create `tests/unit/test_governance_policies.py`:

```python
"""Unit tests for policy management actions."""

import pytest
from unittest.mock import AsyncMock, patch
from quilt_mcp.tools import governance

@pytest.mark.asyncio
async def test_policies_list_discovery():
    """Test policy actions appear in discovery mode."""
    result = await governance.admin(action=None)
    assert "policies_list" in result["actions"]
    assert "policy_create_managed" in result["actions"]
    
@pytest.mark.asyncio
async def test_policy_create_managed_validation():
    """Test managed policy creation validates inputs."""
    result = await governance.admin(
        action="policy_create_managed",
        params={"name": ""}  # Empty name should fail
    )
    assert "error" in result
    assert "cannot be empty" in result["error"]
    
@pytest.mark.asyncio
async def test_policy_create_managed_success(mock_catalog_client):
    """Test successful managed policy creation."""
    # Mock GraphQL response
    mock_catalog_client.return_value = {
        "policyCreateManaged": {
            "__typename": "Policy",
            "id": "policy-123",
            "name": "TestPolicy",
            "permissions": []
        }
    }
    
    result = await governance.admin(
        action="policy_create_managed",
        params={
            "name": "TestPolicy",
            "permissions": [{"bucket_name": "test-bucket", "level": "READ"}]
        }
    )
    
    assert result["success"] is True
    assert result["policy"]["id"] == "policy-123"

# ... similar tests for all 7 actions
```

### Integration Tests

Add to `tests/integration/test_governance_integration.py`:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_policy_lifecycle():
    """Test create → list → get → update → delete policy flow."""
    
    # 1. Create managed policy
    create_result = await governance.admin(
        action="policy_create_managed",
        params={
            "name": "IntegrationTestPolicy",
            "title": "Test policy for integration tests",
            "permissions": [
                {"bucket_name": "test-bucket", "level": "READ"}
            ]
        }
    )
    assert create_result["success"] is True
    policy_id = create_result["policy"]["id"]
    
    # 2. List policies (should include new one)
    list_result = await governance.admin(action="policies_list")
    assert any(p["id"] == policy_id for p in list_result["policies"])
    
    # 3. Get specific policy
    get_result = await governance.admin(
        action="policy_get",
        params={"policy_id": policy_id}
    )
    assert get_result["policy"]["name"] == "IntegrationTestPolicy"
    
    # 4. Update policy
    update_result = await governance.admin(
        action="policy_update_managed",
        params={
            "policy_id": policy_id,
            "title": "Updated title"
        }
    )
    assert update_result["success"] is True
    
    # 5. Delete policy
    delete_result = await governance.admin(
        action="policy_delete",
        params={"policy_id": policy_id}
    )
    assert delete_result["success"] is True
    
    # 6. Verify deletion
    list_result = await governance.admin(action="policies_list")
    assert not any(p["id"] == policy_id for p in list_result["policies"])
```

### Browser Tests (via Qurator)

Test these workflows via `demo.quiltdata.com`:

1. **List all policies**
   - Prompt: "Use admin tool to list all policies"
   - Verify: Returns list of policies with IDs

2. **Create managed policy**
   - Prompt: "Create a managed policy named 'MCPTestPolicy' with READ access to bucket 'example-pharma-data'"
   - Verify: Policy created successfully, returns policy ID

3. **Create role with new policy**
   - Prompt: "Create a managed role named 'MCPTestRole' using the MCPTestPolicy"
   - Verify: Role created successfully (completing the full workflow!)

4. **Delete test resources**
   - Prompt: "Delete the MCPTestRole and MCPTestPolicy"
   - Verify: Both deleted successfully

---

## User Workflow Improvements

### Before (Current State) ❌

**To create a managed role:**
```
User → Quilt Catalog UI → Create Policies → Note IDs → MCP/Qurator → role_create
```
**Problem:** Context switching, manual tracking, not self-service

### After (With Policy Management) ✅

**Complete workflow via MCP:**
```
User → Qurator:
  1. "List available buckets" (search tool)
  2. "Create a managed policy 'DataSciencePolicy' with READ_WRITE access to example-pharma-data"
  3. "List all policies and show me the DataSciencePolicy ID"
  4. "Create a managed role 'DataScienceRole' with the DataSciencePolicy"
  5. "Assign user john.doe to the DataScienceRole"
```
**Benefit:** Fully self-service, no context switching, AI-guided workflow

---

## Implementation Checklist

- [ ] Create `src/quilt_mcp/tools/governance_impl_part3.py`
- [ ] Implement 7 policy management functions
- [ ] Update `src/quilt_mcp/tools/governance.py` imports
- [ ] Update `admin()` function docstring
- [ ] Update discovery mode action list
- [ ] Update dispatch_map
- [ ] Update `__all__` exports
- [ ] Create `tests/unit/test_governance_policies.py`
- [ ] Write 15+ unit tests (discovery, validation, success, error cases)
- [ ] Add integration tests to `tests/integration/test_governance_integration.py`
- [ ] Test full lifecycle: create → list → get → update → delete
- [ ] Update `ADMIN_ACTIONS_IMPLEMENTATION_REVIEW.md`
- [ ] Update `docs/architecture/MCP_OPTIMIZATION.md` tool matrix
- [ ] Update `src/quilt_mcp/optimization/scenarios.py` with policy scenarios
- [ ] Browser test all 7 actions via Qurator
- [ ] Test complete role creation workflow (policy → role)
- [ ] Update CHANGELOG.md
- [ ] Increment version number

---

## Success Criteria

✅ **All 7 policy actions implemented and tested**
✅ **Unit test coverage at 100%**
✅ **Integration tests pass for full lifecycle**
✅ **Browser tests confirm Qurator can use all actions**
✅ **Complete workflow: Create policy → Create role → Assign user works end-to-end**
✅ **Documentation updated to reflect 24 total admin actions**
✅ **No breaking changes to existing 17 actions**

---

## Estimated Effort

**Implementation:** ~4-6 hours
- governance_impl_part3.py: 2-3 hours (following existing patterns)
- governance.py updates: 30 minutes
- Unit tests: 1-2 hours
- Integration tests: 1 hour
- Documentation: 30 minutes

**Total:** ~6-8 hours including testing and documentation

---

## Questions for Implementer

1. **Permission levels:** Should we validate `level` is exactly "READ" or "READ_WRITE"?
2. **ARN validation:** Should we validate ARN format before sending to GraphQL?
3. **Update strategy:** For `policy_update_*`, should we fetch current policy first or require full input?
4. **Delete safety:** Should we prevent deleting policies that are in use by roles?
5. **Naming:** Keep `policy_create_managed` vs `policy_create` with `policy_type` param?

---

## References

- **GraphQL Schema:** `docs/quilt-enterprise-schema.graphql` (lines 169-174, 843-1003)
- **Existing Implementation:** `src/quilt_mcp/tools/governance_impl.py` (user management)
- **Existing Implementation:** `src/quilt_mcp/tools/governance_impl_part2.py` (role management)
- **Catalog Client:** `src/quilt_mcp/clients/catalog.py` (GraphQL helpers)
- **Test Patterns:** `tests/unit/test_governance.py`

---

## Notes for Codex

This spec follows the existing patterns in the codebase:
- All functions are async and return `Dict[str, Any]`
- Use `execute_graphql_query` and `execute_graphql_mutation` from catalog client
- Follow union type pattern: check `__typename` for `Policy`, `InvalidInput`, `OperationError`
- Use `format_error_response()` for consistent error formatting
- Follow TDD: Write tests first, then implementation
- Match the validation style from existing user/role functions

The implementation should be straightforward since the GraphQL schema is already defined and the patterns are established. The main work is translating GraphQL operations into Python functions with proper error handling.


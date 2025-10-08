# Deployment Summary: v0.6.70

**Date:** October 8, 2025, 3:35 PM  
**Version:** 0.6.70  
**Branch:** `integrate-module-tools`  
**Status:** ✅ Successfully Deployed to Production

## Issue Identified

After deploying v0.6.69 (which fixed the docstring clarity), users still encountered **400 BAD REQUEST** errors when trying to create policies via `admin.policy_create_managed`.

### Root Cause: GraphQL Schema Non-Compliance

The implementation did not match the actual GraphQL schema:

1. **Wrong parameter name**: Used `name` instead of `title` (Policy type has no `name` field)
2. **Wrong field name**: Used `bucketName` instead of `bucket` in PermissionInput
3. **Missing required field**: `roles` array was not included (schema requires it)
4. **Wrong query fields**: Queried for non-existent `name` field in Policy type

## GraphQL Schema Reference

```graphql
type Policy {
  id: ID!
  title: String!        # NOT "name"!
  arn: String!
  managed: Boolean!
  permissions: [PolicyBucketPermission!]!
  roles: [ManagedRole!]!
}

input ManagedPolicyInput {
  title: String!        # REQUIRED!
  permissions: [PermissionInput!]!
  roles: [ID!]!         # REQUIRED! (can be empty array)
}

input PermissionInput {
  bucket: String!       # NOT "bucketName"!
  level: BucketPermissionLevel!
}
```

## Changes Made

### 1. Fixed `admin_policy_create_managed` Function Signature

**Before:**
```python
async def admin_policy_create_managed(
    name: str,                                    # ❌ Wrong parameter
    permissions: Optional[List[Dict[str, Any]]] = None,
    title: Optional[str] = None,                  # ❌ Should be required
) -> Dict[str, Any]:
    input_payload = {
        "name": name.strip(),                     # ❌ Schema has no "name"
        "permissions": permissions_input,
    }
    if title:                                     # ❌ Conditional, should be required
        input_payload["title"] = title
    # ❌ Missing "roles" field
```

**After:**
```python
async def admin_policy_create_managed(
    title: str,                                   # ✅ Correct and required
    permissions: Optional[List[Dict[str, Any]]] = None,
    roles: Optional[List[str]] = None,            # ✅ Added required field
) -> Dict[str, Any]:
    input_payload = {
        "title": title.strip(),                   # ✅ Matches schema
        "permissions": permissions_input,
        "roles": roles or [],                     # ✅ Required by schema
    }
```

### 2. Fixed Permission Input Builder

**Before:**
```python
def _build_permissions_input(permissions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    # ...
    converted.append({"bucketName": bucket_name, "level": level})  # ❌ Wrong field
```

**After:**
```python
def _build_permissions_input(permissions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    # ...
    converted.append({"bucket": bucket_name, "level": level})      # ✅ Matches schema
```

### 3. Fixed GraphQL Query

**Before:**
```graphql
... on Policy {
  id
  name        # ❌ Policy type has no "name" field
  arn
  title
  # ...
}
```

**After:**
```graphql
... on Policy {
  id
  arn
  title       # ✅ Only existing fields
  managed     # ✅ Added boolean flag
  # ...
}
```

### 4. Updated Docstring and Examples

Updated `admin` tool docstring to use `title` instead of `name`:

```python
# Create a managed policy with bucket permissions
result = admin(action="policy_create_managed", params={
    "title": "DataSciencePolicy",              # ✅ Correct parameter
    "permissions": [
        {"bucket_name": "my-data-bucket", "level": "READ_WRITE"},
        {"bucket_name": "shared-bucket", "level": "READ"}
    ]
})
```

## Deployment Process

### Build & Push

```bash
# Fix GraphQL schema compliance
git commit -m "fix: correct GraphQL schema compliance for policy_create_managed"

# Bump version
version = "0.6.70"
git commit -m "chore: bump version to 0.6.70"

# Build with correct platform for ECS
python scripts/docker.py push --version 0.6.70 --platform linux/amd64
```

**Note:** Previous deployment failed due to wrong platform (Darwin/ARM64 instead of Linux/AMD64). Rebuilt with `--platform linux/amd64` flag.

### ECS Deployment

```bash
# Force new deployment (task definition already uses :latest)
aws ecs update-service \
  --cluster sales-prod \
  --service sales-prod-mcp-server-production \
  --force-new-deployment \
  --region us-east-1
```

**Deployment Timeline:**
- **3:27 PM** - First push (wrong platform)
- **3:30 PM** - Failed: "CannotPullContainerError: platform 'linux/amd64'"
- **3:31 PM** - Rebuilt with `--platform linux/amd64`
- **3:32 PM** - Pushed corrected image
- **3:33 PM** - Task started successfully
- **3:35 PM** - Deployment reached steady state ✅

## Verification

### ECS Task Status
```bash
$ aws ecs describe-services --cluster sales-prod \
  --services sales-prod-mcp-server-production \
  --region us-east-1 | jq '.services[0].events[0]'

{
  "message": "(service sales-prod-mcp-server-production) has reached a steady state."
}
```

### Image Verification
```bash
$ aws ecs describe-tasks --cluster sales-prod \
  --tasks $(aws ecs list-tasks --cluster sales-prod \
    --service-name sales-prod-mcp-server-production \
    --region us-east-1 --query 'taskArns[0]' --output text) \
  --region us-east-1 | jq '.tasks[0].containers[0].image'

"850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:latest"
```

## Expected Behavior

### Before (v0.6.69 and earlier)
```json
{
  "success": false,
  "error": "Failed to create managed policy: 400 Client Error: BAD REQUEST"
}
```

### After (v0.6.70)
```json
{
  "success": true,
  "policy": {
    "id": "abc123",
    "title": "TestPolicy",
    "arn": "arn:aws:iam::...:policy/...",
    "managed": true,
    "permissions": [
      {
        "bucket": {"name": "fl-158-raw"},
        "level": "READ_WRITE"
      }
    ]
  }
}
```

## Testing Instructions

On `demo.quiltdata.com`, test:

```
"Create a managed policy called 'TestPolicy' with READ_WRITE access to fl-158-raw"
```

**Expected:**
1. AI uses `admin.policy_create_managed` (not `role_create`) ✅
2. AI passes `title` parameter (not `name`) ✅
3. GraphQL request succeeds ✅
4. Policy is created ✅

## Files Modified

- `src/quilt_mcp/tools/governance.py` - Updated docstring and examples
- `src/quilt_mcp/tools/governance_impl_part3.py` - Fixed function signature, input builder, and GraphQL query
- `pyproject.toml` - Bumped version to 0.6.70

## Lessons Learned

1. **Always validate against the actual GraphQL schema**, not assumptions
2. **Check field names carefully** - `bucket` vs `bucketName`, `title` vs `name`
3. **All required fields must be provided** - even empty arrays like `roles: []`
4. **Docker platform matters** - ECS requires `linux/amd64`, not Darwin ARM64
5. **Test GraphQL queries directly** before implementing them in code

## Next Steps

- Monitor production logs for successful policy creation
- Consider adding GraphQL schema validation tests
- Update integration tests to cover policy creation happy path
- Document the policy → role → user workflow

## Related Issues

- v0.6.66: Added policy management actions
- v0.6.67: Implemented 7 policy actions
- v0.6.68: Created comprehensive unit tests
- v0.6.69: Clarified docstring to prevent AI confusion
- v0.6.70: Fixed GraphQL schema compliance (this release)

---

**Status:** Ready for testing on `demo.quiltdata.com` 🚀


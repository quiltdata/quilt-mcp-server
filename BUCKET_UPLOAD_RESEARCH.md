# Bucket Upload Research - Enterprise Repo Analysis

## TL;DR

**Upload via MCP server is NOT possible** with current JWT architecture.

The backend **intentionally does NOT provide** presigned upload URLs or direct S3 write access via GraphQL/REST APIs.

---

## What I Found

### 1. Package Construction Only Accepts S3 URIs

From `registry/quilt_server/graphql/schema.graphql`:

```graphql
input PackageConstructEntry {
  logicalKey: String!
  physicalKey: String!    # <-- Must be S3 URI (s3://bucket/key)
  hash: PackageEntryHash
  size: Float
  meta: JsonRecord
}
```

**Key Point**: `physicalKey` must be an existing S3 URI. The backend **does not accept inline data**.

### 2. Scratch Buckets Exist But Are Internal

Found in `registry/quilt_server/scratch_buckets.py`:

```python
SCRATCH_BUCKET_PREFIX = "quilt-scratch-"
USER_REQUESTS_PREFIX = "user-requests/"
USER_REQUESTS_ACTIONS = "s3:PutObject"
```

**But**: These are used internally by the backend, not exposed via GraphQL/REST APIs.

### 3. No Upload Endpoints Found

Searched for:
- ❌ Presigned POST/PUT URL generation
- ❌ GraphQL mutations for file upload
- ❌ REST endpoints for upload
- ❌ Direct AWS credentials in API responses

**Result**: The backend **intentionally does not provide these**.

### 4. SwitchRole Mutation Doesn't Help

```graphql
mutation {
  switchRole(roleName: String!): SwitchRoleResult!
}

type Me {
  name: String!
  email: String!
  isAdmin: Boolean!
  role: MyRole!
  roles: [MyRole!]!
  # <-- No AWS credentials!
}
```

The `switchRole` mutation changes user roles in the database, but **does NOT return AWS credentials**.

---

## Why This Design?

This is **intentional security architecture**:

1. **Backend Controls AWS Access**: The registry backend assumes IAM roles on behalf of users
2. **No Client-Side Credentials**: Clients never get direct AWS credentials
3. **Audit Trail**: All S3 operations go through the backend for logging/auditing
4. **Policy Enforcement**: Backend enforces bucket policies, user permissions, etc.

---

## How Users Upload Files

### Option 1: Quilt Web UI (Recommended)

The web UI has a file upload interface that:
1. User selects files in browser
2. Frontend uploads to backend endpoint
3. Backend handles S3 upload with proper IAM role
4. Returns S3 URIs for package construction

**This is the intended workflow** - we just don't have access to it from MCP.

### Option 2: AWS CLI + Package Construction

```bash
# User uploads with their own AWS credentials
aws s3 cp file.csv s3://my-bucket/data/file.csv

# Then creates package via MCP
mcp packaging.create \
  --name my-bucket/my-package \
  --files s3://my-bucket/data/file.csv
```

### Option 3: Backend Proxy (Future Enhancement)

**What would be needed**:

1. New GraphQL mutation or REST endpoint:
   ```graphql
   mutation {
     generateUploadUrl(
       bucket: String!
       key: String!
       contentType: String
     ): UploadUrlResult!
   }
   
   type UploadUrlResult {
     uploadUrl: String!      # Presigned POST URL
     fields: JsonRecord!     # POST form fields
     expires: DateTime!
   }
   ```

2. Backend implementation:
   - Assumes appropriate IAM role
   - Generates presigned POST URL
   - Returns to client
   - Client POSTs file directly to S3
   - Client then uses S3 URI in package construction

---

## Impact on MCP Server

### ❌ Cannot Fix: `buckets.objects_put`

This action **cannot be implemented** with current backend APIs because:
- No presigned upload URLs available
- No direct AWS credentials in JWT
- No upload proxy endpoints

### ✅ Workarounds Available

1. **For Package Creation**:
   - Users upload via Quilt web UI first
   - Then use `packaging.create` with S3 URIs

2. **For File Sharing**:
   - Use AWS CLI to upload
   - Use `packaging.create` with S3 URIs

3. **For Temporary Files**:
   - Users can't upload to scratch buckets from MCP
   - Must use web UI or AWS CLI

---

## Recommendations

### Short Term: Clear Documentation

Update `buckets.objects_put` to return helpful error:

```python
def bucket_objects_put(...):
    return {
        "success": False,
        "error": "File upload requires Quilt web UI or AWS CLI",
        "message": (
            "The MCP server cannot upload files because the backend does not "
            "provide presigned upload URLs or direct AWS credentials. "
            "This is intentional security design - the backend controls all S3 access."
        ),
        "workarounds": {
            "web_ui": "Upload files via Quilt catalog web interface",
            "aws_cli": "Upload with AWS CLI: aws s3 cp file.csv s3://bucket/key",
            "then_package": "After upload, use packaging.create with the S3 URI"
        },
        "backend_feature_needed": "generateUploadUrl GraphQL mutation"
    }
```

### Medium Term: Request Backend Feature

File an issue/PR for enterprise repo to add:
- `generateUploadUrl` mutation
- Presigned POST URL generation
- Support for temporary uploads to scratch buckets

### Long Term: Client-Side Upload Flow

If backend adds upload URLs, implement:
1. MCP tool requests upload URL from backend
2. MCP tool streams file content to presigned URL
3. MCP tool uses resulting S3 URI in package construction

---

## Final Status

| Action | Status | Reason |
|--------|--------|--------|
| `bucket_object_link` | ✅ **WORKS** | Uses browsing sessions |
| `bucket_object_fetch` | ✅ **WORKS** | Uses presigned download URLs |
| `bucket_object_info` | ✅ **WORKS** | HEAD request on presigned URL |
| `bucket_object_text` | ✅ **WORKS** | Uses object_fetch |
| `bucket_objects_put` | ❌ **BLOCKED** | No upload URLs in backend API |

**Conclusion**: 4 out of 5 bucket object actions are now functional! 🎉

The 5th action (`objects_put`) is architecturally blocked and requires backend API changes.

---

## Files Examined

- `registry/quilt_server/graphql/schema.graphql` - GraphQL schema
- `registry/quilt_server/graphql/packages.py` - Package mutations
- `registry/quilt_server/graphql/user.py` - User/role mutations
- `registry/quilt_server/scratch_buckets.py` - Scratch bucket system
- `registry/quilt_server/views/browse.py` - Browse/download endpoints
- `registry/quilt_server/views/packages.py` - Package validation endpoint

---

## Related Documents

- `BUCKET_TOOLS_BACKEND_PROXY_SOLUTION.md` - Download solution
- `NAVIGATION_CONTEXT_INTEGRATION.md` - Context usage
- `BUCKET_ACTIONS_FIXABILITY_ANALYSIS.md` - Original analysis (now outdated)


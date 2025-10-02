# Package Creation Workflow

## Architecture Overview

The Quilt MCP server uses a **stateless, JWT-based architecture** where:

- **JWT tokens are for authentication only** - they do not contain AWS credentials
- **The Quilt registry backend handles AWS access** by assuming IAM roles on behalf of authenticated users
- **Package creation happens via GraphQL** using the `packageConstruct` mutation

This architecture follows the same pattern as the Quilt Enterprise web interface.

## Why Can't MCP Upload Files Directly?

The MCP server **cannot upload files to S3** for the following reasons:

1. **JWT tokens don't include AWS credentials** - they're authentication tokens for the Quilt catalog API
2. **Registry backend manages AWS access** - the backend assumes IAM roles and provides credentials server-side
3. **GraphQL `packageConstruct` requires S3 URIs** - files must already exist in S3

This is **by design** - the Quilt architecture centralizes credential management in the registry backend, not in client applications.

## Current Workflow

To create a package with the MCP server, you **must** follow this two-step process:

### Step 1: Upload Files to S3

Files must be uploaded to S3 **before** creating a package. You have multiple options:

#### Option A: Quilt Web UI
1. Navigate to your bucket in the Quilt catalog
2. Use the "Upload" button to upload files
3. Note the S3 URIs of uploaded files

#### Option B: AWS CLI
```bash
# Upload a single file
aws s3 cp README.md s3://my-bucket/.quilt/packages/my-pkg/README.md

# Upload multiple files
aws s3 cp data.csv s3://my-bucket/.quilt/packages/my-pkg/data.csv
aws s3 cp analysis.py s3://my-bucket/.quilt/packages/my-pkg/analysis.py
```

#### Option C: Quilt Python SDK (quilt3)
```python
import quilt3 as q3

# Build and push a package
pkg = q3.Package()
pkg.set("README.md", "README.md")
pkg.set("data.csv", "data.csv")
pkg.push("my-bucket/my-pkg", registry="s3://my-bucket")
```

### Step 2: Create Package via MCP

Once files exist in S3, use the MCP `packaging.create` tool:

```json
{
  "action": "create",
  "params": {
    "name": "my-bucket/my-pkg",
    "files": [
      "s3://my-bucket/.quilt/packages/my-pkg/README.md",
      "s3://my-bucket/.quilt/packages/my-pkg/data.csv"
    ],
    "description": "My package description",
    "metadata": {
      "author": "John Doe",
      "version": "1.0.0"
    }
  }
}
```

The MCP server will:
1. Call the GraphQL `packageConstruct` mutation with the provided S3 URIs
2. The registry backend assumes the user's IAM role
3. The registry backend creates the package manifest
4. Return the package revision details

## Future Enhancement: Presigned URLs

A potential future enhancement would be to implement a **presigned URL flow**:

1. User requests: "I want to upload README.md"
2. MCP server calls registry endpoint: `POST /api/s3/presigned_upload_url`
3. Registry assumes role and generates presigned PUT URL
4. MCP server returns presigned URL to client
5. Client uploads file directly to S3 using presigned URL
6. MCP server calls `packageConstruct` with the S3 URI

This would require:
- New REST/GraphQL endpoint in the registry backend
- Registry backend to generate presigned URLs
- Frontend changes to handle direct-to-S3 uploads

**Status**: Not yet implemented. This would need to be added to the registry backend first.

## Error Messages You Might See

### "Package creation requires 'files' parameter"
**Cause**: You called `packaging.create` without providing S3 URIs.

**Solution**: Upload files to S3 first (via web UI or AWS CLI), then provide their S3 URIs.

### "JWT token did not include aws_credentials"
**Cause**: The MCP server tried to upload files directly, but the JWT doesn't contain AWS credentials.

**Solution**: Don't use the `readme` parameter. Upload files to S3 first, then reference them via S3 URIs.

### "GraphQL package creation failed: 400 Client Error"
**Cause**: The provided S3 URIs may not exist, or there's a permission issue.

**Solution**: 
- Verify files exist in S3: `aws s3 ls s3://bucket/path/`
- Ensure your user/role has access to those files
- Check that S3 URIs are in the correct format: `s3://bucket/key`

## Comparison with Other Tools

| Tool | Can Upload Files? | Why? |
|------|-------------------|------|
| **Quilt Web UI** | ✅ Yes | Frontend uploads directly to S3 using presigned URLs from registry |
| **Quilt Python SDK** | ✅ Yes | Uses local AWS credentials (ambient or configured) |
| **AWS CLI** | ✅ Yes | Uses local AWS credentials |
| **MCP Server** | ❌ No | JWT is auth-only; registry handles credentials server-side |

## Summary

**Key takeaway**: The MCP server orchestrates package creation via GraphQL but **cannot upload files**. Files must be uploaded through other means (web UI, AWS CLI, Python SDK) before creating packages via MCP.

This architecture ensures:
- ✅ Centralized credential management in the registry
- ✅ Consistent security model across all Quilt tools
- ✅ JWT tokens remain lightweight (auth only)
- ✅ No need to distribute AWS credentials to clients

For questions or feature requests, please contact the Quilt team or file an issue in the appropriate repository.


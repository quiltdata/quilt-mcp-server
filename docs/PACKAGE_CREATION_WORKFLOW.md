# Package Creation Workflow

## Architecture Overview

The Quilt MCP server uses a **stateless, JWT-based architecture** where:

- **JWT tokens are for authentication only** - they do not contain AWS credentials
- **The Quilt registry backend handles AWS access** by assuming IAM roles on behalf of authenticated users
- **Package creation happens via GraphQL** using the `packageConstruct` mutation

This architecture follows the same pattern as the Quilt Enterprise web interface.

## Uploading Files Through MCP

Starting in October 2025, the MCP server can upload objects directly to your Quilt buckets.  
The server mirrors the catalog web UI flow:

1. Request short-lived AWS credentials by calling the catalog’s `/api/auth/get_credentials` endpoint with the user’s JWT.
2. Build a request-scoped boto3 session using those credentials.
3. Stream file content to S3 via `bucket_objects_put`.

If the catalog is unreachable or you are running in an environment without Quilt authentication, the tool falls back to ambient AWS credentials (e.g., `AWS_PROFILE`, instance roles) so integration tests continue to work.

### Step 1: Upload Files with `bucket_objects_put` *(optional)*

```json
{
  "name": "bucket_objects_put",
  "arguments": {
    "bucket": "my-team-bucket",
    "items": [
      {
        "key": "packages/my-pkg/README.md",
        "text": "# My Package\\n\\nUploaded via MCP!",
        "content_type": "text/markdown"
      },
      {
        "key": "packages/my-pkg/data.csv",
        "data": "Y29sdW1uMSxjb2x1bW4yCjEsMgo=",
        "content_type": "text/csv",
        "metadata": {"source": "mcp-demo"}
      }
    ]
  }
}
```

The response includes the number of objects uploaded, individual results (ETag, VersionId), and diagnostics about the credential source.  
Behind the scenes, the MCP server calls `/api/auth/get_credentials`, builds an S3 client, and issues `PutObject` requests.

If the catalog cannot provide credentials (for example, when running locally without JWTs), `bucket_objects_put` attempts to use ambient credentials and clearly reports which path succeeded.

> **Tip:** If you call `packaging.create` with the `bucket` parameter and inline `readme` content, the tool uploads the README for you before constructing the package. Use `bucket_objects_put` directly only when you need custom paths or to upload additional assets yourself.

### Step 2: Create Package via MCP

Once your files are in S3, call the MCP `packaging.create` tool:

```json
{
  "action": "create",
  "params": {
    "name": "my-bucket/my-pkg",
    "bucket": "my-bucket",
    "files": [
      "s3://my-bucket/data.csv"
    ],
    "description": "My package description",
    "readme": "# My Package\n\nThis README was uploaded automatically by packaging.create.",
    "metadata": {
      "author": "John Doe",
      "version": "1.0.0"
    }
  }
}
```

The MCP server will:
1. Call the GraphQL `packageConstruct` mutation with the S3 URIs you uploaded
2. The registry backend assumes the user's IAM role
3. The registry backend creates the package manifest
4. Return the package revision details

## Error Messages You Might See

### "Package creation requires 'files' parameter"
**Cause**: You called `packaging.create` without providing any S3 URIs or inline README content.

**Solution**: Either supply existing S3 object URIs in `files`, or include a `readme` value (and `bucket`) so the tool can upload the README for you.

### "JWT token did not include aws_credentials"
**Cause**: The catalog refused to issue temporary credentials (for example, the JWT lacks the correct role or the user is unauthenticated).

**Solution**: Ensure you are logged in through the catalog, confirm your role can call `/api/auth/get_credentials`, or configure ambient AWS credentials as a fallback.

### "GraphQL package creation failed: 400 Client Error"
**Cause**: The provided S3 URIs may not exist, or there's a permission issue.

**Solution**: 
- Verify files exist in S3: `aws s3 ls s3://bucket/path/`
- Ensure your user/role has access to those files
- Check that S3 URIs are in the correct format: `s3://bucket/key`

## Deleting Packages via MCP

Use the `packaging.delete` action to remove a package when you have the appropriate permissions. Deletions require an explicit confirmation flag to prevent mistakes:

```json
{
  "action": "delete",
  "params": {
    "name": "my-bucket/my-pkg",
    "bucket": "my-bucket",
    "confirm": true
  }
}
```

Add `"dry_run": true` instead of `confirm` to preview the target registry/bucket and the confirmation instructions without deleting anything.

## Requesting Write Access

If you receive an `AccessDenied` error while uploading files (for example when `packaging.create` tries to add a README), your Quilt account lacks write access to the target bucket. Use the permissions tool to inspect your current access and share the diagnostic output with an administrator:

```json
{
  "name": "permissions",
  "arguments": {
    "action": "discover",
    "params": { "check_buckets": ["my-team-bucket"] }
  }
}
```

The result highlights whether you have `read_access` or `write_access`. If you need an upgrade, request it through your standard Quilt governance process (catalog UI request or admin ticket). The MCP server cannot bypass AWS permissions; it relies on the same short-lived credentials issued by the catalog.

## Generate Package Visualizations

Packages feel “complete” when they include documentation, metadata, and dashboards. Use the `package_visualization` tool to enrich an existing package with a README, `quilt_summarize.json`, and automatically generated visualizations.

```json
{
  "name": "package_visualization",
  "arguments": {
    "action": "enrich",
    "params": {
      "package_name": "example-team/cellpainting-csv-data",
      "bucket": "quilt-sandbox-bucket"
    }
  }
}
```

The tool performs the following:

- Scans package entries and builds `quilt_summarize.json` using Quilt’s visualization spec.
- Creates or updates `.quilt/packages/<pkg>/README.md` when one is missing.
- Detects embedded HTML dashboards (for example MultiQC reports) and surfaces them in the summary.
- Adds quick previews for tabular assets (`.csv`, `.tsv`, `.parquet`, `.json`).
- Uploads the generated assets to the bucket and records them in the latest package revision.

If the stack does not allow direct HTML embedding, you can edit the generated `quilt_summarize.json` to disable dashboards. The tool never enables Voila; notebook rendering must already be configured in the stack before you reference it in the summary.

## Comparison with Other Tools

| Tool | Can Upload Files? | Why? |
|------|-------------------|------|
| **Quilt Web UI** | ✅ Yes | Frontend uploads directly to S3 using presigned URLs from registry |
| **Quilt Python SDK** | ✅ Yes | Uses local AWS credentials (ambient or configured) |
| **AWS CLI** | ✅ Yes | Uses local AWS credentials |
| **MCP Server** | ✅ Yes | Requests temporary AWS credentials from `/api/auth/get_credentials` and uploads via `bucket_objects_put` |

## Summary

**Key takeaway**: The MCP server now supports end-to-end package creation. Use `bucket_objects_put` to upload files with Quilt-issued credentials, then call `packaging.create` to assemble the package manifest.

The architecture still keeps sensitive AWS access centralized:
- ✅ Credentials are short-lived and issued per request
- ✅ Catalog policy continues to enforce IAM roles and auditing
- ✅ Ambient credentials remain an optional fallback for automated testing

For questions or feature requests, please contact the Quilt team or file an issue in the appropriate repository.

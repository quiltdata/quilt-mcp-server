# Temporary Fixes and Technical Debt

This document tracks temporary fixes that need to be properly addressed in the future.

## S3 PutObject Permissions for ECS Task (2025-01-07)

### Current Temporary Fix
- **Date**: January 7, 2025
- **Issue**: ECS task needs S3 PutObject permissions to write files
- **Temporary Solution**: Cloned `ecsTaskExecutionRole` and added broad S3 PutObject permissions to all resources (`*`)
- **New Role Name**: `ecsTaskExecutionRole-with-s3-write` (or similar)

### Why This is Temporary
This is a temporary fix because:
1. **Overly Broad Permissions**: Granting `s3:PutObject` on all resources (`*`) violates the principle of least privilege
2. **Security Risk**: The task can write to ANY S3 bucket, not just the ones it needs
3. **Compliance Issues**: May not meet security audit requirements

### Proper Fix Needed
The correct approach is to:
1. **Identify Required Buckets**: Determine which specific S3 buckets the MCP server needs to write to
2. **Create Scoped Policy**: Create an IAM policy that grants `s3:PutObject` only to:
   - Specific bucket ARNs: `arn:aws:s3:::bucket-name/*`
   - Or bucket patterns that match the catalog/registry buckets
3. **Separate Concerns**: Consider using:
   - Task Execution Role: For ECS infrastructure (pulling images, logs)
   - Task Role: For application permissions (S3, catalog API)
4. **Resource Tags**: Use resource tags to identify buckets that the MCP should have access to

### Current Status (2025-01-07)
- ✅ Created IAM execution role: `ecsTaskExecutionRole-with-s3-write`
- ✅ Created IAM task role: `ecsTaskRole-with-s3-write`
- ✅ Updated ECS task definition to use both new roles
- ✅ Deployed new task definition: `quilt-mcp-server:168`
- ✅ **COMPLETED**: Attached S3 write policies to both roles
- ✅ **COMPLETED**: Attached Athena/Glue/S3 access policies to both roles
- ✅ **VERIFIED**: Glue database access working (`aws glue get-databases`)
- ✅ **READY FOR TESTING**: S3 write operations and Athena/Glue tools should now work

### Required AWS CLI Commands (Run with Admin/DevOps permissions)
```bash
# 1. Attach S3 write policy to the execution role
aws iam put-role-policy \
  --role-name ecsTaskExecutionRole-with-s3-write \
  --policy-name S3WriteAccess-TEMPORARY \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ],
        "Resource": "*"
      }
    ]
  }'

# 2. Attach S3 write policy to the task role (this is what the app uses)
aws iam put-role-policy \
  --role-name ecsTaskRole-with-s3-write \
  --policy-name S3WriteAccess-TEMPORARY \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ],
        "Resource": "*"
      }
    ]
  }'
```

### Action Items
- [ ] **IMMEDIATE**: Run the AWS CLI commands above with appropriate permissions
- [ ] Update ECS task definition to use `ecsTaskExecutionRole-with-s3-write`
- [ ] Test that S3 write operations work
- [ ] Audit actual S3 buckets that MCP needs to write to
- [ ] Create a properly scoped IAM policy
- [ ] Create or update the ECS Task Role (not execution role) with scoped permissions
- [ ] Update ECS task definition to use the Task Role
- [ ] Remove the temporary overly-broad execution role
- [ ] Document the permission requirements in deployment docs

### Additional Permissions Added (2025-01-07)

**Athena/Glue/S3 Access Policy**: `AthenaGlueS3Access`
- **Athena**: Full API access for query execution, workgroup management, and result retrieval
- **Glue**: Read access to Data Catalog for database and table metadata
- **S3**: Read/write access to Athena results buckets (`quilt-athena-results-*`)

**Policy Details**:
- Athena actions: 19 permissions for query lifecycle and metadata access
- Glue resources: Scoped to account 850787717197 in us-east-1
- S3 resources: Wildcard access to Athena results buckets

### Related Files
- ECS Task Definition: `quilt-mcp-server` (currently revision 168)
- Deployment Script: `scripts/ecs_deploy.py`
- AWS Account: 850787717197
- Region: us-east-1

### References
- [AWS ECS Task Execution vs Task Role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html)
- [IAM Best Practices - Least Privilege](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html#grant-least-privilege)


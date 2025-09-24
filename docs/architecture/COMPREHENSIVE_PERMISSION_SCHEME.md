# Comprehensive Permission Scheme for Quilt MCP Server

## Overview

This document describes the comprehensive permission scheme implemented for the Quilt MCP Server, providing fine-grained, tool-based access control for AWS operations. The system ensures users receive exactly the permissions they need, nothing more, following the principle of least privilege.

## Architecture

### Core Components

1. **BearerAuthService**: Central authentication and authorization service
2. **Tool-Permission Mapping**: Granular mapping of MCP tools to AWS permissions
3. **Role-Based Access Control**: Flexible role definitions with tool-based permissions
4. **JWT Claims Processing**: Extraction and validation of authorization information

### Design Principles

- **Tool-Based Permissions**: Each MCP tool has specific AWS permissions mapped to it
- **Least Privilege**: Users get exactly what they need, nothing more
- **Transparent**: Clear mapping between tools and required permissions
- **Extensible**: Easy to add new tools, roles, and permission categories
- **Self-Service**: Users can discover their available tools and permissions

## Permission Categories

### 1. S3 Bucket Operations
**Tools**: `bucket_objects_list`, `bucket_object_info`, `bucket_object_text`, `bucket_object_fetch`, `bucket_objects_put`, `bucket_object_link`

**AWS Permissions**:
- `s3:ListBucket` - List bucket contents
- `s3:GetObject` - Read objects
- `s3:GetObjectVersion` - Read versioned objects
- `s3:PutObject` - Upload objects
- `s3:PutObjectAcl` - Set object ACLs
- `s3:DeleteObject` - Delete objects
- `s3:GetBucketLocation` - Get bucket region

### 2. Package Operations
**Tools**: `package_create`, `package_update`, `package_delete`, `package_browse`, `package_contents_search`, `package_diff`, `create_package_enhanced`, `create_package_from_s3`, `package_create_from_s3`

**AWS Permissions**:
- `s3:PutObject` - Upload package files
- `s3:PutObjectAcl` - Set ACLs
- `s3:ListBucket` - Check existing files
- `s3:GetObject` - Read existing metadata
- `s3:DeleteObject` - Remove old files

### 3. Athena/Glue Operations
**Tools**: `athena_query_execute`, `athena_databases_list`, `athena_tables_list`, `athena_table_schema`, `athena_workgroups_list`, `athena_query_history`

**AWS Permissions**:
- `athena:StartQueryExecution` - Execute queries
- `athena:GetQueryExecution` - Get query status
- `athena:GetQueryResults` - Retrieve results
- `athena:StopQueryExecution` - Cancel queries
- `glue:GetDatabases` - List databases
- `glue:GetTables` - List tables
- `glue:GetTable` - Read table schemas

### 4. Tabulator Operations
**Tools**: `tabulator_tables_list`, `tabulator_table_create`

**AWS Permissions**:
- `glue:CreateTable` - Create new tables
- `glue:GetTable` - Read table metadata
- `s3:ListBucket` - List bucket contents

### 5. Search Operations
**Tools**: `unified_search`, `packages_search`

**AWS Permissions**:
- `s3:ListBucket` - List bucket contents
- `glue:GetTables` - Read table metadata
- `glue:GetDatabases` - List databases

### 6. Permission Discovery
**Tools**: `aws_permissions_discover`, `bucket_access_check`, `bucket_recommendations_get`

**AWS Permissions**:
- `iam:ListAttachedUserPolicies` - List user policies
- `iam:ListUserPolicies` - List inline policies
- `iam:GetPolicy` - Read policy documents
- `s3:ListAllMyBuckets` - List accessible buckets

## Role Definitions

### ReadWriteQuiltV2-sales-prod
**Authorization Level**: WRITE
**Buckets**: `quilt-sandbox-bucket`, `quilt-sales-prod`
**Tools**: All tools (full access)
**Description**: Full read/write access to sales production buckets with all tool capabilities

### ReadOnlyQuilt
**Authorization Level**: READ
**Buckets**: `quilt-sandbox-bucket`
**Tools**: Read-only operations (S3 read, package browse, Athena queries, search)
**Description**: Read-only access to sandbox bucket with query capabilities

### AdminQuilt
**Authorization Level**: ADMIN
**Buckets**: `*` (all buckets)
**Tools**: `*` (all tools)
**Description**: Administrative access to all buckets and operations

## Implementation Details

### JWT Claims Processing

The system processes JWT tokens to extract authorization claims:

```python
{
    "roles": ["ReadWriteQuiltV2-sales-prod"],
    "permissions": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
    "scopes": ["read", "write"],
    "user_id": "user123",
    "username": "john.doe",
    "email": "john.doe@company.com"
}
```

### Permission Validation Flow

1. **Token Validation**: Parse and validate JWT token
2. **Claims Extraction**: Extract roles, permissions, and scopes
3. **Role Mapping**: Map roles to tool permissions
4. **Tool Validation**: Check if user has access to requested tool
5. **Bucket Validation**: Verify bucket access if specified
6. **AWS Permission Check**: Validate required AWS permissions

### New MCP Tools

#### `validate_tool_access(tool_name, bucket_name)`
Validates if the current user has permission to use a specific tool.

**Parameters**:
- `tool_name`: Name of the tool/operation (e.g., "bucket_objects_list")
- `bucket_name`: Optional bucket name for bucket-specific validation

**Returns**:
```json
{
    "success": true,
    "allowed": true,
    "tool": "bucket_objects_list",
    "bucket": "quilt-sandbox-bucket",
    "reason": null,
    "message": "Tool 'bucket_objects_list' allowed"
}
```

#### `list_available_tools()`
Lists all available tools and their permission requirements.

**Returns**:
```json
{
    "success": true,
    "user_permissions": {
        "level": "write",
        "buckets": ["quilt-sandbox-bucket", "quilt-sales-prod"],
        "tools": ["bucket_objects_list", "package_create", ...]
    },
    "tool_categories": {
        "s3_bucket_operations": {
            "description": "S3 bucket and object operations",
            "tools": {
                "bucket_objects_list": {
                    "allowed": true,
                    "permissions": ["s3:ListBucket", "s3:GetBucketLocation"],
                    "description": "User has access to bucket_objects_list"
                }
            }
        }
    }
}
```

## Security Benefits

### 1. Principle of Least Privilege
- Users receive exactly the permissions they need
- No over-permissioning or unnecessary access
- Clear separation between read and write operations

### 2. Transparent Access Control
- Clear mapping between tools and permissions
- Self-service permission discovery
- Easy debugging of access issues

### 3. Granular Control
- Tool-level permission validation
- Bucket-specific access control
- Operation-specific permissions

### 4. Audit Trail
- Clear logging of permission checks
- Traceable access decisions
- Compliance-ready access control

## Usage Examples

### Check Tool Access
```python
# Validate bucket listing access
result = validate_tool_access("bucket_objects_list", "quilt-sandbox-bucket")
if result["allowed"]:
    print("User can list bucket objects")
else:
    print(f"Access denied: {result['reason']}")
```

### Discover Available Tools
```python
# Get user's available tools
tools = list_available_tools()
for category, info in tools["tool_categories"].items():
    print(f"{category}: {info['description']}")
    for tool_name, tool_info in info["tools"].items():
        if tool_info["allowed"]:
            print(f"  ✓ {tool_name}")
        else:
            print(f"  ✗ {tool_name}")
```

### Package Creation with Permission Check
```python
# Check if user can create packages
result = validate_tool_access("package_create", "quilt-sandbox-bucket")
if result["allowed"]:
    # Proceed with package creation
    package_create("my-team/dataset", ["s3://bucket/file.csv"])
else:
    print(f"Cannot create packages: {result['reason']}")
```

## Configuration

### Adding New Tools

1. **Define Tool Permissions**:
```python
self.tool_permissions["new_tool"] = [
    "s3:GetObject",
    "s3:ListBucket"
]
```

2. **Update Role Mappings**:
```python
"ReadWriteQuiltV2-sales-prod": {
    "tools": [
        # ... existing tools ...
        "new_tool"
    ]
}
```

### Adding New Roles

```python
"CustomRole": {
    "level": AuthorizationLevel.READ,
    "buckets": ["custom-bucket"],
    "tools": ["bucket_objects_list", "package_browse"],
    "description": "Custom role for specific operations"
}
```

## Monitoring and Debugging

### Permission Validation Logs
```python
logger.info("Tool '%s' authorized with permissions: %s", tool_name, required_permissions)
logger.warning("Tool '%s' not in allowed tools: %s", tool_name, allowed_tools)
logger.error("Bucket '%s' not in allowed buckets: %s", bucket_name, allowed_buckets)
```

### Common Issues and Solutions

1. **Missing Tool Access**:
   - Check if tool is in user's allowed tools list
   - Verify role mapping includes the tool
   - Use `list_available_tools()` to debug

2. **Bucket Access Denied**:
   - Verify bucket is in user's allowed buckets
   - Check role bucket permissions
   - Use `validate_tool_access()` with bucket parameter

3. **AWS Permission Errors**:
   - Verify tool-permission mapping is correct
   - Check if AWS IAM role has required permissions
   - Use `aws_permissions_discover()` to debug

## Future Enhancements

### 1. Dynamic Permission Loading
- Load permissions from external configuration
- Support for environment-specific permissions
- Runtime permission updates

### 2. Advanced Role Hierarchies
- Inherited permissions
- Role composition
- Conditional permissions

### 3. Audit and Compliance
- Detailed access logs
- Permission change tracking
- Compliance reporting

### 4. Performance Optimization
- Permission caching
- Batch permission checks
- Lazy permission loading

## Conclusion

The comprehensive permission scheme provides a robust, secure, and maintainable foundation for access control in the Quilt MCP Server. By mapping permissions directly to tools and operations, the system ensures users receive exactly the access they need while maintaining clear audit trails and debugging capabilities.

The tool-based approach makes it easy to understand what permissions are required for each operation, simplifies troubleshooting, and provides a foundation for future enhancements in security and access control.

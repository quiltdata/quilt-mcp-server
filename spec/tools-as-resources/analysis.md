# Tools-as-Resources Analysis

## Overview

This document analyzes the difference between the `legacy_0_7_2` branch (which had MCP Resources) and the current `jwt-merge` branch (which removed them), to identify which tools should actually be implemented as MCP Resources according to the Model Context Protocol specification.

## Background

### What Changed

In the `legacy_0_7_2` branch, the codebase had a complete MCP Resources framework located in `src/quilt_mcp/resources/`:

- **Base Framework**: `base.py` - Provided `MCPResource`, `ResourceResponse`, and `ResourceRegistry` classes
- **Admin Resources**: `admin.py` - `AdminUsersResource`, `AdminRolesResource`
- **S3 Resources**: `s3.py` - `S3BucketsResource`
- **Athena Resources**: `athena.py` - `AthenaDatabasesResource`, `AthenaWorkgroupsResource`
- **Metadata Resources**: `metadata.py` - `MetadataTemplatesResource`, `MetadataExamplesResource`, `MetadataTroubleshootingResource`
- **Workflow Resources**: `workflow.py` - `WorkflowResource`
- **Package Resources**: `package.py` - `PackageToolsResource`
- **Tabulator Resources**: `tabulator.py` - `TabulatorTablesResource`

**All of these resources were deleted** in the transition to `jwt-merge`. The entire `src/quilt_mcp/resources/` directory no longer exists.

## MCP Protocol: Tools vs Resources

According to the Model Context Protocol specification:

### MCP Tools
**Purpose**: Enable agents to perform actions and computations
**Characteristics**:
- Execute operations (create, update, delete)
- Perform calculations or transformations
- Trigger side effects
- Accept parameters for customization
- Return results of operations

**Examples**: Create a package, execute a query, upload files, delete a user

### MCP Resources
**Purpose**: Expose data and information that agents can read
**Characteristics**:
- Provide read-only or primarily informational content
- Return relatively static or slowly-changing data
- Used for discovery and exploration
- Often return lists or catalogs
- No side effects on the system

**Examples**: List available databases, enumerate users, show configuration options, display templates

## Current State Analysis

### Current Tools (jwt-merge branch)

After analyzing the current tool set, here are the tools categorized by their primary function:

#### 1. Authentication & Configuration Tools (Should likely be Resources)
- `auth_status()` - Audit Quilt authentication ✅ **RESOURCE CANDIDATE**
- `catalog_info()` - Summarize catalog configuration ✅ **RESOURCE CANDIDATE**
- `catalog_name()` - Identify catalog name ✅ **RESOURCE CANDIDATE**
- `filesystem_status()` - Probe filesystem access ✅ **RESOURCE CANDIDATE**

#### 2. List/Discovery Tools (Strong Resource Candidates)

**Admin/Governance:**
- `admin_roles_list()` - List all available roles ✅ **RESOURCE CANDIDATE**
- `admin_users_list()` - List all users in registry ✅ **RESOURCE CANDIDATE**
- `admin_sso_config_get()` - Get SSO configuration ✅ **RESOURCE CANDIDATE**
- `admin_tabulator_open_query_get()` - Get tabulator open query status ✅ **RESOURCE CANDIDATE**

**Athena/Glue:**
- `athena_databases_list()` - List available databases ✅ **RESOURCE CANDIDATE**
- `athena_workgroups_list()` - List available workgroups ✅ **RESOURCE CANDIDATE**
- `athena_query_history()` - Retrieve query execution history ✅ **RESOURCE CANDIDATE**

**Buckets:**
- `bucket_objects_list()` - List objects in S3 bucket ✅ **RESOURCE CANDIDATE**

**Tabulator:**
- `tabulator_buckets_list()` - List all buckets in Tabulator catalog ✅ **RESOURCE CANDIDATE**
- `tabulator_tables_list()` - List tabulator tables for a bucket ✅ **RESOURCE CANDIDATE**
- `tabulator_open_query_status()` - Get open query feature status ✅ **RESOURCE CANDIDATE**

**Metadata:**
- `list_metadata_templates()` - List available metadata templates ✅ **RESOURCE CANDIDATE**
- `show_metadata_examples()` - Show metadata usage examples ✅ **RESOURCE CANDIDATE**
- `fix_metadata_validation_issues()` - Provide troubleshooting guidance ✅ **RESOURCE CANDIDATE**

**Package Management:**
- `list_package_tools()` - List package management tools ✅ **RESOURCE CANDIDATE**
- `list_available_resources()` - Auto-detect buckets and registries ✅ **RESOURCE CANDIDATE**

**Workflow:**
- `workflow_list_all()` - List all workflows ✅ **RESOURCE CANDIDATE**
- `workflow_get_status()` - Get workflow status ✅ **RESOURCE CANDIDATE**

**Permissions:**
- `aws_permissions_discover()` - Discover AWS permissions ✅ **RESOURCE CANDIDATE**
- `bucket_recommendations_get()` - Get bucket recommendations ✅ **RESOURCE CANDIDATE**

#### 3. Query/Read Tools (Borderline - could be either)
- `athena_query_execute()` - Execute SQL query ⚠️ **BORDERLINE** (has side effects in Athena)
- `athena_table_schema()` - Get table schema ✅ **RESOURCE CANDIDATE**
- `bucket_object_info()` - Get object metadata ✅ **RESOURCE CANDIDATE**
- `bucket_object_text()` - Read text content ✅ **RESOURCE CANDIDATE**
- `bucket_object_fetch()` - Fetch binary/text data ✅ **RESOURCE CANDIDATE**
- `bucket_objects_search()` - Search objects ✅ **RESOURCE CANDIDATE**
- `bucket_objects_search_graphql()` - Search via GraphQL ✅ **RESOURCE CANDIDATE**
- `package_browse()` - Browse package contents ✅ **RESOURCE CANDIDATE**
- `packages_search()` - Search for packages ✅ **RESOURCE CANDIDATE**
- `package_contents_search()` - Search within package ✅ **RESOURCE CANDIDATE**
- `tabulator_bucket_query()` - Execute SQL against bucket ⚠️ **BORDERLINE** (read-only query)

#### 4. Write/Action Tools (Should remain Tools)
- `configure_catalog()` - Configure catalog URL ❌ **KEEP AS TOOL**
- `switch_catalog()` - Switch catalog ❌ **KEEP AS TOOL**
- `package_create()` - Create package ❌ **KEEP AS TOOL**
- `package_update()` - Update package ❌ **KEEP AS TOOL**
- `package_delete()` - Delete package ❌ **KEEP AS TOOL**
- `bucket_objects_put()` - Upload objects ❌ **KEEP AS TOOL**
- `admin_user_create()` - Create user ❌ **KEEP AS TOOL**
- `admin_user_delete()` - Delete user ❌ **KEEP AS TOOL**
- `admin_user_set_*()` - Various user modifications ❌ **KEEP AS TOOL**
- `admin_sso_config_set()` - Set SSO config ❌ **KEEP AS TOOL**
- `tabulator_table_create()` - Create table ❌ **KEEP AS TOOL**
- `tabulator_table_delete()` - Delete table ❌ **KEEP AS TOOL**
- `workflow_create()` - Create workflow ❌ **KEEP AS TOOL**
- `workflow_add_step()` - Add workflow step ❌ **KEEP AS TOOL**

#### 5. Utility/Helper Tools
- `catalog_uri()` - Build Quilt+ URI ⚠️ **UTILITY** (could be either)
- `catalog_url()` - Generate catalog URL ⚠️ **UTILITY** (could be either)
- `bucket_object_link()` - Generate presigned URL ❌ **KEEP AS TOOL** (creates temporary credential)
- `athena_query_validate()` - Validate SQL syntax ⚠️ **UTILITY** (read-only validation)
- `package_validate()` - Validate package ⚠️ **UTILITY** (read-only validation)
- `search_explain()` - Explain search query ✅ **RESOURCE CANDIDATE**
- `search_suggest()` - Get search suggestions ✅ **RESOURCE CANDIDATE**

## Recommendations

### High Priority - Should Definitely Be Resources

These tools are purely informational, have no side effects, and return discovery/configuration data:

1. **Authentication & Status Resources** (`auth://`)
   - `auth://status` → `auth_status()`
   - `auth://catalog/info` → `catalog_info()`
   - `auth://catalog/name` → `catalog_name()`
   - `auth://filesystem/status` → `filesystem_status()`

2. **Admin Resources** (`admin://`)
   - `admin://users` → `admin_users_list()`
   - `admin://users/{name}` → `admin_user_get(name)`
   - `admin://roles` → `admin_roles_list()`
   - `admin://sso/config` → `admin_sso_config_get()`
   - `admin://tabulator/open-query` → `admin_tabulator_open_query_get()`

3. **Athena Resources** (`athena://`)
   - `athena://databases` → `athena_databases_list()`
   - `athena://workgroups` → `athena_workgroups_list()`
   - `athena://databases/{db}/tables/{table}/schema` → `athena_table_schema()`
   - `athena://queries/history` → `athena_query_history()`

4. **Metadata Resources** (`metadata://`)
   - `metadata://templates` → `list_metadata_templates()`
   - `metadata://templates/{name}` → `get_metadata_template(name)`
   - `metadata://examples` → `show_metadata_examples()`
   - `metadata://troubleshooting` → `fix_metadata_validation_issues()`

5. **Tabulator Resources** (`tabulator://`)
   - `tabulator://buckets` → `tabulator_buckets_list()`
   - `tabulator://buckets/{bucket}/tables` → `tabulator_tables_list(bucket)`
   - `tabulator://open-query/status` → `tabulator_open_query_status()`

6. **Workflow Resources** (`workflow://`)
   - `workflow://workflows` → `workflow_list_all()`
   - `workflow://workflows/{id}` → `workflow_get_status(id)`

7. **Permissions Resources** (`permissions://`)
   - `permissions://discover` → `aws_permissions_discover()`
   - `permissions://buckets/{bucket}/access` → `bucket_access_check(bucket)`
   - `permissions://recommendations` → `bucket_recommendations_get()`

### Medium Priority - Consider As Resources

These have some characteristics of resources but may involve computation or have borderline use cases:

8. **Bucket Object Resources** (`s3://` or `bucket://`)
   - `s3://{bucket}/objects` → `bucket_objects_list(bucket, prefix)`
   - `s3://{bucket}/objects/{key}` → `bucket_object_info(s3_uri)` (metadata)
   - `s3://{bucket}/objects/{key}/content` → `bucket_object_text(s3_uri)` (actual content)

9. **Package Resources** (`package://`)
   - `package://{registry}/packages` → `packages_search()` (with default query)
   - `package://{registry}/packages/{name}` → `package_browse(name)`
   - `package://{registry}/tools` → `list_package_tools()`

10. **Search/Discovery Resources** (`search://`)
    - `search://explain` → `search_explain(query)`
    - `search://suggest` → `search_suggest(partial_query)`

### Lower Priority - Keep As Tools For Now

These either have side effects, perform significant computation, or are primarily action-oriented:

- All `*_create()`, `*_update()`, `*_delete()`, `*_set_*()` functions
- `athena_query_execute()` (creates query execution in Athena)
- `tabulator_bucket_query()` (executes query, has costs)
- `bucket_object_link()` (generates credentials)
- `bucket_objects_put()` (writes data)
- URL/URI builders (`catalog_uri()`, `catalog_url()`)

## Implementation Strategy

### Phase 1: Core Discovery Resources
Implement the most clear-cut cases that align with the legacy resources:

```python
# Resource URIs matching legacy implementation
admin://users
admin://roles
athena://databases
athena://workgroups
metadata://templates
metadata://examples
metadata://troubleshooting
workflow://workflows
tabulator://{bucket}/tables
```

### Phase 2: Extended Discovery Resources
Add new resources that weren't in legacy but follow the same pattern:

```python
auth://status
auth://catalog/info
permissions://discover
permissions://recommendations
tabulator://buckets
```

### Phase 3: Content Resources
Consider whether to expose actual data content as resources:

```python
s3://{bucket}/objects
s3://{bucket}/objects/{key}
package://{registry}/packages
package://{registry}/packages/{name}
```

## URI Scheme Design

Following the legacy implementation and MCP best practices:

### Scheme Conventions

| Scheme | Purpose | Authentication | Examples |
|--------|---------|---------------|----------|
| `admin://` | Administrative functions | Requires admin credentials | `admin://users`, `admin://roles` |
| `auth://` | Authentication status | Current user | `auth://status`, `auth://catalog/info` |
| `athena://` | AWS Athena/Glue | AWS credentials | `athena://databases`, `athena://workgroups` |
| `metadata://` | Metadata help/templates | None (documentation) | `metadata://templates`, `metadata://examples` |
| `tabulator://` | Tabulator catalog | Quilt credentials | `tabulator://buckets`, `tabulator://buckets/my-bucket/tables` |
| `workflow://` | Workflow tracking | Current user | `workflow://workflows`, `workflow://workflows/{id}` |
| `permissions://` | AWS permissions | AWS credentials | `permissions://discover`, `permissions://recommendations` |
| `s3://` | S3 bucket content | AWS credentials | `s3://my-bucket/objects`, `s3://my-bucket/objects/key` |
| `package://` | Quilt packages | Quilt credentials | `package://my-registry/packages`, `package://my-registry/packages/name` |

### Path Patterns

1. **List Pattern**: `scheme://collection`
   - Returns list of items
   - Example: `admin://users` → list of users

2. **Item Pattern**: `scheme://collection/{id}`
   - Returns single item details
   - Example: `admin://users/john` → user details

3. **Nested Pattern**: `scheme://collection/{id}/subcollection`
   - Returns nested collection
   - Example: `tabulator://buckets/my-bucket/tables` → tables in bucket

4. **Property Pattern**: `scheme://collection/{id}/property`
   - Returns specific property
   - Example: `athena://databases/mydb/tables/mytable/schema` → table schema

## Benefits of Resources Over Tools

### 1. Better MCP Semantics
- Resources clearly indicate "read-only, informational"
- Tools clearly indicate "actions with side effects"
- Agents can make better decisions about when to use each

### 2. Caching Opportunities
- MCP clients can cache resource responses
- List endpoints are naturally cacheable
- Reduces unnecessary API calls

### 3. Discovery Support
- Resources can be enumerated via `resources/list`
- Clients can build UI elements from resource URIs
- Better IDE integration and tooling

### 4. URI-Based Access
- RESTful URI patterns are intuitive
- Hierarchical organization is clear
- Compatible with browser-based tools

### 5. Reduced Parameter Complexity
- Resources encode parameters in URI path
- Less ambiguity about required vs optional params
- Cleaner function signatures

## Migration Path

### Backward Compatibility

To maintain backward compatibility while introducing resources:

1. **Keep existing tools** - Don't remove any tools during migration
2. **Add parallel resources** - Implement resources alongside tools
3. **Update documentation** - Clearly indicate preferred approach
4. **Deprecation timeline** - Give users time to migrate

### Example: Admin Users

**Current (Tool Only)**:
```python
# Client calls tool
result = await client.call_tool("admin_users_list", {})
```

**After Migration (Resource + Tool)**:
```python
# Option 1: Resource (preferred for reading)
users = await client.read_resource("admin://users")

# Option 2: Tool (still available)
result = await client.call_tool("admin_users_list", {})
```

### Resource Response Format

Based on legacy implementation, standardize on:

```json
{
  "uri": "admin://users",
  "mimeType": "application/json",
  "content": {
    "items": [...],
    "metadata": {
      "total_count": 42,
      "has_more": false,
      "continuation_token": null,
      "last_updated": "2025-10-18T10:30:00Z"
    }
  }
}
```

## Open Questions

1. **Should read-heavy tools like `bucket_objects_list` be resources?**
   - Pro: Natural fit for resource model, cacheable
   - Con: Large result sets, pagination complexity

2. **How to handle parameterized queries?**
   - Option A: Encode in URI path (`s3://bucket/prefix/my/path`)
   - Option B: Use resource templates (`s3://{bucket}/{prefix}`)
   - Option C: Keep as tools if parameters are complex

3. **Should search be a resource or tool?**
   - Search often has complex parameters
   - But search discovery/suggestions could be resources
   - Recommendation: `search://suggest` resource, `unified_search` tool

4. **How to handle authentication/permissions?**
   - Resources should fail gracefully if no access
   - Admin resources should only be exposed if credentials present
   - Follow legacy pattern: check credentials before registering

## Next Steps

1. **Review this analysis** with the team
2. **Prioritize which resources to implement** in Phase 1
3. **Design the resource framework** (restore legacy or create new?)
4. **Implement core resources** starting with admin and metadata
5. **Update documentation** to guide users on tool vs resource usage
6. **Add integration tests** for all resources
7. **Measure impact** on agent performance and user experience

## Conclusion

The `legacy_0_7_2` branch had the right idea with MCP Resources, but the implementation was removed during the JWT merge. This analysis identifies **32 tools that should be resources** based on MCP best practices.

The highest priority candidates are:
- Admin users/roles listing (13 governance tools)
- Athena/Glue discovery (4 tools)
- Metadata templates/examples (5 tools)
- Tabulator discovery (3 tools)
- Workflow status (2 tools)
- Permission discovery (3 tools)
- Auth/catalog status (4 tools)

Implementing these as resources will improve:
- MCP protocol compliance
- Agent decision-making
- Caching efficiency
- API discoverability
- Code organization

The key is to maintain backward compatibility by keeping tools while adding resources, allowing gradual migration.

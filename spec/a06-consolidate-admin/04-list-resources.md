<!-- markdownlint-disable MD013 MD024 -->
# A06 List Methods as MCP Resources

## Executive Summary

Analysis of MCP tools identifies 10 functions that provide listing functionality across different resource types. These can be reorganized as standardized MCP resources to provide consistent discovery patterns.

**Data Source**: `tests/fixtures/mcp-list.csv` - live server introspection

## Current List Methods Analysis

### 1. AWS Resource Lists (3 functions - athena_glue module)

**Athena Data Catalog Resources:**

- `athena_databases_list` - List available databases in AWS Glue Data Catalog
- `athena_workgroups_list` - List available Athena workgroups that the user can access

**Conversion to MCP Resources:**

```yaml
Resource URI: athena://databases
Description: AWS Glue Data Catalog databases
Parameters:
  - catalog_name: str = 'AwsDataCatalog'
  - service: Optional[Any] = None
```

```yaml
Resource URI: athena://workgroups  
Description: Athena workgroups accessible to user
Parameters:
  - use_quilt_auth: bool = True
  - service: Optional[Any] = None
```

### 2. Admin Resource Lists (2 functions - governance module)

**User Management Resources:**

- `admin_users_list` - List all users in the registry with detailed information
- `admin_roles_list` - List all available roles in the registry

**Conversion to MCP Resources:**

```yaml
Resource URI: admin://users
Description: Registry users with detailed information
Parameters: none
Async: true
```

```yaml
Resource URI: admin://roles
Description: Available registry roles
Parameters: none  
Async: true
```

### 3. S3 Bucket Resources (1 function - unified_package module)

**S3 Bucket Discovery:**

- `list_available_resources` - Auto-detect user's available buckets and registries (unified_package module)

**Conversion to MCP Resources:**

```yaml
Resource URI: s3://buckets
Description: List available S3 buckets accessible to user
Parameters: none
```

**Note:** `bucket_objects_list` is not included as a resource since S3 buckets can contain millions of objects, making it impractical as an MCP resource. This remains as a tool for targeted object queries.

### 4. Metadata Resources (1 function - metadata_templates module)

**Template Discovery:**

- `list_metadata_templates` - List available metadata templates with descriptions

**Conversion to MCP Resources:**

```yaml
Resource URI: metadata://templates
Description: Available metadata templates with descriptions
Parameters: none
```

### 5. Package Tools Discovery (1 function - package_management module)

**Tool Discovery:**

- `package_tools_list` - List all package management tools with usage guidance

**Conversion to MCP Resources:**

```yaml
Resource URI: package://tools
Description: Package management tools with usage guidance
Parameters: none
```

### 6. Tabulator Resources (1 function - tabulator module)

**Table Configuration:**

- `tabulator_tables_list` - List all tabulator tables configured for a bucket

**Conversion to MCP Resources:**

```yaml
Resource URI: tabulator://{bucket}/tables
Description: Tabulator tables configured for bucket
Parameters:
  - bucket_name: str
Async: true
```

### 7. Unified Package Resources (0 functions)

**Note:** The `list_available_resources` function from unified_package module has been categorized under S3 Bucket Resources as it primarily discovers available S3 buckets.

### 8. Workflow Resources (1 function - workflow_orchestration module)

**Workflow Management:**

- `workflow_list` - List all workflows with their current status

**Conversion to MCP Resources:**

```yaml
Resource URI: workflow://workflows
Description: All workflows with current status
Parameters: none
```

## Proposed MCP Resource Consolidation

### Resource URI Patterns

**Standard URI Scheme:**

```text
{service}://{scope}/{resource_type}
```

**Examples:**

- `athena://catalog/databases` - Athena databases
- `athena://user/workgroups` - User's Athena workgroups
- `admin://registry/users` - Registry users
- `admin://registry/roles` - Registry roles
- `s3://buckets` - List available S3 buckets
- `metadata://registry/templates` - Metadata templates
- `package://tools/management` - Package management tools
- `tabulator://{bucket}/tables` - Tabulator tables
- `workflow://registry/workflows` - All workflows

### Standardized Resource Response Format

```json
{
  "resource_uri": "athena://catalog/databases",
  "resource_type": "list",
  "items": [...],
  "metadata": {
    "total_count": 123,
    "has_more": false,
    "continuation_token": null,
    "last_updated": "2025-09-22T10:30:00Z"
  },
  "capabilities": {
    "filterable": true,
    "sortable": true,
    "paginatable": true
  }
}
```

### Implementation Strategy

#### Phase 1: Core Resource Types

1. **Admin Resources** (`admin://users`, `admin://roles`)
   - High-value consolidation
   - Clear resource boundaries
   - Already async-compatible

2. **S3 Resources** (`s3://buckets`)
   - Bucket discovery and permissions
   - Registry detection
   - Permission-aware listing

#### Phase 2: Specialized Resources

1. **Athena Resources** (`athena://databases`, `athena://workgroups`)
   - AWS service integration
   - Service dependency injection

2. **Metadata Resources** (`metadata://templates`)
   - Template discovery patterns
   - Integration with package creation

#### Phase 3: Orchestration Resources

1. **Workflow Resources** (`workflow://workflows`)
   - Management interfaces
   - Status tracking integration

2. **Tabulator Resources** (`tabulator://{bucket}/tables`)
   - Table configuration management
   - Bucket-specific resources

### Benefits of Resource Conversion

#### 1. Standardized Discovery

- Consistent URI patterns across all resource types
- Predictable parameter structures
- Unified response formats

#### 2. Enhanced Client Integration

- MCP clients can automatically discover available resources
- Type-safe resource access patterns
- Built-in pagination and filtering capabilities

#### 3. Improved API Coherence

- Clear separation between actions (tools) and data access (resources)
- Reduced API surface complexity
- Better semantic clarity

#### 4. Future Extensibility

- Resource subscriptions for real-time updates
- Resource templating and inheritance
- Cross-resource relationship modeling

### Migration Considerations

#### Backward Compatibility

- Maintain existing tool functions as shims
- Gradual deprecation with clear migration paths
- Version-aware client support

#### Performance Optimization

- Resource caching strategies
- Lazy loading for expensive operations
- Connection pooling for AWS services

#### Security Model

- Resource-level access controls
- Scope-based permission checking
- Audit logging for resource access

## Implementation Timeline

### Week 1-2: Core Infrastructure

- MCP resource framework setup
- Standard response format implementation
- Basic URI routing and parameter handling

### Week 3-4: Phase 1 Resources

- Admin users and roles resources
- S3 buckets discovery resource
- Backward compatibility shims

### Week 5-6: Phase 2 Resources

- Athena databases and workgroups resources
- Metadata templates resource
- Integration testing

### Week 7-8: Phase 3 Resources

- Workflow and tabulator resources
- Performance optimization
- Documentation and migration guides

## Success Metrics

### API Simplification

- **Target**: 50% reduction in list-type tools
- **Current**: 10 list functions across 7 modules
- **Goal**: 7 standardized resources with unified interface

### Client Integration

- **Target**: 100% resource discoverability
- **Measure**: MCP clients can enumerate all available resources
- **Validation**: Automated client compatibility tests

### Performance Improvement

- **Target**: 30% faster resource discovery
- **Measure**: Time to enumerate all available resources
- **Method**: Caching and connection pooling

## Conclusion

Converting list methods to MCP resources provides a cleaner API architecture with better discoverability, consistency, and extensibility. The phased approach ensures backward compatibility while progressively improving the developer experience.

This consolidation aligns with MCP best practices and positions the server for enhanced client integration capabilities.

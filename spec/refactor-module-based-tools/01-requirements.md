# Module-Based Tools Refactoring - Requirements

## Problem Statement

The current MCP server exposes **84 individual tools** (one per function across 16 modules). This creates several challenges:

1. **Client Overhead**: MCP clients must load and manage 84 separate tool definitions
2. **Discovery Complexity**: Users face cognitive overload when browsing available tools
3. **Maintenance Burden**: Each tool requires individual registration, documentation, and testing
4. **Namespace Pollution**: The flat tool namespace makes it difficult to understand tool organization

### Current Tool Distribution

```
Module                    Tools  Async  Example Tools
────────────────────────────────────────────────────────────
athena_glue                 7      0    athena_databases_list, athena_query_execute
auth                        8      0    auth_status, catalog_info, configure_catalog
buckets                     8      0    bucket_objects_list, bucket_object_fetch
governance                 17     17    admin_users_list, admin_user_create
metadata_examples           3      0    create_metadata_from_template
metadata_templates          3      0    get_metadata_template, list_metadata_templates
package_management          4      0    create_package_enhanced, package_validate
package_ops                 3      0    package_create, package_update, package_delete
packages                    5      0    package_browse, packages_search
permissions                 3      0    aws_permissions_discover, bucket_access_check
quilt_summary               3      0    create_quilt_summary_files
s3_package                  1      0    package_create_from_s3
search                      3      0    unified_search, search_suggest
tabulator                   7      6    tabulator_tables_list, tabulator_table_create
unified_package             3      0    create_package, list_available_resources
workflow_orchestration      6      0    workflow_create, workflow_add_step
────────────────────────────────────────────────────────────
TOTAL                      84     23    (27% async tools)
```

## Objectives

### Primary Goal

**Reduce the tool count from 84 to 16** by exposing one tool per module instead of one tool per function.

### Secondary Goals

1. **Maintain Ergonomics**: The refactored interface should be as easy to use as the current one
2. **Preserve Capabilities**: All existing functionality must remain accessible
3. **Improve Discoverability**: Module-based organization should make tools easier to understand
4. **Simplify Testing**: Reduce test complexity while maintaining coverage
5. **Provide Clear Instructions**: MCP providers should understand available actions without ambiguity

## Success Criteria

1. ✅ Tool count reduced from 84 to 16 (one per module)
2. ✅ All existing functionality remains accessible
3. ✅ Clear documentation of available actions per module
4. ✅ Test coverage maintained at 100%
5. ✅ No breaking changes for MCP client implementations
6. ✅ Action parameter validation with helpful error messages
7. ✅ Async tools remain async, sync tools remain sync

## Non-Goals

- Changing the underlying business logic of any tool
- Modifying the service layer or core functionality
- Removing or deprecating any existing features
- Changing the external API contracts (parameters, return types)

## Constraints

1. **Backward Compatibility**: Existing MCP clients should be able to adapt with minimal changes
2. **Type Safety**: All parameters must remain strongly typed
3. **Error Handling**: Error messages must be clear and actionable
4. **Testing**: All existing test cases must be adapted and pass
5. **Documentation**: All tools must have comprehensive docstrings

## Stakeholders

- **MCP Client Developers**: Will need to update their code to use action-based calls
- **End Users**: Should experience no functional difference
- **MCP Server Maintainers**: Will have simpler registration and testing workflows

## Timeline

- **Phase 1**: Specification and design review (current phase)
- **Phase 2**: Implementation of module wrappers
- **Phase 3**: Test migration
- **Phase 4**: Documentation updates
- **Phase 5**: Integration testing and validation

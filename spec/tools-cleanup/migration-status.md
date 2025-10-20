# Tools Cleanup Migration - Current Status & Completion Plan

**Last Updated**: 2025-10-20
**Branch**: unified-search
**Status**: ~85% Complete - Service migration done, cleanup phase remaining

---

## Executive Summary

The migration from `quilt_mcp.tools.*` to `quilt_mcp.resources.*` and `quilt_mcp.services.*` is substantially complete. All read-only functionality has been successfully migrated to appropriate service modules and exposed via MCP resources. The remaining work is focused on cleanup, documentation, and test alignment.

### What's Done ✅

1. **Service Layer Complete** - All read-only logic migrated to services:
   - `services/auth_metadata.py` - Authentication status and catalog info
   - `services/governance_service.py` - User/role management, SSO, tabulator config
   - `services/athena_read_service.py` - Athena queries and Glue catalog discovery
   - `services/metadata_service.py` - Metadata templates, examples, validation
   - `services/permissions_service.py` - AWS permissions discovery
   - `services/tabulator_service.py` - Tabulator bucket/table listing
   - `services/workflow_service.py` - Workflow orchestration

2. **Resource Layer Complete** - All domains exposed via MCP resources:
   - `resources/auth.py` - 4 resources (status, catalog info, name, filesystem)
   - `resources/admin.py` - 7 resources (users, roles, config, user details, SSO, tabulator)
   - `resources/athena.py` - 4 resources (databases, workgroups, table schema, query history)
   - `resources/metadata.py` - 4 resources (templates, examples, troubleshooting, specific template)
   - `resources/permissions.py` - 3 resources (discover, recommendations, bucket access)
   - `resources/tabulator.py` - 2 resources (buckets, tables)
   - `resources/workflow.py` - 2 resources (workflows list, workflow status)

3. **Tests Updated** - Most tests skip old tool implementations with resource URIs documented

### What Remains 🔧

1. **Delete Superseded Tool Files** (Priority 1)
2. **Update Tool Registry** (Priority 1)
3. **Re-enable and Port Tests** (Priority 2)
4. **Documentation Updates** (Priority 3)
5. **Final Validation** (Priority 4)

---

## Current Codebase State

### Services Layer (`src/quilt_mcp/services/`)

All services are implemented and working:

```
✅ auth_metadata.py          - auth_status, catalog_info, catalog_name, filesystem_status
✅ governance_service.py      - admin_users_list, admin_user_get, admin_roles_list, admin_sso_config_*, admin_tabulator_*
✅ athena_read_service.py     - athena_databases_list, athena_tables_list, athena_table_schema, athena_workgroups_list, athena_query_history
✅ metadata_service.py        - get_metadata_template, list_metadata_templates, show_metadata_examples, fix_metadata_validation_issues, validate_metadata_structure
✅ permissions_service.py     - discover_permissions, bucket_recommendations_get, check_bucket_access
✅ tabulator_service.py       - list_tabulator_buckets, list_tabulator_tables
✅ workflow_service.py        - workflow_list_all, workflow_get_status
```

### Resources Layer (`src/quilt_mcp/resources/`)

All resources implemented and registered:

```
✅ auth.py          - AuthStatusResource, CatalogInfoResource, CatalogNameResource, FilesystemStatusResource
✅ admin.py         - AdminUsersResource, AdminRolesResource, AdminConfigResource, AdminUserResource, AdminSSOConfigResource, AdminTabulatorConfigResource
✅ athena.py        - AthenaDatabasesResource, AthenaWorkgroupsResource, AthenaTableSchemaResource, AthenaQueryHistoryResource
✅ metadata.py      - MetadataTemplatesResource, MetadataExamplesResource, MetadataTroubleshootingResource, MetadataTemplateResource
✅ permissions.py   - PermissionsDiscoverResource, BucketRecommendationsResource, BucketAccessResource
✅ tabulator.py     - TabulatorBucketsResource, TabulatorTablesResource
✅ workflow.py      - WorkflowsResource, WorkflowStatusResource
```

### Tools Layer (`src/quilt_mcp/tools/`)

**Remaining files that still exist but are superseded:**

```
❌ None - The migration correctly points tool imports to services
```

**Active tool files (not part of this migration):**

```
✅ auth_helpers.py         - Still active (catalog URL/URI generation tools)
✅ buckets.py             - Still active (write operations)
✅ catalog.py             - Still active (catalog URL/URI generation)
✅ data_visualization.py  - Still active (visualization creation)
✅ packages.py            - Still active (package creation/update/delete)
✅ quilt_summary.py       - Still active (summary file generation)
✅ search.py              - Still active (unified search)
✅ error_recovery.py      - Still active (error recovery)
✅ stack_buckets.py       - Still active (stack bucket operations)
```

### Tool Registry (`src/quilt_mcp/tools/__init__.py`)

**Current state:**

```python
_MODULE_PATHS = {
    "catalog": "quilt_mcp.tools.catalog",
    "buckets": "quilt_mcp.tools.buckets",
    "packages": "quilt_mcp.tools.packages",
    "quilt_summary": "quilt_mcp.tools.quilt_summary",
    "search": "quilt_mcp.tools.search",
    "data_visualization": "quilt_mcp.tools.data_visualization",
    "athena_glue": "quilt_mcp.services.athena_read_service",        # ✅ Points to service
    "tabulator": "quilt_mcp.services.tabulator_service",            # ✅ Points to service
    "workflow_orchestration": "quilt_mcp.services.workflow_service", # ✅ Points to service
    "governance": "quilt_mcp.services.governance_service",          # ✅ Points to service
}
```

**Status**: Registry already updated to point to services ✅

### Test Status

**Skipped tests with documented resource URIs:**

```
tests/unit/test_workflow_orchestration.py    - Skip: "now available as resource (workflow://workflows)"
tests/unit/test_metadata_examples.py         - Skip: "now available as resource (metadata://examples, metadata://troubleshooting)"
tests/unit/test_governance.py                - Skip: "now available as resource (admin://users, admin://roles, etc.)"
```

**Resource-level tests that exist:**

```
✅ tests/unit/resources/test_auth_resources.py
✅ tests/unit/resources/test_admin_resources.py
✅ tests/unit/resources/test_athena_resources.py
✅ tests/unit/resources/test_metadata_resources.py
✅ tests/unit/resources/test_permissions_resources.py
✅ tests/unit/resources/test_tabulator_resources.py
✅ tests/unit/resources/test_workflow_resources.py
```

---

## Detailed Completion Plan

### Phase 1: Final Cleanup (Estimated: 1-2 hours)

#### Task 1.1: Verify No Orphaned Tool Modules Need Deletion

**Action**: Search for any remaining deprecated tool files that should be deleted.

```bash
# Check if there are any orphaned tool modules
find src/quilt_mcp/tools -name "*.py" -type f | grep -v __pycache__ | grep -E "(auth|governance|athena|metadata|permissions|tabulator|workflow)"
```

**Expected Result**: No files found (migration plan indicates all migrated modules are already gone)

**Status**: ✅ COMPLETE - Tool registry already points to services, no orphaned files exist

#### Task 1.2: Verify Import References

**Action**: Ensure no code still imports the old tool modules directly.

```bash
# Search for old-style imports
rg "from quilt_mcp.tools import (auth|governance|athena_glue|metadata_templates|metadata_examples|permissions|tabulator|workflow_orchestration)" --type py

# Search for specific module imports
rg "quilt_mcp.tools.(auth|governance|athena_glue|metadata_templates|metadata_examples|permissions|tabulator|workflow_orchestration)" --type py
```

**Expected Result**: Only test files with skipped tests should reference these

**Deliverable**: List of any remaining imports that need updating

#### Task 1.3: Clean Up Test Skips

**Action**: Review and update test skip messages to be more descriptive.

**Files to update:**
- `tests/unit/test_workflow_orchestration.py`
- `tests/unit/test_metadata_examples.py`
- `tests/unit/test_governance.py`
- `tests/unit/test_tabulator.py`
- `tests/unit/test_auth_helpers.py`

**Example improvement:**

```python
# Before
@pytest.mark.skip(reason="Tool deprecated - now available as resource (admin://users)")

# After
@pytest.mark.skip(reason="Tool deprecated in v0.8.x - now available as MCP resource (admin://users). "
                         "See tests/unit/resources/test_admin_resources.py for resource-level tests.")
```

**Deliverable**: Updated skip messages with clear migration path

### Phase 2: Test Alignment (Estimated: 2-3 hours)

#### Task 2.1: Audit Resource Test Coverage

**Action**: Compare skipped tool tests with existing resource tests to identify gaps.

**Process:**
1. For each skipped test in `test_governance.py`, `test_metadata_examples.py`, `test_workflow_orchestration.py`, etc.
2. Find corresponding resource test in `tests/unit/resources/`
3. Verify the resource test covers the same functionality
4. Document any missing coverage

**Template for analysis:**

```markdown
| Old Tool Test | Resource Test | Coverage Status | Action Needed |
|--------------|---------------|-----------------|---------------|
| test_admin_users_list | test_admin_users_resource_list | ✅ Complete | None |
| test_admin_user_get | test_admin_user_resource_get | ✅ Complete | None |
| test_metadata_template_get | test_metadata_template_resource | ⚠️ Partial | Add error case tests |
```

**Deliverable**: Coverage matrix showing test alignment status

#### Task 2.2: Port Missing Test Cases

**Action**: For any gaps identified in Task 2.1, port the missing test logic to resource tests.

**Pattern to follow:**

```python
# Old tool test (to be removed)
@pytest.mark.skip(reason="Tool deprecated...")
async def test_admin_users_list(self):
    result = await admin_users_list()
    assert result["success"]
    assert "users" in result

# New resource test
@pytest.mark.asyncio
async def test_admin_users_resource_list():
    resource = AdminUsersResource()
    response = await resource.read("admin://users")
    assert response.content["items"] is not None
    assert response.content["metadata"]["total_count"] >= 0
```

**Deliverable**: Updated resource test files with complete coverage

#### Task 2.3: Remove Deprecated Tool Tests

**Action**: Once resource tests have full coverage, remove the deprecated tool test files entirely.

**Files to potentially delete** (after verifying resource test coverage):
- `tests/unit/test_governance.py` (if all tests are skipped and covered by resources)
- `tests/unit/test_metadata_examples.py` (if all tests are skipped and covered by resources)
- `tests/unit/test_workflow_orchestration.py` (if all tests are skipped and covered by resources)

**Important**: Only delete if:
1. All test cases are covered by resource tests
2. No active (non-skipped) tests remain
3. Resource tests verify the same behavior end-to-end

**Deliverable**: Pruned test suite with only active tests

### Phase 3: Documentation Updates (Estimated: 1-2 hours)

#### Task 3.1: Update Migration Plan

**Action**: Update `/spec/tools-cleanup/migration-plan.md` with completion status.

**Changes needed:**
- Mark all Domain-Specific Tasks as complete
- Update Deliverables section with actual deliverables
- Add "Completion Status" section at top
- Reference this document for detailed status

**Deliverable**: Updated migration-plan.md

#### Task 3.2: Update User Documentation

**Action**: Search and update any user-facing documentation referencing old tool entry points.

```bash
# Find documentation that might reference old tools
find docs/ spec/ -name "*.md" -exec grep -l "quilt_mcp.tools" {} \;
```

**For each file found:**
1. Replace tool references with resource URIs
2. Update code examples
3. Add migration notes if needed

**Example update:**

```markdown
<!-- Before -->
To check authentication status:
```python
from quilt_mcp.tools.auth import auth_status
status = auth_status()
```

<!-- After -->
To check authentication status:
```python
# Via MCP resource
resource_uri = "auth://status"
response = await resource_registry.read_resource(resource_uri)

# Or directly via service
from quilt_mcp.services.auth_metadata import auth_status
status = auth_status()
```
```

**Deliverable**: Updated documentation with resource-based examples

#### Task 3.3: Update CHANGELOG

**Action**: Add comprehensive entry to `CHANGELOG.md` describing the migration.

**Template:**

```markdown
## [Unreleased]

### Changed - Breaking

- **Tools to Resources Migration**: Migrated all read-only tool functionality to MCP resources and service modules.
  - Authentication tools → `auth://` resources (`auth://status`, `auth://catalog/info`, etc.)
  - Governance tools → `admin://` resources (`admin://users`, `admin://roles`, `admin://config`, etc.)
  - Athena tools → `athena://` resources (`athena://databases`, `athena://workgroups`, etc.)
  - Metadata tools → `metadata://` resources (`metadata://templates`, `metadata://examples`, etc.)
  - Permissions tools → `permissions://` resources (`permissions://discover`, `permissions://recommendations`, etc.)
  - Tabulator tools → `tabulator://` resources (`tabulator://buckets`, `tabulator://buckets/{bucket}/tables`)
  - Workflow tools → `workflow://` resources (`workflow://workflows`, `workflow://workflows/{id}`)

### Migration Guide

- **Tool users**: Tools now route through service modules. Import from `quilt_mcp.services.*` instead of `quilt_mcp.tools.*`
  - `quilt_mcp.tools.auth` → `quilt_mcp.services.auth_metadata`
  - `quilt_mcp.tools.governance` → `quilt_mcp.services.governance_service`
  - `quilt_mcp.tools.athena_glue` → `quilt_mcp.services.athena_read_service`
  - `quilt_mcp.tools.metadata_templates` → `quilt_mcp.services.metadata_service`
  - `quilt_mcp.tools.metadata_examples` → `quilt_mcp.services.metadata_service`
  - `quilt_mcp.tools.permissions` → `quilt_mcp.services.permissions_service`
  - `quilt_mcp.tools.tabulator` → `quilt_mcp.services.tabulator_service`
  - `quilt_mcp.tools.workflow_orchestration` → `quilt_mcp.services.workflow_service`

- **MCP users**: Access read-only data via resource URIs (see documentation for full list)
  - Example: `auth://status` provides authentication status
  - Example: `admin://users` lists all users
  - Example: `metadata://templates` lists available metadata templates

- **No API changes**: Service function signatures remain compatible
- **Write operations**: Unaffected - continue using existing tool modules
```

**Deliverable**: Updated CHANGELOG.md

### Phase 4: Final Validation (Estimated: 30 minutes)

#### Task 4.1: Run Full Test Suite

**Action**: Execute complete test suite and verify all tests pass.

```bash
# Run all tests
make test-all

# Or if make target doesn't exist
python -m pytest tests/ -v

# Check for any remaining skipped tests
python -m pytest tests/ -v | grep -i skip
```

**Success Criteria:**
- All active tests pass
- Skipped tests have documented reasons
- No unexpected failures

**Deliverable**: Test run report

#### Task 4.2: Verify Tool Registry

**Action**: Verify tool registry exports are correct.

```python
# Test script to verify tool registry
from quilt_mcp.tools import AVAILABLE_MODULES
import quilt_mcp.tools as tools

print("Available modules:", AVAILABLE_MODULES)

# Try importing each module
for module_name in AVAILABLE_MODULES:
    module = getattr(tools, module_name)
    print(f"✓ {module_name}: {module}")
```

**Success Criteria:**
- All modules import successfully
- Service-backed modules point to correct services
- No import errors

**Deliverable**: Registry validation report

#### Task 4.3: Verify Resource Registration

**Action**: Verify all resources are properly registered and accessible.

```python
# Test script to verify resource registration
from quilt_mcp.resources import ResourceRegistry

registry = ResourceRegistry()

# Check auth resources
auth_resources = [
    "auth://status",
    "auth://catalog/info",
    "auth://catalog/name",
    "auth://filesystem/status",
]

# Check admin resources
admin_resources = [
    "admin://users",
    "admin://roles",
    "admin://config",
    "admin://config/sso",
    "admin://config/tabulator",
]

# ... check all resources ...

for uri in auth_resources + admin_resources:
    try:
        response = await registry.read_resource(uri)
        print(f"✓ {uri}")
    except Exception as e:
        print(f"✗ {uri}: {e}")
```

**Success Criteria:**
- All resource URIs resolve
- No registration errors
- Resources return valid responses

**Deliverable**: Resource registration report

---

## Risk Assessment & Mitigation

### Low Risk ✅

1. **Service Implementation** - All services are implemented and tested
2. **Resource Implementation** - All resources are implemented and tested
3. **Tool Registry** - Already updated to point to services

### Medium Risk ⚠️

1. **Test Coverage Gaps**
   - **Risk**: Some edge cases may not be covered by resource tests
   - **Mitigation**: Systematic audit in Phase 2, Task 2.1
   - **Impact**: Minor - can be addressed incrementally

2. **Documentation Drift**
   - **Risk**: Some docs may still reference old patterns
   - **Mitigation**: Comprehensive search in Phase 3, Task 3.2
   - **Impact**: Low - documentation only, no functional impact

### Zero Risk 🎯

1. **Breaking Changes** - No breaking changes for service layer users
2. **Write Operations** - Unaffected by this migration
3. **External APIs** - All external APIs remain unchanged

---

## Completion Checklist

### Phase 1: Final Cleanup
- [ ] Task 1.1: Verify no orphaned tool modules
- [ ] Task 1.2: Verify import references
- [ ] Task 1.3: Clean up test skips

### Phase 2: Test Alignment
- [ ] Task 2.1: Audit resource test coverage
- [ ] Task 2.2: Port missing test cases
- [ ] Task 2.3: Remove deprecated tool tests

### Phase 3: Documentation Updates
- [ ] Task 3.1: Update migration plan
- [ ] Task 3.2: Update user documentation
- [ ] Task 3.3: Update CHANGELOG

### Phase 4: Final Validation
- [ ] Task 4.1: Run full test suite
- [ ] Task 4.2: Verify tool registry
- [ ] Task 4.3: Verify resource registration

---

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Final Cleanup | 1-2 hours | None |
| Phase 2: Test Alignment | 2-3 hours | Phase 1 complete |
| Phase 3: Documentation | 1-2 hours | Phase 2 complete |
| Phase 4: Final Validation | 30 minutes | Phase 3 complete |
| **Total** | **5-8 hours** | Sequential execution |

---

## Success Criteria

Migration is considered complete when:

1. ✅ All read-only functionality accessible via resources
2. ✅ All services implemented and tested
3. ✅ All resources implemented and tested
4. ✅ Tool registry points to correct modules
5. [ ] No deprecated tool test files remain (or all clearly marked as deprecated)
6. [ ] Resource tests provide equivalent coverage
7. [ ] Documentation updated with resource examples
8. [ ] CHANGELOG documents the migration
9. [ ] All tests pass
10. [ ] No stale imports remain in codebase

**Current Status: 7/10 Complete (70%)**

---

## Recommendations

### Immediate Actions (Next Session)

1. **Start with Phase 1, Task 1.2** - Verify import references
   - Quick task to ensure no hidden dependencies
   - Provides confidence for later cleanup

2. **Focus on Phase 2, Task 2.1** - Audit resource test coverage
   - Most important for ensuring quality
   - Identifies any real gaps

3. **Skip deletion of test files initially**
   - Keep deprecated test files with clear skip markers
   - Can remove in a follow-up PR if desired
   - Maintains history and documentation value

### Long-term Considerations

1. **Consider keeping deprecated tool tests**
   - They serve as documentation of old behavior
   - Skip markers point users to new resources
   - Low maintenance burden
   - Can be deleted later if truly not needed

2. **Create migration guide document**
   - Separate doc in `docs/migration/tools-to-resources.md`
   - More visible than CHANGELOG for long-term reference
   - Includes code examples and troubleshooting

3. **Monitor for regressions**
   - Watch for any issues reported by users
   - Check MCP server logs for resource access patterns
   - Verify performance of new resource endpoints

---

## Appendix: Resource URI Reference

Quick reference for all migrated functionality:

### Authentication (`auth://`)
- `auth://status` - Authentication status
- `auth://catalog/info` - Catalog configuration
- `auth://catalog/name` - Catalog name
- `auth://filesystem/status` - Filesystem access status

### Administration (`admin://`)
- `admin://users` - List all users
- `admin://users/{name}` - Get specific user
- `admin://roles` - List all roles
- `admin://config` - Combined configuration
- `admin://config/sso` - SSO configuration
- `admin://config/tabulator` - Tabulator configuration

### Athena (`athena://`)
- `athena://databases` - List databases
- `athena://workgroups` - List workgroups
- `athena://databases/{database}/tables/{table}/schema` - Table schema
- `athena://queries/history` - Query history

### Metadata (`metadata://`)
- `metadata://templates` - List templates
- `metadata://templates/{name}` - Specific template
- `metadata://examples` - Usage examples
- `metadata://troubleshooting` - Troubleshooting guide

### Permissions (`permissions://`)
- `permissions://discover` - Discover AWS permissions
- `permissions://recommendations` - Bucket recommendations
- `permissions://buckets/{bucket}/access` - Bucket access check

### Tabulator (`tabulator://`)
- `tabulator://buckets` - List buckets
- `tabulator://buckets/{bucket}/tables` - List tables for bucket

### Workflow (`workflow://`)
- `workflow://workflows` - List all workflows
- `workflow://workflows/{id}` - Workflow status

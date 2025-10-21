# Tools Simplification Plan

## Goal

Simplify from 17 modules to 12 modules by consolidating related functionality.

## Comparison

### Target State (Simplified)

```tree
catalog              ✓ (rename from auth)
buckets              ✓
packages             ✓ (merge packages + package_ops + s3_package)
permissions          ✓
metadata             ✓ (merge metadata_templates + metadata_examples)
quilt_summary        ✓
search               ✓ (merge graphql + search)
data_visualization   ✓ (new since 0.7.2)
athena_glue          ✓
tabulator            ✓
workflow_orchestration  ✓
governance           ✓
```

**Total: 12 modules** (down from 17)

### Current (HEAD) - Needs Cleanup

```tree
auth                 → RENAME to "catalog"
buckets              ✓ Keep
packages             → MERGE with package_ops + s3_package
package_ops          → MERGE into "packages"
s3_package           → MERGE into "packages"
permissions          ✓ Keep
unified_package      ✗ REMOVE (user-facing wrapper)
package_management   ✗ REMOVE (user-facing wrapper)
metadata_templates   → MERGE with metadata_examples as "metadata"
metadata_examples    → MERGE into "metadata"
quilt_summary        ✓ Keep
graphql              → MERGE into "search"
search               ✓ Keep as "search"
data_visualization   ✓ Keep
athena_glue          ✓ Keep
tabulator            ✓ Keep
workflow_orchestration  ✓ Keep
governance           ✓ Keep
```

## Actions

### A. Rename Module: `auth` → `catalog`

**Rationale**: The `auth` module contains catalog configuration functions (`catalog_url`, `catalog_uri`, `configure_catalog`, `switch_catalog`).

**Changes**:

1. Rename [src/quilt_mcp/tools/auth.py](../src/quilt_mcp/tools/auth.py) → `catalog.py`
2. Update [src/quilt_mcp/tools/**init**.py](../src/quilt_mcp/tools/__init__.py):
   - Change `"auth"` to `"catalog"` in `_MODULE_PATHS`
3. Update all imports:
   - Test files: `from quilt_mcp.tools import auth` → `from quilt_mcp.tools import catalog`
   - Resources: `quilt_mcp.tools.auth` → `quilt_mcp.tools.catalog`

**Files to update**:

- [tests/unit/test_auth.py](../tests/unit/test_auth.py)
- [tests/integration/test_auth_migration.py](../tests/integration/test_auth_migration.py)
- [tests/integration/test_integration.py](../tests/integration/test_integration.py)
- [tests/integration/test_mcp_server_integration.py](../tests/integration/test_mcp_server_integration.py)
- [src/quilt_mcp/resources/auth.py](../src/quilt_mcp/resources/auth.py)

### B. Merge All Package Operations: `packages` + `package_ops` + `s3_package` → `packages`

**Rationale**: Package browsing, creation, and management are tightly coupled. Having separate modules creates artificial boundaries.

**Current split**:

- `packages`: Browse and search (`package_browse`, `unified_search`, `package_diff`, `unified_search`)
- `package_ops`: Basic CRUD (`package_create`, `package_update`, `package_delete`)
- `s3_package`: S3-to-package workflow (`package_create_from_s3`)

**Target**: Single `packages` module with all package operations:

- `package_browse(package_name, ...)` - from packages
- `unified_search(package_name, query, ...)` - from packages
- `package_diff(package1_name, package2_name, ...)` - from packages
- `unified_search(query, ...)` - from packages
- `package_create(package_name, s3_uris, ...)` - from package_ops
- `package_create_from_s3(source_bucket, package_name, ...)` - from s3_package
- `package_update(package_name, s3_uris, ...)` - from package_ops
- `package_delete(package_name, ...)` - from package_ops

**Changes**:

1. Merge all functions into [src/quilt_mcp/tools/packages.py](../src/quilt_mcp/tools/packages.py)
2. Remove `package_ops.py` and `s3_package.py`
3. Update [src/quilt_mcp/tools/**init**.py](../src/quilt_mcp/tools/__init__.py):
   - Remove `"package_ops"` and `"s3_package"` from `_MODULE_PATHS`
   - Keep only `"packages"`

### C. Remove User-Facing Convenience Modules

**Remove**:

- `unified_package` - User-facing wrapper with auto-detection
- `package_management` - Enhanced UX layer over primitives

**Rationale**: These are convenience layers for end-users, not primitive MCP tools. They add complexity without providing unique functionality.

**Changes**:

1. Delete [src/quilt_mcp/services/unified_package_service.py](../src/quilt_mcp/services/unified_package_service.py)
2. Delete [src/quilt_mcp/services/package_management_service.py](../src/quilt_mcp/services/package_management_service.py)
3. Update [src/quilt_mcp/tools/**init**.py](../src/quilt_mcp/tools/__init__.py):
   - Remove `"unified_package"` and `"package_management"` from `_MODULE_PATHS`
4. Remove/update tests:
   - [tests/e2e/test_unified_package.py](../tests/e2e/test_unified_package.py)
   - [tests/e2e/test_package_management.py](../tests/e2e/test_package_management.py)

### D. Merge Metadata Modules: `metadata_templates` + `metadata_examples` → `metadata`

**Rationale**: Both modules deal with metadata structure and templates. The split is artificial.

**Current split**:

- `metadata_templates`: Template retrieval and validation (`metadata_template_get`, `validate_metadata_structure`)
- `metadata_examples`: Template creation (`create_metadata_from_template`)

**Target**: Single `metadata` module with:

- `metadata_template_get(template_name, ...)`
- `metadata_template_create(...)`
- `metadata_validate_structure(metadata, ...)`

**Changes**:

1. Merge into [src/quilt_mcp/tools/metadata.py](../src/quilt_mcp/tools/metadata.py)
2. Remove `metadata_templates.py` and `metadata_examples.py`
3. Update [src/quilt_mcp/tools/**init**.py](../src/quilt_mcp/tools/__init__.py):
   - Remove `"metadata_templates"` and `"metadata_examples"`
   - Add `"metadata"`

### E. Merge GraphQL into Search: `graphql` + `search` → `search`

**Rationale**: GraphQL is just one search backend. The distinction isn't meaningful to users.

**Current split**:

- `graphql`: Raw GraphQL queries (`catalog_graphql_query`, `objects_search_graphql`)
- `search`: Higher-level search (`unified_search`, `search_suggest`, `search_explain`)

**Target**: Single `search` module with:

- `search(query, ...)` - unified search (current `unified_search`)
- `search_suggest(partial_query, ...)`
- `search_explain(query, ...)`
- `search_graphql(query, ...)` - for raw GraphQL access (renamed from `catalog_graphql_query`)
- `search_objects_graphql(bucket, ...)` - (renamed from `objects_search_graphql`)

**Changes**:

1. Merge all into [src/quilt_mcp/tools/search.py](../src/quilt_mcp/tools/search.py)
2. Remove `graphql.py`
3. Rename `unified_search` → `search` (primary interface)
4. Rename `catalog_graphql_query` → `search_graphql`
5. Update [src/quilt_mcp/tools/**init**.py](../src/quilt_mcp/tools/__init__.py):
   - Remove `"graphql"` from `_MODULE_PATHS`
   - Keep only `"search"`

## Tool Naming Conventions

MCP tools are registered with the pattern: `{module}__{function_name}`

### Current Tools Requiring Rename

When modules are renamed/merged, their tool names must update:

| Old Tool Name | New Tool Name | Module Change |
|--------------|---------------|---------------|
| `auth__catalog_uri` | `catalog__catalog_uri` | auth → catalog |
| `auth__catalog_url` | `catalog__catalog_url` | auth → catalog |
| `auth__configure_catalog` | `catalog__configure_catalog` | auth → catalog |
| `auth__switch_catalog` | `catalog__switch_catalog` | auth → catalog |
| `graphql__catalog_graphql_query` | `search__search_graphql` | graphql → search + rename function |
| `graphql__objects_search_graphql` | `search__search_objects_graphql` | graphql → search + rename function |
| `metadata_examples__create_metadata_from_template` | `metadata__metadata_template_create` | merge + rename function |
| `metadata_templates__validate_metadata_structure` | `metadata__metadata_validate_structure` | merge + keep function name |
| `package_ops__package_create` | `packages__package_create` | package_ops → packages |
| `package_ops__package_update` | `packages__package_update` | package_ops → packages |
| `package_ops__package_delete` | `packages__package_delete` | package_ops → packages |
| `s3_package__package_create_from_s3` | `packages__package_create_from_s3` | s3_package → packages |

### Automation Script

Tool registration happens automatically via the `@tool` decorator. After renaming modules, regenerate the tool list using the existing introspection script:

```bash
# Run the existing tool introspection script
uv run python scripts/mcp-list.py

# This generates:
# - tests/fixtures/mcp-list.csv (test fixture)
# - build/tools_metadata.json (structured metadata)
# - build/consolidation_report.json (overlap analysis)
```

**Note**: The `@tool` decorator automatically:

1. Extracts the module name from the function's `__module__` attribute
2. Registers the tool as `{module}__{function_name}`
3. No manual tool registration needed after module/function renames
4. The [scripts/mcp-list.py](../../scripts/mcp-list.py) script introspects the running MCP server to generate canonical tool lists

## Implementation Order

1. **Phase 1**: Remove convenience modules (C)
   - Delete `unified_package` and `package_management`
   - Remove tests
   - Minimal dependencies

2. **Phase 2**: Rename auth → catalog (A)
   - Rename file and update imports
   - Update resource registration

3. **Phase 3**: Merge packages (B)
   - Merge `package_ops` and `s3_package` into `packages`
   - Update tests

4. **Phase 4**: Merge metadata (D)
   - Merge `metadata_templates` and `metadata_examples` into `metadata`
   - Update tests

5. **Phase 5**: Merge search/graphql (E)
   - Merge `graphql` into `search`
   - Rename functions for consistency
   - Update tests

## Verification

After changes, verify:

```bash
# Check module list matches target
python -c "from quilt_mcp.tools import AVAILABLE_MODULES; print(sorted(AVAILABLE_MODULES))"

# Run tests
uv run pytest tests/

# Regenerate and check tool list
uv run python scripts/mcp-list.py

# Check resources registration
uv run mcp-inspector
```

Expected final module list (12 modules):

```
athena_glue
buckets
catalog            # renamed from auth
data_visualization # new since 0.7.2
governance
metadata           # merged from metadata_templates + metadata_examples
packages           # merged from packages + package_ops + s3_package
permissions
quilt_summary
search             # merged from search + graphql
tabulator
workflow_orchestration
```

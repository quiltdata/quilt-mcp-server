<!-- markdownlint-disable MD013 -->
# Specifications - Aggressive Tool Consolidation & Cleanup

**Reference**: Analysis in `spec/170-tool-audit/02-analysis.md`

## Executive Decision: BRUTAL ELIMINATION

This specification **DELETES REDUNDANT TOOLS IMMEDIATELY** with zero deprecation period. The current 85+ tool chaos is unacceptable and ends NOW.

**Version Impact**: Major version bump (v1.0.0) - clients WILL break and MUST adapt.

## Desired End State

1. **Single Source of Truth**: All tool metadata is auto-generated from MCP server introspection via `scripts/generate_canonical_tools.py` - NO MANUAL MAINTENANCE.
2. **Eliminated Duplicates**: Aggressive consolidation removes 15+ redundant tools, keeping only the most capable implementation in each category.
3. **Auto-Generated Documentation**: `docs/api/TOOLS.md` is completely generated from code, preventing drift and ensuring accuracy.
4. **Breaking Changes Enforced**: CI fails if deprecated tools are referenced in code or documentation.
5. **Migration Path**: Clear upgrade guide maps old tools to new consolidated equivalents.

## Scope & Boundaries

- **In Scope**: Complete removal of duplicate tools, auto-generation pipeline, breaking changes to `src/quilt_mcp/__init__.py`, replacement of manual CSV with generated metadata.
- **Out of Scope**: Maintaining compatibility with existing tool names - this is a clean break.

## Tool Consolidation Plan

### 1. Package Creation - DELETE DUPLICATES

**DELETE IMMEDIATELY:**

- `package_create` - GONE
- `create_package` - GONE
- `package_create_from_s3` - GONE

**SURVIVORS:**

- `create_package_enhanced` - The ONE package creation tool

**NO MIGRATION PERIOD** - Update your code or it breaks.

### 2. Search Functions - DELETE DUPLICATES

**DELETE IMMEDIATELY:**

- `packages_search` - GONE
- `bucket_objects_search` - GONE

**SURVIVORS:**

- `unified_search` - The ONE search tool

**NO MIGRATION PERIOD** - Use unified_search or break.

### 3. URL Generation - DELETE LEGACY

**DELETE IMMEDIATELY:**

- `catalog_uri` - GONE (URIs are dead)

**SURVIVORS:**

- `catalog_url` - URLs only, no legacy URIs

### 4. Tabulator Admin - DELETE INSECURE TOOLS

**DELETE IMMEDIATELY:**

- `tabulator_open_query_status` - GONE (no auth model)
- `tabulator_open_query_toggle` - GONE (no auth model)

**SURVIVORS:**

- `admin_tabulator_open_query_get` - Proper admin tool
- `admin_tabulator_open_query_set` - Proper admin tool

### 5. Metadata Templates - MINOR CONSOLIDATION

**KEEP BOTH** but clarify usage:

- `get_metadata_template` - raw template retrieval
- `create_metadata_from_template` - filled template with validation

## Auto-Generation Pipeline

### 1. Script: `scripts/generate_canonical_tools.py`

**Purpose**: Introspect MCP server to extract authoritative tool metadata.

**Outputs**:

- `quilt_mcp_tools_canonical.csv` - replaces manual CSV
- `build/tools_metadata.json` - structured metadata for tooling
- `build/consolidation_report.json` - breaking changes documentation

**Integration**: Runs in CI to verify no drift between code and documentation.

### 2. Documentation Generation

**Purpose**: Auto-generate `docs/api/TOOLS.md` from server introspection.

**Process**:

1. Extract tool signatures, docstrings, and examples from code
2. Generate organized markdown with consistent formatting
3. Include migration guides for deprecated tools
4. Fail CI if manual edits detected

### 3. Export Validation

**Purpose**: Ensure `src/quilt_mcp/__init__.py` exports match available tools.

**Process**:

1. Compare `__all__` list with actual server tools
2. Fail CI if deprecated tools are exported
3. Require explicit exports for all new tools

## Engineering Implementation

### 1. BRUTAL CODE DELETION

```python
# DELETE THESE IMPORTS from src/quilt_mcp/__init__.py
# from .tools.package_ops import package_create, package_update  # DELETED
# from .tools.unified_package import create_package  # DELETED
# from .tools.s3_package import package_create_from_s3  # DELETED

# DELETE FROM __all__ IMMEDIATELY
__all__ = [
    # ... existing tools ...
    # DELETED: "package_create", "create_package", "package_create_from_s3"
    # DELETED: "packages_search", "bucket_objects_search"
    # DELETED: "catalog_uri"
    # DELETED: "tabulator_open_query_status", "tabulator_open_query_toggle"
]
```

### 2. CI ENFORCEMENT - ZERO TOLERANCE

```yaml
# Add to GitHub Actions
- name: Validate Tool Inventory
  run: |
    python scripts/generate_canonical_tools.py
    # FAIL HARD if any drift detected
    git diff --exit-code quilt_mcp_tools_canonical.csv
    git diff --exit-code docs/api/TOOLS.md

- name: BANNED TOOLS CHECK
  run: |
    # FAIL BUILD if any deleted tools found in code
    ! grep -r "package_create[^_]" src/ --include="*.py" || exit 1
    ! grep -r "create_package[^_]" src/ --include="*.py" || exit 1
    ! grep -r "packages_search" src/ --include="*.py" || exit 1
    ! grep -r "bucket_objects_search" src/ --include="*.py" || exit 1
    ! grep -r "catalog_uri" src/ --include="*.py" || exit 1
```

### 3. Make Targets

```makefile
# Add to Makefile
.PHONY: tools-generate tools-validate

tools-generate:  ## Auto-generate tool listings from code
 python scripts/generate_canonical_tools.py
 @echo "Generated canonical tool listings"

tools-validate:  ## Validate tool listings match code
 python scripts/generate_canonical_tools.py
 git diff --exit-code quilt_mcp_tools_canonical.csv docs/api/TOOLS.md
 @echo "Tool listings are synchronized"

lint: tools-validate  ## Include tool validation in lint
```

## Success Criteria

1. **Zero Manual Maintenance**: Tool documentation generated entirely from code introspection.
2. **Elimination of Duplicates**: Reduced from 85 tools to ~70 tools through aggressive consolidation.
3. **CI Enforcement**: Builds fail if deprecated tools are used or documentation drifts.
4. **Clear Migration Path**: Comprehensive upgrade guide with 1:1 mappings for all deprecated tools.
5. **Improved Developer Experience**: Single authoritative tool for each use case.

## Migration Timeline

### Phase 1: Preparation (Week 1)

- Implement auto-generation script
- Generate consolidation report
- Create migration documentation

### Phase 2: Breaking Changes (Week 2)

- Remove deprecated tools from exports
- Update all internal usage
- Auto-generate documentation

### Phase 3: Release (Week 3)

- Version bump to v1.0.0
- Release notes with migration guide
- Update CLAUDE.md with new tool patterns

## ZERO TOLERANCE POLICY

**Existing clients WILL break** - This is INTENTIONAL and REQUIRED

**No migration grace period** - Update immediately or stay on old version

**No backward compatibility shims** - Clean break, clean codebase

**Bugs are better than bloat** - Better to fix bugs than maintain 85+ redundant tools

## Quality Gates

1. **Auto-Generation Accuracy**: Generated metadata matches manual verification
2. **Breaking Change Coverage**: All deprecated tools have clear migration paths
3. **CI Enforcement**: Pipeline catches any drift or deprecated tool usage
4. **Documentation Completeness**: Auto-generated docs include all tools with examples

This specification embraces necessary breaking changes to create a sustainable, maintainable tool ecosystem.

# Tool Idempotency Tagging Specification

**Date:** 2024-11-12
**Status:** Proposed
**Related:** `scripts/mcp-test.py`, `scripts/mcp-list.py`

## Problem

The MCP server has **46 tools** but only **21 are included** in the test configuration. Additionally, tools are categorized as idempotent/non-idempotent using a **lazy keyword heuristic** that:

1. **Is incomplete** - Only catches tools with keywords like `create`, `delete`, `set`, etc.
2. **Is unreliable** - May miscategorize tools (e.g., `catalog_configure` modifies state but has no trigger keyword)
3. **Is not explicit** - No source-of-truth metadata in the code itself
4. **Misses edge cases** - Tools like `athena_query_execute` might have side effects depending on the query

### Current State

From `scripts/mcp-list.py:268-269`:

```python
non_idempotent_keywords = ['create', 'update', 'delete', 'put', 'upload', 'set', 'add', 'remove', 'reset', 'rename']
is_idempotent = not any(keyword in tool_name.lower() for keyword in non_idempotent_keywords)
```

**Result:**

- 46 total tools
- 20 categorized as idempotent (43%)
- 26 categorized as non-idempotent (57%)
- **Only 1 tool (`tabulator_table_rename`) marked non-idempotent** in test YAML

## Solution

Add explicit `Metadata:` section to **all tool docstrings** with an `idempotent` field.

### Implementation

#### 1. Docstring Format

Add a `Metadata:` section to every tool's docstring:

```python
def bucket_objects_list(...) -> BucketObjectsListResponse:
    """List objects in an S3 bucket with optional prefix filtering.

    Metadata:
        idempotent: true
        risk_level: safe

    Args:
        bucket: S3 bucket name or s3:// URI
        ...

    Returns:
        List of objects with metadata
    """
```

```python
def package_delete(...) -> PackageDeleteSuccess | PackageDeleteError:
    """Delete a Quilt package from the registry.

    Metadata:
        idempotent: false
        risk_level: high
        requires_confirmation: true

    Args:
        package_name: Name of package to delete
        ...

    Returns:
        Deletion confirmation or error
    """
```

#### 2. Update mcp-list.py to Parse Metadata

Add metadata extraction to `extract_tool_metadata()` in `scripts/mcp-list.py`:

```python
def parse_docstring_metadata(docstring: str) -> Dict[str, Any]:
    """Extract structured metadata from docstring Metadata: section."""
    metadata = {}

    # Find Metadata: section
    metadata_match = re.search(
        r'Metadata:\s*\n((?:\s+\w+:\s*.+\n?)+)',
        docstring,
        re.MULTILINE
    )

    if metadata_match:
        metadata_text = metadata_match.group(1)

        # Parse key-value pairs (stop at next section like Args:)
        for line in metadata_text.split('\n'):
            line = line.strip()
            if not line or line.endswith(':'):  # Empty or next section
                break
            if ':' in line:
                key, value = line.split(':', 1)
                value = value.strip()

                # Parse boolean values
                if value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'

                metadata[key] = value

    return metadata
```

Then use it during tool extraction:

```python
async def extract_tool_metadata(server) -> List[Dict[str, Any]]:
    tools = []

    server_tools = await server.get_tools()
    for tool_name, handler in server_tools.items():
        doc = inspect.getdoc(handler.fn) or "No description available"

        # Parse metadata from docstring
        docstring_metadata = parse_docstring_metadata(doc)

        # Determine idempotency
        if 'idempotent' in docstring_metadata:
            is_idempotent = docstring_metadata['idempotent']
        else:
            # Fallback to keyword heuristic with warning
            non_idempotent_keywords = ['create', 'update', 'delete', ...]
            is_idempotent = not any(kw in tool_name.lower() for kw in non_idempotent_keywords)
            print(f"⚠️  {tool_name}: No metadata, using heuristic (idempotent={is_idempotent})")

        tools.append({
            "name": tool_name,
            "idempotent": is_idempotent,
            "metadata": docstring_metadata,
            ...
        })

    return tools
```

#### 3. Test Configuration Generation

Update YAML generation to include ALL tools, not just the 21-tool whitelist:

```python
# Remove the hardcoded tool_order list
# Instead, generate for ALL tools with priority ordering

# Categorize tools by test priority
test_priority = {
    'phase1_setup': [],        # catalog_configure, etc.
    'phase2_idempotent': [],   # Safe read operations
    'phase3_low_risk': [],     # add, update operations
    'phase4_medium_risk': [],  # create, set operations
    'phase5_high_risk': []     # delete, remove operations
}

for tool_name, handler in server_tools.items():
    metadata = parse_docstring_metadata(inspect.getdoc(handler.fn))

    is_idempotent = metadata.get('idempotent', True)
    risk_level = metadata.get('risk_level', 'safe')

    if tool_name in ['catalog_configure']:
        test_priority['phase1_setup'].append(tool_name)
    elif is_idempotent:
        test_priority['phase2_idempotent'].append(tool_name)
    elif risk_level == 'low':
        test_priority['phase3_low_risk'].append(tool_name)
    elif risk_level == 'medium':
        test_priority['phase4_medium_risk'].append(tool_name)
    else:  # high risk
        test_priority['phase5_high_risk'].append(tool_name)
```

## Tool Categorization

### Current Keyword-Based Analysis

Based on the keyword heuristic (as of 2024-11-12):

## Idempotent Tools (Read-Only Operations)

**Count:** 20

| Tool | Module | Description |
|------|--------|-------------|
| `athena_query_execute` | athena_read_service | Execute SQL query against Athena using SQLAlchemy/PyAthena - Athena querying and Glue catalog inspection workflows |
| `athena_query_validate` | athena_read_service | Validate SQL query syntax without executing it - Athena querying and Glue catalog inspection workflows |
| `bucket_object_fetch` | buckets | Fetch binary or text data from an S3 object - S3 bucket exploration and object retrieval tasks |
| `bucket_object_info` | buckets | Get metadata information for a specific S3 object - S3 bucket exploration and object retrieval tasks |
| `bucket_object_link` | buckets | Generate a presigned URL for downloading an S3 object - S3 bucket exploration and object retrieval tasks |
| `bucket_object_text` | buckets | Read text content from an S3 object - S3 bucket exploration and object retrieval tasks |
| `bucket_objects_list` | buckets | List objects in an S3 bucket with optional prefix filtering - S3 bucket exploration and object retrieval tasks |
| `catalog_configure` | catalog | Configure Quilt catalog URL - Quilt authentication and catalog navigation workflows |
| `catalog_uri` | catalog | Build Quilt+ URI - Quilt authentication and catalog navigation workflows |
| `catalog_url` | catalog | Generate Quilt catalog URL - Quilt authentication and catalog navigation workflows |
| `generate_package_visualizations` | quilt_summary | Generate comprehensive visualizations for the package - Quilt summary file generation tasks |
| `generate_quilt_summarize_json` | quilt_summary | Generate a comprehensive quilt_summarize.json file following Quilt standards - Quilt summary file generation tasks |
| `package_browse` | packages | Browse the contents of a Quilt package with enhanced file information - Quilt package discovery and comparison tasks |
| `package_diff` | packages | Compare two package versions and show differences - Quilt package discovery and comparison tasks |
| `search_catalog` | search | Intelligent unified search across Quilt catalog using Elasticsearch - Catalog and package search experiences |
| `search_explain` | search | Explain how a search query would be processed and executed - Catalog and package search experiences |
| `search_suggest` | search | Get intelligent search suggestions based on partial queries and context - Catalog and package search experiences |
| `tabulator_bucket_query` | tabulator_service | Execute a bucket-scoped tabulator query (legacy tool signature). |
| `tabulator_open_query_status` | tabulator_service | Return tabulator open query flag. |
| `workflow_template_apply` | workflow_service | Apply a pre-defined workflow template - Workflow tracking and orchestration tasks |

## Non-Idempotent Tools (State-Modifying Operations)

**Count:** 26

### HIGH Risk (Delete/Remove Operations)

| Tool | Module | Description | Trigger Keywords |
|------|--------|-------------|------------------|
| `admin_sso_config_remove` | governance_service | Remove the SSO configuration - Quilt governance and administrative operations | remove |
| `admin_user_delete` | governance_service | Delete a user from the registry - Quilt governance and administrative operations | delete |
| `admin_user_remove_roles` | governance_service | Remove roles from a user - Quilt governance and administrative operations | remove |
| `package_delete` | packages | Delete a Quilt package from the registry - Core package creation, update, and deletion workflows | delete |
| `tabulator_table_delete` | tabulator_service | Delete tabulator table (legacy tool signature). | delete |

### MEDIUM Risk (Create/Set Operations)

| Tool | Module | Description | Trigger Keywords |
|------|--------|-------------|------------------|
| `admin_sso_config_set` | governance_service | Set the SSO configuration - Quilt governance and administrative operations | set |
| `admin_tabulator_open_query_set` | governance_service | Set the tabulator open query status - Quilt governance and administrative operations | set |
| `admin_user_create` | governance_service | Create a new user in the registry - Quilt governance and administrative operations | create |
| `admin_user_reset_password` | governance_service | Reset a user's password - Quilt governance and administrative operations | reset |
| `admin_user_set_active` | governance_service | Set the active status for a user - Quilt governance and administrative operations | set |
| `admin_user_set_admin` | governance_service | Set the admin status for a user - Quilt governance and administrative operations | set |
| `admin_user_set_email` | governance_service | Update a user's email address - Quilt governance and administrative operations | set |
| `admin_user_set_role` | governance_service | Set the primary and extra roles for a user - Quilt governance and administrative operations | set |
| `create_data_visualization` | data_visualization | Create interactive data visualization for Quilt packages - Generate ECharts configurations from tabular data. | create |
| `create_quilt_summary_files` | quilt_summary | Create all Quilt summary files for a package - Quilt summary file generation tasks | create |
| `package_create` | packages | Create a new Quilt package from S3 objects - Core package creation, update, and deletion workflows | create |
| `package_create_from_s3` | packages | Create a well-organized Quilt package from S3 bucket contents with smart organization - Bulk S3-to-package ingestion workflows | create |
| `tabulator_table_create` | tabulator_service | Create tabulator table (legacy tool signature). | create |
| `workflow_create` | workflow_service | Create a new workflow for tracking multi-step operations - Workflow tracking and orchestration tasks | create |

### LOW Risk (Add/Update Operations)

| Tool | Module | Description | Trigger Keywords |
|------|--------|-------------|------------------|
| `admin_user_add_roles` | governance_service | Add roles to a user - Quilt governance and administrative operations | add |
| `bucket_objects_put` | buckets | Upload multiple objects to an S3 bucket - S3 bucket exploration and object retrieval tasks | put |
| `package_update` | packages | Update an existing Quilt package by adding new S3 objects - Core package creation, update, and deletion workflows | update |
| `tabulator_open_query_toggle` | tabulator_service | Toggle tabulator open query flag. | toggle |
| `tabulator_table_rename` | tabulator_service | Rename tabulator table (legacy tool signature). | rename |
| `workflow_add_step` | workflow_service | Add a step to an existing workflow - Workflow tracking and orchestration tasks | add |
| `workflow_update_step` | workflow_service | Update the status of a workflow step - Workflow tracking and orchestration tasks | update |

### Edge Cases Requiring Manual Review

1. **`catalog_configure`** - Currently marked idempotent, but **modifies persistent state** (catalog URL configuration)
2. **`athena_query_execute`** - Marked idempotent, but **depends on query content** (SELECT is safe, INSERT/UPDATE/DELETE is not)
3. **`generate_*` tools** - Create files but don't persist them, may be considered idempotent in memory
4. **`workflow_template_apply`** - May create workflow state, unclear if idempotent

## Benefits

1. **Explicit documentation** - Idempotency is clearly stated in source code
2. **Better testing** - mcp-test.py can report which non-idempotent tools weren't tested
3. **Safer automation** - AI agents and scripts can check metadata before invoking tools
4. **Complete coverage** - All 46 tools will have test configurations
5. **Risk awareness** - High-risk operations are clearly identified

## Implementation Checklist

- [ ] Add `Metadata: idempotent:` to all 46 tool docstrings
- [ ] Add `parse_docstring_metadata()` to mcp-list.py
- [ ] Update tool extraction to use explicit metadata with fallback
- [ ] Remove 21-tool whitelist, generate configs for ALL tools
- [ ] Add risk categorization (safe/low/medium/high)
- [ ] Regenerate mcp-test.yaml with all 46 tools
- [ ] Update mcp-test.py summary output (already done)
- [ ] Document edge cases that need manual verification

## Testing Strategy

### Phase 1: Idempotent Tools (Safe)

Run frequently, in CI/CD, no side effects

### Phase 2: Low Risk (Add/Update)

Run in staging, reversible operations

### Phase 3: Medium Risk (Create/Set)

Run manually, requires cleanup

### Phase 4: High Risk (Delete/Remove)

Run only in isolated test environments, requires explicit confirmation

## Future Enhancements

1. **Tool capabilities metadata** - `requires_auth`, `requires_admin`, `side_effects`
2. **Cost estimation** - Tools that incur AWS charges
3. **Performance hints** - Expected execution time
4. **Dependency tracking** - Which tools depend on others

## References

- `scripts/mcp-list.py` - Tool metadata extraction
- `scripts/mcp-test.py` - Test execution with non-idempotent tracking
- `scripts/tests/mcp-test.yaml` - Generated test configuration
- `spec/227-input-schemas/solution.md` - Example of `json_schema_extra` usage

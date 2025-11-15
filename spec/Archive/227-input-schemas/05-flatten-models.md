# 05: Flatten Input Parameter Models

## Problem

Current pattern requires nested MCP calls:
```
tool(params={bucket: "x", items: [...]})  ← params wrapper
```

Should be:
```
tool(bucket="x", items=[...])  ← flat parameters
```

The `params` wrapper:
- Creates unnecessary nesting for MCP clients
- Adds boilerplate (`.params.field` access throughout implementation)
- Provides zero value (FastMCP already validates inputs)

## Solution

Use `Annotated[type, Field(...)]` on individual function parameters instead of wrapping in a params model.

**Before:**
```
def bucket_objects_put(params: BucketObjectsPutParams) -> Response
```

**After:**
```
def bucket_objects_put(
    bucket: Annotated[str, Field(...)],
    items: Annotated[list[BucketObjectsPutItem], Field(...)]
) -> Response
```

## What Changes

### Input Parameters
- Remove params wrapper from all tool function signatures
- Convert `ParamsModel` classes to individual `Annotated` parameters
- Update implementations to use parameters directly (not `params.field`)

### Affected Files
- `src/quilt_mcp/tools/buckets.py` - 6 tools
- `src/quilt_mcp/tools/packages.py` - 6 tools
- `src/quilt_mcp/tools/athena_glue.py` - 2 tools
- `src/quilt_mcp/tools/catalog.py` - 4 tools
- `src/quilt_mcp/tools/data_visualization.py` - 1 tool
- `src/quilt_mcp/tools/governance.py` - 14 tools
- `src/quilt_mcp/tools/search.py` - 3 tools
- `src/quilt_mcp/tools/workflow_orchestration.py` - 4 tools
- `src/quilt_mcp/models/inputs.py` - remove ~30 params classes

### Affected Tests
- All integration tests that call these tools
- Unit tests for parameter validation

## What Stays The Same

### Keep These
- **Output/return type models** - provide structured response schemas for MCP clients
- **Nested complex types** - `BucketObjectsPutItem`, `S3Object`, etc. used in arrays/objects
- **All Field metadata** - descriptions, examples, constraints, patterns
- **Validation behavior** - FastMCP validates identically with Annotated

### No Changes To
- Tool behavior/logic
- Response formats
- Error handling patterns
- Authorization flows

## Benefits

- Cleaner MCP tool calls (no params wrapper)
- Less boilerplate code (~25% LOC reduction in tools)
- Better developer experience (direct parameter access)
- Maintains all semantic richness (Field metadata preserved)

## Scope

**~30 tools affected across 8 files**

Breaking change for MCP clients currently using `params` wrapper.

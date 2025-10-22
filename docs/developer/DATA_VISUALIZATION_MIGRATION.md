# Data Visualization Module - Pydantic Migration Summary

## Migration Completed: 2025-10-20

### Overview
Successfully migrated `src/quilt_mcp/tools/data_visualization.py` from using `dict[str, Any]` returns to Pydantic models for type-safe, validated inputs and outputs.

---

## Changes Made

### 1. Model Updates

#### Fixed Model Definitions
**File**: `src/quilt_mcp/models/responses.py`

- **VisualizationConfig.type**: Changed from `Literal["boxplot", "scatter", "line", "bar"]` to `Literal["echarts"]`
  - **Reason**: The `type` field represents the visualization engine (e.g., "echarts"), not the plot type

- **DataVisualizationSuccess.metadata**: Changed from `dict[str, str | int | float]` to `dict`
  - **Reason**: The metadata contains nested structures:
    - `statistics`: dict with mean, median, std, etc.
    - `columns_used`: list of column names
    - `plot_type`, `data_points`, `visualization_engine`: simple values

### 2. Function Signature Migration

**Before**:
```python
def create_data_visualization(
    data: dict[str, Iterable[Any]] | Sequence[Dict[str, Any]] | str,
    plot_type: str,
    x_column: str,
    y_column: Optional[str] = None,
    group_column: Optional[str] = None,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    color_scheme: str = "genomics",
    template: str = "research",
    output_format: str = "echarts",
) -> Dict[str, Any]:
```

**After**:
```python
def create_data_visualization(
    params: DataVisualizationParams,
) -> DataVisualizationSuccess | DataVisualizationError:
```

### 3. Implementation Changes

#### Success Case
**Before**:
```python
return {
    "success": True,
    "visualization_config": {"type": viz.engine, "option": viz.option, "filename": viz.filename},
    "data_file": data_file,
    "quilt_summarize": quilt_sum,
    "files_to_upload": files_to_upload,
    "metadata": {...}
}
```

**After**:
```python
return DataVisualizationSuccess(
    visualization_config=VisualizationConfig(
        type="echarts",
        option=viz.option,
        filename=viz.filename,
    ),
    data_file=VisualizationFile(
        key=data_file["filename"],
        text=data_file["content"],
        content_type=data_file["content_type"],
    ),
    quilt_summarize=VisualizationFile(
        key=quilt_sum["filename"],
        text=json.dumps(quilt_sum["content"], indent=2),
        content_type="application/json",
    ),
    files_to_upload=files_to_upload,
    metadata={...}
)
```

#### Error Case
**Before**:
```python
return {"success": False, "error": str(exc), "suggestion": _get_error_suggestion(exc)}
```

**After**:
```python
return DataVisualizationError(
    error=str(exc),
    possible_fixes=[_get_error_suggestion(exc)],
    plot_type=getattr(params, "plot_type", None),
    x_column=getattr(params, "x_column", None),
    y_column=getattr(params, "y_column", None),
)
```

### 4. Test Updates

**File**: `tests/unit/test_data_visualization.py`

All tests updated to:
1. Import `DataVisualizationParams`
2. Create params objects: `params = DataVisualizationParams(...)`
3. Access response fields as attributes: `result.success`, `result.visualization_config`
4. Use Pydantic models throughout

---

## Benefits of Migration

### 1. Type Safety
- **Before**: `result["visualization_config"]["option"]` - no type hints, prone to typos
- **After**: `result.visualization_config.option` - IDE autocomplete, static type checking

### 2. Validation
- Input parameters validated automatically by Pydantic
- Invalid plot types, missing columns caught at model level
- Clear validation error messages

### 3. Documentation
- Model fields have descriptions and examples
- MCP automatically generates JSON schemas from models
- Self-documenting API

### 4. Consistency
- All tools now follow the same pattern
- Easier to maintain and extend
- Follows project conventions

---

## Backward Compatibility

### MCP Tool Registration
The FastMCP framework automatically handles conversion:
```python
# MCP receives kwargs dict
@server.tool()
async def create_data_visualization(**kwargs) -> Dict[str, Any]:
    # Automatically converts to Pydantic model
    params = DataVisualizationParams(**kwargs)
    result = create_data_visualization(params)
    # Converts back to dict for MCP
    return result.model_dump()
```

### Direct Function Calls
Code calling the function directly needs to be updated:
```python
# Old way (no longer supported)
result = create_data_visualization(
    data=my_data,
    plot_type="boxplot",
    x_column="gene",
    y_column="expression"
)

# New way
from quilt_mcp.models import DataVisualizationParams
params = DataVisualizationParams(
    data=my_data,
    plot_type="boxplot",
    x_column="gene",
    y_column="expression"
)
result = create_data_visualization(params)
```

---

## Testing Results

### Unit Tests
✅ All 3 tests in `test_data_visualization.py` pass:
- `test_boxplot_from_dict_data`
- `test_scatter_from_csv_string`
- `test_missing_column_returns_error`

### Full Test Suite
✅ 427 passed, 19 failed (unrelated to this migration - catalog.py issues)

### Type Checking
- Models provide full type hints
- Pydantic ensures runtime validation matches type hints

---

## Related Files Modified

1. **src/quilt_mcp/tools/data_visualization.py**
   - Function signature updated
   - Implementation updated to use Pydantic models
   - Docstring updated

2. **src/quilt_mcp/models/responses.py**
   - Fixed `VisualizationConfig.type` field
   - Fixed `DataVisualizationSuccess.metadata` field type

3. **tests/unit/test_data_visualization.py**
   - All tests updated to use Pydantic models
   - Test assertions updated for attribute access

---

## Key Learnings

### 1. Field Type Precision
- Don't over-constrain types (e.g., `dict` vs `dict[str, str | int | float]`)
- Consider nested structures when defining types
- Review actual data structure before defining model

### 2. Model Validation
- Pydantic validates on construction, catching errors early
- Validation errors are clear and actionable
- Models can catch issues that dict-based code would miss

### 3. Testing with Models
- Models make tests more explicit and readable
- Type hints help catch test bugs during development
- Attribute access (`result.field`) clearer than dict access (`result["field"]`)

---

## Next Steps

### Potential Improvements
1. Create a dedicated `VisualizationMetadata` model for the metadata field
2. Add custom validators for plot_type compatibility checks
3. Consider adding computed fields for common metadata queries

### Other Tools to Migrate
Following the same pattern established here, these tools could benefit from migration:
- `quilt_summary.py` - Summary file generation tools
- `workflow_orchestration.py` - Workflow tools (partially done)
- Any remaining tools still returning `dict[str, Any]`

---

## References

- [Pydantic Migration Guide](./PYDANTIC_MIGRATION_GUIDE.md)
- [Migration Status Report](./PYDANTIC_MIGRATION_STATUS.md)
- [Pydantic Documentation](https://docs.pydantic.dev/)

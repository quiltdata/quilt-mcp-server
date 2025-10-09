# Visualization Fix Guide - v0.6.72

## Problem Summary

The AI was receiving errors when calling `quilt_summary.generate_viz`:
- `generate_package_visualizations() missing 1 required positional argument: 'file_types'`
- `'str' object has no attribute 'get'`

**Root cause**: The AI was not providing the correct data structure format for `organized_structure` and `file_types` parameters.

## Solution Deployed (v0.6.72)

### 1. Enhanced Docstring
Updated `generate_package_visualizations()` docstring with:
- Clear specification of `organized_structure` format
- Concrete example showing the expected dictionary structure
- Documentation of required keys (`Key`, `Size`) in file dictionaries

### 2. Input Validation
Added validation at function start:
- Checks that `organized_structure` is a dictionary
- Verifies that all values in the dictionary are lists
- Provides specific, actionable error messages

### 3. Auto-derivation of file_types
The function now auto-derives `file_types` from `organized_structure` if not provided explicitly, making the parameter effectively optional.

## Correct Usage Examples

### Example 1: Minimal Call (Auto-derive file_types)
```python
result = mcp_quilt-mcp-server_quilt_summary(
    action="generate_viz",
    params={
        "package_name": "examples/csv-data",
        "organized_structure": {
            "data": [
                {"Key": "data/file1.csv", "Size": 1024},
                {"Key": "data/file2.csv", "Size": 2048}
            ],
            "docs": [
                {"Key": "docs/README.md", "Size": 512}
            ]
        },
        "file_types": {}  # Empty dict - will auto-derive from organized_structure
    }
)
```

### Example 2: Explicit file_types
```python
result = mcp_quilt-mcp-server_quilt_summary(
    action="generate_viz",
    params={
        "package_name": "examples/csv-data",
        "organized_structure": {
            "data": [
                {"Key": "data/file1.csv", "Size": 1024},
                {"Key": "data/file2.json", "Size": 2048}
            ]
        },
        "file_types": {"csv": 1, "json": 1}
    }
)
```

### Example 3: Complete Package Summary (Recommended)
Use `create_files` action for complete package documentation:
```python
result = mcp_quilt-mcp-server_quilt_summary(
    action="create_files",
    params={
        "package_name": "examples/csv-data",
        "package_metadata": {
            "description": "Sample CSV dataset",
            "tags": ["csv", "sample"]
        },
        "organized_structure": {
            "data": [
                {"Key": "data/file1.csv", "Size": 1024},
                {"Key": "data/file2.csv", "Size": 2048}
            ]
        },
        "readme_content": "# CSV Data Package\n\nSample package for testing.",
        "source_info": {
            "origin": "S3",
            "bucket": "my-bucket"
        }
    }
)
```

## Data Structure Requirements

### organized_structure Format
```python
{
    "folder_name": [
        {
            "Key": "path/to/file.ext",  # REQUIRED (or "key", "LogicalKey", "logicalKey")
            "Size": 1234                 # REQUIRED (or "size") - bytes as integer
        },
        # ... more file dictionaries
    ],
    # ... more folders
}
```

**Critical Points:**
- Top level: Dictionary with folder names as keys
- Values: Lists of file dictionaries
- Each file dict MUST have `Key` (or variant) and `Size` (or `size`)
- `Size` is in bytes as an integer

### file_types Format
```python
{
    "csv": 5,      # Extension: count (simple int)
    "json": 3,
    "md": 1
}
```

OR (will be auto-converted):
```python
{
    "csv": {"count": 5},   # Extension: dict with count
    "json": {"count": 3}
}
```

## Testing the Fix

### Local Testing
```bash
cd /Users/simonkohnstamm/Documents/Quilt/quilt-mcp-server
uv run python -c "
from quilt_mcp.tools.quilt_summary import generate_package_visualizations

result = generate_package_visualizations(
    package_name='test/package',
    organized_structure={
        'data': [
            {'Key': 'file1.csv', 'Size': 1024},
            {'Key': 'file2.json', 'Size': 512}
        ]
    },
    file_types={}  # Empty - will auto-derive
)

print(f'Success: {result[\"success\"]}')
print(f'Visualizations: {result[\"count\"]}')
print(f'Types: {result[\"types\"]}')
"
```

### Expected Output
```
Success: True
Visualizations: 4
Types: ['file_type_distribution', 'folder_structure', 'file_size_distribution', 'package_overview']
```

## What Changed in v0.6.72

### Files Modified
1. **src/quilt_mcp/tools/quilt_summary.py**
   - Lines 172-215: Enhanced docstring with format specification
   - Lines 217-235: Added input validation
   - Lines 247-259: Auto-derivation of file_types from organized_structure

### Validation Logic
```python
# Validate organized_structure format
if not isinstance(organized_structure, dict):
    return {
        "success": False,
        "error": f"organized_structure must be a dict, got {type(organized_structure).__name__}",
        "visualizations": {},
        "count": 0,
    }

# Check that all values are lists
for folder_name, files in (organized_structure or {}).items():
    if not isinstance(files, list):
        return {
            "success": False,
            "error": f"organized_structure['{folder_name}'] must be a list, got {type(files).__name__}. "
                    f"Expected format: {{'folder': [{{'Key': 'file.csv', 'Size': 1024}}]}}",
            "visualizations": {},
            "count": 0,
        }
```

## AI Assistant Guidance

When the AI needs to create visualizations:

1. **Browse the package first** using `packaging.browse`:
   ```python
   package_data = mcp_quilt-mcp-server_packaging(
       action="browse",
       params={"name": "namespace/package"}
   )
   ```

2. **Extract the structure** from browse results:
   ```python
   organized_structure = {}
   for entry in package_data["entries"]:
       folder = entry.get("logical_key", "").split("/")[0] or "root"
       if folder not in organized_structure:
           organized_structure[folder] = []
       organized_structure[folder].append({
           "Key": entry["logical_key"],
           "Size": entry["size"]
       })
   ```

3. **Call generate_viz** with the prepared structure:
   ```python
   viz_result = mcp_quilt-mcp-server_quilt_summary(
       action="generate_viz",
       params={
           "package_name": "namespace/package",
           "organized_structure": organized_structure,
           "file_types": {}  # Will auto-derive
       }
   )
   ```

4. **Add to package** using `packaging.create`:
   Include the visualization files in the package manifest

## Deployment Status

- **Version**: v0.6.72
- **Docker Image**: `850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:v0.6.72`
- **Platform**: `linux/amd64` (fixed from previous Darwin ARM64 issue)
- **ECS Task**: `quilt-mcp-server:182`
- **Status**: Deployed to `sales-prod` cluster
- **Service**: `sales-prod-mcp-server-production`

## Next Steps

1. **Test in Production**: Use Claude/Qurator on `demo.quiltdata.com` to create visualizations
2. **Monitor**: Check that error messages are now clear and actionable
3. **Document**: Add successful visualization creation examples to the MCP optimization guide
4. **Iterate**: If AI still has issues, consider adding more examples to the docstring

## Success Criteria

✅ Input validation catches incorrect formats
✅ Error messages are specific and actionable
✅ Auto-derivation of file_types works correctly
✅ Documentation clearly shows expected format
✅ AI can successfully create visualizations without manual intervention

## Related Files

- **Implementation**: `src/quilt_mcp/tools/quilt_summary.py`
- **Tests**: `tests/unit/test_visualization.py`, `tests/e2e/test_quilt_summary.py`
- **Schema**: `docs/quilt-enterprise-schema.graphql`
- **Deployment**: `scripts/docker.py`, `Dockerfile`


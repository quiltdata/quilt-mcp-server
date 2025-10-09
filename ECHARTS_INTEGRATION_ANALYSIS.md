# ECharts Integration Analysis

## Current State

### What We Have
1. **Full ECharts Support**: `src/quilt_mcp/visualization/generators/echarts.py`
   - Bar charts, line charts, scatter plots, pie charts, heatmaps
   - Generates JSON configurations compatible with ECharts library
   - Used by `VisualizationEngine` for interactive charts

2. **VisualizationEngine**: `src/quilt_mcp/visualization/engine.py`
   - Uses ECharts generator for package overview visualizations
   - Outputs JSON configs to files
   - Creates `quilt_summarize.json` with ECharts references

3. **MCP Tool**: `src/quilt_mcp/tools/quilt_summary.py`
   - **Currently only uses matplotlib** for PNG generation
   - Not leveraging the existing ECharts infrastructure
   - Outputs base64-encoded PNG images + widget configs

### The Gap

**The `quilt_summary` MCP tool doesn't use ECharts**, even though we have full ECharts support implemented!

```python
# Current flow in quilt_summary.py:
matplotlib.pyplot → PNG image → base64 encoding → JSON

# Available but unused flow:
EChartsGenerator → JSON config → quilt_summarize.json
```

### What Should Happen

When the AI calls `quilt_summary.generate_viz`, it should generate **ECharts JSON configurations** that can be:
1. Embedded directly in `quilt_summarize.json`
2. Rendered interactively in the Quilt catalog UI
3. No image encoding needed - pure JSON

## ECharts Benefits

### Advantages Over matplotlib PNG

| Feature | matplotlib PNG | ECharts JSON |
|---------|---------------|--------------|
| **File Size** | Large (base64 encoded) | Small (pure JSON) |
| **Interactivity** | None | Full (zoom, pan, tooltips) |
| **Rendering** | Pre-rendered | Client-side on-demand |
| **Customization** | Fixed at generation | User can interact |
| **Accessibility** | Limited | Screen reader friendly |
| **Mobile** | Fixed size | Responsive |

### User Experience Example

**matplotlib PNG**:
```json
{
  "visualization": {
    "image_base64": "iVBORw0KGgoAAAANSUhEUgAAA...[5000+ characters]",
    "mime_type": "image/png"
  }
}
```

**ECharts JSON** (like the user's example):
```json
{
  "visualization": {
    "type": "echarts",
    "config": {
      "color": ["#80FFA5", "#00DDFF", "#37A2FF"],
      "title": {"text": "File Type Distribution"},
      "tooltip": {"trigger": "axis"},
      "series": [{
        "name": "Files",
        "type": "pie",
        "data": [
          {"value": 335, "name": "CSV"},
          {"value": 310, "name": "JSON"}
        ]
      }]
    }
  }
}
```

## Proposed Solution

### Option 1: Replace matplotlib with ECharts (Recommended)
**Pros**:
- Better UX (interactive charts)
- Smaller file sizes
- Already implemented
- Consistent with VisualizationEngine

**Cons**:
- Breaking change for existing PNG consumers (if any)

### Option 2: Support Both Formats
**Pros**:
- No breaking changes
- User can choose format

**Cons**:
- More complex code
- Redundant implementations

### Option 3: Hybrid Approach
**Pros**:
- ECharts for web display
- PNG fallback for thumbnails/exports

**Cons**:
- Most complex
- Larger output size

## Recommended Implementation

### Phase 1: Add ECharts to quilt_summary.py

```python
from quilt_mcp.visualization.generators.echarts import EChartsGenerator

def generate_package_visualizations(
    package_name: str,
    organized_structure: Dict[str, List[Dict[str, Any]]],
    file_types: Dict[str, Any],
    metadata_template: str = "standard",
    output_format: str = "echarts",  # New parameter: "echarts", "png", or "both"
    **_extra: Any,
) -> Dict[str, Any]:
    """Generate visualizations in ECharts or PNG format."""
    
    if output_format in ("echarts", "both"):
        # Use EChartsGenerator
        echarts_gen = EChartsGenerator()
        
        # File type pie chart
        file_type_config = echarts_gen.create_pie_chart(
            data={"types": list(file_types.keys()), "counts": list(file_types.values())},
            categories="types",
            values="counts",
            title=f"File Type Distribution - {package_name}"
        )
        
        visualizations["file_type_distribution"] = {
            "type": "echarts",
            "config": file_type_config,
            "description": "Interactive file type distribution"
        }
    
    if output_format in ("png", "both"):
        # Existing matplotlib code
        ...
```

### Phase 2: Update quilt_summarize.json Structure

```json
{
  "version": "1.0",
  "package": "namespace/package-name",
  "visualizations": {
    "file_type_distribution": {
      "type": "echarts",
      "config": {
        "title": {"text": "File Type Distribution"},
        "series": [...]
      }
    },
    "folder_structure": {
      "type": "echarts",
      "config": {
        "title": {"text": "Folder Structure"},
        "series": [...]
      }
    }
  },
  "visualization_dashboards": [
    {
      "id": "package-overview",
      "title": "Package Overview",
      "widgets": [
        {
          "type": "chart",
          "chart_type": "echarts",
          "config": {...}
        }
      ]
    }
  ]
}
```

### Phase 3: Test with Quilt Catalog

1. Generate ECharts configs using MCP tool
2. Add to package via `packaging.create`
3. Verify rendering in `demo.quiltdata.com`
4. Validate interactivity (zoom, tooltips, etc.)

## Implementation Checklist

- [ ] Add `output_format` parameter to `generate_package_visualizations`
- [ ] Import and use `EChartsGenerator` in `quilt_summary.py`
- [ ] Create ECharts pie chart for file types
- [ ] Create ECharts bar chart for folder structure
- [ ] Create ECharts histogram for file sizes
- [ ] Update `visualization_dashboards` to use ECharts configs
- [ ] Add tests for ECharts output format
- [ ] Update documentation
- [ ] Test with real packages on demo.quiltdata.com

## Testing Strategy

### Unit Tests
```python
def test_generate_visualizations_echarts_format():
    """Test ECharts format generation."""
    result = generate_package_visualizations(
        package_name="test/pkg",
        organized_structure={"data": [{"Key": "file.csv", "Size": 1024}]},
        file_types={"csv": 1},
        output_format="echarts"
    )
    
    assert result["success"] is True
    assert "file_type_distribution" in result["visualizations"]
    assert result["visualizations"]["file_type_distribution"]["type"] == "echarts"
    assert "config" in result["visualizations"]["file_type_distribution"]
    assert "series" in result["visualizations"]["file_type_distribution"]["config"]
```

### Integration Tests
```python
async def test_quilt_summary_with_echarts():
    """Test complete package summary with ECharts."""
    result = await quilt_summary(
        action="generate_viz",
        params={
            "package_name": "examples/test",
            "organized_structure": {...},
            "file_types": {"csv": 5},
            "output_format": "echarts"
        }
    )
    
    # Verify ECharts structure
    assert "visualization_dashboards" in result
    for dashboard in result["visualization_dashboards"]:
        for widget in dashboard["widgets"]:
            if widget["type"] == "chart":
                assert "config" in widget
```

### E2E Tests (Browser)
1. Navigate to `demo.quiltdata.com`
2. Create a package with ECharts visualizations
3. Verify charts render correctly
4. Test interactivity (tooltips, zoom, etc.)
5. Verify responsive behavior on mobile

## Migration Path

### For Existing Packages (Optional)
If packages already have matplotlib PNGs, we can:
1. Keep PNG images as fallback
2. Add ECharts configs alongside
3. Let catalog UI prefer ECharts when available
4. Deprecate PNG generation in future version

### For New Packages
- Default to ECharts format
- Only generate PNGs if explicitly requested
- Document ECharts as the recommended format

## Questions to Resolve

1. **Does the Quilt catalog UI currently support ECharts?**
   - Need to verify in `demo.quiltdata.com`
   - Check if `quilt_summarize.json` with ECharts configs renders

2. **Should we maintain matplotlib support?**
   - For backwards compatibility?
   - For use cases where PNGs are needed (exports, emails)?

3. **What's the preferred structure for ECharts in quilt_summarize.json?**
   - Inline in `visualizations` object?
   - Referenced by path?
   - In `visualization_dashboards` widgets?

## Next Steps

1. **Verify catalog support**: Check if demo.quiltdata.com renders ECharts
2. **Implement ECharts generation**: Add to `quilt_summary.py`
3. **Test end-to-end**: Create package with ECharts, verify rendering
4. **Document**: Update guide for AI assistants
5. **Deploy**: Push to production

## Expected Outcome

After implementation, the AI should be able to:
```
User: "Create visualizations for this package"
AI: Calls quilt_summary.generate_viz with ECharts format
Result: Interactive charts in quilt_summarize.json that render in catalog UI
```

No more base64 PNG images, no more static charts - just pure, interactive ECharts JSON!


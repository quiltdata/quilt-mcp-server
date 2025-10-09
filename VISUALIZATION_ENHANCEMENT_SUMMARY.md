# Visualization Enhancement Summary

## Current State vs. Desired State

### What We Have Now (v0.6.72)
- ✅ **ECharts Generator**: Fully implemented but **only used by VisualizationEngine**, not by MCP tool
- ✅ **matplotlib PNG generation**: Used by `quilt_summary` tool (generates base64-encoded images)
- ❌ **No Vega/Vega-Lite support**
- ❌ **No Perspective support**
- ❌ **No IGV support**
- ❌ **No intelligent format selection**
- ❌ **No automatic `quilt_summarize.json` generation**

### What You Want
From [[the Quilt documentation](https://docs.quilt.bio/quilt-platform-catalog-user/visualizationdashboards)]:

1. **Multi-Format Support**:
   - **Vega/Vega-Lite** for statistical charts
   - **ECharts** for interactive charts (already have, not using in MCP tool!)
   - **Perspective** for data grids
   - **IGV** for genomic data

2. **Intelligent Selection**:
   - Auto-detect data type from file extensions
   - Choose optimal visualizer based on viz type needed
   - IGV for BAM/VCF, Perspective for CSV, etc.

3. **Automatic Integration**:
   - Generate visualization JSON files
   - Create `quilt_summarize.json` entries
   - Include files in package automatically

## The Gap

### Critical Discovery
**We already have ECharts implemented** (`src/quilt_mcp/visualization/generators/echarts.py`) but:
- `VisualizationEngine` uses it ✅
- `quilt_summary` MCP tool **does NOT use it** ❌
- AI assistants can't access ECharts through MCP ❌

### Missing Pieces
1. **VegaLiteGenerator** - Need to implement
2. **IGVConfigGenerator** - Need to implement
3. **Perspective config generation** - Need to implement (simple, just file refs)
4. **MultiFormatVisualizationGenerator** - Orchestrator with intelligent selection
5. **Integration into quilt_summary tool** - New `generate_multi_viz` action
6. **Automatic quilt_summarize.json generation** - Return ready-to-use config

## Implementation Scope

### High-Level Tasks

1. **Create Missing Generators** (Est: 4-6 hours)
   - `VegaLiteGenerator` class with common chart types
   - `IGVConfigGenerator` class for genomic data
   - Perspective config helper (simpler, mostly file refs)

2. **Build Intelligent Selector** (Est: 2-3 hours)
   - `MultiFormatVisualizationGenerator` class
   - File extension detection logic
   - Visualization type mapping
   - Format selection algorithm

3. **Integrate with MCP Tool** (Est: 2-3 hours)
   - Add `generate_multi_viz` action to `quilt_summary`
   - Generate visualization files
   - Create `quilt_summarize.json` entries
   - Return files ready for package inclusion

4. **Enhanced Documentation** (Est: 1-2 hours)
   - Update tool docstring with format selection guide
   - Add examples for each format
   - Document best practices

5. **Testing** (Est: 3-4 hours)
   - Unit tests for each generator
   - Integration tests
   - E2E browser tests on demo.quiltdata.com

**Total Estimate**: 12-18 hours of focused development

## Recommended Approach

### Option 1: Complete Implementation (Recommended for Production)
**Pros**:
- Full feature parity with Quilt docs
- Best user experience
- Leverages existing ECharts code
- Future-proof

**Cons**:
- Significant development effort (12-18 hours)
- Needs thorough testing
- Requires E2E validation

**Timeline**: 2-3 days

### Option 2: Phase Implementation
**Phase 1** (Quick Win - 4 hours):
- Connect existing ECharts to MCP tool
- Add basic `quilt_summarize.json` generation
- Document ECharts usage in tool

**Phase 2** (Expand - 4 hours):
- Add Vega-Lite generator
- Add basic file type detection

**Phase 3** (Complete - 4 hours):
- Add IGV and Perspective support
- Implement intelligent selection
- Full testing

**Pros**:
- Incremental value delivery
- Can validate each phase
- Lower initial risk

**Cons**:
- Takes longer overall
- Multiple deployment cycles

### Option 3: Immediate Quick Fix (2 hours)
Just connect existing ECharts to `quilt_summary` tool:
- Replace matplotlib with ECharts in `generate_package_visualizations`
- Use existing `EChartsGenerator`
- Generate `quilt_summarize.json` entries
- Test on demo.quiltdata.com

**Pros**:
- Immediate improvement
- Uses existing code
- Smaller, safer change

**Cons**:
- Doesn't address full requirement
- No Vega/Perspective/IGV support
- No intelligent selection

## Decision Required

**Which approach do you prefer?**

1. **Full implementation** (Option 1) - Complete multi-format support with intelligent selection
2. **Phased approach** (Option 2) - Start with ECharts, add others incrementally
3. **Quick fix** (Option 3) - Just connect existing ECharts to MCP tool now

## Immediate Next Step (Recommended)

Regardless of long-term choice, I recommend **Option 3 as Phase 0**:

### Why Start with ECharts Integration?
1. **Already implemented** - 90% of code exists
2. **Immediate value** - Better than matplotlib PNGs
3. **Low risk** - Small, focused change
4. **Validates approach** - Test catalog rendering
5. **Foundation** - Sets pattern for other formats

### What This Delivers
After 2-3 hours:
- ✅ Interactive ECharts instead of static PNGs
- ✅ Smaller file sizes (JSON vs base64 PNG)
- ✅ `quilt_summarize.json` generation
- ✅ Catalog rendering validated
- ✅ Pattern established for other formats

Then we can discuss whether to continue with Vega/Perspective/IGV.

## Technical Notes

### ECharts Integration (Quick Fix)
The change is straightforward:

**Current** (`quilt_summary.py`):
```python
# Uses matplotlib
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
# ... generate PNG ...
img_base64 = base64.b64encode(img_buffer.getvalue())
```

**Updated**:
```python
# Use existing EChartsGenerator
from quilt_mcp.visualization.generators.echarts import EChartsGenerator

echarts_gen = EChartsGenerator()
config = echarts_gen.create_pie_chart(data, "types", "counts", title)

# Save as JSON file
with open("visualizations/file_distribution.json", "w") as f:
    json.dump(config, f)

# Add to quilt_summarize.json
quilt_summarize_entry = {
    "path": "visualizations/file_distribution.json",
    "title": "File Type Distribution",
    "types": ["echarts"]
}
```

### Files to Modify
1. `src/quilt_mcp/tools/quilt_summary.py` - Update `generate_package_visualizations`
2. Update return structure to include `quilt_summarize` entries
3. Return visualization files as strings/objects for package inclusion

### Files to Create (for full implementation)
1. `src/quilt_mcp/visualization/generators/vega_lite.py`
2. `src/quilt_mcp/visualization/generators/igv.py`
3. `src/quilt_mcp/visualization/multi_format.py`
4. `tests/unit/test_vega_lite_generator.py`
5. `tests/unit/test_igv_generator.py`
6. `tests/unit/test_multi_format.py`

## References Created

I've created two comprehensive documents:

1. **`ECHARTS_INTEGRATION_ANALYSIS.md`** - Analysis of current ECharts support
2. **`MULTI_FORMAT_VISUALIZATION_SPEC.md`** - Complete specification for multi-format support (500+ lines)

These provide:
- Detailed implementation plans
- Format selection matrices
- JSON structure examples
- Testing strategies
- Docstring templates

## Questions for You

1. **Which approach?** Full implementation, phased, or quick fix?
2. **Timeline?** How urgent is this feature?
3. **Priority formats?** If phased, which formats are most critical?
4. **Testing scope?** How much E2E testing on demo.quiltdata.com?

## My Recommendation

**Start with Quick Fix (Option 3), then assess:**

1. **Now** (2-3 hours): Connect ECharts to MCP tool
2. **Test**: Validate on demo.quiltdata.com  
3. **Deploy**: Push v0.6.73 with ECharts support
4. **Decide**: Based on user feedback, proceed with full multi-format or iterate

This gives immediate value while preserving the option for full implementation.

**Ready to proceed?** Let me know which approach you'd like, and I'll begin implementation.


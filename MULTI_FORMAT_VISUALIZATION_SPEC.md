# Multi-Format Visualization Specification

## Overview

Implement intelligent, multi-format visualization generation in the `quilt_summary` tool to support all 5 Quilt catalog visualization types:

1. **Vega/Vega-Lite** - Declarative visualization grammar (statistical charts)
2. **ECharts** - Interactive JavaScript charts
3. **Perspective** - Streaming data grids with pivot/filter
4. **IGV** - Genomic data visualization
5. **Voila** - Interactive Jupyter notebooks (already supported, out of scope)

## Visualization Selection Matrix

### By Data Type

| Data Type | File Extensions | Recommended Visualizer | Fallback |
|-----------|----------------|----------------------|----------|
| **Genomic** | `.bam`, `.vcf`, `.bed`, `.gff`, `.gtf`, `.bigwig`, `.bw` | **IGV** | None |
| **Tabular** | `.csv`, `.tsv`, `.xlsx`, `.xls`, `.parquet`, `.jsonl` | **Perspective** | Vega-Lite |
| **Time Series** | `.csv`, `.json` (with timestamp column) | **Vega-Lite** (line) | ECharts (line) |
| **Statistical** | `.csv`, `.json` (numerical data) | **Vega-Lite** | ECharts |
| **Hierarchical** | `.json` (nested structure) | **ECharts** (tree/sunburst) | Vega |
| **Geospatial** | `.geojson`, `.topojson` | **Vega-Lite** (map) | Vega |
| **Network** | `.json` (nodes/edges) | **ECharts** (graph) | Vega |

### By Visualization Type

| Visualization | Best Tool | Reason |
|--------------|-----------|---------|
| **Bar Chart** | ECharts / Vega-Lite | Both excellent, ECharts more interactive |
| **Line Chart** | Vega-Lite / ECharts | Vega-Lite better for multi-series |
| **Scatter Plot** | Vega-Lite | Superior for statistical analysis |
| **Pie Chart** | ECharts | Better interactivity and animations |
| **Histogram** | Vega-Lite | Built-in binning and aggregation |
| **Box Plot** | Vega-Lite | Native statistical support |
| **Heatmap** | ECharts / Vega-Lite | ECharts for large datasets |
| **Treemap** | ECharts | Better hierarchical support |
| **Sunburst** | ECharts | Native hierarchical radial layout |
| **Data Grid** | Perspective | Only tool for interactive tables |
| **Genome Track** | IGV | Only tool for genomic data |

## Tool Capabilities

### 1. Vega-Lite

**Strengths**:
- Declarative, concise syntax
- Excellent for statistical visualizations
- Native support for data transformations (binning, aggregation)
- Built-in statistical visualizations (box plots, error bars)
- Automatic axis and legend generation
- Good for publication-quality charts

**Chart Types**:
- Bar (grouped, stacked)
- Line (single, multi-series)
- Scatter (with regression lines)
- Area (stacked, normalized)
- Histogram (with automatic binning)
- Box plot
- Heat map
- Circle/point maps
- Faceted/trellis plots

**JSON Format**:
```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "description": "A simple bar chart",
  "data": {"url": "./data.csv"},
  "mark": "bar",
  "encoding": {
    "x": {"field": "category", "type": "nominal"},
    "y": {"field": "value", "type": "quantitative"}
  }
}
```

**Use When**:
- Need statistical transformations
- Creating publication-quality charts
- Data needs binning or aggregation
- Multiple linked views (dashboards)

### 2. ECharts

**Strengths**:
- Highly interactive (zoom, pan, tooltips)
- Beautiful animations
- Excellent for hierarchical data
- Large dataset support
- Rich customization options
- Mobile-friendly

**Chart Types**:
- Bar (3D, stacked, waterfall)
- Line (area, smooth, step)
- Pie (doughnut, rose, nested)
- Scatter (bubble, with symbol sizes)
- Heatmap (calendar, geographic)
- Tree (horizontal, radial)
- Treemap
- Sunburst
- Graph (force-directed, circular)
- Gauge, funnel, sankey
- Candlestick (financial)

**JSON Format**:
```json
{
  "title": {"text": "Sample Chart"},
  "tooltip": {"trigger": "axis"},
  "xAxis": {"type": "category", "data": ["Mon", "Tue", "Wed"]},
  "yAxis": {"type": "value"},
  "series": [{
    "type": "line",
    "data": [120, 200, 150]
  }]
}
```

**Use When**:
- Need rich interactivity
- Visualizing hierarchical data
- Creating animated charts
- Need advanced customization
- Mobile responsiveness required

### 3. Perspective

**Strengths**:
- Real-time streaming data
- Interactive pivoting and filtering
- Sorting and aggregation
- Export capabilities
- Large dataset support (6MB+ compressed)
- Multiple view types (grid, chart, map)

**Supported Formats**:
- CSV, TSV
- Excel (`.xls`, `.xlsx`)
- Parquet
- JSONL (JSON Lines)

**JSON Format** (configuration):
```json
{
  "path": "data.csv",
  "types": [{
    "name": "perspective",
    "config": {
      "columns": ["col1", "col2"],
      "group_by": ["col1"],
      "settings": true,
      "theme": "Material Light"
    }
  }]
}
```

**Use When**:
- Need interactive data exploration
- Users need to pivot/filter data
- Working with large tabular datasets
- Need multiple aggregation views
- Data analysis workflow

### 4. IGV (Integrative Genomics Viewer)

**Strengths**:
- Industry standard for genomics
- Supports all major genomic formats
- Multi-track visualization
- Zoom and pan through genome
- Reference genome integration
- Annotation track support

**Supported Formats**:
- BAM (aligned reads)
- VCF (variants)
- BED (genomic regions)
- GFF/GTF (gene annotations)
- BigWig/BigBed (signal tracks)
- SEG (copy number)

**JSON Format**:
```json
{
  "genome": "hg38",
  "locus": "chr1:1-1000000",
  "tracks": [
    {
      "name": "Alignments",
      "url": "./alignments.bam",
      "indexURL": "./alignments.bam.bai",
      "format": "bam",
      "type": "alignment"
    },
    {
      "name": "Variants",
      "url": "./variants.vcf",
      "format": "vcf",
      "type": "variant"
    }
  ]
}
```

**Use When**:
- Working with genomic data
- Need genome browser functionality
- Multiple genomic tracks
- Reference genome alignment

### 5. Vega (Full Grammar)

**Strengths**:
- Complete control over visualization
- Complex multi-view dashboards
- Advanced interactions
- Custom layouts

**Use When**:
- Vega-Lite is too limited
- Need custom layouts
- Complex linked views
- Advanced transformations

**Note**: Vega-Lite compiles to Vega, so start with Vega-Lite and only use Vega for advanced cases.

## Implementation Architecture

### New Module: `src/quilt_mcp/visualization/multi_format.py`

```python
class MultiFormatVisualizationGenerator:
    """
    Intelligent multi-format visualization generator.
    
    Selects the optimal visualization format based on:
    - Data type (genomic, tabular, hierarchical, etc.)
    - File extensions
    - Desired visualization type
    - Data size and complexity
    """
    
    def __init__(self):
        self.echarts_gen = EChartsGenerator()
        self.vega_gen = VegaLiteGenerator()  # New
        self.igv_gen = IGVConfigGenerator()  # New
    
    def generate_visualization(
        self,
        data: Union[pd.DataFrame, Dict, Path],
        viz_type: str,
        title: str = None,
        auto_select: bool = True
    ) -> Dict[str, Any]:
        """
        Generate visualization in optimal format.
        
        Args:
            data: Input data (DataFrame, dict, or file path)
            viz_type: Desired visualization type (bar, line, scatter, etc.)
            title: Chart title
            auto_select: Automatically select best format
            
        Returns:
            {
                "format": "echarts|vega-lite|perspective|igv",
                "config": {...},
                "quilt_summarize_entry": {...}
            }
        """
```

### Updated: `src/quilt_mcp/tools/quilt_summary.py`

Add new action: `generate_multi_viz`

```python
def generate_multi_format_visualizations(
    package_name: str,
    organized_structure: Dict[str, List[Dict[str, Any]]],
    file_types: Dict[str, Any],
    metadata_template: str = "standard",
    viz_preferences: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Generate visualizations in multiple formats with intelligent selection.
    
    Creates visualizations using the optimal format for each data type:
    - IGV for genomic data (BAM, VCF, BED)
    - Perspective for large tabular data (CSV, Parquet)
    - Vega-Lite for statistical charts
    - ECharts for interactive hierarchical data
    
    Args:
        package_name: Package identifier
        organized_structure: File structure by folder
        file_types: File type counts
        metadata_template: Color scheme template
        viz_preferences: Optional format preferences per viz type
        
    Returns:
        {
            "success": True,
            "visualizations": {
                "file_distribution": {
                    "format": "echarts",
                    "config": {...},
                    "file_path": "visualizations/file_distribution.json"
                },
                "genomic_tracks": {
                    "format": "igv",
                    "config": {...},
                    "file_path": "visualizations/genomic_tracks.json"
                }
            },
            "quilt_summarize": [...],  # Ready for quilt_summarize.json
            "files": {  # Files to add to package
                "visualizations/file_distribution.json": "...",
                "visualizations/genomic_tracks.json": "..."
            }
        }
    """
```

## quilt_summarize.json Structure

### Example Output

```json
[
  {
    "path": "visualizations/file_distribution.json",
    "title": "File Type Distribution",
    "description": "Interactive breakdown of package contents",
    "types": ["echarts"]
  },
  {
    "path": "visualizations/data_table.csv",
    "title": "Data Explorer",
    "description": "Interactive data grid with pivot/filter",
    "types": [{
      "name": "perspective",
      "config": {
        "settings": true,
        "theme": "Material Light"
      }
    }]
  },
  {
    "path": "visualizations/genome_tracks.json",
    "title": "Genomic Alignments",
    "description": "BAM and VCF tracks for chromosome 1",
    "types": ["igv"]
  },
  {
    "path": "visualizations/scatter_analysis.json",
    "title": "Statistical Analysis",
    "description": "Correlation scatter plot with regression",
    "types": ["vega-lite"]
  }
]
```

## Implementation Plan

### Phase 1: Core Infrastructure
1. Create `VegaLiteGenerator` class
2. Create `IGVConfigGenerator` class  
3. Create `MultiFormatVisualizationGenerator` orchestrator
4. Add intelligent format selection logic

### Phase 2: Integration
1. Update `quilt_summary.py` with `generate_multi_viz` action
2. Add format detection from file extensions
3. Generate `quilt_summarize.json` entries automatically
4. Return visualization files ready for package inclusion

### Phase 3: Enhanced Docstring
Update `quilt_summary` tool docstring with:
- Visualization format selection guide
- Examples for each format
- File extension mapping
- Best practices

### Phase 4: Testing
1. Unit tests for each generator
2. Integration tests with real data
3. E2E browser tests on demo.quiltdata.com
4. Test each visualization format renders correctly

## Docstring Template for quilt_summary Tool

```python
"""
Quilt package summary and visualization generation with multi-format support.

VISUALIZATION FORMAT SELECTION GUIDE:
=====================================

The tool intelligently selects the optimal visualization format based on your data:

1. **IGV (Integrative Genomics Viewer)** - For genomic data
   - File types: .bam, .vcf, .bed, .gff, .gtf, .bigwig, .bw
   - Use for: Genome tracks, variant visualization, alignment viewing
   - Output: JSON config with track definitions

2. **Perspective** - For large tabular data requiring exploration
   - File types: .csv, .tsv, .xlsx, .xls, .parquet, .jsonl
   - Use for: Interactive data grids, pivot tables, data analysis
   - Features: Filter, sort, group, aggregate, multiple view types
   - Handles: Up to 6MB compressed data

3. **Vega-Lite** - For statistical and analytical charts
   - Best for: Statistical analysis, publication-quality charts
   - Chart types: Box plots, histograms, scatter (with regression), faceted plots
   - Use when: Need data binning, aggregation, or statistical transforms
   - Output: Declarative JSON specification

4. **ECharts** - For interactive, animated charts
   - Best for: Interactive dashboards, hierarchical data, mobile
   - Chart types: Pie, tree, treemap, sunburst, graph, gauge, sankey
   - Use when: Need rich interactivity, animations, or custom styling
   - Output: ECharts option JSON

5. **Voila** - For interactive Jupyter notebooks
   - Use for: Custom Python-driven dashboards
   - Features: Full Jupyter kernel, ipywidgets, live computation
   - Note: Requires separate notebook file in package

AUTOMATIC SELECTION LOGIC:
=========================

File Extension → Format:
- .bam, .vcf, .bed, .gff → IGV
- .csv, .parquet (>100 rows) → Perspective
- .csv (statistical analysis) → Vega-Lite
- Hierarchical .json → ECharts
- .ipynb → Voila

Visualization Type → Format:
- Bar chart → ECharts (for interactivity) or Vega-Lite (for simplicity)
- Scatter plot → Vega-Lite (statistical features)
- Pie chart → ECharts (better animations)
- Box plot → Vega-Lite (native support)
- Treemap/Sunburst → ECharts (only option)
- Data grid → Perspective (only option)
- Genome tracks → IGV (only option)

Available actions:
- create_files: Create all summary files (README, quilt_summarize.json, visualizations)
- generate_viz: Generate visualizations (legacy, matplotlib PNGs)
- generate_multi_viz: Generate multi-format visualizations (NEW - recommended)
- generate_json: Generate quilt_summarize.json

Examples:

# Generate multi-format visualizations automatically
result = quilt_summary(
    action="generate_multi_viz",
    params={
        "package_name": "genomics/study",
        "organized_structure": {
            "data": [
                {"Key": "alignments.bam", "Size": 1024000},
                {"Key": "variants.vcf", "Size": 512000},
                {"Key": "results.csv", "Size": 8192}
            ]
        },
        "file_types": {"bam": 1, "vcf": 1, "csv": 1}
    }
)

# Result includes:
# - IGV config for BAM/VCF files
# - Perspective grid for CSV
# - quilt_summarize.json entries
# - All visualization files ready to add to package
"""
```

## Testing Checklist

- [ ] VegaLiteGenerator creates valid specs
- [ ] IGVConfigGenerator creates valid IGV configs
- [ ] Multi-format generator selects correct format
- [ ] quilt_summarize.json entries are valid
- [ ] IGV visualization renders in catalog
- [ ] Perspective grid renders and is interactive
- [ ] Vega-Lite charts render correctly
- [ ] ECharts remain functional
- [ ] Docstring provides clear guidance
- [ ] AI can select appropriate format
- [ ] E2E test on demo.quiltdata.com

## Success Criteria

1. **Intelligent Selection**: Tool automatically picks best format
2. **Complete Coverage**: All 5 formats supported
3. **Catalog Integration**: All visualizations render in Quilt catalog
4. **Clear Documentation**: AI assistant can use tool effectively
5. **Automatic quilt_summarize.json**: Generated and included
6. **File Management**: Visualization files ready for package

## References

- [Quilt Visualization Docs](https://docs.quilt.bio/quilt-platform-catalog-user/visualizationdashboards)
- [Vega-Lite Docs](https://vega.github.io/vega-lite/)
- [ECharts Docs](https://echarts.apache.org/)
- [Perspective Docs](https://perspective.finos.org/)
- [IGV.js Docs](https://github.com/igvteam/igv.js)


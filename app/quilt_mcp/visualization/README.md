# Automatic Visualization Generation for Quilt Packages

This module provides automatic visualization generation for Quilt packages, analyzing package contents and creating appropriate visualizations including charts, genomic views, and interactive dashboards.

## 🚀 Features

### **Automatic Discovery**
- **File Type Detection**: Automatically identifies CSV, JSON, Excel, Parquet, and genomic files
- **Content Analysis**: Analyzes data structure, types, and relationships
- **Smart Suggestions**: Recommends appropriate visualization types based on content

### **Visualization Types**
- **Data Charts**: Bar charts, line charts, scatter plots, heatmaps, pie charts
- **Genomic Visualizations**: IGV tracks, sequence views, variant analysis, coverage plots
- **Interactive Dashboards**: ECharts, Vega-Lite, and Perspective integrations
- **Static Charts**: Matplotlib-based chart generation

### **IGV Integration**
- **Genome Tracks**: Automatic track generation for BAM, VCF, BED, GTF files
- **Multi-track Views**: Coordinated visualization of multiple genomic datasets
- **Session Management**: Complete IGV session files for reproducible analysis
- **Genome Assembly Support**: hg38, mm10, rn6, dm6, ce11, sacCer3

## 🏗️ Architecture

```
app/quilt_mcp/visualization/
├── __init__.py                 # Main module exports
├── engine.py                   # Core visualization engine
├── generators/                 # Chart generators
│   ├── __init__.py
│   ├── echarts.py             # ECharts chart generation
│   ├── vega_lite.py           # Vega-Lite specifications
│   ├── igv.py                 # IGV genomic visualization
│   ├── matplotlib.py          # Static chart generation
│   └── perspective.py         # Data grid generation
├── analyzers/                  # Content analysis
│   ├── __init__.py
│   ├── data_analyzer.py       # Data structure analysis
│   ├── file_analyzer.py       # File type detection
│   └── genomic_analyzer.py    # Genomic content analysis
├── layouts/                    # Layout management
│   ├── __init__.py
│   └── grid_layout.py         # Grid-based layouts
└── utils/                      # Utility functions
    ├── __init__.py
    ├── data_processing.py     # Data loading and preprocessing
    └── file_utils.py          # File operations
```

## 📦 Installation

### **Dependencies**
```toml
[project.dependencies]
# Core visualization
matplotlib = ">=3.7.0"
numpy = ">=1.24.0"
pandas = ">=2.0.0"
plotly = ">=5.15.0"
altair = ">=5.0.0"

# Genomics and bioinformatics
pysam = ">=0.21.0"
pyvcf = ">=0.6.8"
biopython = ">=1.81"
pybedtools = ">=0.9.0"
pybigwig = ">=0.3.18"
```

### **Installation Steps**
1. **Install Python dependencies**:
   ```bash
   pip install pandas numpy matplotlib plotly altair
   ```

2. **Install genomics dependencies** (optional):
   ```bash
   pip install pysam pyvcf biopython pybedtools pybigwig
   ```

3. **Verify installation**:
   ```bash
   python -c "from quilt_mcp.visualization import VisualizationEngine; print('✅ Installation successful!')"
   ```

## 🎯 Quick Start

### **Basic Usage**
```python
from quilt_mcp.visualization import VisualizationEngine

# Initialize the engine
engine = VisualizationEngine()

# Generate visualizations for a package
result = engine.generate_package_visualizations("/path/to/package")

if result['success']:
    print(f"Generated {result['visualization_count']} visualizations")
    print(f"quilt_summarize.json: {result['quilt_summarize']}")
else:
    print(f"Error: {result['error']}")
```

### **Step-by-Step Workflow**
```python
from quilt_mcp.visualization import VisualizationEngine

# 1. Initialize engine
engine = VisualizationEngine()

# 2. Analyze package contents
analysis = engine.analyze_package_contents("/path/to/package")
print(f"Found {len(analysis.data_files)} data files")
print(f"Found {len(analysis.genomic_files)} genomic files")

# 3. Generate visualizations
visualizations = engine.generate_visualizations(analysis)
print(f"Generated {len(visualizations)} visualizations")

# 4. Create quilt_summarize.json
quilt_summary = engine.create_quilt_summary(visualizations)

# 5. Save to package
with open("/path/to/package/quilt_summarize.json", "w") as f:
    f.write(quilt_summary)
```

## 🔧 Configuration

### **Default Configuration**
```python
config = {
    "default_chart_types": {
        "csv": "bar_chart",
        "tsv": "bar_chart", 
        "json": "line_chart",
        "xlsx": "scatter_plot",
        "parquet": "heatmap"
    },
    "color_schemes": {
        "default": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
        "genomics": ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00"]
    },
    "default_genome": "hg38",
    "track_colors": {
        "coverage": "#1f77b4",
        "variants": "#ff7f0e", 
        "annotations": "#2ca02c"
    }
}

engine = VisualizationEngine(config)
```

### **Customizing Chart Types**
```python
# Override default chart types
config = {
    "default_chart_types": {
        "csv": "heatmap",  # Always use heatmap for CSV files
        "json": "scatter_plot"  # Always use scatter plot for JSON files
    }
}
```

## 🧬 Genomic Visualization

### **Supported File Types**
- **Sequence Data**: FASTA, FASTQ
- **Alignment Data**: BAM, SAM
- **Variant Data**: VCF
- **Annotation Data**: BED, GTF, GFF
- **Coverage Data**: BigWig, BigBed

### **IGV Integration Example**
```python
from quilt_mcp.visualization.generators.igv import IGVGenerator

igv_gen = IGVGenerator()

# Create genomic dashboard
dashboard = igv_gen.create_genomic_dashboard(
    genomic_files=["sample.bam", "variants.vcf", "genes.gtf"],
    genome="hg38",
    title="Sample Analysis Dashboard"
)

# Export IGV session
igv_gen.export_session_file(dashboard, "igv_session.json")
```

### **Multi-track Visualization**
```python
# Create coordinated multi-track view
tracks = [
    igv_gen.create_genome_track("coverage.bam", "coverage", {"height": 100}),
    igv_gen.create_genome_track("variants.vcf", "variant", {"height": 80}),
    igv_gen.create_genome_track("genes.gtf", "annotation", {"height": 60})
]

session = igv_gen.create_igv_session(tracks, "hg38")
```

## 📊 Data Visualization

### **ECharts Integration**
```python
from quilt_mcp.visualization.generators.echarts import EChartsGenerator

echarts_gen = EChartsGenerator()

# Create bar chart
chart_config = echarts_gen.create_bar_chart(
    data=df,
    categories="category",
    values="value",
    title="Sample Bar Chart"
)

# Save chart configuration
with open("chart.json", "w") as f:
    json.dump(chart_config, f, indent=2)
```

### **Chart Type Selection**
The system automatically selects appropriate chart types:

- **Bar Charts**: Categorical data with counts/values
- **Line Charts**: Time series or sequential data
- **Scatter Plots**: Correlation analysis between variables
- **Heatmaps**: Multi-dimensional data relationships
- **Pie Charts**: Proportional data distribution

## 🧪 Testing

### **Run Test Script**
```bash
cd app
python test_visualization.py
```

### **Test Output**
```
🚀 Quilt Package Automatic Visualization Generation Test
============================================================

Creating sample package in: /tmp/quilt_viz_test_xxxxx
Sample package created with:
  - sample_data.csv
  - config.json
  - genomic_data.fasta
  - README.md

Initializing visualization engine...
Analyzing package contents...
Package analysis complete:
  - File types: ['data', 'genomic', 'text']
  - Data files: 2
  - Genomic files: 1
  - Suggested visualizations: ['bar_chart', 'line_chart', 'genome_track']

Generating visualizations...
Generated 4 visualizations:
  - bar_chart: sample_data.csv Visualization
  - genome_track: genomic_data.fasta annotation_track
  - igv_session: IGV Session
  - pie_chart: Package Overview

Creating quilt_summarize.json...
quilt_summarize.json created: /tmp/quilt_viz_test_xxxxx/quilt_summarize.json

✅ Visualization generation successful!
  - Package: /tmp/quilt_viz_test_xxxxx
  - Visualizations: 4
  - Summary file: /tmp/quilt_viz_test_xxxxx/quilt_summarize.json
```

## 🔍 Troubleshooting

### **Common Issues**

1. **Import Errors**
   ```bash
   # Ensure you're in the correct directory
   cd app
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

2. **Missing Dependencies**
   ```bash
   # Install required packages
   pip install pandas numpy matplotlib
   ```

3. **File Permission Errors**
   ```bash
   # Check file permissions
   ls -la /path/to/package
   chmod 644 /path/to/package/*.csv
   ```

### **Debug Mode**
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable detailed logging
engine = VisualizationEngine()
engine.config['debug'] = True
```

## 📈 Performance

### **Optimization Features**
- **Data Sampling**: Automatic sampling for large datasets (>10,000 rows)
- **Lazy Loading**: Data loaded only when needed
- **Caching**: Chart configurations cached for reuse
- **Parallel Processing**: Multiple visualizations generated concurrently

### **Memory Management**
- **Streaming**: Large files processed in chunks
- **Garbage Collection**: Automatic cleanup of temporary data
- **Resource Limits**: Configurable memory and CPU limits

## 🔮 Future Enhancements

### **Planned Features**
- **Machine Learning**: AI-powered chart type selection
- **Real-time Updates**: Live data streaming and updates
- **Custom Themes**: User-defined visualization styles
- **Export Formats**: Additional export options (PDF, SVG, PNG)

### **Advanced Analytics**
- **Statistical Analysis**: Built-in statistical tests and summaries
- **Anomaly Detection**: Automatic outlier identification
- **Trend Analysis**: Pattern recognition and forecasting
- **Correlation Analysis**: Multi-variable relationship detection

## 📚 API Reference

### **Core Classes**

#### `VisualizationEngine`
Main engine for automatic visualization generation.

**Methods:**
- `analyze_package_contents(package_path)` → `PackageAnalysis`
- `generate_visualizations(analysis)` → `List[Visualization]`
- `create_quilt_summarize(visualizations)` → `str`
- `generate_package_visualizations(package_path)` → `Dict[str, Any]`

#### `PackageAnalysis`
Results of package content analysis.

**Attributes:**
- `package_path`: Path to package directory
- `file_types`: Dictionary mapping file types to file lists
- `data_files`: List of data file paths
- `genomic_files`: List of genomic file paths
- `suggested_visualizations`: List of recommended visualization types

#### `Visualization`
Represents a generated visualization.

**Attributes:**
- `id`: Unique identifier
- `type`: Visualization type
- `title`: Display title
- `description`: Description text
- `file_path`: Path to visualization file
- `config`: Configuration dictionary

### **Generator Classes**

#### `EChartsGenerator`
Generates ECharts chart configurations.

#### `IGVGenerator`
Generates IGV genomic visualization configurations.

#### `VegaLiteGenerator`
Generates Vega-Lite visualization specifications.

### **Analyzer Classes**

#### `FileAnalyzer`
Analyzes file types and structure.

#### `DataAnalyzer`
Analyzes data content and structure.

#### `GenomicAnalyzer`
Analyzes genomic content and biological context.

## 🤝 Contributing

### **Development Setup**
1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/new-visualization-type`
3. **Make changes** and add tests
4. **Run tests**: `python test_visualization.py`
5. **Submit pull request**

### **Code Style**
- **Python**: Follow PEP 8 guidelines
- **Documentation**: Use Google-style docstrings
- **Testing**: Maintain >90% test coverage
- **Type Hints**: Use type annotations for all functions

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Quilt Team**: For the excellent data package framework
- **IGV Team**: For the powerful genomic visualization platform
- **ECharts Team**: For the beautiful charting library
- **Vega Team**: For the declarative visualization language

---

**For support and questions**, please open an issue on GitHub or contact the development team.





# Quilt Package Summary Format and Visualization Guide

## Overview

This document describes the automatic generation of `quilt_summarize.json` files and visualizations for all Quilt packages created through the MCP server. These files provide machine-readable summaries and human-friendly visualizations for automated processing and discovery.

## quilt_summarize.json Format

The `quilt_summarize.json` file follows Quilt documentation standards and provides a comprehensive, machine-readable summary of package contents, structure, and metadata.

### File Structure

```json
{
  "package_info": {
    "name": "namespace/package-name",
    "namespace": "namespace",
    "package_name": "package-name",
    "version": "1.0.0",
    "created_by": "quilt-mcp-server",
    "creation_date": "2024-01-01T00:00:00Z",
    "metadata_template": "standard",
    "description": "Package description"
  },
  "data_summary": {
    "total_files": 42,
    "total_size_bytes": 1048576,
    "total_size_mb": 1.0,
    "total_size_gb": 0.001,
    "file_types": {
      "csv": 15,
      "json": 8,
      "png": 12,
      "md": 7
    },
    "file_type_distribution": {
      "csv": {
        "count": 15,
        "total_size_bytes": 524288,
        "total_size_mb": 0.5
      }
    }
  },
  "structure": {
    "folders": {
      "data/": {
        "file_count": 23,
        "total_size_bytes": 786432,
        "total_size_mb": 0.75
      },
      "docs/": {
        "file_count": 7,
        "total_size_bytes": 51200,
        "total_size_mb": 0.05
      }
    },
    "organization_type": "smart_hierarchy",
    "auto_organized": true
  },
  "source": {
    "type": "s3_bucket",
    "bucket": "source-bucket",
    "prefix": "data/",
    "source_description": "Data sourced from S3 bucket"
  },
  "documentation": {
    "readme_generated": true,
    "readme_length": 2048,
    "metadata_complete": true,
    "visualizations_generated": true
  },
  "quilt_metadata": {
    "created_by": "quilt-mcp-server",
    "creation_date": "2024-01-01T00:00:00Z",
    "package_version": "1.0.0"
  },
  "access": {
    "browse_command": "quilt3.Package.browse('namespace/package-name')",
    "catalog_url": "https://open.quiltdata.com/b/bucket/packages/namespace/package-name",
    "api_access": true,
    "cli_access": true
  },
  "generated_at": "2024-01-01T00:00:00Z",
  "generator": "quilt-mcp-server",
  "generator_version": "1.0.0"
}
```

### Field Descriptions

#### package_info
- **name**: Full package name in namespace/name format
- **namespace**: Package namespace (organization/team)
- **package_name**: Individual package name
- **version**: Semantic version of the package
- **created_by**: Tool or user that created the package
- **creation_date**: ISO 8601 timestamp of creation
- **metadata_template**: Template used for metadata generation
- **description**: Human-readable package description

#### data_summary
- **total_files**: Total number of files in the package
- **total_size_bytes**: Total size in bytes
- **total_size_mb**: Total size in megabytes (human-readable)
- **total_size_gb**: Total size in gigabytes (human-readable)
- **file_types**: Count of files by file extension
- **file_type_distribution**: Detailed breakdown by file type including counts and sizes

#### structure
- **folders**: Per-folder statistics including file counts and sizes
- **organization_type**: Type of folder organization applied
- **auto_organized**: Whether automatic organization was applied

#### source
- **type**: Data source type (s3_bucket, local_files, etc.)
- **bucket**: Source S3 bucket name
- **prefix**: S3 prefix if applicable
- **source_description**: Human-readable source description

#### documentation
- **readme_generated**: Whether README.md was generated
- **readme_length**: Length of README content in characters
- **metadata_complete**: Whether Quilt metadata is complete
- **visualizations_generated**: Whether visualizations were created

#### access
- **browse_command**: Python command to browse the package
- **catalog_url**: Direct link to package in Quilt catalog
- **api_access**: Whether API access is available
- **cli_access**: Whether CLI access is available

## Visualization Capabilities

The MCP server automatically generates comprehensive visualizations for each package, providing insights into data structure and contents.

### Visualization Types

#### 1. File Type Distribution Pie Chart
- **Purpose**: Shows distribution of files by file extension
- **Use Case**: Understanding data composition and file type diversity
- **Features**: 
  - Percentage breakdown
  - File count labels
  - Color-coded by template theme

#### 2. Folder Structure Bar Chart
- **Purpose**: Displays file distribution across organized folders
- **Use Case**: Understanding package organization and data hierarchy
- **Features**:
  - Horizontal bar chart for readability
  - File counts per folder
  - Value labels on bars

#### 3. File Size Distribution Histogram
- **Purpose**: Shows distribution of file sizes
- **Use Case**: Identifying large files and size patterns
- **Features**:
  - Size in MB for readability
  - Mean and median indicators
  - Statistical summary

#### 4. Package Overview Dashboard
- **Purpose**: Comprehensive package summary in visual format
- **Use Case**: Quick package assessment and reporting
- **Features**:
  - 2x2 grid layout
  - Combined metrics visualization
  - Template-specific color schemes

### Color Schemes

The visualizations use template-specific color schemes:

- **default**: Standard blue/orange/green palette
- **genomics**: Green/teal/cyan palette for biological data
- **ml**: Red/cyan/blue palette for machine learning datasets
- **research**: Purple/pink/orange palette for research data
- **analytics**: Green/blue/orange palette for business analytics

### Visualization Output

All visualizations are generated as:
- **Format**: PNG images
- **Resolution**: 150 DPI
- **Encoding**: Base64 strings for easy embedding
- **Metadata**: Complete data and statistics

## Automatic Generation

### When Generated

Quilt summary files are automatically generated for:
- All package creation operations
- S3-to-package conversions
- Enhanced package creation
- Package updates with new content

### Integration Points

The summary generation is integrated into:
- `package_create_from_s3()` - S3 bucket to package conversion
- `create_package_enhanced()` - Enhanced package creation
- `create_package()` - Unified package creation
- All package management operations

### Generated Files

Each package automatically includes:
1. **quilt_summarize.json** - Machine-readable package summary
2. **README.md** - Human-readable documentation
3. **Visualizations** - Charts and graphs for package overview

## Usage Examples

### Python API

```python
from quilt_mcp.tools.quilt_summary import create_quilt_summary_files

# Generate summary files for a package
summary = create_quilt_summary_files(
    package_name="team/dataset",
    package_metadata=metadata,
    organized_structure=structure,
    readme_content=readme,
    source_info=source,
    metadata_template="ml"
)

# Access generated content
quilt_summary = summary["summary_package"]["quilt_summarize.json"]
visualizations = summary["summary_package"]["visualizations"]
```

### MCP Tools

```python
# Create package with automatic summary generation
result = create_package_enhanced(
    name="team/dataset",
    files=["s3://bucket/file1.csv", "s3://bucket/file2.json"],
    metadata_template="ml"
)

# Access summary files in response
summary_files = result["summary_files"]
quilt_summary = summary_files["quilt_summarize.json"]
visualizations = summary_files["visualizations"]
```

## Benefits

### For Users
- **Automatic Documentation**: No need to manually create package summaries
- **Visual Insights**: Immediate understanding of package contents
- **Consistent Format**: Standardized summary format across all packages
- **Professional Appearance**: Ready-to-use documentation and visualizations

### For Organizations
- **Data Discovery**: Machine-readable summaries enable automated processing
- **Quality Assurance**: Consistent documentation standards
- **Compliance**: Structured metadata for regulatory requirements
- **Collaboration**: Clear package overviews for team members

### For Data Scientists
- **Quick Assessment**: Visual package overviews
- **Content Understanding**: File type and size distributions
- **Metadata Access**: Complete package information in structured format
- **Integration Ready**: JSON format for automated workflows

## Technical Details

### Dependencies
- **matplotlib**: Chart generation and visualization
- **numpy**: Statistical calculations and data processing
- **PIL/Pillow**: Image processing (optional)
- **base64**: Image encoding for transport

### Performance
- **Generation Time**: Typically <1 second for most packages
- **Memory Usage**: Minimal overhead during generation
- **Storage**: Base64 encoded images add ~10-30% to summary size
- **Scalability**: Handles packages with thousands of files

### Error Handling
- **Graceful Degradation**: Continues operation if visualization fails
- **Fallback Options**: Provides data even if charts can't be generated
- **Logging**: Comprehensive error logging for troubleshooting
- **User Feedback**: Clear error messages and recovery suggestions

## Future Enhancements

### Planned Features
- **Interactive Visualizations**: HTML-based interactive charts
- **Custom Templates**: User-defined visualization templates
- **Export Formats**: SVG, PDF, and other output formats
- **Real-time Updates**: Live visualization updates during package changes

### Integration Opportunities
- **Quilt Catalog**: Direct integration with Quilt web interface
- **Data Lineage**: Package dependency and relationship tracking
- **Quality Metrics**: Automated data quality assessment
- **Collaboration Tools**: Team-based package management features

## Conclusion

The automatic generation of `quilt_summarize.json` files and visualizations transforms Quilt packages from simple data containers into comprehensive, self-documenting data assets. This capability ensures that every package created through the MCP server includes professional-grade documentation and insights, making data discovery, understanding, and collaboration significantly more effective.

By following Quilt documentation standards and providing both machine-readable and human-friendly formats, these summary files serve as the foundation for automated data workflows while maintaining accessibility for human users.

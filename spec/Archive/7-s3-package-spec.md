# Phase 7: S3-to-Package Creation Specification

## Overview

Phase 7 implements advanced S3-to-package creation functionality that allows users to create properly structured Quilt packages directly from S3 bucket contents, following Quilt workflow best practices and organizational standards.

## Requirements

### Functional Requirements

- **Smart Package Naming**: Validates and enforces `namespace/packagename` convention
- **Intelligent Bucket Selection**: Suggests logical target buckets based on source patterns
- **Organized Structure**: Creates hierarchical folder layouts preserving logical organization
- **Automated Documentation**: Generates comprehensive README.md files at package root
- **Rich Metadata**: Creates structured, searchable metadata following Quilt standards
- **User Confirmation**: Interactive workflow confirming bucket selection and structure

### Quality Requirements

- **Structure Validation**: Ensures consistent, logical package organization
- **Metadata Completeness**: All packages include discoverable, standardized metadata
- **README Generation**: Auto-generated documentation with package overview
- **User Experience**: Clear confirmation and preview of package structure
- **Error Recovery**: Graceful handling of permission and access issues

### Technical Requirements

- **Quilt3 Integration**: Uses `quilt3.Package` API for compliant package creation
- **S3 Operations**: Efficient streaming operations without local downloads
- **Pattern Matching**: Advanced filtering with include/exclude patterns
- **Async Operations**: Non-blocking operations for large datasets
- **Progress Tracking**: Real-time feedback for long-running operations

## Implementation Details

### Package Structure Organization

**Logical Organization Patterns:**
```
namespace/packagename/
├── README.md                 # Auto-generated package documentation
├── data/                     # Primary data files
│   ├── raw/                  # Raw source data (if applicable)
│   ├── processed/            # Cleaned/processed data
│   └── exports/              # Final outputs
├── docs/                     # Additional documentation
│   ├── schemas/              # Data schemas and specifications
│   └── notes/                # Analysis notes and methodology
└── metadata/                 # Package-level metadata files
    ├── data_dictionary.json  # Field descriptions
    └── provenance.json       # Data lineage information
```

**Folder Assignment Logic:**
- **CSV/TSV/Parquet files** → `data/processed/`
- **JSON/XML data files** → `data/processed/`
- **Raw sensor/log files** → `data/raw/`
- **Images/Media** → `data/media/`
- **Documentation files** → `docs/`
- **Schema files** → `docs/schemas/`
- **Configuration files** → `metadata/`

### Smart Bucket Selection

**Bucket Suggestion Algorithm:**
1. **Pattern Analysis**: Analyze source bucket naming patterns
2. **Registry Inference**: Determine appropriate target registry
3. **Organization Rules**: Apply customer's organizational policies
4. **User Confirmation**: Present suggestion with rationale

**Examples:**
```
Source: s3://ml-training-data/models/
Suggested Target: s3://ml-packages/ (registry)
Rationale: ML data pattern detected, using ML registry

Source: s3://analytics-reports/quarterly/
Suggested Target: s3://analytics-packages/ (registry)  
Rationale: Analytics data pattern, using analytics registry
```

### README.md Generation

**Auto-generated Template:**
```markdown
# {namespace}/{packagename}

## Overview
This package contains {data_type} sourced from {source_description}.

## Contents
{file_summary_table}

## Data Dictionary
{metadata_summary}

## Usage
```python
import quilt3
pkg = quilt3.Package.browse("{namespace}/{packagename}")
# Access data files
data = pkg["data/processed/filename.csv"]()
```

## Metadata
- **Created**: {creation_date}
- **Source**: {source_s3_location}
- **Total Size**: {total_size}
- **File Count**: {file_count}
- **Last Updated**: {last_modified}

## Data Quality
{data_quality_summary}
```

### Metadata Structure

**Package-Level Metadata:**
```json
{
  "quilt": {
    "created_by": "mcp-s3-package-tool",
    "creation_date": "2024-08-20T14:30:00Z",
    "source": {
      "type": "s3_bucket",
      "bucket": "source-bucket",
      "prefix": "data/path/",
      "total_objects": 1247,
      "total_size_bytes": 2147483648
    },
    "organization": {
      "structure_type": "logical_hierarchy",
      "folder_mapping": {
        "data/processed/": "Cleaned and processed data files",
        "data/raw/": "Original source data",
        "docs/": "Documentation and schemas"
      }
    },
    "data_profile": {
      "file_types": ["csv", "parquet", "json"],
      "date_range": {
        "earliest": "2024-01-01",
        "latest": "2024-08-20"
      }
    }
  },
  "user_metadata": {
    "description": "User-provided description",
    "tags": ["analytics", "quarterly", "production"],
    "department": "Data Science",
    "contact": "team@company.com"
  }
}
```

## Tool Interface

### `package_create_from_s3` Enhanced Specification

```python
async def package_create_from_s3(
    source_bucket: str,
    source_prefix: str = "",
    package_name: str,
    target_registry: str = None,  # Will suggest if not provided
    description: str = "",
    include_patterns: List[str] = None,
    exclude_patterns: List[str] = None,
    auto_organize: bool = True,    # Enable smart folder organization
    generate_readme: bool = True,   # Generate README.md
    confirm_structure: bool = True, # Require user confirmation
    metadata_template: str = "standard", # Metadata template to use
    dry_run: bool = False          # Preview without creating
) -> Dict[str, Any]:
```

**Enhanced Return Structure:**
```json
{
  "success": true,
  "package_name": "analytics/quarterly-reports",
  "registry": "s3://analytics-packages",
  "structure": {
    "folders_created": ["data/processed", "docs", "metadata"],
    "files_organized": 1247,
    "readme_generated": true
  },
  "metadata": {
    "package_size": "2.1 GB",
    "file_types": ["csv", "json", "pdf"],
    "organization_applied": "logical_hierarchy"
  },
  "confirmation": {
    "bucket_suggested": "s3://analytics-packages",
    "structure_preview": "...",
    "user_approved": true
  }
}
```

## Validation Process

The SPEC-compliant validation follows this 6-step process:

1. **Preconditions** (`make init`): Check AWS credentials, Quilt authentication
2. **Execution** (`make run`): Execute S3-to-package creation workflows
3. **Testing** (`make test`): Validate package structure and metadata compliance
4. **Verification** (`make verify`): Confirm package accessibility and README quality
5. **Zero** (`make zero`): Clean up test packages and resources
6. **Config** (`make config`): Generate `.config` with validation results

## Success Criteria

- ✅ Package names follow `namespace/packagename` convention
- ✅ Smart bucket selection suggests appropriate registries
- ✅ Logical folder structure automatically applied
- ✅ README.md generated with comprehensive package information
- ✅ Structured metadata follows Quilt workflow standards
- ✅ User confirmation workflow operates smoothly
- ✅ Large datasets (>1GB) process efficiently
- ✅ Error handling provides actionable feedback
- ✅ Package structure validates against organizational standards

## Files and Structure

```text
app/quilt_mcp/tools/
├── s3_package.py              # Enhanced S3-to-package implementation
├── package_templates/         # README and metadata templates
│   ├── standard_readme.md     # Standard README template
│   ├── metadata_schemas.json  # Metadata structure definitions
│   └── folder_mappings.json   # Organization patterns
└── validators/                # Package validation utilities
    ├── structure_validator.py # Folder structure validation
    ├── metadata_validator.py  # Metadata compliance checking
    └── naming_validator.py    # Package naming validation

spec/
└── 7-s3-package-spec.md      # This specification

tests/
├── test_s3_package_advanced.py # Enhanced functionality tests
├── test_package_organization.py # Structure validation tests
└── test_metadata_generation.py  # Metadata and README tests
```

## User Experience Flow

### 1. Initial Request
```
User: "Create a package from my ML training data in s3://ml-data/experiments/model-v2/"
```

### 2. Smart Analysis
```
MCP: "Analyzing s3://ml-data/experiments/model-v2/...
     Found: 1,247 files (2.3 GB)
     Detected: ML training data with models and logs
     
     Suggested package name: ml-team/model-v2-training
     Suggested registry: s3://ml-packages
     
     Proposed structure:
     ├── data/raw/           # Training datasets (890 files)
     ├── data/processed/     # Preprocessed features (201 files) 
     ├── models/            # Trained models (12 files)
     └── logs/              # Training logs (144 files)
     
     Generate README.md with model documentation? (Y/n)"
```

### 3. User Confirmation
```
User: "Yes, looks good. Also add metadata about the training parameters."
```

### 4. Package Creation
```
MCP: "Creating package ml-team/model-v2-training...
     ✅ Organized 1,247 files into logical structure
     ✅ Generated comprehensive README.md
     ✅ Added metadata with training parameters
     ✅ Package available at s3://ml-packages
     
     Package summary:
     - Size: 2.3 GB
     - Structure: 4 organized folders
     - Documentation: README.md with usage examples
     - Metadata: Training parameters and model specifications"
```

## Common Issues

- **Bucket Access**: Ensure read access to source and write access to target buckets
- **Package Naming**: Validate namespace/packagename format before processing
- **Large Datasets**: Monitor progress and provide streaming operations
- **Metadata Quality**: Validate generated metadata against Quilt standards
- **README Generation**: Ensure comprehensive documentation without sensitive information

## Environment Variables

- `DEFAULT_PACKAGE_REGISTRY`: Default target registry for package creation
- `PACKAGE_TEMPLATE_PATH`: Path to custom README and metadata templates
- `MAX_PACKAGE_SIZE_GB`: Maximum package size limit (default: 50GB)
- `ENABLE_SMART_ORGANIZATION`: Enable/disable automatic folder organization
- `METADATA_VALIDATION_LEVEL`: Strict/moderate/basic metadata validation

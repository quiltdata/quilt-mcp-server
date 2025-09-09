<!-- markdownlint-disable MD013 -->
# Specifications: Use-Case-Centric MCP Tools Architecture

**Issue**: [#116 - Streamline Tools](https://github.com/quiltdata/quilt-mcp-server/issues/116)  
**Type**: Architecture Enhancement  
**Priority**: Medium  
**Phase**: IRS/DSCO Step 2 - Engineering Specifications

## Executive Summary

This specification defines a two-tier MCP tools architecture that optimizes for user workflow efficiency while maintaining clean technical architecture:

- **Workflow Tools** (14 tools): Use-case-centric tools that MCP clients call directly to fulfill user requests
- **Utility Layer** (hidden): Atomic operations that workflow tools compose internally

This architecture enables MCP clients to fulfill complete user workflows through single tool calls while maintaining clean separation of concerns in the implementation.

## Architecture Philosophy

### Current State Analysis

The existing MCP tools in the Quilt server present architectural challenges:

1. **Too High-Level**: Some tools hide complexity internally and require orchestration that breaks atomicity
2. **Too Granular**: Other tools are too atomic, requiring complex MCP client orchestration and creating poor developer experience
3. **Inconsistent Abstraction**: Mixed levels of abstraction make it difficult for MCP clients to provide consistent user experiences

### Proposed Solution: Two-Tier Architecture

**Workflow Tools (MCP-Exposed)**:

- Directly serve core user workflows and use cases
- Handle complete user workflows with single tool calls
- Rich input/output schemas optimized for MCP client consumption
- Internal composition of utility functions (hidden complexity)

**Utility Layer (Internal)**:

- Atomic operations (S3 access, JSON parsing, URL generation)
- Pure functions with minimal schemas
- Composable building blocks for workflow tools
- Not exposed to MCP clients

## Core Use Case Mapping

### 1. Catalog Operations → `catalog_authenticate` + `catalog_buckets` + `catalog_tables`

**User Stories**: "Show me available buckets" | "Connect to this catalog" | "What can I access?" | "What tables are available for SQL queries?"

```python
def catalog_authenticate(catalog_url: str, force_refresh: bool = False) -> AuthResult:
    """Authenticate with Quilt catalog and return access status with login guidance"""
    return {
        "success": False,  # If authentication fails
        "catalog_url": "https://open.quiltdata.com",
        "error": "Authentication required",
        "login_steps": [
            "Run: quilt3 login",
            "Or set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY",
            "For catalog access, run: quilt3 config https://open.quiltdata.com"
        ],
        # On success:
        "user_info": {"name": "user@example.com", "permissions": ["read", "write"]},
        "available_registries": ["s3://bucket1", "s3://bucket2"],
        "expires_at": "2024-01-15T10:30:00Z"
    }

def catalog_buckets() -> BucketList:
    """List available S3 buckets accessible to current user"""
    return {
        "success": True,
        "buckets": [
            {
                "name": "ml-datasets", 
                "registry_url": "s3://ml-datasets",
                "permissions": ["read", "write"],
                "package_count": 127,
                "last_activity": "2024-01-10T15:30:00Z",
                "catalog_url": "https://open.quiltdata.com/b/ml-datasets"
            }
        ],
        "total_count": 5,
        "access_method": "aws_credentials|catalog_auth"
    }

def catalog_tables() -> CatalogTablesResult:
    """List available tables/datasets for SQL querying across accessible buckets"""
    return {
        "success": True,
        "tables": [
            {
                "table_name": "ml_datasets.housing_data",
                "registry": "s3://ml-datasets",
                "package_name": "data-science/housing",
                "entry_path": "data/housing.csv",
                "schema": {
                    "columns": [
                        {"name": "house_id", "type": "bigint", "nullable": False},
                        {"name": "price", "type": "double", "nullable": True},
                        {"name": "sqft", "type": "bigint", "nullable": True},
                        {"name": "bedrooms", "type": "bigint", "nullable": True}
                    ],
                    "row_count": 5000,
                    "size_bytes": 524288
                },
                "athena_info": {
                    "database": "quilt_ml_datasets",
                    "table": "housing_data",
                    "location": "s3://ml-datasets/.quilt/packages/abc123.../data/housing.csv",
                    "partitioned": False
                },
                "query_examples": [
                    "SELECT * FROM ml_datasets.housing_data LIMIT 10",
                    "SELECT AVG(price) FROM ml_datasets.housing_data WHERE bedrooms = 3"
                ],
                "last_updated": "2024-01-10T15:30:00Z"
            }
        ],
        "total_tables": 127,
        "databases": [
            {
                "name": "quilt_ml_datasets",
                "registry": "s3://ml-datasets", 
                "table_count": 89
            },
            {
                "name": "quilt_research_data",
                "registry": "s3://research-data",
                "table_count": 38
            }
        ],
        "athena_settings": {
            "region": "us-east-1",
            "workgroup": "primary",
            "output_location": "s3://athena-results-bucket/queries/",
            "estimated_cost_per_tb": "$5.00"
        }
    }
```

**Utility Dependencies**:

- `aws_identity_get()` ← Extract from auth.py:348
- `quilt_config_get()` ← Extract from auth.py:38  
- `s3_bucket_list()` ← Extract from permission_discovery.py:177
- `bucket_permissions_test()` ← Extract from permissions.py:28
- `athena_catalog_get()`, `glue_table_list()` ← **CREATE NEW**

### 2. Package Operations → `package_create` + `package_get` + `package_delete` + `package_search`

**User Stories**: "Create a package from this data" | "Get this package info" | "Delete this package version" | "Find packages about housing data"

```python
def package_create(
    name: str,
    registry: str,
    s3_sources: List[str] = None,  # S3 URLs or bucket/prefix patterns  
    local_files: List[str] = None,  # Local file paths
    metadata: dict = None,
    preserve_structure: bool = True,     # Preserve subfolders for logical keys
    generate_metadata: bool = True,   # Generate README.md with package description [flags for all three?]
    generate_readme: bool = True,   # Generate README.md with package description
    generate_summary: bool = True   # Generate SUMMARY.json with file statistics and structure
) -> PackageCreationResult:
    """Create package from S3 sources or local files with intelligent organization"""
    return {
        "success": True,
        "package_name": "data-science/housing",
        "top_hash": "abc123...",
        "entry_count": 15,
        "total_size_bytes": 1024000,
        "organization": {
            "data/": 12,
            "docs/": 2, 
            "notebooks/": 1
        },
        "urls": {
            "catalog": "https://open.quiltdata.com/b/bucket/packages/data-science/housing",
            "browse": "https://open.quiltdata.com/b/bucket/tree/data-science/housing"
        },
        "generated_files": ["README.md", "SUMMARY.json"],
        "auto_organization": {
            "enabled": True,
            "rules_applied": [
                "*.csv, *.parquet → data/",
                "*.md, *.txt → docs/", 
                "*.ipynb → notebooks/"
            ]
        }
    }

def package_get(
    package_uri: str,  # "s3://bucket#package=name" or "name" with registry context
    path: str = None   # Get specific path within package, or None for package root
) -> PackageGetResult:
    """Get package info and structure, or specific entry content"""
    return {
        "success": True,
        "package_info": {
            "name": "data-science/housing",
            "top_hash": "abc123...",
            "created": "2024-01-10T15:30:00Z",
            "size_bytes": 1024000,
            "entry_count": 15,
            "metadata": {...}  # Package-level metadata
        },
        "entries": {
            "data/housing.csv": {
                "size": 524288,
                "hash": "def456...",
                "physical_key": "s3://bucket/.quilt/packages/abc123.../data/housing.csv"
            },
            "README.md": {
                "size": 2048,
                "hash": "ghi789...", 
                "physical_key": "s3://bucket/.quilt/packages/abc123.../README.md"
            }
        },
        "current_path": path or "",
        "available_paths": ["data/", "docs/", "notebooks/"]
    }

def package_delete(
    package_uri: str,  # "s3://bucket#package=name" or "name" with registry context
    version: str = "latest",  # "latest", "all", or specific hash
    confirm: bool = False     # Safety confirmation required
) -> PackageDeleteResult:
    """Delete package version(s) with safety confirmations"""
    return {
        "success": True,
        "package_name": "data-science/housing",
        "deleted_versions": ["abc123..."] if version != "all" else ["abc123...", "def456...", "ghi789..."],
        "deletion_scope": version,  # "latest", "all", or specific hash
        "registry": "s3://ml-datasets",
        "freed_space_bytes": 1024000 if version == "latest" else 5120000,
        "remaining_versions": [] if version == "all" else ["def456...", "ghi789..."],
        "safety_checks": {
            "confirmation_required": True,
            "dependents_found": [],  # Other packages that reference this one
            "shared_objects": 0,     # Objects shared with other packages
            "warnings": [
                "This will permanently delete package data",
                "Package cannot be recovered after deletion"
            ]
        },
        "urls_removed": [
            "https://open.quiltdata.com/b/bucket/packages/data-science/housing"
        ]
    }

def package_search(
    query: str,
    registries: List[str] = None,
    filters: dict = None,
    limit: int = 50,
    fallback_to_list: bool = True
) -> PackageSearchResults:
    """Search for packages across catalogs with fallback to package listing"""
    return {
        "success": True,
        "search_method": "elasticsearch|graphql|list_fallback",
        "query": query,
        "packages": [
            {
                "name": "data-science/housing",
                "registry": "s3://ml-datasets", 
                "description": "Housing price prediction dataset...",
                "last_modified": "2024-01-10T15:30:00Z",
                "size_bytes": 1024000,
                "entry_count": 15,
                "tags": ["housing", "real-estate", "prediction"],
                "relevance_score": 0.95,
                "match_reasons": ["name", "description", "metadata"],
                "urls": {
                    "catalog": "https://open.quiltdata.com/b/ml-datasets/packages/data-science/housing",
                    "quilt_uri": "quilt+s3://ml-datasets#package=data-science/housing"
                }
            }
        ],
        "total_matches": 27,
        "search_performance": {"took_ms": 245, "backend": "elasticsearch"},
        "fallback_used": False  # True if search failed and package_list was used
    }
```

**Utility Dependencies**:

- `package_list()` ← Rename from packages.py:27
- `package_manifest_get()` ← Extract from packages.py:177
- `package_manifest_validate()` ← Adapt from tabulator.py
- `s3_object_*()` ← Adapt from buckets.py:78,151,19
- `file_organize()` ← Extract from s3_package.py:84
- `package_delete()` ← **CREATE NEW**

**Existing Functions** (reuse):

- `readme_generate()` ← s3_package.py:85+
- `elasticsearch_query()` ← search/backends/elasticsearch.py:61
- `graphql_query()` ← tools/graphql.py:37

### 3. Object Operations → `object_create` + `object_get` + `object_delete` + `object_search`

**User Stories**: "Add this file to S3" | "Get this file content" | "Delete this file from S3" | "Search for CSV files in this bucket"

```python
def object_create(
    registry: str,
    s3_key: str,
    content: str = None,      # Text content
    content_base64: str = None,  # Binary content (base64 encoded)
    content_type: str = None,
    metadata: dict = None
) -> ObjectCreationResult:
    """Create individual S3 objects for use in packages"""
    return {
        "success": True,
        "s3_uri": f"s3://{registry.split('/')[-1]}/{s3_key}",
        "size_bytes": 1024,
        "etag": "abc123...",
        "content_type": content_type or "text/plain",
        "ready_for_package": True
    }

def object_get(
    s3_uri: str,             # "s3://bucket/key" or package entry physical_key
    max_size: int = 65536,   # Max bytes to read (64KB default)
    as_text: bool = True     # Return as text or base64-encoded binary
) -> ObjectGetResult:
    """Get individual S3 object content"""
    return {
        "success": True,
        "s3_uri": s3_uri,
        "content_type": "text/csv",
        "size_bytes": 524288,
        "content": "house_id,price,sqft,bedrooms\n1,450000,2100,3\n...",  # If as_text=True
        "content_base64": None,  # If as_text=False, contains base64 data
        "truncated": False,      # True if content exceeds max_size
        "etag": "def456..."
    }

def object_delete(
    s3_uri: str,             # "s3://bucket/key"
    confirm: bool = False    # Safety confirmation required
) -> ObjectDeleteResult:
    """Delete individual S3 objects (latest version only)"""
    return {
        "success": True,
        "s3_uri": s3_uri,
        "deleted_version": "abc123...",  # Version ID of deleted object
        "size_bytes": 524288,
        "deletion_type": "latest_version",  # Only deletes latest, not all versions
        "safety_checks": {
            "confirmation_required": True,
            "in_packages": [  # Packages that reference this object
                {"package": "data-science/housing", "logical_key": "data/prices.csv"}
            ],
            "shared_references": 1,  # Number of packages referencing this object
            "warnings": [
                "Object is referenced by 1 package(s)",
                "Deletion will break package integrity",
                "Consider using package_delete instead"
            ]
        },
        "impact_assessment": {
            "broken_packages": ["data-science/housing"],
            "alternative_actions": [
                "Delete the entire package instead",
                "Create new package version without this object"
            ]
        }
    }

def object_search(
    query: str,
    registries: List[str] = None,
    file_extensions: List[str] = None,
    size_range: dict = None,
    limit: int = 100,
    fallback_to_list: bool = True  
) -> ObjectSearchResults:
    """Search for individual objects/files with fallback to object listing"""
    return {
        "success": True,
        "search_method": "s3_search|elasticsearch|list_fallback",
        "query": query,
        "objects": [
            {
                "key": "data/housing-prices.csv",
                "bucket": "ml-datasets", 
                "s3_uri": "s3://ml-datasets/data/housing-prices.csv",
                "size": 524288,
                "last_modified": "2024-01-10T15:30:00Z",
                "content_type": "text/csv",
                "in_packages": [
                    {
                        "package": "data-science/housing",
                        "logical_key": "data/prices.csv"
                    }
                ],
                "relevance_score": 0.88,
                "preview": "house_id,price,sqft,bedrooms\n1,450000,2100,3\n..."
            }
        ],
        "total_matches": 156,
        "search_performance": {"took_ms": 180, "backend": "s3_list"},
        "fallback_used": True  # True if advanced search failed and s3_list was used
    }
```

**Utility Dependencies**:

- `s3_object_get()`, `s3_object_put()`, `s3_object_list()` ← Adapt from buckets.py:78,151,19
- `s3_object_delete()` ← **CREATE NEW**
- `package_manifest_*()` ← Extract from existing package operations
- `object_usage_check()` ← Extract from telemetry/metrics.py + data_analyzer.py

### 4. Data Operations → `data_visualize` + `data_query` + `data_tabulate`

**User Stories**: "Create a chart from this data" | "Query this data with SQL" | "Show this data as an interactive table"

```python
def data_visualize(
    package_uri: str,          # "s3://bucket#package=name" 
    entry_path: str,           # Path within package, e.g., "data/housing.csv"
    chart_type: str = "auto",  # auto|bar|line|scatter|histogram|pie
    columns: List[str] = None, # Specific columns to visualize
    parameters: dict = None,   # Chart-specific parameters
    style: dict = None         # Styling options
) -> VisualizationResult:
    """Generate visualizations from package data with intelligent defaults"""
    return {
        "success": True,
        "chart_info": {
            "type": "histogram",
            "title": "Price Distribution in Housing Dataset", 
            "data_source": f"{package_uri}/{entry_path}",
            "data_summary": {
                "rows_analyzed": 1000,
                "columns_used": ["price"],
                "data_types": {"price": "numeric"},
                "missing_values": {"price": 15}
            }
        },
        "outputs": {
            "image_base64": "data:image/png;base64,...",
            "image_url": "https://temp-storage/viz_abc123.png",
            "interactive_html": "<div class='chart-container'>...</div>",
            "chart_data": {  # Processed data used for chart
                "x_values": [200000, 250000, 300000],
                "y_values": [15, 25, 35]
            }
        },
        "suggested_alternatives": [
            {"type": "scatter", "description": "Show price vs square footage", "columns": ["price", "sqft"]},
            {"type": "box", "description": "Show price distribution by neighborhood", "columns": ["price", "neighborhood"]}
        ]
    }

def data_query(
    package_uri: str,          # "s3://bucket#package=name"
    entry_path: str = None,    # Specific file, or None for auto-detect
    sql_query: str = None,     # SQL query, or None for simple SELECT *
    filters: dict = None,      # Simple filters: {"price": ">= 400000", "bedrooms": 3}
    limit: int = 1000,         # Row limit for results
    output_format: str = "json"  # json|csv|parquet
) -> DataQueryResult:
    """Query package data with SQL or simple filters for analysis and export"""
    return {
        "success": True,
        "query_info": {
            "data_source": f"{package_uri}/{entry_path or 'auto-detected'}",
            "resolved_file": "s3://bucket/.quilt/packages/abc123.../data/housing.csv",
            "sql_used": sql_query or "SELECT * FROM data WHERE price >= 400000",
            "rows_scanned": 5000,
            "execution_time_ms": 850,
            "estimated_cost": "$0.025"  # If using Athena
        },
        "results": {
            "columns": [
                {"name": "house_id", "type": "integer"},
                {"name": "price", "type": "float64"},
                {"name": "bedrooms", "type": "integer"}
            ],
            "rows": [
                {"house_id": 1, "price": 450000, "bedrooms": 3},
                {"house_id": 2, "price": 380000, "bedrooms": 2}
            ],
            "row_count": 150,
            "truncated": False
        },
        "export_options": {
            "csv_download": "https://temp-results/query_abc123.csv",
            "parquet_download": "https://temp-results/query_abc123.parquet",
            "json_download": "https://temp-results/query_abc123.json"
        }
    }

def data_tabulate(
    package_uri: str,          # "s3://bucket#package=name"
    entry_path: str,           # Path to data file in package
    table_config: dict = None, # Tabulator configuration (columns, filters, etc.)
    interactive_features: List[str] = None,  # ["sort", "filter", "export", "pagination"]
    page_size: int = 100       # Rows per page
) -> TabulatorResult:
    """Create interactive Tabulator tables with rich formatting and controls"""
    return {
        "success": True,
        "table_info": {
            "table_id": "tab_abc123",
            "data_source": f"{package_uri}/{entry_path}",
            "total_rows": 5000,
            "displayed_rows": 100,
            "page_size": 100
        },
        "tabulator_config": {
            "columns": [
                {
                    "field": "price",
                    "title": "Price", 
                    "formatter": "money",
                    "formatterParams": {"symbol": "$"},
                    "sorter": "number",
                    "headerFilter": True
                },
                {
                    "field": "bedrooms",
                    "title": "Bedrooms",
                    "sorter": "number",
                    "headerFilter": "select"
                }
            ],
            "pagination": "local",
            "paginationSize": 100,
            "movableColumns": True,
            "resizableColumns": True
        },
        "rendering": {
            "html_container": "<div id='tab_abc123' class='tabulator-table'>Loading...</div>",
            "javascript_init": "var table = new Tabulator('#tab_abc123', config);",
            "data_url": "https://api/tables/abc123/data.json",
            "config_json": {...}  # Full Tabulator config as JSON
        },
        "interaction_endpoints": {
            "data": "https://api/tables/abc123/data",
            "export_csv": "https://api/tables/abc123/export/csv", 
            "export_xlsx": "https://api/tables/abc123/export/xlsx"
        }
    }
```

**Utility Dependencies**:

- `package_data_load()` ← Extract from existing data loading patterns
- `data_analyze()` ← Extract from data_analyzer.py
- `tabulator_config_generate()`, `table_render()` ← Extract from existing tabulator functionality

**Existing Functions** (reuse):

- `chart_generate()` ← quilt_summary.py:240+
- `image_encode()` ← quilt_summary.py:264+
- `sql_execute()` ← athena_glue.py:217
- `data_filter()` ← unified_search.py:185
- `export_generate()` ← aws/athena_service.py:403

## Implementation Architecture

### Architecture Overview

**Workflow Tools (14 Primary Tools)**:

1. `catalog_authenticate` - Connect to Quilt catalogs with login guidance
2. `catalog_buckets` - List available S3 buckets  
3. `catalog_tables` - List available tables/datasets for SQL querying
4. `package_create` - Create packages from S3/local sources (with auto-organize)
5. `package_get` - Get package structure and entries
6. `package_delete` - Delete package versions with safety confirmations
7. `package_search` - Search packages with fallback to listing
8. `object_create` - Create individual S3 objects for packages
9. `object_get` - Get individual S3 object content
10. `object_delete` - Delete individual S3 objects (latest version only)
11. `object_search` - Search objects with fallback to listing  
12. `data_visualize` - Generate charts from package data
13. `data_query` - Query data with SQL for analysis and export
14. `data_tabulate` - Create interactive Tabulator tables

**Utility Layer File Organization** (prevents circular dependencies):

```tree
├── core_ops.py      # Foundation: AWS, config, S3 objects
├── package_ops.py   # Package operations (depends on core_ops)
├── content_ops.py   # Content & data processing (depends on package_ops)
└── search_ops.py    # Search backends (depends on all others)
```

**Utility Categories** (~35-45 functions):

- **AWS Operations**: `s3_object_*`, `athena_query`, `sts_identity`
- **Package Operations**: `package_manifest_*`, `quilt_config_*`
- **Object Operations**: `object_usage_check`, `package_integrity_check`
- **Data Processing**: `data_load`, `schema_detect`, `stats_calculate`
- **Content Generation**: `readme_generate`, `chart_create`, `table_render`
- **Search Backends**: `elasticsearch_query`, `graphql_execute`

## Implementation Strategy

**Key Insight**: 80% extraction and refactoring, 20% creation of new functionality.

### Implementation Phases

#### Phase 1: Prefactoring

- Audit existing tests around extraction areas
- Add missing behavioral tests for edge cases
- Eliminate technical debt in extraction areas
- Refactor to create reusable components for new utilities

#### Phase 2: Direct Extraction

Extract existing functionality from quilt_mcp/tools:

- auth.py:348 → `aws_identity_get()`
- auth.py:38 → `quilt_config_get()`
- permission_discovery.py:177 → `s3_bucket_list()`
- permissions.py:28 → `bucket_permissions_test()`
- packages.py:27 → `package_list()` [rename]
- packages.py:177 → `package_manifest_get()` [extract]
- buckets.py:78,151,19 → `s3_object_*()` [adapt]
- s3_package.py:84 → `file_organize()` [extract]
- telemetry/metrics.py + data_analyzer.py → `object_usage_check()` [extract]

#### Phase 3: Missing Functionality Creation

Create 4 new functions:

- `athena_catalog_get()` - **CREATE NEW**
- `glue_table_list()` - **CREATE NEW**
- `s3_object_delete()` - **CREATE NEW**
- `package_delete()` - **CREATE NEW** (Quilt package deletion)

#### Phase 4: Workflow Tool Implementation

- Build 14 workflow tools using extracted and new utility functions
- Follow TDD with BDD test coverage
- Use dependency-layer file organization

#### Phase 5: MCP Registration Update

- Update tool registration to expose workflow tools only
- Add deprecation warnings to old tools
- Provide client migration documentation

#### Phase 6: Legacy Tool Archival

- Archive non-core tools with migration guides
- Performance validation and optimization
- Documentation updates

## Conclusion

This two-tier architecture provides workflow tools that handle complete user workflows through single MCP calls, while maintaining clean technical architecture through internal utility layers.

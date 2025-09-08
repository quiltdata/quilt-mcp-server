# Phase 1 Design: Utility Layer Extraction

**Issue**: [#116 - Streamline Tools](https://github.com/quiltdata/quilt-mcp-server/issues/116)  
**Type**: Architecture Enhancement  
**Priority**: Medium  
**Phase**: IRS/DSCO Step 4 - Phase 1 Design

## Executive Summary

Phase 1 implements the "Utility Layer Extraction" as specified in the migration strategy. This phase extracts 42-50 pure utility functions from existing MCP tools to create the composable foundation layer for the two-tier architecture.

**Goal**: Transform existing monolithic MCP tools into atomic utility functions with minimal schemas, single responsibility, and high composability to enable Phase 2 workflow tool implementation.

## Design Overview

### Architecture Goals for Phase 1

1. **Utility Function Extraction**: Extract 42-50 atomic utility functions from existing tools
2. **Pure Function Design**: Create functions with minimal schemas, single responsibility, no side effects
3. **Composability**: Design utility functions as building blocks for future workflow tools
4. **Category Organization**: Group utilities into logical categories (AWS, Package, Object, Data, Content)
5. **Testing Foundation**: Establish comprehensive BDD test coverage for all utility functions

### Technical Architecture

```
Phase 1 Architecture: Utility Layer Extraction

┌─────────────────────────────────────────────────────────────┐
│                    Current MCP Tools                       │
├─────────────────────────────────────────────────────────────┤
│  auth.py         buckets.py      packages.py    s3_package.py│
│  ├─ Complex      ├─ Mixed        ├─ Monolithic  ├─ Coupled   │
│  ├─ Side Effects ├─ Dependencies ├─ Multi-Role  ├─ Stateful │
│  └─ MCP-Coupled  └─ Schema Heavy └─ Hard to Test└─ Complex   │
└─────────────────────────────────────────────────────────────┘
                                │
              EXTRACT UTILITY FUNCTIONS
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   Utility Layer (New)                      │
├─────────────────────────────────────────────────────────────┤
│   AWS Ops        Package Ops    Object Ops      Data Ops    │
│  ├─aws_identity  ├─package_list ├─s3_object_get ├─data_load │
│  ├─quilt_config  ├─manifest_get ├─s3_object_put ├─stats_calc│
│  └─s3_bucket_*   └─dependencies └─object_usage  └─schema_det │
│                                                             │
│   Content Generation            Search & Query              │
│  ├─readme_generate             ├─elasticsearch_query        │
│  ├─chart_create               ├─graphql_execute            │
│  └─table_render               └─s3_search                  │
└─────────────────────────────────────────────────────────────┘
                                │
                 FOUNDATION FOR PHASE 2
                                ▼
┌─────────────────────────────────────────────────────────────┐
│              Future Workflow Tools (Phase 2)               │
├─────────────────────────────────────────────────────────────┤
│  catalog_*       package_*       object_*       data_*      │
│  ├─ Compose      ├─ Compose      ├─ Compose     ├─ Compose  │
│  ├─ Utilities    ├─ Utilities    ├─ Utilities   ├─ Utilities│
│  └─ Rich Output  └─ Rich Output  └─ Rich Output └─ Rich Out │
└─────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Utility Function Categories

Based on the migration strategy from specifications, we extract utility functions organized by functional categories:

**AWS Operations** (10-12 functions)
```python
# From auth.py
def aws_identity_get() -> Dict[str, str]:
    """Get current AWS identity (account, user, role)"""
    # Pure function: no side effects, consistent output
    # Returns: {"account_id": "123", "user_arn": "...", "assumed_role": "..."}

def quilt_config_get(key: str) -> Optional[str]:
    """Get Quilt configuration value by key"""
    # Pure function: reads config, no mutations
    # Returns: config value or None

def quilt_config_set(key: str, value: str) -> bool:
    """Set Quilt configuration value"""
    # Minimal side effect: only config file write
    # Returns: success boolean

# From buckets.py  
def s3_bucket_list(region: Optional[str] = None) -> List[Dict[str, Any]]:
    """List available S3 buckets with metadata"""
    # Pure AWS API call, no local state
    # Returns: [{"name": "bucket", "region": "us-east-1", "created": "..."}]

def bucket_permissions_test(bucket: str, operations: List[str]) -> Dict[str, bool]:
    """Test specific bucket permissions (read, write, delete)"""
    # Pure function: test permissions without side effects
    # Returns: {"read": True, "write": False, "delete": False}

def bucket_location_get(bucket: str) -> str:
    """Get bucket AWS region"""
    # Pure AWS API call
    # Returns: "us-east-1"

def athena_catalog_get(registry: str) -> Dict[str, Any]:
    """Get Athena catalog information for registry"""
    # Pure function: catalog metadata retrieval
    # Returns: {"database": "quilt_bucket", "tables": [...], "location": "..."}

def glue_table_list(database: str) -> List[Dict[str, Any]]:
    """List Glue tables in database with schema information"""
    # Pure function: table metadata listing
    # Returns: [{"name": "table", "columns": [...], "location": "s3://..."}]
```

**Package Operations** (10-12 functions)
```python
# From packages.py
def package_list(registry: str, prefix: str = "") -> List[Dict[str, Any]]:
    """List packages in registry with basic metadata"""
    # Pure function: read-only package discovery
    # Returns: [{"name": "pkg", "hash": "abc", "created": "..."}]

def package_manifest_get(registry: str, package: str, hash: Optional[str] = None) -> Dict[str, Any]:
    """Get package manifest (entries, metadata)"""
    # Pure function: manifest retrieval
    # Returns: {"entries": {...}, "metadata": {...}, "hash": "..."}

def package_manifest_validate(manifest: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate package manifest structure and content"""
    # Pure function: validation only
    # Returns: (is_valid, ["error messages"])

def package_dependencies_check(registry: str, package: str) -> List[Dict[str, str]]:
    """Check if package is referenced by other packages"""
    # Pure function: dependency analysis
    # Returns: [{"dependent_package": "pkg", "reference_type": "..."}]

def package_metadata_generate(entries: Dict[str, Any]) -> Dict[str, Any]:
    """Generate package metadata from entries"""
    # Pure function: metadata calculation
    # Returns: {"size_bytes": 123, "entry_count": 45, "file_types": [...]}
```

**S3 Object Operations** (8-10 functions)
```python
# From s3_package.py
def s3_object_get(s3_uri: str, max_bytes: int = 65536) -> Dict[str, Any]:
    """Get S3 object content and metadata"""
    # Pure function: object retrieval
    # Returns: {"content": "...", "size": 123, "etag": "...", "truncated": False}

def s3_object_put(s3_uri: str, content: Union[str, bytes], content_type: str = None) -> Dict[str, str]:
    """Put content to S3 object"""
    # Minimal side effect: S3 write only
    # Returns: {"etag": "...", "version_id": "...", "size_bytes": "123"}

def s3_object_delete(s3_uri: str) -> Dict[str, Any]:
    """Delete S3 object (latest version)"""
    # Minimal side effect: S3 delete only
    # Returns: {"deleted": True, "version_id": "...", "delete_marker": False}

def s3_object_list(bucket: str, prefix: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
    """List S3 objects with metadata"""
    # Pure function: listing only
    # Returns: [{"key": "path", "size": 123, "modified": "...", "etag": "..."}]

def object_usage_check(s3_uri: str) -> List[Dict[str, str]]:
    """Check which packages reference this S3 object"""
    # Pure function: usage analysis
    # Returns: [{"package": "pkg", "logical_key": "path", "registry": "s3://..."}]

def file_organize(files: List[str], rules: Dict[str, str] = None) -> Dict[str, str]:
    """Organize files into logical structure based on patterns"""
    # Pure function: path mapping
    # Returns: {"input/file.csv": "data/file.csv", "doc.md": "docs/doc.md"}
```

**Data Processing Operations** (6-8 functions)
```python
# New utility functions for data operations
def data_load(s3_uri: str, format: str = "auto") -> Dict[str, Any]:
    """Load data from S3 object for analysis"""
    # Pure function: data loading
    # Returns: {"data": [...], "columns": [...], "rows": 123, "format": "csv"}

def schema_detect(data: Union[List, Dict], sample_size: int = 1000) -> Dict[str, Any]:
    """Detect data schema from sample"""
    # Pure function: schema inference
    # Returns: {"columns": [{"name": "col", "type": "int64", "nullable": True}]}

def stats_calculate(data: List[Dict[str, Any]], columns: List[str] = None) -> Dict[str, Any]:
    """Calculate basic statistics for dataset"""
    # Pure function: statistical analysis
    # Returns: {"rows": 123, "columns": 5, "numeric_summary": {...}, "missing": {...}}

def data_filter(data: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Apply filters to dataset"""
    # Pure function: data filtering
    # Returns: filtered data array
```

**Content Generation Operations** (6-8 functions)
```python
# New utility functions for content generation
def readme_generate(package_info: Dict[str, Any], entries: Dict[str, Any]) -> str:
    """Generate README.md content for package"""
    # Pure function: content generation
    # Returns: markdown string

def chart_generate(data: List[Dict[str, Any]], chart_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate chart from data"""
    # Pure function: visualization generation
    # Returns: {"image_base64": "...", "config": {...}, "data_summary": {...}}

def table_render(data: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    """Render data as interactive table"""
    # Pure function: table generation
    # Returns: {"html": "...", "config_json": "...", "data_url": "..."}

def tabulator_config_generate(data: List[Dict[str, Any]], features: List[str]) -> Dict[str, Any]:
    """Generate Tabulator configuration from data and desired features"""
    # Pure function: configuration generation
    # Returns: {"columns": [...], "pagination": "local", "features": [...]}

def export_generate(data: List[Dict[str, Any]], format: str) -> Union[str, bytes]:
    """Export data to specified format"""
    # Pure function: format conversion
    # Returns: exported data as string or bytes

def summary_generate(package_info: Dict[str, Any], entries: Dict[str, Any]) -> Dict[str, Any]:
    """Generate SUMMARY.json with package statistics and structure"""
    # Pure function: package summary generation
    # Returns: {"file_count": 15, "total_size": 1024000, "structure": {...}}

def metadata_generate(entries: Dict[str, Any], user_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate package metadata from entries and user input"""
    # Pure function: metadata compilation
    # Returns: {"generated": {...}, "user": {...}, "computed": {...}}
```

**Search and Query Operations** (8-10 functions)
```python
# New utility functions for search and query
def elasticsearch_query(query: Dict[str, Any], index: str) -> Dict[str, Any]:
    """Execute Elasticsearch query"""
    # Pure function: search execution
    # Returns: {"hits": [...], "total": 123, "took_ms": 45}

def graphql_query(query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
    """Execute GraphQL query against Quilt API"""
    # Pure function: query execution
    # Returns: {"data": {...}, "errors": [...]}

def package_schema_detect(entries: Dict[str, Any]) -> Dict[str, Any]:
    """Detect schema information from package entries"""
    # Pure function: schema inference from package data
    # Returns: {"schemas": {...}, "data_files": [...], "formats": [...]}

def s3_search(bucket: str, query: str, file_types: List[str] = None) -> List[Dict[str, str]]:
    """Search S3 objects by name/content patterns"""
    # Pure function: object search
    # Returns: [{"key": "path", "bucket": "...", "score": 0.95}]

def athena_query(sql: str, database: str, output_location: str) -> Dict[str, Any]:
    """Execute Athena SQL query"""
    # Pure function: SQL execution
    # Returns: {"results": [...], "execution_id": "...", "cost_estimate": "$0.05"}

def sql_execute(query: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Execute SQL-like query on in-memory data"""
    # Pure function: in-memory SQL
    # Returns: query results as data array
```

### 2. Utility Function Design Principles

**Pure Function Characteristics**
- Single responsibility - one clear purpose per function
- No side effects - reads data, returns results, no logging/caching
- Minimal parameters - typically 1-4 parameters with clear types
- Predictable output - consistent return format with type hints
- Good docstrings - clear description of purpose, parameters, and return value

**Example: Good vs Bad**
```python
# GOOD: Pure utility function
def package_manifest_get(registry: str, package: str, hash: Optional[str] = None) -> Dict[str, Any]:
    """Get package manifest (entries, metadata)"""
    # Implementation: reads manifest, returns data
    
# BAD: Complex tool function (what we're replacing)  
def package_browse(registry: str, package: str = None, **kwargs) -> Dict[str, Any]:
    """Complex tool that does authentication, listing, UI generation, etc."""
    # Multiple responsibilities, side effects, complex schema
```

### 3. Implementation Structure

**File Organization**
```python
# Simple utility layer structure
src/
└── quilt_mcp_server/
    └── utilities/
        ├── __init__.py              # Simple imports
        ├── aws_operations.py        # AWS identity, config, S3 bucket ops
        ├── package_operations.py    # Package listing, manifest, validation  
        ├── object_operations.py     # S3 object CRUD, usage analysis
        ├── data_operations.py       # Data loading, analysis, filtering
        ├── content_generation.py    # README, charts, tables, exports
        └── search_operations.py     # Search, query, SQL execution

# Test structure mirrors utilities
tests/
└── utilities/
    ├── test_aws_operations.py
    ├── test_package_operations.py
    ├── test_object_operations.py
    ├── test_data_operations.py
    ├── test_content_generation.py
    └── test_search_operations.py
```

**Simple Import System**
```python
# src/quilt_mcp_server/utilities/__init__.py
"""Utility functions for internal use by workflow tools"""

# Direct imports for easy access
from .aws_operations import (
    aws_identity_get,
    quilt_config_get,
    quilt_config_set,
    s3_bucket_list,
    bucket_permissions_test,
    bucket_location_get,
    athena_catalog_get,
    glue_table_list
)

from .package_operations import (
    package_list,
    package_manifest_get,
    package_manifest_validate,
    package_dependencies_check,
    package_metadata_generate,
    package_schema_detect
)

# ... other imports
```

## Implementation Strategy

### Stage 1: AWS Operations Utilities (Days 1-2)
1. **Extract Identity and Config Functions**
   - Extract `aws_identity_get()` from auth.py
   - Extract `quilt_config_*()` functions from auth.py  
   - Create pure functions with minimal schemas
   - Write comprehensive BDD tests

2. **Extract Bucket Operations**
   - Extract `s3_bucket_list()` from buckets.py
   - Extract `bucket_permissions_test()` from buckets.py
   - Create `bucket_location_get()` utility
   - Test all bucket utilities with real AWS credentials

### Stage 2: Package Operations Utilities (Days 3-4)
1. **Extract Package Core Functions** 
   - Extract `package_list()` from packages.py
   - Extract `package_manifest_get()` from packages.py
   - Create `package_manifest_validate()` utility
   - Create `package_dependencies_check()` utility

2. **Add Package Support Functions**
   - Create `package_metadata_generate()` utility
   - Test all package utilities with real S3 packages
   - Validate schema consistency across package functions

### Stage 3: Object Operations Utilities (Days 5-6)
1. **Extract S3 Object Functions**
   - Extract `s3_object_get()` from s3_package.py
   - Extract `s3_object_put()` from s3_package.py  
   - Extract `s3_object_delete()` from s3_package.py
   - Extract `s3_object_list()` from s3_package.py

2. **Add Object Analysis Functions**
   - Create `object_usage_check()` utility
   - Extract `file_organize()` from s3_package.py
   - Test all object utilities with real S3 objects

### Stage 4: Data and Content Operations (Days 7-8)
1. **Create Data Processing Utilities**
   - Implement `data_load()` utility
   - Implement `schema_detect()` utility
   - Implement `stats_calculate()` utility
   - Implement `data_filter()` utility

2. **Create Content Generation Utilities**
   - Implement `readme_generate()` utility
   - Implement `chart_generate()` utility (basic charts)
   - Implement `table_render()` utility
   - Implement `export_generate()` utility

### Stage 5: Search and Query Utilities (Days 9-10)
1. **Create Search Functions**
   - Implement `elasticsearch_query()` utility
   - Implement `graphql_query()` utility
   - Implement `s3_search()` utility

2. **Create Query Functions**
   - Implement `athena_query()` utility
   - Implement `sql_execute()` utility (in-memory SQL)
   - Test all search/query utilities


## Integration Points

### Input Dependencies
- **Requirements Document**: Core use cases and acceptance criteria from `01-requirements.md`
- **Specifications**: Two-tier architecture and utility layer specifications from `03-specifications.md`
- **Current Tools**: Existing MCP tools in `src/quilt_mcp_server/tools/` (auth.py, buckets.py, packages.py, s3_package.py)

### Output Artifacts
- **Utility Layer**: Complete `src/quilt_mcp_server/utilities/` module with 42-50 functions
- **Test Suite**: Comprehensive BDD tests for all utilities in `tests/utilities/`
- **Simple Import System**: Direct imports for workflow tools to use

### Phase 2 Handoff
- **Utility Functions**: 42-50 tested, pure utility functions organized by category
- **Function Documentation**: Clear docstrings and type hints for each utility
- **Test Examples**: BDD tests showing expected behavior and usage patterns

## Success Metrics

### Utility Function Quality
- **Function Count**: 42-50 utility functions extracted from existing tools
- **Pure Function Compliance**: 100% of utilities are pure functions (no side effects)
- **Single Responsibility**: Each utility has one clear, testable responsibility
- **Minimal Schemas**: All utilities have simple, consistent input/output schemas

### Test Coverage and Quality
- **BDD Test Coverage**: 100% coverage with behavior-driven tests
- **Test Isolation**: All tests run independently with proper fixtures and mocks
- **Test Documentation**: Clear test names and descriptions showing expected behavior

### Organization and Integration
- **Category Organization**: Utilities properly categorized into 6 functional areas  
- **Simple Import System**: Direct imports make utilities easy to use in workflow tools
- **Phase 2 Readiness**: All utilities ready for integration into workflow tools

## Risk Mitigation

### Extraction Risks
1. **Complex Function Dependencies**: Some tool functions may have complex interdependencies
   - **Mitigation**: Extract utilities incrementally, maintaining backward compatibility
   - **Validation**: Test each utility in isolation before integration

2. **Pure Function Design**: Existing tools may have hidden side effects
   - **Mitigation**: Careful analysis and refactoring to remove side effects
   - **Testing**: BDD tests validate expected behavior without side effects

### Integration Risks
1. **Backward Compatibility**: Extraction may break existing tool functionality
   - **Mitigation**: Maintain existing tools during Phase 1, refactor carefully
   - **Testing**: Comprehensive regression testing after each extraction

2. **Test Coverage Gaps**: Complex scenarios may be missed in utility tests
   - **Mitigation**: BDD tests cover real usage patterns from existing tools
   - **Validation**: Integration testing with actual data

## Technology Choices

### Utility Function Implementation
- **Function Design**: Pure functions with type hints and comprehensive docstrings
- **Error Handling**: Consistent exception hierarchy with clear error messages
- **Return Types**: Structured dictionaries with consistent key naming

### Testing Framework
- **Testing Library**: `pytest` with BDD-style test organization
- **Mocking**: `pytest-mock` for external service mocking
- **Fixtures**: Shared test fixtures for common data structures
- **Coverage**: `pytest-cov` for coverage measurement and reporting

### Code Organization
- **Module Structure**: Category-based modules with clear naming
- **Import System**: Simple direct imports in `__init__.py`
- **Type Safety**: `mypy` for static type checking

## Deliverables

1. **Utility Layer**: Complete `src/quilt_mcp_server/utilities/` module with 42-50 pure utility functions
2. **Test Suite**: Comprehensive BDD tests achieving 100% coverage for all utilities
3. **Import System**: Simple direct imports for easy workflow tool integration
4. **Documentation**: Clear docstrings and type hints for all utility functions
5. **Phase 2 Foundation**: Ready-to-use building blocks for workflow tool implementation

This Phase 1 design creates the essential utility layer foundation for the two-tier architecture by extracting atomic, composable functions from existing tools, enabling Phase 2 to build workflow tools through utility composition rather than complex monolithic implementations.
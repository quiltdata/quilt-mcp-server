<!-- markdownlint-disable MD013 -->
# Phase 1 Design: Prefactoring and Extraction

**Issue**: [#116 - Streamline Tools](https://github.com/quiltdata/quilt-mcp-server/issues/116)  
**Type**: Architecture Enhancement  
**Priority**: Medium  
**Phase**: IRS/DSCO Step 4 - Phase 1 Design

## Executive Summary

**CRITICAL LEARNING**: Based on thorough codebase analysis, Phase 1 is **80% extraction, 20% creation**. Most utility functions already exist but are embedded within larger tools/classes.

Phase 1 implements "Prefactoring and Extraction" using dependency-layer file organization to avoid circular dependencies. This phase extracts proven utility functions from existing MCP tools to create the composable foundation for the two-tier architecture.

**Goal**: Transform embedded functionality into atomic utility functions with clean dependency layers, single responsibility, and high composability to enable workflow tool implementation.

## Design Overview

### Architecture Reality Check

**Initial Assumption**: Need to create 20+ utility functions from scratch  
**Reality Discovered**: Only 2 functions truly missing, 15+ exist but embedded

**Core Learning**:

- `s3_object_delete()` and `package_delete()` - **CREATE NEW** (only truly missing functions)
- All other utilities - **EXTRACT** from existing proven implementations

### Technical Architecture

```tree
Phase 1 Architecture: Extraction-Heavy Approach

┌─────────────────────────────────────────────────────────────┐
│                 Existing Codebase Analysis                │
├─────────────────────────────────────────────────────────────┤
│ ✅ FOUND: aws_identity_get() ← auth_status() auth.py:348   │
│ ✅ FOUND: quilt_config_get() ← _get_catalog_info() auth.py:38│  
│ ✅ FOUND: s3_bucket_list() ← discover_accessible_buckets() │
│ ✅ FOUND: package_list() ← packages_list() packages.py:27  │
│ ✅ FOUND: s3_object_*() ← bucket_object_*() buckets.py     │
│ ❌ MISSING: s3_object_delete() - No S3 delete anywhere     │
│ ❌ MISSING: package_delete() - No package deletion exists  │
└─────────────────────────────────────────────────────────────┘
                                │
             EXTRACT EMBEDDED FUNCTIONALITY
                                ▼
┌─────────────────────────────────────────────────────────────┐
│              Dependency-Layer Organization                  │
├─────────────────────────────────────────────────────────────┤
│ core_ops.py      │ Foundation: AWS, config, S3 objects     │
│ ├─aws_identity   │ (no dependencies)                       │
│ ├─quilt_config   │                                        │
│ └─s3_object_*    │                                        │
├─────────────────────────────────────────────────────────────┤
│ package_ops.py   │ Package operations                      │
│ ├─package_list   │ (depends on core_ops)                  │
│ ├─manifest_get   │                                        │
│ └─dependencies   │                                        │
├─────────────────────────────────────────────────────────────┤
│ content_ops.py   │ Content & data processing               │
│ ├─data_load      │ (depends on package_ops)               │
│ ├─chart_create   │                                        │
│ └─table_render   │                                        │
├─────────────────────────────────────────────────────────────┤
│ search_ops.py    │ Search backends                         │
│ ├─elasticsearch  │ (depends on all others)                │
│ ├─graphql_query  │                                        │
│ └─s3_search      │                                        │
└─────────────────────────────────────────────────────────────┘
                                │
                  FOUNDATION FOR WORKFLOW TOOLS
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

### 1. Dependency-Layer File Organization

**CRITICAL**: Prevents circular dependencies discovered in learnings analysis.

```tree
src/quilt_mcp_server/utils/
├── core_ops.py      # Foundation: AWS, config, S3 objects (no dependencies)
├── package_ops.py   # Package operations (depends on core_ops)
├── content_ops.py   # Content & data processing (depends on package_ops)  
└── search_ops.py    # Search backends (depends on all others)
```

**Why This Structure Prevents Problems**:

- **Clean Hierarchy**: Each layer only depends on layers below it
- **No Circular Dependencies**: Clear import direction prevents cycles
- **Usage-Based Grouping**: Functions grouped by actual interdependencies

### 2. Extraction Mapping

**Functions with Existing Implementations** (Extract/Adapt):

| Utility Function | Source Location (in quilt_mcp/tools) | Action Required |
|------------------|----------------|-----------------|
| `aws_identity_get()` | `auth_status()` auth.py:348 | **Extract** identity logic |
| `quilt_config_get()` | `_get_catalog_info()` auth.py:38 | **Extract** config access |
| `s3_bucket_list()` | `AWSPermissionDiscovery.discover_accessible_buckets()` permission_discovery.py:177 | **Extract** from class |
| `bucket_location_get()` | `AWSPermissionDiscovery.discover_bucket_permissions()` permission_discovery.py:521 | **Extract** region logic |
| `bucket_permissions_test()` | `aws_permissions_discover()` permissions.py:28 | **Extract** single bucket testing |
| `package_list()` | `packages_list()` packages.py:27 | **Rename** function |
| `package_manifest_get()` | `package_browse()` packages.py:177 | **Extract** manifest logic |
| `package_manifest_validate()` | `_validate_schema()` tabulator.py | **Adapt** validation patterns |
| `s3_object_get/put/list()` | `bucket_object_*()` buckets.py:78,151,19 | **Adapt** for generic S3 operations |
| `file_organize()` | `_organize_file_structure()` s3_package.py:84 | **Extract** and make public |
| `object_usage_check()` | `MetricsCalculator` + `DataAnalyzer` telemetry/metrics.py + data_analyzer.py | **Extract** from analytics |

**Functions That DON'T Exist** (Create New):

| Function | Reality | Effort |
|----------|---------|--------|
| `s3_object_delete()` | No S3 delete functionality found anywhere | **CREATE** new |
| `package_delete()` | No package deletion functionality exists | **CREATE** new |

### 3. Core Operations Layer (core_ops.py)

**Foundation layer with no dependencies**:

```python
# AWS Operations (Extract from auth.py)
def aws_identity_get() -> Dict[str, str]:
    """Get current AWS identity (account, user, role)"""
    # EXTRACT FROM: auth_status() at auth.py:348
    # Returns: {"account_id": "123", "user_arn": "...", "assumed_role": "..."}

def quilt_config_get(key: str = None) -> Union[str, Dict[str, str]]:
    """Get Quilt configuration value by key or all config"""
    # EXTRACT FROM: _get_catalog_info() at auth.py:38
    # Returns: config value or full config dict

def quilt_config_set(key: str, value: str) -> bool:
    """Set Quilt configuration value"""
    # BUILD ON: Existing config patterns in auth.py
    # Returns: success boolean

# S3 Bucket Operations (Extract from permission_discovery.py)
def s3_bucket_list(region: Optional[str] = None) -> List[Dict[str, Any]]:
    """List available S3 buckets with metadata"""
    # EXTRACT FROM: AWSPermissionDiscovery.discover_accessible_buckets() permission_discovery.py:177
    # Returns: [{"name": "bucket", "region": "us-east-1", "created": "..."}]

def bucket_permissions_test(bucket: str, operations: List[str]) -> Dict[str, bool]:
    """Test specific bucket permissions (read, write, delete)"""
    # EXTRACT FROM: aws_permissions_discover() permissions.py:28
    # Returns: {"read": True, "write": False, "delete": False}

def bucket_location_get(bucket: str) -> str:
    """Get bucket AWS region"""
    # EXTRACT FROM: AWSPermissionDiscovery.discover_bucket_permissions() permission_discovery.py:521
    # Returns: "us-east-1"

# S3 Object Operations (Adapt from buckets.py)
def s3_object_get(s3_uri: str, max_bytes: int = 65536) -> Dict[str, Any]:
    """Get S3 object content and metadata"""
    # ADAPT FROM: bucket_object_info() buckets.py:78
    # Returns: {"content": "...", "size": 123, "etag": "...", "truncated": False}

def s3_object_put(s3_uri: str, content: Union[str, bytes], content_type: str = None) -> Dict[str, str]:
    """Put content to S3 object"""
    # ADAPT FROM: bucket_objects_put() buckets.py:151
    # Returns: {"etag": "...", "version_id": "...", "size_bytes": "123"}

def s3_object_list(bucket: str, prefix: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
    """List S3 objects with metadata"""
    # ADAPT FROM: bucket_objects_list() buckets.py:19
    # Returns: [{"key": "path", "size": 123, "modified": "...", "etag": "..."}]

def s3_object_delete(s3_uri: str) -> Dict[str, Any]:
    """Delete S3 object (latest version)"""
    # CREATE NEW: No S3 delete functionality found anywhere
    # Returns: {"deleted": True, "version_id": "...", "delete_marker": False}

def file_organize(files: List[str], rules: Dict[str, str] = None) -> Dict[str, str]:
    """Organize files into logical structure based on patterns"""
    # EXTRACT FROM: _organize_file_structure() s3_package.py:84
    # Returns: {"input/file.csv": "data/file.csv", "doc.md": "docs/doc.md"}
```

### 4. Package Operations Layer (package_ops.py)

**Depends on core_ops only**:

```python
from .core_ops import s3_object_get, s3_object_list

def package_list(registry: str, prefix: str = "") -> List[Dict[str, Any]]:
    """List packages in registry with basic metadata"""
    # RENAME FROM: packages_list() packages.py:27
    # Returns: [{"name": "pkg", "hash": "abc", "created": "..."}]

def package_manifest_get(registry: str, package: str, hash: Optional[str] = None) -> Dict[str, Any]:
    """Get package manifest (entries, metadata)"""
    # EXTRACT FROM: package_browse() packages.py:177
    # Returns: {"entries": {...}, "metadata": {...}, "hash": "..."}

def package_manifest_validate(manifest: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate package manifest structure and content"""
    # ADAPT FROM: _validate_schema() tabulator.py
    # Returns: (is_valid, ["error messages"])

def package_delete(registry: str, package: str, version: str = "latest") -> Dict[str, Any]:
    """Delete package version(s) with safety confirmations"""
    # CREATE NEW: No package deletion functionality exists
    # Returns: {"deleted_versions": [...], "freed_space_bytes": 1024}

def package_dependencies_check(registry: str, package: str) -> List[Dict[str, str]]:
    """Check if package is referenced by other packages"""
    # BUILD ON: Existing package analysis patterns
    # Returns: [{"dependent_package": "pkg", "reference_type": "..."}]

def package_metadata_generate(entries: Dict[str, Any]) -> Dict[str, Any]:
    """Generate package metadata from entries"""
    # BUILD ON: Existing metadata patterns
    # Returns: {"size_bytes": 123, "entry_count": 45, "file_types": [...]}
```

### 5. Content Operations Layer (content_ops.py)

**Depends on package_ops**:

```python
from .package_ops import package_manifest_get
from .core_ops import s3_object_get

def data_load(s3_uri: str, format: str = "auto") -> Dict[str, Any]:
    """Load data from S3 object for analysis"""
    # BUILD ON: Existing data loading patterns
    # Returns: {"data": [...], "columns": [...], "rows": 123, "format": "csv"}

def object_usage_check(s3_uri: str) -> List[Dict[str, str]]:
    """Check which packages reference this S3 object"""
    # EXTRACT FROM: MetricsCalculator + DataAnalyzer telemetry/metrics.py + data_analyzer.py
    # Returns: [{"package": "pkg", "logical_key": "path", "registry": "s3://..."}]

def schema_detect(data: Union[List, Dict], sample_size: int = 1000) -> Dict[str, Any]:
    """Detect data schema from sample"""
    # BUILD ON: Existing schema detection patterns
    # Returns: {"columns": [{"name": "col", "type": "int64", "nullable": True}]}

def readme_generate(package_info: Dict[str, Any], entries: Dict[str, Any]) -> str:
    """Generate README.md content for package"""
    # CREATE NEW: Pure function for content generation
    # Returns: markdown string

def chart_generate(data: List[Dict[str, Any]], chart_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate chart from data"""
    # CREATE NEW: Visualization generation
    # Returns: {"image_base64": "...", "config": {...}, "data_summary": {...}}

def table_render(data: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    """Render data as interactive table"""
    # EXTRACT/ADAPT FROM: Existing tabulator functionality
    # Returns: {"html": "...", "config_json": "...", "data_url": "..."}
```

### 6. Search Operations Layer (search_ops.py)

**Depends on all other layers**:

```python
from .core_ops import s3_object_list
from .package_ops import package_list
from .content_ops import data_load

def elasticsearch_query(query: Dict[str, Any], index: str) -> Dict[str, Any]:
    """Execute Elasticsearch query"""
    # CREATE NEW: Search execution
    # Returns: {"hits": [...], "total": 123, "took_ms": 45}

def graphql_query(query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
    """Execute GraphQL query against Quilt API"""
    # CREATE NEW: Query execution
    # Returns: {"data": {...}, "errors": [...]}

def package_schema_detect(entries: Dict[str, Any]) -> Dict[str, Any]:
    """Detect schema information from package entries"""
    # BUILD ON: Existing schema detection + package analysis
    # Returns: {"schemas": {...}, "data_files": [...], "formats": [...]}

def s3_search(bucket: str, query: str, file_types: List[str] = None) -> List[Dict[str, str]]:
    """Search S3 objects by name/content patterns"""
    # BUILD ON: s3_object_list with filtering
    # Returns: [{"key": "path", "bucket": "...", "score": 0.95}]
```

## Implementation Strategy

**Key Learning**: 80% extraction, 20% creation. Build on proven implementations.

### Stage 1: Prefactoring - Prepare for Extraction

**Objective**: Strengthen test coverage and prepare existing code for extraction.

#### 1.1 Test Coverage Expansion

- **Audit existing tests** around extraction areas - identify behavior coverage gaps
- **Add missing behavioral tests** for edge cases and integration points  
- **Ensure test reliability** - tests should fail when they should, pass when they should

#### 1.2 Code Preparation

**Eliminate technical debt** in areas where utilities will be extracted:

**PREFACTOR auth.py:**

- Extract identity logic from `auth_status()` (line 348) into separate helper function
- Extract config logic from `_get_catalog_info()` (line 38) into separate helper function
- Ensure all existing auth tests still pass

**PREFACTOR permission_discovery.py:**  

- Extract bucket listing from `AWSPermissionDiscovery.discover_accessible_buckets()` (line 177)
- Extract region detection from `AWSPermissionDiscovery.discover_bucket_permissions()` (line 521)
- Ensure all existing permission tests still pass

**PREFACTOR packages.py:**

- Extract manifest access logic from `package_browse()` (line 177) into separate helper
- Ensure all existing package tests still pass

**PREFACTOR analytics code:**

- Make telemetry/metrics.py functions more modular for extraction
- Prepare data_analyzer.py functions for utility extraction

### Stage 2: Direct Extraction

**Objective**: Extract existing functionality into clean utility functions.

#### 2.1 Core Operations Extraction

Follow TDD: **Red → Green → Refactor** for each extraction.

**EXTRACT AWS Operations:**

```python
# 1. Write failing test for aws_identity_get()
# 2. Extract identity logic from auth_status() 
# 3. Refactor for clean utility API
```

**EXTRACT S3 Operations:**  

```python
# 1. Write failing tests for s3_object_get/put/list()
# 2. Adapt from bucket_object_*() functions
# 3. Refactor for generic S3 use
```

**EXTRACT Package Operations:**

```python  
# 1. Write failing tests for package_manifest_get()
# 2. Extract from package_browse() 
# 3. Refactor for utility use
```

#### 2.2 Dependency Layer Implementation

**Import Strategy** (prevents circular dependencies):

```python
# core_ops.py - No imports from other utils
# package_ops.py
from .core_ops import s3_object_get, s3_bucket_list

# content_ops.py  
from .core_ops import s3_object_get
from .package_ops import package_manifest_get

# search_ops.py
from .core_ops import s3_object_list
from .package_ops import package_list  
from .content_ops import data_load
```

### Stage 3: Missing Functionality Creation

**Objective**: Create only the truly missing functions.

#### 3.1 S3 Delete Operations

**CREATE `s3_object_delete()`:**

- **Reality**: No S3 delete functionality exists anywhere in codebase
- **Implementation**: Follow existing S3 operation patterns from buckets.py
- **Error Handling**: Use same response format as other S3 operations

#### 3.2 Package Delete Operations

**CREATE `package_delete()`:**  

- **Reality**: No package deletion functionality exists
- **Implementation**: Use Quilt3 package deletion APIs
- **Safety**: Include confirmation and dependency checking

### Stage 4: Refactoring and Optimization

**Objective**: Clean up extracted utilities and optimize for workflow tool use.

#### 4.1 Performance Optimization

- Optimize extracted functions for better performance
- Add appropriate caching where beneficial  
- Improve error handling and edge cases
- Add comprehensive type hints and documentation

#### 4.2 Integration Testing

- Test extracted utilities work together correctly
- Verify original tools still function with extracted utilities
- Performance regression testing

## Testing Strategy

### Test-Driven Development Requirements

**Each stage MUST follow TDD principles:**

1. **Red Phase**: Write failing BDD tests for each utility before implementation
2. **Green Phase**: Implement minimal code to make tests pass
3. **Refactor Phase**: Clean up implementation while keeping tests green

### Extraction-Specific Testing

**Test Extracted Functions Independently:**

```python
# Good: Test utility function directly
def test_aws_identity_get():
    identity = aws_identity_get()
    assert "account_id" in identity
    assert "user_arn" in identity

# Also Good: Test original tool still works
def test_auth_status_still_works():
    result = auth_status()
    assert result["success"] == True
```

**Test Dependency Layers:**

```python
# Ensure import dependencies work correctly
def test_package_ops_uses_core_ops():
    # package_ops.py should be able to import from core_ops
    from quilt_mcp_server.utils.core_ops import s3_object_get
    from quilt_mcp_server.utils.package_ops import package_manifest_get
    
    # Test that package_manifest_get can use s3_object_get internally
```

## Success Metrics

### Quantitative Goals

- **Test Coverage**: Maintain 100% test coverage for all utilities
- **Function Count**: Extract ~15 utilities, create ~2 new utilities
- **Performance**: No regression in existing tool performance  
- **Documentation**: Complete docstrings and type hints for all utilities

### Qualitative Goals

- **Code Quality**: All utilities are clean, single-responsibility functions
- **Dependency Clarity**: Clean dependency layers prevent circular imports
- **Extraction Quality**: Utilities maintain functionality of original implementations
- **Phase 2 Readiness**: All utilities ready for workflow tool composition

## Risk Mitigation

### Extraction Risks

1. **Complex Function Dependencies**: Embedded functions may be tightly coupled
   - **Mitigation**: Prefactoring phase prepares code for clean extraction
   - **Validation**: Test each utility in isolation before integration

2. **Hidden Side Effects**: Original functions may have undocumented side effects  
   - **Mitigation**: Comprehensive behavior testing during prefactoring
   - **Testing**: BDD tests validate expected behavior without side effects

3. **Performance Degradation**: Extracted utilities may be slower than embedded versions
   - **Mitigation**: Performance testing and optimization during refactoring
   - **Advantage**: Building on proven implementations reduces risk

### Integration Risks

1. **Backward Compatibility**: Extraction may break existing tool functionality
   - **Mitigation**: Maintain existing tools during extraction, test thoroughly
   - **Testing**: Comprehensive regression testing after each extraction

2. **Circular Dependencies**: Poor organization may create import cycles
   - **Mitigation**: Strict dependency-layer organization prevents cycles
   - **Validation**: Import testing verifies clean dependency structure

## Deliverables

1. **Utility Layer**: Complete `src/quilt_mcp_server/utils/` module with dependency-layer organization
2. **Test Suite**: Comprehensive BDD tests achieving 100% coverage for all utilities  
3. **Extraction Documentation**: Clear mapping of source → utility for all extractions
4. **Performance Validation**: Proof that extractions maintain original performance
5. **Phase 2 Foundation**: Ready-to-compose building blocks for workflow tool implementation

This Phase 1 design leverages the critical learning that most functionality already exists, transforming the approach from creation-heavy to extraction-heavy while using dependency-layer organization to prevent the circular dependency problems discovered in the learnings analysis.

<!-- markdownlint-disable MD013 -->
# Issue #227: Input Schema Complexity Analysis

## Problem Statement

After adding Pydantic types (PR #225), some tools became HARDER to call due to deeply nested and complex schemas. According to ChatGPT's assessment referenced in the issue, deeply nested Pydantic models inflate schemas and make it harder for models or clients to reason about available parameters.

## Data Analysis

### Tool Parameter Complexity (sorted by schema size)

| Tool | Total Props | Required | Optional | Nested Types | Schema Size (chars) |
|------|------------|----------|----------|--------------|---------------------|
| PackageCreateFromS3Params | 15 | 2 | 13 | 0 | 2,921 |
| DataVisualizationParams | 11 | 3 | 8 | 0 | 2,483 |
| BucketObjectsPutParams | 2 | 2 | 0 | **1** | 1,737 |
| PackageUpdateParams | 7 | 2 | 5 | 0 | 1,610 |
| PackageCreateParams | 7 | 2 | 5 | 0 | 1,602 |
| AthenaQueryExecuteParams | 7 | 1 | 6 | 0 | 1,417 |
| PackageBrowseParams | 7 | 1 | 6 | 0 | 1,326 |

### Key Findings

#### 1. **Too Many Optional Parameters**

- `PackageCreateFromS3Params`: 15 parameters (only 2 required, 13 optional)
- `DataVisualizationParams`: 11 parameters (only 3 required, 8 optional)
- This creates cognitive overload for LLMs trying to understand what's truly needed

#### 2. **Nested Type Definitions**

- `BucketObjectsPutParams` has nested `BucketObjectsPutItem` with 6 additional properties
- While only 1 level deep, the nesting inflates the schema significantly (1,737 chars for just 2 top-level params)

#### 3. **Schema Size Impact**

- Top tools have schemas of 2,000-3,000 characters
- This is token-expensive for the LLM to process
- More importantly, it's cognitively expensive to understand

## Root Causes

### 1. Feature Creep in Single Tools

Tools like `package_create_from_s3` try to do too much:

- Source bucket specification
- Package naming and metadata
- File filtering (include/exclude patterns)
- Organization options (auto_organize, generate_readme)
- Confirmation and dry-run flags
- Metadata template selection
- Copy mode configuration

### 2. Nested Object Definitions

`BucketObjectsPutParams.items` requires a list of `BucketObjectsPutItem` objects, each with:

- key
- text OR data (mutually exclusive)
- content_type
- encoding
- metadata dict

This nested structure is hard for LLMs to construct correctly.

### 3. Overly Permissive Type Unions

Many fields use `Optional[X]` or `str | None` with complex default logic, making it unclear when fields are needed.

## Proposed Solutions

### Strategy 1: Split Complex Tools into Simpler Variants

**Problem Tool:** `package_create_from_s3` (15 parameters)

**Solution:** Create focused variants:

```python
# Simple version - just the essentials
def package_create_from_s3_simple(
    source_bucket: str,
    package_name: str,
    source_prefix: str = "",
) -> PackageCreateFromS3Response:
    """Create a package from S3 with smart defaults."""
    ...

# Advanced version - for power users
def package_create_from_s3_advanced(
    params: PackageCreateFromS3Params  # Keep full params for advanced use
) -> PackageCreateFromS3Response:
    """Create a package from S3 with full control over all options."""
    ...
```

**Benefits:**

- LLMs can easily call the simple version
- Advanced users still have full control
- Schema for simple version is <500 chars

### Strategy 2: Flatten Nested Structures

**Problem Tool:** `BucketObjectsPutParams` (nested items)

**Current approach:**

```python
params = BucketObjectsPutParams(
    bucket="my-bucket",
    items=[
        BucketObjectsPutItem(key="file.txt", text="content", content_type="text/plain"),
        BucketObjectsPutItem(key="data.json", text='{"x": 1}', content_type="application/json"),
    ]
)
```

**Simplified approach:**

```python
# Option A: Accept dict instead of nested Pydantic model
def bucket_objects_put(
    bucket: str,
    items: list[dict[str, Any]],  # Simple dict structure
) -> BucketObjectsPutResponse:
    ...

# Option B: Provide a builder helper
def bucket_objects_put_simple(
    bucket: str,
    files: dict[str, str],  # key -> content mapping
    content_type: str = "text/plain",
) -> BucketObjectsPutResponse:
    """Upload multiple text files with the same content type."""
    ...
```

### Strategy 3: Reduce Optional Parameter Count

**Problem:** Too many optional parameters create decision paralysis

**Solution:** Use sensible defaults and remove rarely-used options from the main signature:

```python
# Before (7 optional params)
class PackageCreateParams(BaseModel):
    package_name: str  # required
    s3_uris: list[str]  # required
    registry: str = "s3://quilt-ernest-staging"
    metadata: Optional[dict] = None
    message: str = "Created via package_create tool"
    flatten: bool = True
    copy_mode: Literal["all", "same_bucket", "none"] = "all"

# After (3 optional params, move advanced to separate tool)
class PackageCreateParams(BaseModel):
    package_name: str  # required
    s3_uris: list[str]  # required
    registry: str = "s3://quilt-ernest-staging"  # commonly changed
    # metadata, message, flatten, copy_mode moved to _advanced variant
```

### Strategy 4: Use Progressive Disclosure

Organize tools into tiers:

1. **Tier 1: Simple/Common** - Exposed by default, <5 parameters, no nesting
2. **Tier 2: Advanced** - For power users, can have complex schemas
3. **Tier 3: Expert** - Internal/testing tools

Mark advanced tools clearly in their descriptions:

```python
def package_create_advanced(params: PackageCreateParams) -> Response:
    """[ADVANCED] Create a package with full control over all options.

    For simple use cases, use package_create_simple() instead.
    """
```

## Recommended Implementation Plan

### Phase 1: Create Simple Variants (Low Risk)

1. Add `*_simple()` versions of top 3 most complex tools:
   - `package_create_from_s3_simple()`
   - `data_visualization_create_simple()`
   - `bucket_objects_put_simple()`

2. Keep existing tools unchanged (no breaking changes)

3. Update tool descriptions to guide LLMs toward simple variants

### Phase 2: Flatten Nested Structures (Medium Risk)

1. Accept `list[dict]` in addition to `list[PydanticModel]` for nested params
2. Use runtime validation to convert dicts to models internally
3. Update schemas to show flattened structure

### Phase 3: Deprecate Complex Signatures (High Risk)

1. Mark overly complex tools as `[ADVANCED]`
2. Create migration guide for users
3. Eventually remove or hide from default tool list

## Success Metrics

1. **Schema Size**: Reduce average schema size for top 10 tools by 50%
2. **Parameter Count**: Keep simple variants to ≤5 parameters
3. **Nesting Depth**: Eliminate nested Pydantic models in simple variants
4. **LLM Success Rate**: Measure how often Claude successfully calls tools without errors
5. **User Feedback**: Track issue reports about tool complexity

## Risks and Mitigation

### Risk 1: API Proliferation

**Mitigation:** Only create simple variants for the most complex tools (top 3-5)

### Risk 2: Maintenance Burden

**Mitigation:** Simple variants call the same underlying implementation, just with different defaults

### Risk 3: User Confusion

**Mitigation:** Clear naming (`_simple` vs `_advanced`) and comprehensive documentation

### Risk 4: Breaking Changes

**Mitigation:** Phase 1 adds new tools without changing existing ones

## Next Steps

1. ✅ Analyze current tool complexity
2. ✅ Identify top 3 most complex tools
3. ⏳ Create simple variants for top 3 tools
4. ⏳ Test with real-world LLM usage
5. ⏳ Measure impact on success rates
6. ⏳ Iterate based on feedback

## Appendix: Full Complexity Table

```table
Tool Parameter Complexity Analysis
================================================================================
Name                                     Props    Req   Opt   Nested  Size
--------------------------------------------------------------------------------
PackageCreateFromS3Params                15       2     13    0       2921
DataVisualizationParams                  11       3     8     0       2483
BucketObjectsPutParams                   2        2     0     1       1737
PackageUpdateParams                      7        2     5     0       1610
PackageCreateParams                      7        2     5     0       1602
AthenaQueryExecuteParams                 7        1     6     0       1417
PackageBrowseParams                      7        1     6     0       1326
WorkflowAddStepParams                    6        3     3     0       1284
AthenaQueryHistoryParams                 6        0     6     0       1258
CatalogUriParams                         6        1     5     0       1165
PackageDiffParams                        5        2     3     0       1089
BucketObjectsListParams                  5        1     4     0       1001
WorkflowTemplateApplyParams              3        3     0     0       985
CatalogUrlParams                         4        1     3     0       958
WorkflowUpdateStepParams                 5        3     2     0       905
WorkflowCreateParams                     4        2     2     0       900
AthenaTablesListParams                   4        1     3     0       898
AthenaTableSchemaParams                  4        2     2     0       832
BucketObjectTextParams                   3        1     2     0       685
BucketObjectFetchParams                  3        1     2     0       683
PackagesListParams                       3        0     3     0       579
PackageDeleteParams                      2        1     1     0       544
BucketObjectLinkParams                   2        1     1     0       525
AthenaDatabasesListParams                2        0     2     0       494
AthenaWorkgroupsListParams               2        0     2     0       462
BucketObjectInfoParams                   1        1     0     0       444
WorkflowGetStatusParams                  1        1     0     0       321
AthenaQueryValidateParams                1        1     0     0       307
WorkflowListAllParams                    0        0     0     0       127
```

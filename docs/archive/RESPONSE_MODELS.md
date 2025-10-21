# Response Type Models

## Overview

This document describes the Pydantic models for MCP tool responses, replacing generic `Dict[str, Any]` with structured, validated response types.

## Motivation

Previously, all tools returned `dict[str, Any]`, which:

- ❌ Provides no type safety or validation
- ❌ Makes it unclear what fields are available
- ❌ Prevents IDE autocomplete and type checking
- ❌ Allows inconsistent response structures

With Pydantic models:

- ✅ Full type safety and runtime validation
- ✅ Clear, documented response structures
- ✅ IDE autocomplete and type checking
- ✅ Consistent responses across all tools
- ✅ Automatic JSON schema generation for MCP

## Using Response Models

### Basic Example

```python
from quilt_mcp.models import BucketObjectsListSuccess, BucketObjectsListError

def bucket_objects_list(
    bucket: str,
    prefix: str = "",
    max_keys: int = 100,
) -> BucketObjectsListSuccess | BucketObjectsListError:
    """List objects in an S3 bucket."""
    try:
        # ... fetch objects ...

        return BucketObjectsListSuccess(
            bucket=bucket,
            prefix=prefix,
            objects=objects,
            count=len(objects),
            is_truncated=False,
        )
    except Exception as e:
        return BucketObjectsListError(
            error=str(e),
            bucket=bucket,
            prefix=prefix,
        )
```

### Pattern: Success/Error Union Types

Most tools return a union of success and error types:

```python
from quilt_mcp.models import CatalogUrlResponse  # Union type alias

def catalog_url(registry: str, ...) -> CatalogUrlResponse:
    """Generate catalog URL."""
    try:
        # Success case
        return CatalogUrlSuccess(
            status="success",
            catalog_url=url,
            view_type="package",
            bucket=bucket,
            ...
        )
    except Exception as e:
        # Error case
        return CatalogUrlError(
            status="error",
            error=str(e),
        )
```

### Converting Existing Tools

Before:

```python
def my_tool(param: str) -> dict[str, Any]:
    """My tool."""
    try:
        result = do_something()
        return {
            "success": True,
            "data": result,
            "count": len(result),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
```

After:

```python
from quilt_mcp.models import SuccessResponse, ErrorResponse

class MyToolSuccess(SuccessResponse):
    """Success response for my_tool."""
    data: list[str]
    count: int

def my_tool(param: str) -> MyToolSuccess | ErrorResponse:
    """My tool."""
    try:
        result = do_something()
        return MyToolSuccess(
            data=result,
            count=len(result),
        )
    except Exception as e:
        return ErrorResponse(
            error=str(e),
        )
```

## Available Response Models

### Base Models

#### `SuccessResponse`

Base model for all successful operations.

```python
class SuccessResponse(BaseModel):
    success: Literal[True] = True
```

#### `ErrorResponse`

Base model for all error responses.

```python
class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: str
    cause: Optional[str] = None
    possible_fixes: Optional[list[str]] = None
    suggested_actions: Optional[list[str]] = None
```

### Catalog Models

#### `CatalogUrlSuccess`

```python
CatalogUrlSuccess(
    status="success",
    catalog_url="https://catalog.example.com/b/bucket/...",
    view_type="package",  # or "bucket"
    bucket="my-bucket",
    package_name="team/dataset",  # optional
    path="data/file.csv",  # optional
    catalog_host="catalog.example.com",  # optional
)
```

#### `CatalogUriSuccess`

```python
CatalogUriSuccess(
    status="success",
    quilt_plus_uri="quilt+s3://bucket#package=team/dataset@hash",
    bucket="my-bucket",
    package_name="team/dataset",  # optional
    path="data/",  # optional
    top_hash="abc123",  # optional
    tag="latest",  # optional
    catalog_host="catalog.example.com",  # optional
)
```

### S3/Bucket Models

#### `S3Object`

Metadata for a single S3 object.

```python
S3Object(
    key="data/file.csv",
    s3_uri="s3://bucket/data/file.csv",
    size=1024,
    last_modified="2024-10-20T12:00:00Z",
    etag='"abc123"',
    storage_class="STANDARD",  # optional
    signed_url="https://...",  # optional
    signed_url_expiry=3600,  # optional
)
```

#### `BucketObjectsListSuccess`

```python
BucketObjectsListSuccess(
    bucket="my-bucket",
    prefix="data/",
    objects=[S3Object(...), ...],
    count=10,
    is_truncated=False,
    next_continuation_token="...",  # optional
    auth_type="quilt",  # optional
)
```

#### `ObjectMetadata`

Detailed metadata for a single object.

```python
ObjectMetadata(
    bucket="my-bucket",
    key="data/file.csv",
    s3_uri="s3://my-bucket/data/file.csv",
    size=1024,
    content_type="text/csv",  # optional
    last_modified="2024-10-20T12:00:00Z",
    etag='"abc123"',
    version_id="v123",  # optional
    metadata={"key": "value"},  # user metadata
    storage_class="STANDARD",  # optional
)
```

#### `PresignedUrlResponse`

```python
PresignedUrlResponse(
    bucket="my-bucket",
    key="data/file.csv",
    s3_uri="s3://my-bucket/data/file.csv",
    signed_url="https://bucket.s3.amazonaws.com/...",
    expiration_seconds=3600,
    expires_at="2024-10-20T13:00:00Z",
    auth_type="quilt",  # optional
)
```

### Package Models

#### `PackageFileEntry`

```python
PackageFileEntry(
    logical_key="data/file.csv",
    physical_key="s3://bucket/.quilt/packages/abc123",
    size=1024,
    hash="sha256:...",  # optional
    meta={"key": "value"},  # optional
)
```

#### `PackageMetadata`

```python
PackageMetadata(
    user_meta={"description": "My dataset"},
    version="1.0.0",  # optional
    message="Initial commit",  # optional
)
```

#### `PackageBrowseSuccess`

```python
PackageBrowseSuccess(
    package_name="team/dataset",
    registry="s3://my-bucket",
    top_hash="abc123",
    entries=[PackageFileEntry(...), ...],
    metadata=PackageMetadata(...),
    total_size=10240,
    file_count=5,
)
```

#### `PackageCreateSuccess`

```python
PackageCreateSuccess(
    package_name="team/dataset",
    registry="s3://my-bucket",
    top_hash="abc123",
    message="Package created",
    files_added=5,
    total_size=10240,
    catalog_url="https://...",  # optional
)
```

### Athena Query Models

#### `QueryExecutionMetadata`

```python
QueryExecutionMetadata(
    query_execution_id="abc-123",
    state="SUCCEEDED",
    state_change_reason=None,  # optional
    data_scanned_bytes=1024,  # optional
    execution_time_ms=500,  # optional
    workgroup="primary",  # optional
    database="default",  # optional
)
```

#### `AthenaQuerySuccess`

```python
AthenaQuerySuccess(
    query="SELECT * FROM table",
    columns=["id", "name", "value"],
    data=[{"id": "1", "name": "Alice", "value": "100"}],  # Raw strings
    formatted_data=[{"id": 1, "name": "Alice", "value": 100}],  # Typed
    row_count=1,
    execution=QueryExecutionMetadata(...),
    output_format="json",
)
```

### Data Visualization Models

#### `VisualizationConfig`

```python
VisualizationConfig(
    type="boxplot",  # or "scatter", "line", "bar"
    option={...},  # ECharts option object
    filename="viz_boxplot_gene_expression.json",
)
```

#### `VisualizationFile`

```python
VisualizationFile(
    key="viz_data_boxplot.csv",
    text="gene,expression\nBRCA1,42.5\n...",
    content_type="text/csv",
)
```

#### `DataVisualizationSuccess`

```python
DataVisualizationSuccess(
    visualization_config=VisualizationConfig(...),
    data_file=VisualizationFile(...),
    quilt_summarize=VisualizationFile(...),
    files_to_upload=[VisualizationFile(...), ...],
    metadata={"total_points": 100, "mean": 42.5},
)
```

### Workflow Models

#### `WorkflowStep`

```python
WorkflowStep(
    step_id="step-1",
    description="Upload files",
    status="completed",  # or "pending", "in_progress", "failed", "skipped"
    step_type="manual",
    dependencies=["step-0"],
    result={"files_uploaded": 5},  # optional
    error_message=None,  # optional
    started_at="2024-10-20T12:00:00Z",  # optional
    completed_at="2024-10-20T12:05:00Z",  # optional
)
```

#### `WorkflowCreateSuccess`

```python
WorkflowCreateSuccess(
    workflow_id="wf-123",
    name="Data Processing Pipeline",
    description="Process genomics data",
    status="created",
    steps=[WorkflowStep(...), ...],
    created_at="2024-10-20T12:00:00Z",
)
```

## Type Aliases

For convenience, union types are provided:

```python
# Catalog
CatalogUrlResponse = CatalogUrlSuccess | CatalogUrlError
CatalogUriResponse = CatalogUriSuccess | CatalogUriError

# Bucket
BucketObjectsListResponse = BucketObjectsListSuccess | BucketObjectsListError
BucketObjectInfoResponse = BucketObjectInfoSuccess | BucketObjectInfoError

# Package
PackageBrowseResponse = PackageBrowseSuccess | ErrorResponse
PackageCreateResponse = PackageCreateSuccess | PackageCreateError

# Athena
AthenaQueryResponse = AthenaQuerySuccess | AthenaQueryError
AthenaQueryValidationResponse = AthenaQueryValidationSuccess | AthenaQueryValidationError

# Visualization
DataVisualizationResponse = DataVisualizationSuccess | DataVisualizationError

# Workflow
WorkflowCreateResponse = WorkflowCreateSuccess | ErrorResponse
WorkflowStepUpdateResponse = WorkflowStepUpdateSuccess | ErrorResponse
```

## Migration Guide

### Step 1: Import Models

```python
from quilt_mcp.models import (
    MyToolSuccess,
    MyToolError,
    MyToolResponse,  # Union type
)
```

### Step 2: Update Function Signature

```python
# Before
def my_tool(...) -> dict[str, Any]:

# After
def my_tool(...) -> MyToolResponse:
```

### Step 3: Replace Dict Construction with Model Construction

```python
# Before
return {
    "success": True,
    "data": result,
    "count": len(result),
}

# After
return MyToolSuccess(
    data=result,
    count=len(result),
)
```

### Step 4: Verify with Type Checker

```bash
uv run mypy src/quilt_mcp/tools/my_module.py
```

## Benefits

### 1. Type Safety

```python
# Type checker catches errors
response = bucket_objects_list(...)
if isinstance(response, BucketObjectsListSuccess):
    # response.objects is typed as list[S3Object]
    for obj in response.objects:
        print(obj.key)  # IDE autocomplete works!
```

### 2. Runtime Validation

```python
# Pydantic validates at runtime
try:
    response = BucketObjectsListSuccess(
        bucket="my-bucket",
        objects=[],
        count="invalid",  # Type error!
    )
except ValidationError as e:
    print(e.errors())
```

### 3. JSON Schema Generation

```python
# Automatically generates JSON schema for MCP
schema = BucketObjectsListSuccess.model_json_schema()
```

### 4. Consistent Error Handling

```python
# All errors follow the same structure
if not response.success:
    print(f"Error: {response.error}")
    if response.possible_fixes:
        print("Try:")
        for fix in response.possible_fixes:
            print(f"  - {fix}")
```

## Best Practices

### 1. Always Use Specific Models

❌ Don't:

```python
def my_tool() -> dict[str, Any]:
    return {"data": "..."}
```

✅ Do:

```python
def my_tool() -> MyToolSuccess | ErrorResponse:
    return MyToolSuccess(data="...")
```

### 2. Include Helpful Error Details

✅ Good:

```python
return ErrorResponse(
    error="Failed to access S3 bucket",
    cause="AccessDenied",
    possible_fixes=[
        "Check AWS credentials are configured",
        "Verify bucket permissions",
        "Ensure bucket exists",
    ],
    suggested_actions=[
        "Run: aws s3 ls s3://bucket-name",
        "Check IAM policy",
    ],
)
```

### 3. Use Optional Fields Appropriately

```python
class MyResponse(SuccessResponse):
    required_field: str
    optional_field: Optional[str] = None  # Can be omitted
    field_with_default: int = 0  # Has default value
```

### 4. Document Response Structure

```python
def my_tool() -> MyToolResponse:
    """My tool.

    Returns:
        MyToolSuccess with processed data, or ErrorResponse on failure.

        Success response includes:
        - data: Processed results
        - count: Number of items
        - metadata: Additional info

        Error response includes:
        - error: Error message
        - possible_fixes: List of suggested fixes
    """
```

## Testing with Models

```python
import pytest
from quilt_mcp.models import BucketObjectsListSuccess
from quilt_mcp.tools.buckets import bucket_objects_list

def test_bucket_objects_list_success():
    result = bucket_objects_list(bucket="test-bucket")

    # Type validation
    assert isinstance(result, BucketObjectsListSuccess)

    # Field access with type safety
    assert result.success is True
    assert result.bucket == "test-bucket"
    assert isinstance(result.objects, list)

    # Can serialize to dict
    data = result.model_dump()
    assert data["success"] is True

    # Can serialize to JSON
    json_str = result.model_dump_json()
```

## Future Work

- Add models for remaining tools (governance, tabulator, etc.)
- Generate OpenAPI documentation from models
- Add response validation middleware
- Create model factories for testing

## See Also

- [LLM Docstring Style Guide](./LLM_DOCSTRING_STYLE_GUIDE.md)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [MCP Specification](https://spec.modelcontextprotocol.io/)

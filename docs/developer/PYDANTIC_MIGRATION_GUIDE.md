# Pydantic Models Migration Guide

A practical guide for migrating MCP tools from `dict[str, Any]` to Pydantic models.

## Quick Start

### For Tools with Existing Models

If models already exist in `src/quilt_mcp/models/`, migration is straightforward:

```python
# 1. Import the models
from quilt_mcp.models import (
    YourToolParams,      # Input model
    YourToolSuccess,     # Success response
    YourToolError        # Error response
)

# 2. Update function signature
def your_tool(params: YourToolParams) -> YourToolSuccess | YourToolError:
    try:
        # Your implementation
        return YourToolSuccess(...)
    except Exception as e:
        return YourToolError(error=str(e), ...)

# 3. Update MCP registration to handle conversion
@server.tool()
async def your_tool(**kwargs) -> Dict[str, Any]:
    params = YourToolParams(**kwargs)
    result = your_tool(params)
    return result.model_dump()
```

### For Tools Without Models

Create new models following this template:

```python
# src/quilt_mcp/models/inputs.py
class YourToolParams(BaseModel):
    """Parameters for your tool."""

    required_field: str = Field(
        description="Description of the field",
        examples=["example1", "example2"]
    )
    optional_field: Optional[int] = Field(
        default=None,
        ge=0,  # Greater than or equal to 0
        le=100,  # Less than or equal to 100
        description="Optional parameter with constraints"
    )

# src/quilt_mcp/models/responses.py
class YourToolSuccess(SuccessResponse):
    """Successful response from your tool."""

    result_data: Any
    metadata: Dict[str, Any]
    count: int

class YourToolError(ErrorResponse):
    """Error response from your tool."""

    context: Optional[str] = None
    retry_after: Optional[int] = None
```

## Migration Steps

### Step 1: Assess Current State

Check your tool's current implementation:

```bash
# Find all functions returning dict[str, Any]
grep -n "-> .*[Dd]ict\[str, Any\]" src/quilt_mcp/tools/your_tool.py

# Check if models already exist for your tool
ls src/quilt_mcp/models/ | grep -i your_tool
```

### Step 2: Create or Verify Models

#### Check Existing Models
```python
# Check what's available
from quilt_mcp.models import *
print([m for m in dir() if "YourTool" in m])
```

#### Create New Models if Needed
```python
# Template for input models
class YourToolParams(BaseModel):
    """Input parameters with validation."""

    # Required fields
    required_str: str = Field(description="Required string")

    # Optional with defaults
    optional_int: int = Field(default=100, ge=1, le=1000)

    # Pattern validation
    s3_uri: str = Field(pattern=r"^s3://[a-z0-9.\-]+/.*$")

    # Enum constraints
    output_format: Literal["json", "csv", "parquet"] = Field(default="json")

    # Complex types
    items: List[Dict[str, Any]] = Field(default_factory=list)

    # Custom validation
    @field_validator("s3_uri")
    def validate_s3_uri(cls, v):
        if not v.startswith("s3://"):
            raise ValueError("Must be an S3 URI")
        return v
```

### Step 3: Update Function Implementation

#### Before (Current State)
```python
def my_tool(
    param1: str,
    param2: int = 100,
    param3: Optional[str] = None
) -> dict[str, Any]:
    try:
        # Implementation
        return {
            "status": "success",
            "result": result,
            "metadata": {...}
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
```

#### After (With Pydantic)
```python
from quilt_mcp.models import MyToolParams, MyToolSuccess, MyToolError

def my_tool(params: MyToolParams) -> MyToolSuccess | MyToolError:
    try:
        # Implementation using params.param1, params.param2, etc.
        return MyToolSuccess(
            result=result,
            metadata={...}
        )
    except Exception as e:
        return MyToolError(
            error=str(e),
            suggestions=_get_suggestions(e)
        )
```

### Step 4: Update MCP Registration

The MCP server expects dict returns, so convert models:

```python
# src/quilt_mcp/server.py or registration file

@server.tool()
async def my_tool(
    param1: str,
    param2: int = 100,
    param3: Optional[str] = None
) -> Dict[str, Any]:
    """Tool description for MCP."""
    from quilt_mcp.tools.my_module import my_tool
    from quilt_mcp.models import MyToolParams

    # Create validated params
    params = MyToolParams(
        param1=param1,
        param2=param2,
        param3=param3
    )

    # Execute tool
    result = my_tool(params)

    # Convert to dict for MCP
    return result.model_dump(exclude_none=True)
```

### Step 5: Update Tests

#### Unit Tests
```python
# tests/unit/test_my_tool.py

from quilt_mcp.models import MyToolParams, MyToolSuccess, MyToolError
from quilt_mcp.tools.my_module import my_tool

def test_my_tool_success():
    """Test successful execution."""
    params = MyToolParams(param1="test", param2=50)
    result = my_tool(params)

    assert isinstance(result, MyToolSuccess)
    assert result.status == "success"
    # Type-safe field access
    assert result.metadata is not None

def test_my_tool_validation():
    """Test input validation."""
    with pytest.raises(ValidationError) as exc:
        params = MyToolParams(
            param1="",  # Empty string might fail validation
            param2=10000  # Exceeds maximum
        )

    errors = exc.value.errors()
    assert len(errors) > 0

def test_my_tool_error():
    """Test error handling."""
    params = MyToolParams(param1="trigger_error")
    result = my_tool(params)

    assert isinstance(result, MyToolError)
    assert len(result.suggestions) > 0
```

#### Integration Tests
```python
# tests/integration/test_my_tool_integration.py

def test_my_tool_mcp_integration():
    """Test MCP registration and schema generation."""
    # Test that MCP can handle the tool
    from quilt_mcp.server import server

    # Get tool schema
    tools = server.list_tools()
    my_tool_schema = next(t for t in tools if t.name == "my_tool")

    # Verify schema has proper constraints
    assert my_tool_schema.inputSchema["properties"]["param2"]["minimum"] == 1
    assert my_tool_schema.inputSchema["properties"]["param2"]["maximum"] == 1000
```

### Step 6: Add Backward Compatibility (Optional)

For gradual migration:

```python
def my_tool(
    param1: str = None,
    param2: int = None,
    params: Optional[MyToolParams] = None
) -> MyToolSuccess | MyToolError | dict[str, Any]:
    """Backward compatible implementation."""

    # Support both old and new calling patterns
    if params is None:
        # Legacy call - create params from arguments
        params = MyToolParams(param1=param1, param2=param2)
        # Return dict for backward compatibility
        result = _my_tool_impl(params)
        return result.model_dump()
    else:
        # New call with params object
        return _my_tool_impl(params)
```

## Model Best Practices

### 1. Use Descriptive Field Names
```python
# Good
class PackageCreateParams(BaseModel):
    package_name: str
    source_bucket: str
    target_registry: str

# Bad
class Params(BaseModel):
    name: str
    src: str
    tgt: str
```

### 2. Add Comprehensive Validation
```python
class S3Params(BaseModel):
    s3_uri: str = Field(
        pattern=r"^s3://[a-z0-9.\-]+/.*$",
        description="S3 URI in format s3://bucket/key"
    )

    @field_validator("s3_uri")
    def validate_not_root(cls, v):
        if v == "s3://":
            raise ValueError("Cannot use root S3 URI")
        return v
```

### 3. Use Union Types for Responses
```python
# Type alias for convenience
PackageCreateResponse = PackageCreateSuccess | PackageCreateError

def package_create(params: PackageCreateParams) -> PackageCreateResponse:
    # Implementation
```

### 4. Include Examples in Fields
```python
query: str = Field(
    description="SQL query to execute",
    examples=[
        "SELECT * FROM my_table LIMIT 10",
        "SHOW DATABASES",
        "DESCRIBE my_table"
    ]
)
```

### 5. Document Model Purpose
```python
class DataVisualizationParams(BaseModel):
    """Parameters for creating interactive data visualizations.

    This model validates inputs for chart generation including
    data format, plot type, and styling options.
    """
```

## Testing Models

### Validation Tests
```python
def test_model_validation():
    """Test all validation rules."""

    # Test required fields
    with pytest.raises(ValidationError):
        MyModel()  # Missing required fields

    # Test constraints
    with pytest.raises(ValidationError):
        MyModel(count=-1)  # Negative not allowed

    # Test patterns
    with pytest.raises(ValidationError):
        MyModel(s3_uri="http://example.com")  # Not S3

    # Test valid model
    model = MyModel(
        required_field="value",
        count=10,
        s3_uri="s3://bucket/key"
    )
    assert model.count == 10
```

### Schema Generation Tests
```python
def test_schema_generation():
    """Test JSON schema generation."""
    schema = MyModel.model_json_schema()

    # Check required fields
    assert "required" in schema
    assert "required_field" in schema["required"]

    # Check constraints
    assert schema["properties"]["count"]["minimum"] == 0
    assert schema["properties"]["count"]["maximum"] == 1000

    # Check descriptions
    assert "description" in schema["properties"]["s3_uri"]
```

### Serialization Tests
```python
def test_serialization():
    """Test model serialization."""
    model = MyModel(field1="value", field2=42)

    # To dict
    data = model.model_dump()
    assert data["field1"] == "value"

    # To JSON
    json_str = model.model_dump_json()
    assert "field1" in json_str

    # Exclude None values
    data = model.model_dump(exclude_none=True)
    assert "optional_field" not in data
```

## Common Migration Issues

### Issue 1: Circular Imports
**Problem**: Models importing from tools, tools importing from models.
**Solution**: Keep models independent, import only in functions.

```python
# Good - import inside function
def my_tool(params):
    from quilt_mcp.services.helper import process_data
    return process_data(params)

# Bad - top-level circular import
from quilt_mcp.services.helper import process_data
```

### Issue 2: Breaking Changes
**Problem**: Existing code expects dict returns.
**Solution**: Use compatibility wrappers during transition.

```python
def my_tool_compat(**kwargs) -> dict[str, Any]:
    """Compatibility wrapper."""
    params = MyToolParams(**kwargs)
    result = my_tool_new(params)
    return result.model_dump()
```

### Issue 3: Complex Nested Structures
**Problem**: Deep nesting makes models complex.
**Solution**: Break into smaller, reusable models.

```python
# Good - composable models
class FileMetadata(BaseModel):
    size: int
    modified: datetime

class S3Object(BaseModel):
    key: str
    metadata: FileMetadata

class BucketListResponse(BaseModel):
    objects: List[S3Object]

# Bad - everything in one model
class Response(BaseModel):
    objects: List[Dict[str, Any]]  # No structure
```

### Issue 4: Optional vs Required Fields
**Problem**: Unclear which fields are optional.
**Solution**: Be explicit with Optional and defaults.

```python
class MyModel(BaseModel):
    required: str  # Required, no default
    optional: Optional[str] = None  # Optional with None default
    with_default: int = 100  # Optional with value default
```

## Migration Checklist

For each tool being migrated:

- [ ] **Assessment**
  - [ ] Identify current function signature
  - [ ] Document current return structure
  - [ ] Check if models already exist

- [ ] **Model Creation/Verification**
  - [ ] Create/verify input parameter model
  - [ ] Create/verify success response model
  - [ ] Create/verify error response model
  - [ ] Add validation rules and constraints
  - [ ] Add field descriptions and examples

- [ ] **Implementation**
  - [ ] Update function signature
  - [ ] Update function body to use models
  - [ ] Update error handling
  - [ ] Add type hints throughout

- [ ] **Integration**
  - [ ] Update MCP registration
  - [ ] Handle model-to-dict conversion
  - [ ] Test schema generation

- [ ] **Testing**
  - [ ] Update existing tests
  - [ ] Add validation tests
  - [ ] Add serialization tests
  - [ ] Run integration tests

- [ ] **Documentation**
  - [ ] Update docstrings
  - [ ] Update API documentation
  - [ ] Add migration notes

- [ ] **Compatibility**
  - [ ] Add compatibility wrapper if needed
  - [ ] Document deprecation timeline
  - [ ] Update dependent code

## Resources

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [MCP Schema Specification](https://modelcontextprotocol.io/docs/spec/schema)
- [Example Migration: athena_query_execute](./MIGRATION_EXAMPLE_ATHENA.md)
- [Migration Status Report](./PYDANTIC_MIGRATION_STATUS.md)

## Getting Help

- Check existing migrated tools in `src/quilt_mcp/tools/buckets.py` for examples
- Review model definitions in `src/quilt_mcp/models/`
- Run tests to verify your migration: `pytest tests/unit/test_your_tool.py`
- Use type checkers to catch issues: `mypy src/quilt_mcp/tools/your_tool.py`
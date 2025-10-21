# Example Migration: athena_query_execute

This document shows the step-by-step process of migrating `athena_query_execute` from `Dict[str, Any]` to Pydantic models.

## Step 1: Review Current Implementation

### Current Function Signature
```python
def athena_query_execute(
    query: str,
    database_name: Optional[str] = None,
    workgroup_name: Optional[str] = None,
    data_catalog_name: str = "AwsDataCatalog",
    max_results: int = 1000,
    output_format: str = "json",
    use_quilt_auth: bool = True,
    service: Optional[Any] = None,
) -> Dict[str, Any]:
```

### Current Return Structure
```python
# Success case
return {
    "status": "success",
    "data": results,
    "row_count": len(results),
    "columns": column_names,
    "query_execution_id": query_id,
    "execution_time_ms": execution_ms,
    "data_scanned_bytes": bytes_scanned,
    "output_format": output_format
}

# Error case
return {
    "status": "error",
    "error": str(error),
    "suggestions": ["Check syntax", "Verify permissions"]
}
```

## Step 2: Verify Available Models

### Input Model (already exists)
```python
# src/quilt_mcp/models/inputs.py
class AthenaQueryExecuteParams(BaseModel):
    """Parameters for executing an Athena query."""

    query: str = Field(
        description="SQL query to execute",
        examples=["SELECT * FROM my_table LIMIT 10"]
    )
    database_name: Optional[str] = Field(
        default=None,
        description="Default database for query context"
    )
    workgroup_name: Optional[str] = Field(
        default=None,
        description="Athena workgroup to use"
    )
    data_catalog_name: str = Field(
        default="AwsDataCatalog",
        description="Data catalog to use"
    )
    max_results: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of results to return"
    )
    output_format: str = Field(
        default="json",
        pattern="^(json|csv|parquet|table)$",
        description="Output format for results"
    )
    use_quilt_auth: bool = Field(
        default=True,
        description="Use Quilt assumed role credentials if available"
    )
    service: Optional[Any] = Field(
        default=None,
        description="Optional pre-configured AthenaQueryService"
    )
```

### Response Models (already exist)
```python
# src/quilt_mcp/models/responses.py
class QueryExecutionMetadata(BaseModel):
    """Metadata about query execution."""

    query_execution_id: str
    execution_time_ms: int
    data_scanned_bytes: Optional[int] = None
    output_location: Optional[str] = None

class AthenaQuerySuccess(SuccessResponse):
    """Successful Athena query execution."""

    data: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    metadata: QueryExecutionMetadata
    output_format: str

class AthenaQueryError(ErrorResponse):
    """Error during Athena query execution."""

    query: str
    database: Optional[str] = None
    workgroup: Optional[str] = None
```

## Step 3: Migration Implementation

### Updated Function Implementation

```python
# src/quilt_mcp/services/athena_read_service.py

from quilt_mcp.models import (
    AthenaQueryExecuteParams,
    AthenaQuerySuccess,
    AthenaQueryError,
    QueryExecutionMetadata
)

def athena_query_execute(
    params: AthenaQueryExecuteParams
) -> AthenaQuerySuccess | AthenaQueryError:
    """Execute SQL query against Athena using SQLAlchemy/PyAthena.

    Args:
        params: Validated query execution parameters

    Returns:
        AthenaQuerySuccess with results or AthenaQueryError with details
    """
    try:
        # Use params.service if provided, otherwise create service
        if params.service:
            service = params.service
        else:
            service = AthenaQueryService(
                use_quilt_auth=params.use_quilt_auth
            )

        # Execute query using existing service logic
        result = service.execute_query(
            query=params.query,
            database_name=params.database_name,
            workgroup_name=params.workgroup_name,
            data_catalog_name=params.data_catalog_name,
            max_results=params.max_results
        )

        # Format results based on output format
        formatted_data = service.format_results(
            result_data=result,
            output_format=params.output_format
        )

        # Create metadata object
        metadata = QueryExecutionMetadata(
            query_execution_id=result.get("query_execution_id", ""),
            execution_time_ms=result.get("execution_time_ms", 0),
            data_scanned_bytes=result.get("data_scanned_bytes"),
            output_location=result.get("output_location")
        )

        # Return success response
        return AthenaQuerySuccess(
            data=formatted_data["data"],
            row_count=len(formatted_data["data"]),
            columns=formatted_data.get("columns", []),
            metadata=metadata,
            output_format=params.output_format
        )

    except Exception as e:
        # Determine error suggestions based on error type
        suggestions = _get_error_suggestions(str(e), params.query)

        return AthenaQueryError(
            error=str(e),
            suggestions=suggestions,
            query=params.query,
            database=params.database_name,
            workgroup=params.workgroup_name
        )

def _get_error_suggestions(error_msg: str, query: str) -> List[str]:
    """Generate helpful suggestions based on error message."""
    suggestions = []

    if "TABLE_NOT_FOUND" in error_msg:
        suggestions.append("Verify table exists with SHOW TABLES")
        suggestions.append("Check database name is correct")

    if "mismatched input" in error_msg and "-" in query:
        suggestions.append("Wrap names with hyphens in double quotes")
        suggestions.append("Example: SELECT * FROM \"table-name\"")

    if "AccessDenied" in error_msg:
        suggestions.append("Check IAM permissions for Athena")
        suggestions.append("Verify S3 access to query results location")

    if not suggestions:
        suggestions.append("Check query syntax")
        suggestions.append("Verify database and table names")

    return suggestions
```

## Step 4: Update MCP Tool Registration

### Current Registration
```python
# src/quilt_mcp/server.py (or wherever tools are registered)

@server.tool()
async def athena_query_execute(
    query: str,
    database_name: Optional[str] = None,
    # ... other params
) -> Dict[str, Any]:
    from quilt_mcp.services.athena_read_service import athena_query_execute
    return athena_query_execute(query, database_name, ...)
```

### Updated Registration
```python
# src/quilt_mcp/server.py

@server.tool()
async def athena_query_execute(
    query: str,
    database_name: Optional[str] = None,
    workgroup_name: Optional[str] = None,
    data_catalog_name: str = "AwsDataCatalog",
    max_results: int = 1000,
    output_format: str = "json",
    use_quilt_auth: bool = True,
) -> Dict[str, Any]:  # Keep dict for MCP compatibility
    """Execute SQL query against Athena."""
    from quilt_mcp.services.athena_read_service import athena_query_execute
    from quilt_mcp.models import AthenaQueryExecuteParams

    # Create params object (validates input)
    params = AthenaQueryExecuteParams(
        query=query,
        database_name=database_name,
        workgroup_name=workgroup_name,
        data_catalog_name=data_catalog_name,
        max_results=max_results,
        output_format=output_format,
        use_quilt_auth=use_quilt_auth
    )

    # Execute with models
    result = athena_query_execute(params)

    # Convert to dict for MCP
    return result.model_dump()
```

## Step 5: Update Tests

### Current Test
```python
def test_athena_query_execute():
    result = athena_query_execute(
        query="SELECT * FROM test_table",
        database_name="test_db"
    )
    assert result["status"] == "success"
    assert "data" in result
```

### Updated Test
```python
from quilt_mcp.models import (
    AthenaQueryExecuteParams,
    AthenaQuerySuccess,
    AthenaQueryError
)

def test_athena_query_execute_success():
    """Test successful query execution with models."""
    params = AthenaQueryExecuteParams(
        query="SELECT * FROM test_table",
        database_name="test_db",
        max_results=10
    )

    result = athena_query_execute(params)

    # Type-safe assertions
    assert isinstance(result, AthenaQuerySuccess)
    assert result.row_count >= 0
    assert len(result.columns) > 0
    assert result.metadata.query_execution_id

def test_athena_query_execute_validation():
    """Test input validation."""
    with pytest.raises(ValidationError) as exc_info:
        params = AthenaQueryExecuteParams(
            query="",  # Empty query should fail
            max_results=100000  # Exceeds maximum
        )

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("query",) for e in errors)
    assert any(e["loc"] == ("max_results",) for e in errors)

def test_athena_query_execute_error():
    """Test error handling with models."""
    params = AthenaQueryExecuteParams(
        query="SELECT * FROM nonexistent_table"
    )

    result = athena_query_execute(params)

    assert isinstance(result, AthenaQueryError)
    assert "nonexistent_table" in result.error
    assert len(result.suggestions) > 0
    assert result.query == params.query
```

## Step 6: Backward Compatibility Wrapper (Optional)

If you need to maintain backward compatibility temporarily:

```python
def athena_query_execute_legacy(
    query: str,
    database_name: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Legacy wrapper for backward compatibility."""
    import warnings
    warnings.warn(
        "Using legacy athena_query_execute signature. "
        "Please migrate to using AthenaQueryExecuteParams.",
        DeprecationWarning,
        stacklevel=2
    )

    params = AthenaQueryExecuteParams(
        query=query,
        database_name=database_name,
        **kwargs
    )

    result = athena_query_execute(params)
    return result.model_dump()
```

## Benefits of This Migration

### 1. Type Safety
```python
# IDE knows exactly what fields are available
result = athena_query_execute(params)
if isinstance(result, AthenaQuerySuccess):
    print(result.metadata.execution_time_ms)  # Autocomplete works!
```

### 2. Input Validation
```python
# Validation happens automatically
try:
    params = AthenaQueryExecuteParams(
        query="SELECT *",
        max_results=1000000  # ValidationError: exceeds maximum
    )
except ValidationError as e:
    print(e.errors())  # Clear error messages
```

### 3. Better MCP Schemas
The MCP server automatically generates rich JSON schemas from Pydantic models:
```json
{
    "properties": {
        "query": {
            "type": "string",
            "description": "SQL query to execute",
            "examples": ["SELECT * FROM my_table LIMIT 10"]
        },
        "max_results": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10000,
            "default": 1000,
            "description": "Maximum number of results to return"
        }
    }
}
```

### 4. Consistent Error Handling
```python
# All errors follow the same structure
if isinstance(result, AthenaQueryError):
    print(f"Error: {result.error}")
    print("Suggestions:")
    for suggestion in result.suggestions:
        print(f"  - {suggestion}")
```

## Migration Checklist

- [ ] Import Pydantic models
- [ ] Update function signature to accept params object
- [ ] Update return type to use response models
- [ ] Convert internal logic to use model fields
- [ ] Update error handling to return error models
- [ ] Update MCP registration to handle model conversion
- [ ] Update existing tests to use models
- [ ] Add validation tests
- [ ] Add backward compatibility wrapper if needed
- [ ] Update documentation
- [ ] Test with MCP client to verify schema generation

## Common Pitfalls

1. **Forgetting to convert models to dict for MCP**
   - MCP expects dict returns, so use `model.model_dump()`

2. **Not handling all error cases**
   - Ensure all exceptions return the error model

3. **Breaking existing integrations**
   - Use compatibility wrappers during transition

4. **Missing validation constraints**
   - Review and add appropriate Field constraints

5. **Incomplete test coverage**
   - Test both success and error paths with models

## Next Steps

After migrating this tool:
1. Monitor for any issues in production
2. Gather feedback on the new structure
3. Apply learnings to other tool migrations
4. Remove compatibility wrappers after transition period
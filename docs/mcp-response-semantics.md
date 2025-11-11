# MCP Response Semantics: Understanding Success vs. Failure

## The Problem

When looking at MCP Inspector, you might see a tool report "Tool Result: Success" (green) but the response content shows `success: false`. This appears contradictory but is actually **correct behavior** following MCP best practices.

## Two Layers of Success/Failure

MCP tools have two distinct layers:

### 1. Tool Execution Layer (MCP Framework)

This is what the MCP framework reports:

- **"Tool Result: Success"** ✅ = The Python function executed without raising an exception
- **"Tool Result: Error"** ❌ = The Python function raised an exception

### 2. Application Layer (Tool Response)

This is what the response content indicates:

- **`success: true`** = The operation succeeded (found results, completed action, etc.)
- **`success: false`** = The operation failed (not authenticated, no backends available, etc.)

## Example

When `search_catalog` is called but the user isn't authenticated:

```python
result = search_catalog(query="test")
```

**MCP Inspector shows:**
```
Tool Result: Success  ✅
```

**Response content shows:**
```json
{
  "success": false,
  "error": "Search catalog requires authentication",
  "query": "test",
  "scope": "global"
}
```

### Why This Is Correct

1. **The tool executed successfully** - No Python exception was raised
2. **The search operation failed** - User needs to authenticate first
3. **The error is expected** - Not authenticating is a normal failure case, not a bug

## MCP Best Practices

According to MCP design principles:

### ✅ DO: Return structured responses for expected failures

```python
def search_catalog(query: str) -> SearchCatalogSuccess | SearchCatalogError:
    if not authenticated():
        return SearchCatalogError(
            error="Search catalog requires authentication",
            query=query
        )
    # ... normal processing
```

### ❌ DON'T: Raise exceptions for expected failures

```python
def search_catalog(query: str):
    if not authenticated():
        raise Exception("Not authenticated")  # Wrong!
```

### Why?

- **Exceptions are for bugs** - Unexpected, unhandled errors
- **Structured responses are for operations** - Expected outcomes, including failures
- **Type safety** - Union types (`Success | Error`) make error handling explicit
- **Better UX** - AI agents can parse structured errors and take action

## Implementation Pattern

### Response Models

```python
from pydantic import BaseModel
from typing import Literal, Dict, Any

class SuccessResponse(BaseModel):
    success: Literal[True] = True

class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: str
    # ... additional error fields

class SearchCatalogSuccess(SuccessResponse):
    results: list[SearchResult]
    total_results: int
    # ... additional success fields

class SearchCatalogError(ErrorResponse):
    query: str
    scope: str
    # ... additional error context
```

### Tool Implementation

**IMPORTANT**: For operational failures, raise exceptions instead of returning error models!

```python
def search_catalog(query: str) -> Dict[str, Any]:
    """
    Returns dict on success, raises RuntimeError on failure.
    We use Pydantic models for validation, then serialize to dict.
    """
    try:
        # Attempt operation
        results = perform_search(query)

        if not results.authenticated:
            # Raise exception for operational failures
            raise RuntimeError("Authentication required")

        # Success: return serialized model
        return SearchCatalogSuccess(
            results=results.items,
            total_results=len(results.items)
        ).model_dump()  # ← Serialize to dict!

    except SearchException as e:
        # Convert domain exceptions to RuntimeError
        raise RuntimeError(str(e))
```

### Why `.model_dump()` is Required

FastMCP wraps return values in an envelope. If you return a Pydantic model object directly:

```python
# ❌ WRONG - Returns model object
return SearchCatalogSuccess(...)

# Result in MCP Inspector:
# {
#   "result": {  ← Extra wrapper!
#     "success": true,
#     "results": [...]
#   }
# }
```

When you call `.model_dump()`:

```python
# ✅ CORRECT - Returns plain dict
return SearchCatalogSuccess(...).model_dump()

# Result in MCP Inspector:
# {
#   "success": true,
#   "results": [...]
# }
```

The model object gets double-wrapped, but the plain dict doesn't.

### Using Error Models for Exception Context

Error response models are still useful for structuring exception information:

```python
# Build structured error
error_model = SearchCatalogError(
    error="Search not available",
    query=query,
    scope=scope,
    backend_status={"elasticsearch": "unavailable"}
)

# Raise exception with structured JSON
raise RuntimeError(f"{error_model.error}\n{error_model.model_dump_json(indent=2)}")
```

This provides rich error context in the exception message that can be parsed by the AI agent.

## Summary

| Scenario | MCP Status | Response Data | Meaning |
|----------|------------|---------------|---------|
| Search found results | Success ✅ | `{"success": true, "results": [...]}` | Everything worked |
| User not authenticated | Error ❌ | Exception with structured JSON | Operational failure |
| Permission denied | Error ❌ | Exception with structured JSON | Operational failure |
| Python exception raised | Error ❌ | Exception message | Unexpected bug |

**Key Insight**:
- **Success** = Tool returns data (serialized Pydantic model)
- **Error** = Tool raises exception (optionally with structured error info)

This makes the MCP Inspector UX clear: "Success" means data was returned, "Error" means an exception was raised.

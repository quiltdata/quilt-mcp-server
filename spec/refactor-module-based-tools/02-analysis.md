# Module-Based Tools Refactoring - Analysis

## Current Architecture

### Tool Registration Pattern

```python
# Current: utils.py
def register_tools(mcp: FastMCP, tool_modules: list[Any] | None = None) -> int:
    for module in tool_modules:
        functions = inspect.getmembers(module, predicate=inspect.isfunction)
        for name, func in functions:
            if not name.startswith("_"):
                mcp.tool(func)  # Each function becomes a separate tool
```

**Result**: 84 individual MCP tools

### Example: Current athena_glue Module

```python
# Current: tools/athena_glue.py
def athena_databases_list(catalog_name: str = "AwsDataCatalog") -> Dict[str, Any]:
    """List available databases in AWS Glue Data Catalog."""
    ...

def athena_query_execute(query: str, database_name: Optional[str] = None, ...) -> Dict[str, Any]:
    """Execute SQL query against Athena."""
    ...

# ... 5 more functions
```

**MCP Client Usage**:
```json
{
  "method": "tools/call",
  "params": {
    "name": "athena_databases_list",
    "arguments": {"catalog_name": "AwsDataCatalog"}
  }
}
```

## Proposed Architecture Options

### Option 1: Action-Based Dispatch (Recommended)

Create a single wrapper function per module that dispatches based on an `action` parameter.

**Structure**:
```python
# Proposed: tools/athena_glue.py
def athena_glue(action: str, **kwargs) -> Dict[str, Any]:
    """
    AWS Athena and Glue Data Catalog operations.
    
    Available actions:
    - databases_list: List available databases
    - query_execute: Execute SQL query
    - query_history: Get query execution history
    - query_validate: Validate SQL syntax
    - table_schema: Get table schema details
    - workgroups_list: List available workgroups
    - tables_list: List tables in a database
    
    Args:
        action: The operation to perform
        **kwargs: Action-specific parameters
    
    Returns:
        Action-specific response dictionary
    
    Examples:
        # List databases
        athena_glue(action="databases_list", catalog_name="AwsDataCatalog")
        
        # Execute query
        athena_glue(action="query_execute", query="SELECT * FROM my_table", database_name="default")
    """
    # Dispatch to appropriate function
    actions = {
        "databases_list": athena_databases_list,
        "query_execute": athena_query_execute,
        "query_history": athena_query_history,
        # ... other actions
    }
    
    if action not in actions:
        return format_error_response(
            f"Unknown action: {action}. Available actions: {', '.join(actions.keys())}"
        )
    
    try:
        return actions[action](**kwargs)
    except TypeError as e:
        # Handle parameter mismatches
        return format_error_response(f"Invalid parameters for action '{action}': {e}")
```

**MCP Client Usage**:
```json
{
  "method": "tools/call",
  "params": {
    "name": "athena_glue",
    "arguments": {
      "action": "databases_list",
      "catalog_name": "AwsDataCatalog"
    }
  }
}
```

**Pros**:
- ✅ Reduces tool count from 84 to 16
- ✅ Clear module-based organization
- ✅ Action names appear in tool schema for discoverability
- ✅ Easy to validate actions before execution
- ✅ Maintains type safety with **kwargs
- ✅ Simple error handling for unknown actions

**Cons**:
- ⚠️ Action parameter adds one level of indirection
- ⚠️ Type checkers may not validate action-specific parameters
- ⚠️ Slightly more verbose client code
- ⚠️ Requires client code updates

### Option 2: Nested Tool Objects

Create tool classes that group related functions as methods.

**Structure**:
```python
class AthenaGlue:
    """AWS Athena and Glue Data Catalog operations."""
    
    @staticmethod
    def databases_list(catalog_name: str = "AwsDataCatalog") -> Dict[str, Any]:
        """List available databases."""
        ...
    
    @staticmethod
    def query_execute(query: str, ...) -> Dict[str, Any]:
        """Execute SQL query."""
        ...
```

**Pros**:
- ✅ Clear organization
- ✅ Maintains individual method signatures

**Cons**:
- ❌ FastMCP doesn't natively support class-based tools
- ❌ Would require custom registration logic
- ❌ More complex implementation
- ❌ Still exposes many tools (just grouped differently)

### Option 3: Hybrid Approach (Action + Aliases)

Maintain both action-based and individual tools, with individual tools calling the action-based wrapper.

**Structure**:
```python
def athena_glue(action: str, **kwargs) -> Dict[str, Any]:
    """Main module tool with action dispatch."""
    ...

def athena_databases_list(catalog_name: str = "AwsDataCatalog") -> Dict[str, Any]:
    """Alias for athena_glue(action="databases_list", ...)."""
    return athena_glue(action="databases_list", catalog_name=catalog_name)
```

**Pros**:
- ✅ Backward compatible
- ✅ Gradual migration path

**Cons**:
- ❌ Doesn't reduce tool count (defeats the purpose)
- ❌ Duplicates code
- ❌ Confusing for users (two ways to do the same thing)

## Recommendation

**Adopt Option 1: Action-Based Dispatch** for the following reasons:

1. **Achieves Primary Goal**: Reduces tool count from 84 to 16
2. **Clear Organization**: Module-based grouping is intuitive
3. **Maintainable**: Simple dispatch pattern, easy to test
4. **Discoverable**: Action names listed in docstrings and error messages
5. **Extensible**: Easy to add new actions to existing modules

## Implementation Strategy

### Phase 1: Create Wrapper Functions

For each module, create a wrapper function that:
1. Accepts an `action` parameter
2. Validates the action against a known set
3. Dispatches to the appropriate implementation function
4. Provides helpful error messages

### Phase 2: Update Tool Registration

Modify `utils.py` to register only the wrapper functions:

```python
def register_tools(mcp: FastMCP, tool_modules: list[Any] | None = None) -> int:
    for module in tool_modules:
        # Look for module-level wrapper function (same name as module)
        wrapper_name = module.__name__.split(".")[-1]  # e.g., "athena_glue"
        if hasattr(module, wrapper_name):
            wrapper_func = getattr(module, wrapper_name)
            mcp.tool(wrapper_func)
```

### Phase 3: Migrate Tests

Update test files to use action-based calls:

**Before**:
```python
def test_athena_databases_list():
    result = athena_databases_list(catalog_name="AwsDataCatalog")
    assert result["success"] is True
```

**After**:
```python
def test_athena_databases_list():
    result = athena_glue(action="databases_list", catalog_name="AwsDataCatalog")
    assert result["success"] is True
```

### Phase 4: Documentation Updates

1. Update README.md with new usage patterns
2. Update tool docstrings to list all available actions
3. Create migration guide for MCP client developers
4. Add examples for each module's common use cases

## Async Tool Handling

**Challenge**: Some tools are async (governance, tabulator)

**Solution**: Module wrapper matches the async nature of its tools:

```python
# Sync module wrapper
def athena_glue(action: str, **kwargs) -> Dict[str, Any]:
    ...

# Async module wrapper
async def governance(action: str, **kwargs) -> Dict[str, Any]:
    actions = {
        "users_list": admin_users_list,  # async function
        "user_create": admin_user_create,  # async function
        ...
    }
    func = actions[action]
    return await func(**kwargs)
```

## Error Handling Strategy

1. **Unknown Action**: Return error with list of available actions
2. **Parameter Mismatch**: Return error with expected parameter names
3. **Business Logic Errors**: Pass through from underlying functions
4. **Type Validation**: Use TypedDict or Pydantic for action-specific parameters (future enhancement)

## Migration Impact Assessment

### For MCP Clients

**Breaking Change**: Yes, clients must update their tool calls

**Mitigation**:
1. Provide detailed migration guide
2. Show before/after examples for each module
3. Consider maintaining old tools as deprecated for one release cycle (if needed)

**Migration Effort**: Low to Medium
- Simple find-and-replace for tool names
- Add `action` parameter to existing calls

### For MCP Server

**Breaking Change**: No, internal implementation details

**Impact Areas**:
- Tool registration logic
- Test files
- Documentation

## Open Questions

1. **Q**: Should we provide a migration period with both old and new tools?
   **A**: Not recommended - it would defeat the purpose of reducing tool count. Better to make a clean break with good documentation.

2. **Q**: How do we handle parameter validation?
   **A**: Use `**kwargs` with try/except for TypeError. Future: add Pydantic models per action.

3. **Q**: Should action names include the module prefix?
   **A**: No - the tool name already provides the module context. Use `query_execute` not `athena_query_execute`.

4. **Q**: What about modules with only 1-2 tools?
   **A**: Still wrap them for consistency. Example: `s3_package(action="create_from_s3", ...)`.

5. **Q**: How do we document action-specific parameters?
   **A**: In the module wrapper's docstring, list each action with its parameters and examples.

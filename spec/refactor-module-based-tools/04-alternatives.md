# Module-Based Tools Refactoring - Alternative Approaches

## Summary of Approaches

This document explores alternative strategies for reducing tool count while maintaining or improving ergonomics.

## Alternative 1: Natural Language Action Names

Instead of structured action parameters, use natural language-style actions.

### Example

```python
def athena_glue(action: str, **kwargs) -> Dict[str, Any]:
    """
    Actions (natural language):
    - "list databases"
    - "execute query"
    - "get query history"
    - "validate query"
    - "show table schema"
    """
    # Normalize and match
    action_normalized = action.lower().strip()
    
    action_map = {
        "list databases": athena_databases_list,
        "list db": athena_databases_list,  # alias
        "execute query": athena_query_execute,
        "run query": athena_query_execute,  # alias
        # ... with fuzzy matching
    }
```

**Pros**:
- More intuitive for LLM-based clients (like Claude)
- Natural language is easier to remember
- Can support aliases and fuzzy matching

**Cons**:
- Less structured/predictable
- Harder to validate and document
- Potential ambiguity in action names
- More complex matching logic

**Verdict**: ❌ Not recommended - too loose for reliable automation

---

## Alternative 2: Hierarchical Tool Names

Use dot-notation in tool names to create hierarchy without wrapper functions.

### Example

```python
# Register tools with hierarchical names
mcp.tool(athena_databases_list, name="athena.databases.list")
mcp.tool(athena_query_execute, name="athena.query.execute")
mcp.tool(admin_users_list, name="governance.users.list")
```

**MCP Client Usage**:
```json
{
  "method": "tools/call",
  "params": {
    "name": "athena.databases.list",
    "arguments": {"catalog_name": "AwsDataCatalog"}
  }
}
```

**Pros**:
- ✅ No wrapper functions needed
- ✅ Clear hierarchical organization
- ✅ Maintains original function signatures
- ✅ Better type safety (no **kwargs)
- ✅ Easier testing (no dispatch layer)

**Cons**:
- ⚠️ Still 84 tools (but better organized)
- ⚠️ Requires MCP client support for dot-notation
- ⚠️ Namespace still polluted (just differently)

**Verdict**: ⚠️ Doesn't achieve primary goal of reducing tool count

---

## Alternative 3: Capability-Based Grouping

Group tools by capability/use-case rather than module.

### Example Groupings

```python
# Query-focused tool
def query(target: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Execute queries across different systems.
    
    Targets: athena, elasticsearch, graphql
    Actions: execute, validate, history
    """
    if target == "athena":
        if action == "execute":
            return athena_query_execute(**kwargs)
    # ...

# Admin-focused tool  
def admin(resource: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Administrative operations.
    
    Resources: users, roles, sso, tabulator
    Actions: list, create, update, delete, get
    """
    if resource == "users":
        if action == "list":
            return admin_users_list(**kwargs)
    # ...
```

**Pros**:
- ✅ Reduces tools even further (maybe 5-8 capability tools)
- ✅ Use-case driven organization
- ✅ Intuitive for user workflows

**Cons**:
- ❌ Breaks module boundaries
- ❌ Harder to maintain (cross-module dependencies)
- ❌ Loses semantic organization
- ❌ More complex dispatch logic (2D: resource + action)
- ❌ Unclear ownership of capabilities

**Verdict**: ❌ Not recommended - breaks good module boundaries

---

## Alternative 4: Parameter-Based Action (Method Overloading Style)

Use parameter presence to infer action instead of explicit action parameter.

### Example

```python
def athena_glue(
    query: str | None = None,
    catalog_name: str | None = None,
    database_name: str | None = None,
    table_name: str | None = None,
    workgroup: str | None = None,
    history: bool = False,
    validate: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Infer action from parameter combination:
    - query="SELECT..." → execute query
    - catalog_name="..." (only) → list databases
    - database_name + table_name → get table schema
    - history=True → get query history
    - validate=True + query="..." → validate query
    """
    if history:
        return athena_query_history(**kwargs)
    if validate and query:
        return athena_query_validate(query=query)
    if query:
        return athena_query_execute(query=query, database_name=database_name, **kwargs)
    if table_name and database_name:
        return athena_table_schema(database_name=database_name, table_name=table_name)
    if catalog_name:
        return athena_databases_list(catalog_name=catalog_name)
    # ...
```

**Pros**:
- ✅ No explicit action parameter
- ✅ More "magical" feeling
- ✅ Can feel natural for simple cases

**Cons**:
- ❌ Ambiguous parameter combinations
- ❌ Hidden logic - unclear what will execute
- ❌ Hard to document and discover
- ❌ Complex validation
- ❌ Error-prone for users
- ❌ Difficult to extend

**Verdict**: ❌ Not recommended - too implicit and error-prone

---

## Alternative 5: Sub-Tool Discovery Pattern

Create a meta-tool that lists available actions and their schemas.

### Example

```python
def athena_glue(action: str | None = None, **kwargs) -> Dict[str, Any]:
    """
    If action is None, return available actions with schemas.
    Otherwise, execute the action.
    """
    actions = {
        "databases_list": {
            "function": athena_databases_list,
            "params": {"catalog_name": "str"},
            "description": "List available databases",
        },
        # ... all actions with metadata
    }
    
    if action is None:
        # Discovery mode
        return {
            "success": True,
            "module": "athena_glue",
            "actions": [
                {
                    "name": name,
                    "description": meta["description"],
                    "parameters": meta["params"],
                }
                for name, meta in actions.items()
            ],
        }
    
    # Execute mode
    if action not in actions:
        return format_error_response(f"Unknown action: {action}")
    
    return actions[action]["function"](**kwargs)
```

**Usage**:
```python
# Discover actions
schema = athena_glue()
print(schema["actions"])  # List all available actions

# Execute action
result = athena_glue(action="databases_list", catalog_name="AwsDataCatalog")
```

**Pros**:
- ✅ Built-in action discovery
- ✅ Self-documenting
- ✅ Rich metadata for each action
- ✅ Clients can introspect capabilities

**Cons**:
- ⚠️ More complex implementation
- ⚠️ Adds discovery call overhead
- ⚠️ Duplicate metadata (docstrings + action metadata)

**Verdict**: ✅ Good enhancement - can be added to Option 1

---

## Alternative 6: Smart Defaults with Optional Action

Infer common actions from parameters but allow explicit override.

### Example

```python
def athena_glue(
    action: str | None = None,
    query: str | None = None,
    catalog_name: str | None = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Auto-detect action from parameters if not specified.
    
    Examples:
        # Explicit action
        athena_glue(action="databases_list", catalog_name="...")
        
        # Inferred action (query present → execute)
        athena_glue(query="SELECT * FROM table")
        
        # Inferred action (only catalog → list databases)
        athena_glue(catalog_name="AwsDataCatalog")
    """
    if action is None:
        # Smart inference
        if query:
            action = "query_execute"
        elif catalog_name and not kwargs:
            action = "databases_list"
        else:
            return format_error_response(
                "Cannot infer action from parameters. Please specify 'action' explicitly."
            )
    
    # Standard dispatch
    actions = {"query_execute": athena_query_execute, ...}
    return actions[action](query=query, catalog_name=catalog_name, **kwargs)
```

**Pros**:
- ✅ Best of both worlds (explicit and implicit)
- ✅ Power users can be concise
- ✅ New users have clear action parameter
- ✅ Backwards compatible with smart defaults

**Cons**:
- ⚠️ Inference logic can be tricky
- ⚠️ Potential for confusing behavior
- ⚠️ More complex to test

**Verdict**: ⚠️ Interesting but adds complexity - maybe for v2

---

## Alternative 7: Keep Tools Flat but Add Grouping Metadata

Don't change tool registration, just add metadata for organization.

### Example

```python
def athena_databases_list(catalog_name: str = "AwsDataCatalog") -> Dict[str, Any]:
    """
    List available databases in AWS Glue Data Catalog.
    
    Metadata:
        module: athena_glue
        category: discovery
        tags: [athena, glue, databases]
    """
    ...

# Registration includes metadata
mcp.tool(
    athena_databases_list,
    metadata={
        "module": "athena_glue",
        "category": "discovery",
        "tags": ["athena", "glue", "databases"],
    }
)
```

**Pros**:
- ✅ No breaking changes
- ✅ Better organization for discovery UIs
- ✅ Zero implementation risk

**Cons**:
- ❌ Doesn't reduce tool count (defeats the purpose)
- ❌ MCP clients need to support metadata filtering

**Verdict**: ❌ Doesn't solve the problem

---

## Recommendation Matrix

| Approach | Tool Reduction | Ergonomics | Risk | Implementation |
|----------|---------------|------------|------|----------------|
| **Option 1: Action-Based** | ✅ 84→16 | ⭐⭐⭐⭐ | 🟢 Low | Medium |
| Alt 1: Natural Language | ✅ 84→16 | ⭐⭐ | 🟡 Medium | High |
| Alt 2: Hierarchical Names | ❌ Still 84 | ⭐⭐⭐⭐⭐ | 🟢 Low | Low |
| Alt 3: Capability-Based | ✅ 84→8 | ⭐⭐ | 🔴 High | High |
| Alt 4: Parameter-Based | ✅ 84→16 | ⭐⭐ | 🔴 High | High |
| Alt 5: Sub-Tool Discovery | ✅ 84→16 | ⭐⭐⭐⭐ | 🟡 Medium | High |
| Alt 6: Smart Defaults | ✅ 84→16 | ⭐⭐⭐⭐ | 🟡 Medium | High |
| Alt 7: Metadata Only | ❌ Still 84 | ⭐⭐⭐⭐⭐ | 🟢 Low | Low |

## Final Recommendation

**Primary**: **Option 1: Action-Based Dispatch** (from analysis document)
- Achieves goal of 84→16 tools
- Clear, predictable interface
- Low implementation risk
- Good balance of ergonomics and simplicity

**Enhancement**: **Add Alt 5 (Sub-Tool Discovery)** as optional feature
- Make `action=None` return available actions
- Helps with tooling and documentation
- Can be added in Phase 2

### Enhanced Implementation

```python
def athena_glue(action: str | None = None, **kwargs) -> Dict[str, Any]:
    """
    AWS Athena and Glue Data Catalog operations.
    
    If action is None, returns available actions. Otherwise, executes the action.
    
    Available actions: databases_list, query_execute, query_history, ...
    """
    actions = {
        "databases_list": athena_databases_list,
        "query_execute": athena_query_execute,
        # ... all actions
    }
    
    # Discovery mode
    if action is None:
        return {
            "success": True,
            "module": "athena_glue",
            "actions": list(actions.keys()),
            "usage": "Call with action='<action_name>' to execute",
        }
    
    # Execution mode
    if action not in actions:
        return format_error_response(
            f"Unknown action '{action}'. Available: {', '.join(actions.keys())}"
        )
    
    try:
        return actions[action](**kwargs)
    except TypeError as e:
        return format_error_response(f"Invalid parameters for '{action}': {e}")
```

This combines the best aspects:
1. Reduces tool count (primary goal)
2. Self-documenting (call without action to discover)
3. Clear action-based interface
4. Simple to implement and test

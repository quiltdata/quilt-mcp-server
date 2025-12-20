# Analysis Document: get-resource Tool for Legacy MCP Clients

**Issue Reference**: GitHub Issue #233 - get-resource tool
**Branch**: `233-get-resource-tool`
**Status**: Current State Analysis

## References to Requirements

This analysis addresses the user stories and acceptance criteria from [01-requirements.md](./01-requirements.md):

- **US1**: Legacy MCP Client Compatibility - Need tool-based access to resource data
- **US2**: Resource URI Discovery - List all available resources programmatically
- **US3**: Consistent Data Access - Identical data structures between resources and tools
- **US4**: Template Resource Support - Handle parameterized resources with variables
- **US5**: Error Handling and User Guidance - Clear, actionable error messages

**Key Acceptance Criteria Being Analyzed**:

- AC1: Tool signature and parameter design
- AC2: Coverage of all 19 resource URIs
- AC3: Discovery mode implementation
- AC4: Data consistency between tool and resource implementations
- AC5: Template expansion mechanism
- AC6: Error response format
- AC7: Authentication passthrough
- AC10: Documentation requirements

## Current Codebase Architecture

### 1. Resource Implementation Pattern

#### 1.1 FastMCP Decorator-Based Resources

**Location**: `src/quilt_mcp/resources.py`

**Current Pattern**:

```python
def register_resources(mcp: "FastMCP") -> None:
    """Register all MCP resources with the FastMCP server."""

    @mcp.resource(
        "auth://status",
        name="Auth Status",
        description="Check authentication status and catalog configuration",
        mime_type="application/json",
    )
    async def auth_status_resource() -> str:
        """Check authentication status."""
        from quilt_mcp.services.auth_metadata import auth_status

        result = await asyncio.to_thread(auth_status)
        return _serialize_result(result)
```

**Key Observations**:

1. All resources are registered within a single `register_resources()` function
2. Resources use `@mcp.resource()` decorator with URI, name, description, and mime_type
3. Resources are async functions that return serialized JSON strings
4. Resources wrap service function calls with `asyncio.to_thread()` for sync functions
5. A helper `_serialize_result()` function handles Pydantic model serialization
6. Resources are registered in `create_configured_server()` via `register_resources(mcp)`

#### 1.2 Resource URI Patterns

**Current URI Schemes**:

- `auth://` - Authentication and configuration (3 resources)
- `athena://` - AWS Athena databases and queries (3 resources)
- `admin://` - Administrative operations (4 resources)
- `metadata://` - Package metadata templates (4 resources, 1 with template variable)
- `permissions://` - AWS permissions discovery (2 resources)
- `tabulator://` - Tabulator bucket listings (1 resource)
- `workflow://` - Workflow tracking (2 resources, 1 with template variable)

**Template Resources** (with URI variables):

1. `metadata://templates/{template}` - Parameterized by template name
2. `workflow://workflows/{workflow_id}/status` - Parameterized by workflow ID

**Total**: 19 resources (17 static + 2 templated)

#### 1.3 Resource Registration Flow

```
src/quilt_mcp/utils.py::create_configured_server()
    ↓
    if resource_config.RESOURCES_ENABLED:
        from quilt_mcp.resources import register_resources
        register_resources(mcp)
    ↓
    Resources registered with FastMCP server
```

**Configuration**: `src/quilt_mcp/config.py::ResourceConfig`

- `RESOURCES_ENABLED`: Default `true`
- `RESOURCE_CACHE_TTL`: 300 seconds (not currently used)
- `RESOURCE_CACHE_ENABLED`: Default `false`
- `RESOURCE_ACCESS_LOGGING`: Default `true`

### 2. Tool Implementation Pattern

#### 2.1 Tool Registration Mechanism

**Location**: `src/quilt_mcp/utils.py::register_tools()`

**Current Pattern**:

```python
def register_tools(mcp: FastMCP, tool_modules: list[Any] | None = None, verbose: bool = True) -> int:
    """Register all public functions from tool modules as MCP tools."""
    if tool_modules is None:
        tool_modules = get_tool_modules()

    # Exclusion lists
    RESOURCE_AVAILABLE_TOOLS = [...]  # Functions available as resources
    excluded_tools = {...}  # Deprecated or internal functions

    # Register public functions from each module
    for module in tool_modules:
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("_") and name not in excluded and name not in RESOURCE_AVAILABLE_TOOLS:
                mcp.tool(func)
```

**Module Registration**: `src/quilt_mcp/tools/__init__.py::_MODULE_PATHS`

```python
_MODULE_PATHS = {
    "package": "quilt_mcp.tools.catalog",
    "buckets": "quilt_mcp.tools.buckets",
    "packages": "quilt_mcp.tools.packages",
    "quilt_summary": "quilt_mcp.tools.quilt_summary",
    "search": "quilt_mcp.tools.search",
    "data_visualization": "quilt_mcp.tools.data_visualization",
    "athena_glue": "quilt_mcp.services.athena_read_service",
    "tabulator": "quilt_mcp.services.tabulator_service",
    "workflow_orchestration": "quilt_mcp.services.workflow_service",
    "governance": "quilt_mcp.services.governance_service",
    "permissions": "quilt_mcp.services.permissions_service",
}
```

**Key Observations**:

1. Tools are auto-discovered from module paths via introspection
2. Functions starting with `_` are automatically excluded
3. Functions in `RESOURCE_AVAILABLE_TOOLS` are explicitly excluded (already available as resources)
4. Tools use standard Python function signatures with Pydantic `Field` annotations
5. Both `tools/` modules and `services/` modules can provide tools
6. Tools are synchronous or async - FastMCP handles both

#### 2.2 Tool Response Patterns

**Location**: `src/quilt_mcp/models/responses.py`

**Standard Response Models**:

```python
class SuccessResponse(DictAccessibleModel):
    """Base model for successful operations."""
    success: Literal[True] = True

class ErrorResponse(DictAccessibleModel):
    """Base model for error responses."""
    success: Literal[False] = False
    error: str
    cause: Optional[str] = None
    possible_fixes: Optional[list[str]] = None
    suggested_actions: Optional[list[str]] = None
```

**Tool Response Union Types**:

- Tools return Union types like `BucketObjectsListResponse = BucketObjectsListSuccess | BucketObjectsListError`
- Response models inherit from `DictAccessibleModel` for backward compatibility
- Models use Pydantic for validation and serialization

### 3. Resource Discovery and Metadata

#### 3.1 MCP List Generation

**Location**: `scripts/mcp-list.py`

**Current Capabilities**:

- Introspects the MCP server to extract all tools and resources
- Generates `tests/fixtures/mcp-list.csv` with comprehensive metadata
- Extracts resources via `await server.get_resources()` and `await server.get_resource_templates()`
- Distinguishes between static resources and templated resources
- Captures URI patterns, names, descriptions, and template variables

**CSV Schema**:

```
type, module, function_name, signature, description, is_async, full_module_path
```

**Resource Entries** (from mcp-list.csv lines 54-73):

- All 19 resources are listed with `type="resource"`
- Template resources show `{variable}` in their URIs
- All marked as `is_async=True`
- All reference `module="resources"` and `full_module_path="quilt_mcp.resources"`

#### 3.2 FastMCP Resource Introspection

**Methods Available**:

1. `server.get_resources()` - Returns list of static Resource objects
2. `server.get_resource_templates()` - Returns list of ResourceTemplate objects
3. Each has `.uri`, `.name`, `.description` attributes
4. Templates have `.uri_template` with `{variable}` placeholders

### 4. Service Layer Architecture

#### 4.1 Service Function Patterns

**Locations**:

- `src/quilt_mcp/services/auth_metadata.py` - Authentication status functions
- `src/quilt_mcp/services/permissions_service.py` - AWS permissions discovery
- `src/quilt_mcp/services/governance_service.py` - Admin user/role management
- `src/quilt_mcp/services/athena_read_service.py` - Athena queries
- `src/quilt_mcp/services/metadata_service.py` - Package metadata templates
- `src/quilt_mcp/services/workflow_service.py` - Workflow tracking
- `src/quilt_mcp/services/tabulator_service.py` - Tabulator operations

**Service Function Characteristics**:

1. Mix of sync and async functions
2. Return structured dictionaries or Pydantic models
3. Some have Pydantic `Field` annotations (for tool registration)
4. Some lack annotations (designed for internal use only)
5. Error handling varies by service

**Resource-to-Service Mapping**:

- Each resource wrapper calls a corresponding service function
- Service functions contain the actual business logic
- Resources handle serialization and async wrapping

### 5. Authentication and Authorization

#### 5.1 Current Auth Flow

**Authentication Context**:

- Quilt login state tracked via `quilt3` library
- AWS credentials managed via boto3 sessions
- Bearer token support via `JwtAuthError` and `get_bearer_auth_service()`
- Runtime auth state managed in `quilt_mcp.runtime_context`

**Authorization Patterns** (from resources.py):

```python
# Admin resources handle unauthorized access
try:
    result = await admin_users_list()
    return _serialize_result(result)
except Exception as e:
    if "Unauthorized" in error_msg or "403" in error_msg:
        return _serialize_result({
            "error": "Unauthorized",
            "message": "This resource requires admin privileges...",
            "suggestion": "Contact your Quilt administrator..."
        })
```

**Key Observations**:

1. Resources implement try/catch for authorization errors
2. Admin resources provide helpful messages for privilege requirements
3. No centralized authorization checking for resources
4. Tools inherit authorization from service functions

### 6. Error Handling Patterns

#### 6.1 Resource Error Handling

**Current Approach**:

- Try/catch blocks around service function calls
- Special handling for admin/authorization errors
- Errors serialized to JSON with `_serialize_result()`
- No standardized error response format for resources

**Example** (from resources.py:132-147):

```python
try:
    result = await admin_users_list()
    return _serialize_result(result)
except Exception as e:
    error_msg = str(e)
    if "Unauthorized" in error_msg or "403" in error_msg:
        return _serialize_result({
            "error": "Unauthorized",
            "message": "This resource requires admin privileges...",
            "suggestion": "Contact your Quilt administrator..."
        })
    return _serialize_result({
        "error": "Failed to list users",
        "message": error_msg
    })
```

#### 6.2 Tool Error Handling

**Tool Response Pattern**:

- Tools return Union types: `SuccessResponse | ErrorResponse`
- `ErrorResponse` includes `error`, `cause`, `possible_fixes`, `suggested_actions`
- Pydantic validation errors handled by FastMCP
- Service-level errors propagated through response models

**Example** (from responses.py:48-56):

```python
class ErrorResponse(DictAccessibleModel):
    success: Literal[False] = False
    error: str
    cause: Optional[str] = None
    possible_fixes: Optional[list[str]] = None
    suggested_actions: Optional[list[str]] = None
```

### 7. Testing Infrastructure

#### 7.1 Resource Testing

**Location**: `tests/integration/test_resources.py`

**Current Coverage**:

- Tests server creation with resources registered
- Validates `register_resources()` doesn't raise errors
- No tests for individual resource data correctness
- No tests for template resource expansion

**Gap**: Resource content validation is not covered by existing tests

#### 7.2 MCP Test Framework

**Location**: `scripts/tests/mcp-test.yaml` (generated by mcp-list.py)

**Test Configuration**:

- YAML-based test definitions for all tools
- Environment variable configuration embedded
- Resource test cases with URI patterns and validation schemas
- Template variable substitution for parameterized resources
- Effect classification (none/create/update/remove) for safe testing

**Resource Test Structure**:

```yaml
test_resources:
  "auth://status":
    description: "Check authentication status and catalog configuration"
    effect: "none"  # Resources are read-only
    uri: "auth://status"
    uri_variables: {}
    expected_mime_type: "application/json"
    content_validation:
      type: "json"
      schema: {type: "object"}
```

## Current System Constraints and Limitations

### 1. Resource Protocol Support

**Constraint**: Legacy MCP clients (Claude Desktop, Cursor) do not support the resources protocol

- Resources are inaccessible in older clients
- No fallback mechanism exists
- Feature parity across clients is inconsistent

**Impact**: Users on legacy clients cannot access:

- Authentication status (`auth://status`)
- Permissions discovery (`permissions://discover`)
- Admin operations (`admin://users`, `admin://roles`)
- Configuration details (SSO, tabulator settings)
- Metadata templates and examples
- Workflow status tracking
- Query history

### 2. Resource Discovery

**Limitation**: No programmatic way to list available resources from tool context

- `mcp-list.csv` exists but requires file system access
- Resource introspection requires server-side access to FastMCP instance
- No MCP tool provides resource enumeration

**Impact**: Users must:

- Refer to external documentation
- Manually discover resources through trial and error
- Cannot build dynamic resource-based workflows

### 3. Template Resource Expansion

**Constraint**: Template resources require URI variables (e.g., `{template}`, `{workflow_id}`)

- Current resources: `metadata://templates/{template}`, `workflow://workflows/{workflow_id}/status`
- FastMCP handles template expansion internally
- No public API for template variable extraction or validation

**Complexity**: Tool must:

1. Detect template URIs from resource metadata
2. Parse URI patterns to extract variable names
3. Validate provided values against expected types
4. Expand templates before calling resource functions

### 4. Resource-to-Function Mapping

**Challenge**: Resources are registered via decorators, not direct function references

**Current Mapping** (from resources.py):

```
URI Pattern                                → Async Wrapper Function  → Service Function
"auth://status"                            → auth_status_resource()  → auth_status()
"metadata://templates/{template}"          → metadata_template()     → get_metadata_template(name=template)
"workflow://workflows/{workflow_id}/status" → workflow_status()       → workflow_get_status(id=workflow_id)
```

**Gap**: No programmatic registry mapping URIs to implementation functions

- Must maintain manual mapping in tool code
- Risk of drift between resource definitions and tool implementation
- Template parameter names may differ from function parameter names

### 5. Async vs Sync Function Handling

**Constraint**: Resources are all async, service functions are mixed

**Pattern** (from resources.py):

```python
# Sync service function wrapped with asyncio.to_thread
result = await asyncio.to_thread(auth_status)

# Async service function called directly
result = await admin_users_list()
```

**Implications for Tool**:

- Tool could be sync or async
- Must handle both sync and async service functions
- Cannot directly reuse resource wrapper code (all async)
- May need separate code paths for sync/async calls

### 6. Response Format Consistency

**Challenge**: Resources return serialized JSON strings, tools return Pydantic models

**Resources**:

```python
return _serialize_result(result)  # Returns JSON string
```

**Tools**:

```python
return BucketObjectsListSuccess(...)  # Returns Pydantic model instance
```

**Implication**: Tool must decide whether to:

1. Return raw service function results (Pydantic models/dicts)
2. Serialize to JSON strings (matching resource behavior)
3. Wrap in new response model (standard tool pattern)

### 7. Error Response Inconsistency

**Resource Errors**: Ad-hoc JSON dictionaries with varying fields

```python
{"error": "Unauthorized", "message": "...", "suggestion": "..."}
{"error": "Failed to list users", "message": "..."}
```

**Tool Errors**: Structured `ErrorResponse` models

```python
class ErrorResponse:
    success: Literal[False] = False
    error: str
    cause: Optional[str] = None
    possible_fixes: Optional[list[str]] = None
    suggested_actions: Optional[list[str]] = None
```

**Gap**: No unified error format across resources and tools

### 8. Authentication Passthrough

**Current State**: Resources inherit authentication from runtime context

- `quilt_mcp.runtime_context` manages auth state
- Service functions access credentials via global state
- No explicit auth parameter passing

**Implications**:

- Tool will automatically inherit same auth context
- No additional auth plumbing required
- BUT: Must ensure tool calls happen in same runtime context as resources

### 9. Performance Characteristics

**Resource Access**: Direct function call with minimal overhead

- Async wrapper adds slight overhead
- JSON serialization adds processing time
- No caching currently implemented (despite config flag)

**Tool Access**: Same underlying service functions

- Expected performance: Identical to resources
- Additional overhead: URI parsing, validation, dispatch logic
- **Constraint**: Must meet AC9 requirement (within same time bounds as resources, typically <2 seconds)

## Gaps Between Current State and Requirements

### Gap 1: No Tool-Based Resource Access (US1, AC1-2)

**Current State**: Resources only accessible via MCP resources protocol
**Required State**: Tool named `get_resource` accepting optional `uri` parameter
**Challenge**: Must map 19 different resource URIs to their implementation functions

### Gap 2: No Discovery Mode (US2, AC3)

**Current State**: No way to list resources programmatically from tool context
**Required State**: Calling `get_resource()` with no arguments returns list of all resources
**Challenge**: Must introspect FastMCP server or parse mcp-list.csv at runtime

### Gap 3: Template Resource Tool Access (US4, AC5)

**Current State**: Templates work in resource protocol, but no tool equivalent
**Required State**: Tool must parse and expand template URIs like `metadata://templates/standard`
**Challenge**: Template variable extraction, validation, and expansion logic needed

### Gap 4: Unified Error Format (US5, AC6)

**Current State**: Resources use ad-hoc error dictionaries, tools use `ErrorResponse`
**Required State**: Consistent error format with actionable guidance
**Challenge**: Deciding on single format that works for both contexts

### Gap 5: Resource Metadata Access (AC3)

**Current State**: Resource metadata (names, descriptions, templates) only available server-side
**Required State**: Tool must return structured metadata for all 19 resources
**Challenge**: Metadata must be embedded in tool or loaded from external source (mcp-list.csv)

### Gap 6: Data Consistency Validation (AC4)

**Current State**: No tests comparing resource data vs tool data
**Required State**: 100% data structure matching between resource and tool access
**Challenge**: Must test all 19 resources for exact parity

### Gap 7: Authorization Handling (AC8)

**Current State**: Resources have inconsistent authorization error handling
**Required State**: Tool must gracefully handle admin-only resources with clear guidance
**Challenge**: Deciding whether to:

1. Attempt call and catch authorization errors (current resource pattern)
2. Pre-check permissions and return early guidance
3. Mark admin resources in discovery mode

### Gap 8: Performance Validation (AC9)

**Current State**: No benchmarks for resource access time
**Required State**: Tool must complete within 10% of direct resource access (95th percentile)
**Challenge**: Must measure and optimize URI parsing/dispatch overhead

### Gap 9: Documentation Requirements (AC10)

**Current State**: Resources have basic descriptions, no comprehensive tool docs
**Required State**: Tool docstring with purpose, parameters, return values, URI list, examples
**Challenge**: Embedding 19 URIs in documentation without making it unwieldy

## Architectural Challenges and Design Considerations

### Challenge 1: URI-to-Function Dispatch

**Problem**: No direct mapping from URI string to resource implementation function

**Options**:

1. **Hard-coded dispatch table**: Manual mapping of URIs to functions
2. **Introspect FastMCP**: Query server for resource registry at runtime
3. **Parse mcp-list.csv**: Load resource metadata from generated file
4. **Decorator registry**: Create custom registry during resource registration

**Trade-offs**:

- Option 1: Simple, fast, but requires maintenance
- Option 2: Dynamic, accurate, but couples tool to server internals
- Option 3: External dependency, but leverages existing infrastructure
- Option 4: Requires refactoring resource registration

### Challenge 2: Template Parameter Extraction

**Problem**: Template URIs like `metadata://templates/{template}` need variable extraction

**Considerations**:

- Must parse URI to identify template variables
- Must match template pattern to determine which resource matches
- Must validate variable values before calling service function
- Must handle parameter name mismatches (URI `{template}` vs function `name`)

**Example Mapping**:

```
URI: "metadata://templates/standard"
Pattern: "metadata://templates/{template}"
Extracted: {"template": "standard"}
Function: get_metadata_template(name="standard")  # Note: parameter name differs!
```

### Challenge 3: Sync vs Async Implementation

**Problem**: Should `get_resource` be sync or async?

**Considerations**:

- Resources are all async (use `async def`)
- Service functions are mixed (some sync, some async)
- Legacy clients may have different async handling
- FastMCP supports both sync and async tools

**Implications**:

- If tool is async: Must `await` async service calls, use `asyncio.to_thread()` for sync
- If tool is sync: Must use `asyncio.run()` to call async service functions
- **Open Question from Requirements**: AC4 asks about this trade-off

### Challenge 4: Response Format Decision

**Problem**: Should tool return JSON strings (like resources) or Pydantic models (like tools)?

**Options**:

1. **JSON strings**: Matches resource behavior exactly, simpler comparison
2. **Pydantic models**: Standard tool pattern, better type safety
3. **Hybrid**: Discovery mode returns model, resource access returns JSON

**Trade-offs**:

- JSON strings: Harder for tools to parse programmatically
- Pydantic models: May not match resource JSON structure exactly
- Hybrid: Inconsistent return types, complex Union type

### Challenge 5: Error Response Strategy

**Problem**: Resources have ad-hoc errors, tools have structured `ErrorResponse`

**Options**:

1. **Use ErrorResponse**: Standardize on tool pattern
2. **Match resources**: Use ad-hoc dictionaries for consistency
3. **Convert errors**: Transform resource errors to tool format

**Considerations**:

- AC6 requires specific error response format with `error`, `message`, `details`, `valid_uris`
- Must provide actionable recovery suggestions
- Must distinguish authentication, authorization, and validation errors

### Challenge 6: Discovery Mode Design

**Problem**: How to return metadata for all 19 resources efficiently?

**Options**:

1. **Static embedded list**: Hard-code resource metadata in tool
2. **Load from mcp-list.csv**: Parse generated file at runtime
3. **Introspect FastMCP**: Query server dynamically
4. **Generate from decorators**: Build registry during registration

**Considerations**:

- Must include URI, name, description, template info
- Must indicate admin-only resources (AC3)
- Must be machine-readable JSON (AC3)
- Must stay synchronized with resource definitions

**Size Impact**: 19 resources × ~100 bytes metadata = ~2KB embedded data

### Challenge 7: Performance Optimization

**Problem**: Must minimize overhead to meet AC9 (<10% slower than direct resource access)

**Potential Bottlenecks**:

1. URI parsing and validation
2. Template pattern matching
3. Dispatch table lookup
4. JSON serialization/deserialization
5. Error handling logic

**Optimization Strategies**:

- Pre-compile regex patterns for template matching
- Use simple dict lookup for static URIs (O(1))
- Minimize string operations in hot path
- Cache resource metadata if discovery called multiple times

### Challenge 8: Maintenance and Drift Prevention

**Problem**: Tool must stay synchronized with resource definitions as they evolve

**Risks**:

1. New resources added but tool dispatch not updated
2. Resource URIs changed but tool patterns not updated
3. Service function signatures changed but tool calls not updated
4. Template parameters renamed but tool extraction not updated

**Mitigation Strategies**:

- Automated tests comparing tool vs resource output
- CI pipeline checking mcp-list.csv for changes
- Integration tests for all 19 resources
- Documentation generation from single source of truth

### Challenge 9: Testing Strategy

**Problem**: Must validate 100% data consistency (AC4) and all error paths (AC6)

**Test Requirements**:

1. Unit tests for URI parsing and template expansion
2. Integration tests for all 19 resources (static + template)
3. Comparison tests: resource output vs tool output
4. Error path tests: invalid URIs, missing auth, missing params
5. Performance tests: response time benchmarks
6. Discovery mode tests: metadata accuracy

**Test Data Needs**:

- Valid template variable values for parameterized resources
- Invalid URIs for error path testing
- Admin credentials for authorization testing (or mock setup)

### Challenge 10: Documentation Burden

**Problem**: AC10 requires comprehensive docstring with all URI examples

**Challenges**:

1. Listing all 19 URIs without overwhelming users
2. Explaining template syntax clearly
3. Providing usage examples for common cases
4. Documenting error codes and recovery steps

**Structure Considerations**:

- Brief one-line purpose statement
- Parameter descriptions with examples
- Return value documentation
- Separate section for URI listing (possibly collapsible)
- Error response documentation
- Usage examples (discovery + specific resource + template)

## Summary of Challenges

### High Priority Challenges

1. **URI-to-Function Dispatch** - Core requirement, multiple design options
2. **Template Parameter Extraction** - Complex parsing and validation logic required
3. **Data Consistency Validation** - Must ensure 100% parity with resources (AC4)
4. **Discovery Mode Implementation** - Must provide complete, accurate resource listing (AC3)
5. **Error Response Standardization** - Must unify divergent error formats (AC6)

### Medium Priority Challenges

6. **Performance Optimization** - Must minimize overhead to meet AC9
7. **Authentication Passthrough** - Must ensure correct auth context (AC7)
8. **Sync vs Async Decision** - Impacts implementation complexity (OQ4)
9. **Response Format Decision** - Affects type safety and consistency (OQ5)

### Low Priority Challenges

10. **Documentation Burden** - Important but can be addressed incrementally (AC10)
11. **Maintenance Strategy** - Mitigated by automated testing
12. **Caching Strategy** - Optional optimization (OQ2)

## Next Steps

This analysis provides the foundation for the specifications document (03-specifications.md), which will:

1. Define the desired end state for the `get_resource` tool
2. Specify URI dispatch mechanism design
3. Define template expansion algorithm
4. Specify response format and error handling
5. Establish discovery mode data structure
6. Define success criteria and quality gates
7. Identify integration points with existing systems

**No implementation details or code samples should be included in specifications** - those will be addressed in the design phase (05-phase1-design.md).

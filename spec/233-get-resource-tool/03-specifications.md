# Engineering Specifications: get-resource Tool for Legacy MCP Clients

**Issue Reference**: GitHub Issue #233 - get-resource tool
**Branch**: `233-get-resource-tool`
**Status**: Specifications

## References to Requirements and Analysis

This specification addresses the user stories and acceptance criteria from [01-requirements.md](./01-requirements.md):

- **US1**: Legacy MCP Client Compatibility (AC1-6)
- **US2**: Resource URI Discovery (AC3)
- **US3**: Consistent Data Access (AC4)
- **US4**: Template Resource Support (AC5)
- **US5**: Error Handling and User Guidance (AC6)

Building upon the current state analysis from [02-analysis.md](./02-analysis.md):

- Current resource implementation patterns (FastMCP decorator-based)
- Tool registration and response patterns
- Authentication and authorization flows
- Error handling strategies
- Testing infrastructure and validation approaches

## 1. Desired End State: System Overview

### 1.1 System Goal

The `get_resource` tool will provide a compatibility layer that exposes all MCP resource data through a tool interface, enabling legacy MCP clients (Claude Desktop, Cursor) to access resource data that would otherwise be unavailable to them.

**Key Characteristics**:

- **Zero Modification Required**: Resources remain unchanged; tool acts as an adapter layer
- **100% Coverage**: All 19 resource URIs accessible via the tool
- **Data Parity**: Tool returns identical data structures to resource protocol
- **Self-Documenting**: Discovery mode eliminates need for external documentation
- **Performance Transparent**: Tool overhead negligible (<10% additional latency)

### 1.2 Architectural Position

```
┌─────────────────────────────────────────────────────────────┐
│                        MCP Client                           │
│  ┌──────────────────────┐  ┌───────────────────────────┐  │
│  │ Modern Client        │  │ Legacy Client             │  │
│  │ (Claude Code)        │  │ (Claude Desktop, Cursor)  │  │
│  └──────────────────────┘  └───────────────────────────┘  │
└─────────────┬──────────────────────────┬──────────────────┘
              │                          │
              │ Resources Protocol       │ Tools Protocol
              │ (Native)                 │ (Compatibility Layer)
              │                          │
┌─────────────▼──────────────────────────▼──────────────────┐
│                   Quilt MCP Server                         │
│  ┌──────────────────────┐  ┌───────────────────────────┐  │
│  │ resources.py         │  │ get_resource tool         │  │
│  │ (Decorator-based)    │  │ (Adapter/Bridge)          │  │
│  └──────────────────────┘  └───────────────────────────┘  │
│              │                          │                  │
│              └──────────┬───────────────┘                  │
│                         │                                  │
│            ┌────────────▼────────────┐                     │
│            │   Service Functions     │                     │
│            │   (Business Logic)      │                     │
│            └─────────────────────────┘                     │
└────────────────────────────────────────────────────────────┘
```

**Design Principle**: The tool is a **bridge adapter** that maps tool calls to service function invocations, mirroring the exact same data paths that resources use.

## 2. Tool Interface Contract

### 2.1 Tool Signature Specification

**Function Name**: `get_resource`

**Parameter Specification**:

- `uri` (type: `Optional[str]`, default: `None`)
  - When `None` or empty string: Triggers **discovery mode**
  - When non-empty: Specifies the resource URI to access
  - Format: Standard MCP resource URI patterns (e.g., `auth://status`, `metadata://templates/standard`)

**Return Type Specification**:

- Union type: `GetResourceSuccess | GetResourceError`
- Both response models inherit from `DictAccessibleModel` for backward compatibility
- Success response contains resource data in structured format
- Error response follows standard tool error response pattern

### 2.2 Success Response Model Contract

```python
class GetResourceSuccess(SuccessResponse):
    """Successful resource access response."""

    success: Literal[True] = True
    uri: str  # The resolved URI (expanded if templated)
    resource_name: str  # Human-readable name of the resource
    data: dict[str, Any]  # The actual resource data
    timestamp: datetime  # When the data was retrieved
    mime_type: str = "application/json"  # Resource MIME type
```

**Success Response Guarantees**:

1. **Data Fidelity**: The `data` field contains exactly the same structure as the corresponding resource would return
2. **Metadata Completeness**: All metadata fields (`uri`, `resource_name`, `mime_type`) accurately reflect the resource definition
3. **Timestamp Accuracy**: The `timestamp` field reflects the actual time of data retrieval (not cached timestamps)

### 2.3 Error Response Model Contract

```python
class GetResourceError(ErrorResponse):
    """Failed resource access response."""

    success: Literal[False] = False
    error: str  # Error type classification
    message: str  # Human-readable error description
    details: Optional[str] = None  # Technical error details
    valid_uris: Optional[list[str]] = None  # Available URIs (for invalid URI errors)
    suggested_actions: Optional[list[str]] = None  # Recovery suggestions
```

**Error Response Guarantees**:

1. **Classification Accuracy**: The `error` field uses consistent error type strings
2. **Actionability**: Every error includes specific recovery suggestions in `suggested_actions`
3. **Context Completeness**: For invalid URI errors, `valid_uris` contains the complete list of available resources

### 2.4 Discovery Mode Response Contract

**Trigger**: When `uri` parameter is `None` or empty string

**Response Structure**:

```python
class GetResourceSuccess:
    success: Literal[True] = True
    uri: Literal[""] = ""  # Empty URI indicates discovery mode
    resource_name: str = "Available Resources"
    data: dict[str, list[ResourceMetadata]]  # Organized by category
    timestamp: datetime
    mime_type: str = "application/json"

class ResourceMetadata:
    """Metadata for a single resource."""
    uri: str  # Full URI pattern (with {variables} if templated)
    name: str  # Human-readable name
    description: str  # Functional description
    is_template: bool  # True if URI contains template variables
    template_variables: list[str]  # List of variable names (empty if not templated)
    requires_admin: bool  # True if admin privileges required
    category: str  # Resource category (auth, athena, admin, etc.)
```

**Discovery Mode Guarantees**:

1. **Completeness**: All 19 resources are included in discovery output
2. **Organization**: Resources are grouped by category for clarity
3. **Template Identification**: Template resources clearly marked with variable names listed
4. **Authorization Transparency**: Admin-only resources explicitly flagged

## 3. URI Dispatch Mechanism Specifications

### 3.1 URI Resolution Strategy

**Two-Phase Resolution**:

1. **Static URI Matching**: Direct lookup in URI-to-function registry (O(1) complexity)
   - Exact match against static resource URIs
   - Most common case, highest performance

2. **Template URI Matching**: Pattern-based matching with variable extraction
   - Applied only if static matching fails
   - Uses precompiled regex patterns for efficiency
   - Extracts template variables and validates against expected patterns

**Design Goal**: Minimize overhead for the 17 static resources (89% of cases) while supporting the 2 templated resources (11% of cases) efficiently.

### 3.2 URI-to-Function Registry Design

**Registry Structure**: Static mapping of URI patterns to service function references

**Registry Requirements**:

1. **Immutability**: Registry constructed at module initialization, not mutated at runtime
2. **Type Safety**: All function references properly typed with return type annotations
3. **Completeness**: All 19 resources represented in registry
4. **Maintainability**: Registry structure allows easy addition of new resources
5. **Introspectability**: Registry can be queried for discovery mode implementation

**Registry Schema**:

```python
class ResourceDefinition:
    """Definition of a single resource in the registry."""
    uri: str  # URI pattern (may contain {variables})
    name: str  # Human-readable name
    description: str  # Functional description
    service_function: Callable[..., Any]  # Function to call
    is_async: bool  # Whether service function is async
    is_template: bool  # Whether URI contains variables
    template_variables: list[str]  # Variable names (empty if not templated)
    requires_admin: bool  # Whether admin privileges required
    category: str  # Resource category
    parameter_mapping: dict[str, str]  # URI variable -> function parameter mapping
```

**Parameter Mapping Examples**:

- `metadata://templates/{template}` → `get_metadata_template(name=...)`
  - Mapping: `{"template": "name"}`
- `workflow://workflows/{workflow_id}/status` → `workflow_get_status(id=...)`
  - Mapping: `{"workflow_id": "id"}`

### 3.3 Template Variable Extraction Algorithm

**High-Level Algorithm**:

1. **Pattern Compilation**: At initialization, compile all template URIs into regex patterns
   - Convert `{variable}` syntax to named capture groups
   - Store compiled patterns for O(1) lookup

2. **Variable Extraction**: When template URI is requested
   - Apply regex pattern to extract variable values
   - Validate extracted values (non-empty, expected format)
   - Map variable names to function parameter names using registry

3. **Function Invocation**: Call service function with mapped parameters
   - Apply parameter mapping from registry
   - Pass extracted values as keyword arguments

**Validation Requirements**:

- **Non-Empty Check**: Template variables cannot be empty strings
- **Format Validation**: Variables must match expected character set (alphanumeric, hyphens, underscores)
- **Existence Validation**: For certain resources, validate that referenced entity exists (e.g., workflow ID)

**Error Cases**:

- Missing required template variable → Error with clear message
- Invalid variable format → Error with format requirements
- Non-existent entity reference → Error with "not found" guidance

## 4. Data Consistency Specifications

### 4.1 Data Parity Requirements

**Acceptance Criterion AC4 Compliance**: 100% data structure matching

**Parity Definition**:

1. **Structural Equivalence**: JSON serialization of tool response matches resource response exactly
2. **Type Preservation**: All data types preserved (strings, numbers, booleans, nested objects, arrays)
3. **Field Completeness**: All fields present in resource response also present in tool response
4. **Value Identity**: All field values identical between resource and tool responses

**Exclusions from Parity**:

- **Timestamp Metadata**: Tool may include additional timestamp field (not present in resources)
- **Response Wrapper**: Tool wraps data in success response model (resources return raw JSON strings)

### 4.2 Service Function Invocation Strategy

**Synchronous vs Asynchronous Handling**:

**Decision**: Tool will be implemented as **async function**

**Rationale**:

1. Matches resource implementation pattern (all resources are async)
2. Simplifies service function invocation (no need for `asyncio.run()`)
3. Compatible with FastMCP framework (supports both sync and async tools)
4. Enables future optimizations (parallel resource access, caching)

**Invocation Pattern**:

```python
# For async service functions (majority case)
result = await service_function(**params)

# For sync service functions (minority case)
result = await asyncio.to_thread(service_function, **params)
```

**Registry Requirement**: Each `ResourceDefinition` must include `is_async` flag to determine invocation strategy.

### 4.3 Serialization Strategy

**Resources Return**: JSON strings (via `_serialize_result()`)
**Tools Return**: Pydantic models (auto-serialized by FastMCP)

**Strategy**: Tool returns Pydantic model with resource data in `data` field

**Serialization Guarantees**:

1. **Pydantic Model Handling**: Service functions returning Pydantic models are serialized via `.model_dump()`
2. **Dict Handling**: Service functions returning dicts are passed through unchanged
3. **Datetime Handling**: Datetime objects serialized to ISO 8601 strings
4. **Nested Model Handling**: Nested Pydantic models recursively serialized

**Implementation Approach**: Reuse existing `_serialize_result()` logic from resources.py, but deserialize back to dict for inclusion in response model.

## 5. Authentication and Authorization Specifications

### 5.1 Authentication Passthrough Strategy

**Requirement AC7**: Tool must use the same authentication context as resources

**Implementation Goal**: **Zero Additional Auth Plumbing**

**Mechanism**:

- Service functions already access authentication state via `quilt_mcp.runtime_context`
- Tool inherits this context automatically (no explicit parameter passing needed)
- No changes to service function signatures required

**Authentication Flow**:

```
User authenticates → Runtime context updated → Service functions access context
                                                          ↓
                           ┌──────────────────────────────┴────────────────┐
                           │                                               │
                    Resource wrapper                               get_resource tool
                    calls service fn                               calls service fn
                           │                                               │
                           └───────────────┬───────────────────────────────┘
                                           │
                               Both get same auth context
```

**Guarantee**: If a resource call succeeds with current auth state, the equivalent tool call will succeed. If a resource call fails due to auth, the tool call will fail identically.

### 5.2 Authorization Handling Strategy

**Requirement AC8**: Graceful handling of admin-only resources with clear guidance

**Authorization Error Types**:

1. **Unauthenticated**: User not logged in to Quilt
2. **Unauthorized**: User logged in but lacks required privileges
3. **Forbidden**: Specific resource/operation denied by AWS IAM

**Handling Strategy**: **Attempt and Handle** (match resource pattern)

**Rationale**:

- Resources use try/catch around service calls
- Pre-checking permissions would require duplicating authorization logic
- Service functions already implement authorization checks
- Consistent error messages across resources and tools

**Error Response Structure** (for authorization failures):

```python
GetResourceError(
    error="Unauthorized",
    message="This resource requires admin privileges.",
    details="Resource '{uri}' is restricted to administrators.",
    suggested_actions=[
        "Contact your Quilt administrator to request access.",
        "Verify you are logged in with an admin account using 'auth://status'.",
        "Check available resources without admin requirements using get_resource()."
    ]
)
```

### 5.3 Admin Resource Marking

**Discovery Mode Requirement**: Admin-only resources must be flagged

**Admin Resources** (from registry):

- `admin://users`
- `admin://roles`
- `admin://config/sso`
- `admin://config/tabulator`

**Discovery Mode Field**: `requires_admin: bool` in `ResourceMetadata`

**Guarantee**: Discovery mode accurately identifies which resources require admin privileges before user attempts access.

## 6. Error Handling Specifications

### 6.1 Error Classification Taxonomy

**Error Categories** (exhaustive):

1. **Invalid URI** (`error="InvalidURI"`)
   - Provided URI does not match any resource pattern
   - URI format is malformed (missing scheme, invalid characters)

2. **Missing Template Variable** (`error="MissingTemplateVariable"`)
   - Template URI provided without required variable values
   - Example: `metadata://templates/` instead of `metadata://templates/standard`

3. **Invalid Template Variable** (`error="InvalidTemplateVariable"`)
   - Template variable value is invalid format
   - Example: `metadata://templates/{}`

4. **Unauthorized Access** (`error="Unauthorized"`)
   - Resource requires admin privileges user lacks
   - User not authenticated

5. **Resource Execution Error** (`error="ResourceExecutionError"`)
   - Service function raised an exception during execution
   - Underlying AWS service error

6. **Not Found** (`error="NotFound"`)
   - Template references non-existent entity
   - Example: `workflow://workflows/invalid-id/status`

**Error Response Requirements**:

- **Every error** must include at least one suggested action
- **Invalid URI errors** must include complete list of valid URIs
- **Template errors** must show correct template format with examples
- **Authorization errors** must explain privilege requirements and how to check current permissions
- **Execution errors** must distinguish transient (retry) vs permanent (fix config) failures

### 6.2 Error Response Specifications by Type

#### 6.2.1 Invalid URI Error

**When**: URI does not match any resource pattern

**Response Structure**:

```python
GetResourceError(
    error="InvalidURI",
    message=f"Resource URI '{uri}' not recognized.",
    details="The URI must match one of the available resource patterns.",
    valid_uris=[...],  # Complete list of 19 URIs
    suggested_actions=[
        "Call get_resource() with no arguments to see all available resources.",
        "Verify the URI scheme and path are correct.",
        "Check for typos in the URI."
    ]
)
```

#### 6.2.2 Missing Template Variable Error

**When**: Template URI provided without required variables

**Response Structure**:

```python
GetResourceError(
    error="MissingTemplateVariable",
    message=f"Template URI '{uri_pattern}' requires variable(s): {missing_vars}",
    details="Template URIs must include values for all variables.",
    suggested_actions=[
        f"Example: get_resource('metadata://templates/standard')",
        f"Valid variable values: {example_values}",
        "Call get_resource() to see all templates and their variables."
    ]
)
```

#### 6.2.3 Unauthorized Access Error

**When**: Admin-only resource accessed without privileges

**Response Structure**:

```python
GetResourceError(
    error="Unauthorized",
    message=f"Resource '{uri}' requires admin privileges.",
    details="This operation is restricted to Quilt administrators.",
    suggested_actions=[
        "Contact your Quilt administrator to request elevated access.",
        "Check your current permissions using get_resource('auth://status').",
        "Use get_resource() to see resources available to all users."
    ]
)
```

#### 6.2.4 Resource Execution Error

**When**: Service function raises exception

**Response Structure**:

```python
GetResourceError(
    error="ResourceExecutionError",
    message=f"Failed to retrieve resource '{uri}'.",
    details=str(original_exception),
    suggested_actions=[
        "Verify you have network connectivity to AWS services.",
        "Check authentication status using get_resource('auth://status').",
        "Retry the operation if this was a transient failure.",
        "Contact support if the problem persists."
    ]
)
```

### 6.3 Error Response Consistency

**Guarantee**: All error responses follow the same structure regardless of error type

**Field Guarantees**:

- `error`: Always present, always a clear error type string
- `message`: Always present, always human-readable
- `details`: Optional, provides technical details when available
- `suggested_actions`: Always present, always non-empty list
- `valid_uris`: Present only for invalid URI errors

**Testing Requirement**: Every error type must have dedicated test cases validating correct response structure and actionable suggestions.

## 7. Performance Specifications

### 7.1 Performance Requirements (AC9)

**Target**: Tool must complete within the same time bounds as direct resource access

**Quantitative Metrics**:

- **95th Percentile Response Time**: Within 10% of corresponding resource access
- **Typical Response Time**: <2 seconds for all resource types
- **Overhead Budget**: <100ms for URI parsing and dispatch logic
- **Discovery Mode**: <500ms for generating complete resource list

### 7.2 Performance Optimization Strategy

**Optimization Priorities**:

1. **Static URI Fast Path** (89% of cases)
   - O(1) dict lookup for static URIs
   - No regex evaluation required
   - Minimal string operations

2. **Template URI Optimization** (11% of cases)
   - Precompiled regex patterns (compiled at initialization)
   - Early termination on first pattern match
   - Lazy evaluation of template expansion

3. **Discovery Mode Caching**
   - Resource metadata list constructed once at initialization
   - Cached in module-level constant
   - No runtime computation for discovery calls

**Anti-Patterns to Avoid**:

- Dynamic regex compilation on each request
- Iterating through all resources for every URI match
- Redundant JSON serialization/deserialization
- Unnecessary copying of large data structures

### 7.3 Performance Monitoring Strategy

**Instrumentation Requirements**:

- Log response time for each tool invocation (at DEBUG level)
- Include URI and resource type in performance logs
- Track static vs template dispatch separately

**Performance Testing Requirements**:

- Benchmark suite comparing tool vs resource access times
- Test all 19 resources individually
- Test discovery mode performance
- Validate overhead stays within 10% budget

**Regression Prevention**:

- CI pipeline includes performance benchmark comparison
- Alert if any resource shows >15% slowdown vs baseline
- Automated tracking of 95th percentile response times

## 8. Testing and Validation Strategy

### 8.1 Test Coverage Requirements

**Unit Test Coverage**: Each test category must achieve 100% code path coverage

**Test Categories**:

1. **URI Dispatch Tests**
   - Static URI matching (17 resources)
   - Template URI matching (2 resources)
   - Invalid URI handling
   - Edge cases (empty string, malformed URIs, special characters)

2. **Data Consistency Tests** (Critical for AC4)
   - Compare tool output vs resource output for each of 19 resources
   - Validate JSON serialization equivalence
   - Test with various authentication states
   - Verify nested object handling

3. **Template Variable Tests**
   - Valid template expansion for all template resources
   - Missing variable detection
   - Invalid variable format detection
   - Parameter mapping validation

4. **Error Handling Tests**
   - Each error type (6 types) tested with representative cases
   - Verify error response structure completeness
   - Validate suggested actions are present and actionable
   - Test error responses match tool error pattern

5. **Discovery Mode Tests**
   - Verify all 19 resources present in output
   - Validate resource metadata accuracy
   - Check admin flag correctness
   - Confirm categorization accuracy

6. **Authentication/Authorization Tests**
   - Test with authenticated user
   - Test with unauthenticated user
   - Test admin resources with non-admin user
   - Test admin resources with admin user

7. **Performance Tests**
   - Benchmark each resource type
   - Compare tool vs resource response times
   - Validate overhead within budget
   - Test discovery mode performance

### 8.2 Integration Test Strategy

**Integration Test Requirements**:

1. **End-to-End Workflow Tests**
   - Simulate real user workflows (discovery → access → handle errors)
   - Test across multiple transport modes (stdio, HTTP, SSE)
   - Validate behavior in Claude Desktop and Cursor (when possible)

2. **Resource Parity Validation**
   - Automated comparison of tool vs resource output
   - Test with real service function calls (not mocks)
   - Validate with actual AWS resources when available
   - Test against current `mcp-list.csv` for completeness

3. **Error Path Testing**
   - Trigger all error conditions in realistic scenarios
   - Validate error recovery guidance is accurate
   - Test error message clarity with real users

### 8.3 Test Data and Fixtures

**Test Fixtures Required**:

1. **Mock Service Responses**: Representative data for each resource type
2. **Invalid URI Examples**: Comprehensive set of malformed URIs
3. **Template Variable Examples**: Valid and invalid values for each template
4. **Authentication States**: Fixtures for various auth scenarios
5. **Expected Error Messages**: Reference error responses for validation

**Test Data Sources**:

- `tests/fixtures/mcp-list.csv`: Source of truth for resource metadata
- Existing resource integration tests: Baseline for data consistency tests
- Real MCP server introspection: Validation of discovery mode accuracy

### 8.4 Quality Gates

**Pre-Merge Requirements** (all must pass):

1. **Unit Tests**: 100% pass rate, >95% code coverage
2. **Integration Tests**: 100% pass rate
3. **Data Consistency Tests**: 19/19 resources match resource output
4. **Performance Tests**: All benchmarks within 10% of baseline
5. **Lint and Type Checks**: No errors or warnings
6. **Documentation**: Complete docstring with examples

**CI/CD Validation**:

- All quality gates automated in CI pipeline
- Performance regression detection
- Resource coverage validation (alert if new resources added without tool support)

## 9. Documentation Specifications

### 9.1 Docstring Requirements (AC10)

**Required Sections**:

1. **Purpose Statement**
   - One-sentence description of tool function
   - Clear indication this is for legacy client compatibility
   - Brief explanation of relationship to resources protocol

2. **Parameter Documentation**
   - `uri` parameter: Format, examples, behavior when omitted
   - Template URI syntax explanation
   - Discovery mode trigger conditions

3. **Return Value Documentation**
   - Success response structure
   - Error response structure
   - Discovery mode response structure

4. **Resource URI Reference**
   - Complete list of 19 URIs organized by category
   - Template URIs with variable syntax clearly shown
   - Admin-only resources marked explicitly

5. **Usage Examples**
   - Discovery mode example
   - Static resource access example
   - Template resource access example
   - Error handling example

**Docstring Length Budget**: 100-150 lines (comprehensive but not overwhelming)

**Formatting Requirements**:

- Use reStructuredText formatting for PyCharm/VS Code compatibility
- Include type hints in signature (not just docstring)
- Use code blocks for examples
- Use bullet lists for URI reference

### 9.2 External Documentation Requirements

**README Update**:

- Add section explaining `get_resource` tool purpose
- Include comparison table: resources vs tool access
- Provide migration guide for legacy client users

**API Documentation**:

- Auto-generated from docstring via FastMCP
- Ensure examples render correctly in MCP client tools panel

**Troubleshooting Guide**:

- Common error scenarios and resolutions
- Link to resource documentation
- Explanation of authentication requirements

### 9.3 Example Documentation Requirements

**Minimum Example Set**:

1. **Discovery Mode**:

   ```python
   # List all available resources
   get_resource()
   ```

2. **Static Resource Access**:

   ```python
   # Get authentication status
   get_resource("auth://status")
   ```

3. **Template Resource Access**:

   ```python
   # Get specific metadata template
   get_resource("metadata://templates/standard")
   ```

4. **Error Handling**:

   ```python
   # Handle invalid URI gracefully
   result = get_resource("invalid://uri")
   if not result["success"]:
       print(result["suggested_actions"])
   ```

**Example Quality Standards**:

- All examples must be executable
- All examples must be tested in CI
- All examples must include expected output (as comments or docstring)

## 10. Integration Points and API Contracts

### 10.1 Integration with Existing Resource System

**Contract**: Tool implementation must NOT modify existing resource definitions

**Integration Strategy**: **Read-Only Dependency**

**Allowed**:

- Reading resource metadata via FastMCP introspection
- Calling service functions that resources call
- Reusing serialization utilities (`_serialize_result`)

**Prohibited**:

- Modifying resource decorator parameters
- Changing service function signatures
- Altering resource registration flow
- Adding dependencies to resources module

**Guarantee**: Resources remain independently functional and testable regardless of tool implementation.

### 10.2 Integration with Tool Registration System

**Contract**: Tool must register via standard tool registration mechanism

**Registration Requirements**:

- Tool module location: `src/quilt_mcp/tools/resource_access.py`
- Function decorated or auto-discovered via `get_tool_modules()`
- No special registration logic required
- Must NOT appear in `RESOURCE_AVAILABLE_TOOLS` exclusion list

**Module Structure**:

```
src/quilt_mcp/tools/
  resource_access.py  # New module for get_resource tool
    - get_resource() function
    - URI registry definitions
    - Response models (or import from responses.py)
```

### 10.3 Integration with MCP List Generation

**Contract**: Tool behavior must align with `mcp-list.csv` resource definitions

**Integration Requirements**:

- Discovery mode output should match resource metadata in `mcp-list.csv`
- Test suite should validate tool coverage against `mcp-list.csv`
- CI pipeline should detect drift between tool registry and MCP list

**Validation Strategy**:

- Parse `mcp-list.csv` in test suite
- Compare tool's discovery mode output against CSV data
- Alert if resource count or URIs differ

### 10.4 FastMCP Framework Compatibility

**Contract**: Tool must operate within FastMCP framework constraints

**Framework Requirements**:

- Compatible with FastMCP async execution model
- Uses standard FastMCP response serialization
- No framework-specific hacks or workarounds
- Compatible with all transport modes (stdio, HTTP, SSE)

**Testing Requirement**: Integration tests must validate tool behavior across transport modes.

## 11. Quality Assurance and Validation

### 11.1 Definition of Done

**Feature Completion Criteria**:

1. ✅ Tool accessible in all MCP client environments
2. ✅ All 19 resource URIs accessible via tool
3. ✅ Discovery mode returns complete resource list
4. ✅ Data consistency tests pass for all resources (100%)
5. ✅ All error types tested and validated
6. ✅ Performance benchmarks within 10% of baseline
7. ✅ Documentation complete with examples
8. ✅ All quality gates pass in CI
9. ✅ Manual testing in Claude Desktop successful
10. ✅ No regressions in existing resource functionality

### 11.2 Acceptance Testing Criteria

**User Acceptance Tests** (from requirements AC1-10):

1. **AC1 Compliance**: Tool named `get_resource`, accepts optional `uri` parameter ✓
2. **AC2 Compliance**: All 19 resources accessible and tested ✓
3. **AC3 Compliance**: Discovery mode returns structured list ✓
4. **AC4 Compliance**: Data consistency validated for all resources ✓
5. **AC5 Compliance**: Template expansion works for 2 template resources ✓
6. **AC6 Compliance**: Error responses follow standard format ✓
7. **AC7 Compliance**: Authentication passthrough validated ✓
8. **AC8 Compliance**: Authorization handling tested ✓
9. **AC9 Compliance**: Performance within 10% of baseline ✓
10. **AC10 Compliance**: Documentation complete and accurate ✓

**Manual Testing Checklist**:

- [ ] Test in Claude Desktop with `get_resource()` (discovery)
- [ ] Test in Claude Desktop with `get_resource("auth://status")` (static)
- [ ] Test in Claude Desktop with template resource
- [ ] Test error handling for invalid URI
- [ ] Verify suggested actions are clear and actionable
- [ ] Confirm tool appears in tools list
- [ ] Validate documentation is visible and clear

### 11.3 Success Metrics Validation

**Quantitative Metrics** (from requirements):

1. **Compatibility**: Works in 100% of tested legacy clients ✓
2. **Coverage**: 19/19 resources accessible (100%) ✓
3. **Consistency**: Data matches resources in 19/19 tests (100%) ✓
4. **Discovery**: Zero external lookups needed ✓
5. **Error Recovery**: 95%+ self-service resolution rate ✓
6. **Performance**: 95th percentile within 10% of baseline ✓

**Qualitative Metrics**:

- User feedback indicates tool is intuitive to use
- Documentation is sufficient for self-service usage
- Error messages successfully guide users to resolution

## 12. Risks and Mitigation Strategies

### 12.1 Technical Risks

**Risk 1: Resource-Tool Data Drift**

**Description**: Tool output diverges from resource output as resources evolve

**Likelihood**: Medium | **Impact**: High | **Priority**: High

**Mitigation**:

- Automated data consistency tests in CI (detect drift immediately)
- Registry validation against `mcp-list.csv` (detect missing resources)
- Test suite requires updating when resources change (forces awareness)
- Documentation specifies "read-only dependency" contract (sets expectations)

**Risk 2: Performance Degradation**

**Description**: Tool overhead exceeds 10% budget, violating AC9

**Likelihood**: Low | **Impact**: Medium | **Priority**: Medium

**Mitigation**:

- Performance benchmarks in CI (detect regressions)
- Static URI fast path optimization (minimize overhead for common case)
- Profiling during development (identify bottlenecks early)
- Performance budget enforcement (block merges that exceed threshold)

**Risk 3: Template Variable Mapping Errors**

**Description**: URI variables incorrectly mapped to function parameters

**Likelihood**: Low | **Impact**: High | **Priority**: High

**Mitigation**:

- Explicit parameter mapping in registry (document transforms)
- Dedicated tests for each template resource (validate mapping)
- Type hints in registry definition (catch errors at development time)
- Integration tests with real service calls (verify end-to-end behavior)

### 12.2 Maintenance Risks

**Risk 4: Registry Maintenance Burden**

**Description**: Manual registry requires updates when resources added/changed

**Likelihood**: Medium | **Impact**: Low | **Priority**: Low

**Mitigation**:

- Clear documentation on how to add new resources (reduce friction)
- CI validation catches missing resources (prevent silent failures)
- Centralized registry definition (single source of truth)
- Consider future automation (generate registry from resource definitions)

**Risk 5: Test Maintenance Overhead**

**Description**: Data consistency tests require updates for every resource change

**Likelihood**: Medium | **Impact**: Low | **Priority**: Low

**Mitigation**:

- Parameterized test design (reduce code duplication)
- Fixtures in external files (separate test data from test logic)
- Test generation from `mcp-list.csv` (automate test case creation)

### 12.3 Compatibility Risks

**Risk 6: Legacy Client Behavioral Differences**

**Description**: Claude Desktop and Cursor handle tools differently, causing unexpected behavior

**Likelihood**: Low | **Impact**: Medium | **Priority**: Medium

**Mitigation**:

- Manual testing in both legacy clients (validate actual behavior)
- Follow FastMCP best practices (minimize client-specific issues)
- Use standard response models (avoid client-specific serialization)
- Community feedback integration (learn from actual usage)

**Risk 7: FastMCP Framework Changes**

**Description**: FastMCP updates break tool implementation

**Likelihood**: Low | **Impact**: Medium | **Priority**: Low

**Mitigation**:

- Pin FastMCP version in dependencies (control upgrade timing)
- Monitor FastMCP release notes (stay informed of breaking changes)
- Comprehensive test suite (detect breakage quickly)
- Standard patterns only (avoid framework internals)

## 13. Future Extensibility Considerations

### 13.1 Future Enhancement Opportunities

**Potential Enhancements** (not in current scope):

1. **Batch Resource Access** (`get_resources` tool accepting multiple URIs)
   - Reduces network overhead for multiple resource requests
   - Complexity: Medium | Value: Medium

2. **Resource Caching** (leverage `ResourceConfig.RESOURCE_CACHE_ENABLED`)
   - Improves performance for frequently accessed resources
   - Complexity: Low | Value: Low (resources already fast)

3. **Resource Change Notifications** (subscribe to resource updates)
   - Enables reactive workflows
   - Complexity: High | Value: Low (niche use case)

4. **URI Fuzzy Matching** (suggest similar URIs for typos)
   - Improves error recovery UX
   - Complexity: Medium | Value: Low (error messages already good)

5. **Dynamic Registry Generation** (introspect resources at runtime)
   - Eliminates manual registry maintenance
   - Complexity: Medium | Value: Medium

### 13.2 Extensibility Design Principles

**Design for Future Extensions**:

1. **Registry Abstraction**: Current manual registry should be replaceable with dynamic generation
2. **Response Model Extensibility**: Success/error models should allow additional fields without breaking clients
3. **Dispatch Mechanism**: Should accommodate new URI schemes and pattern types
4. **Performance Monitoring**: Instrumentation should support adding new metrics without code changes

**Constraints for Future Work**:

- Must maintain backward compatibility with current tool interface
- Cannot break existing tools or resources
- Must preserve data consistency guarantees
- Performance must not degrade with new features

### 13.3 Deprecation Considerations

**Open Question from Requirements**: Should tool be marked as compatibility layer with potential future deprecation?

**Recommendation**: **Yes, document as compatibility layer**

**Rationale**:

- Sets correct expectations (temporary bridge, not primary API)
- Encourages legacy clients to upgrade to resource support
- Allows eventual removal when legacy clients updated
- Documents architectural decision for future maintainers

**Implementation**: Include deprecation timeline in documentation (e.g., "This tool provides compatibility with legacy MCP clients that lack resource protocol support. When all supported clients implement resources, this tool may be deprecated in favor of native resource access.")

## 14. Summary and Next Steps

### 14.1 Specifications Summary

This document specifies a `get_resource` tool that provides a compatibility layer for accessing MCP resource data via tool interface in legacy MCP clients.

**Key Specifications**:

- **Tool Interface**: `get_resource(uri: Optional[str]) → GetResourceSuccess | GetResourceError`
- **Coverage**: All 19 MCP resources accessible
- **Discovery Mode**: Complete resource listing when URI omitted
- **Data Consistency**: 100% parity with resource protocol
- **Performance**: <10% overhead vs direct resource access
- **Error Handling**: Comprehensive error classification with actionable guidance
- **Authentication**: Zero-config passthrough of existing auth context
- **Testing**: Rigorous data consistency and performance validation

**Success Criteria**:

- All 10 acceptance criteria from requirements met
- All 6 success metrics from requirements achieved
- All quality gates pass
- Manual testing in legacy clients successful

### 14.2 Technical Uncertainties Identified

**Uncertainties Requiring Design Decisions**:

1. **Registry Implementation Approach**: Static manual registry vs dynamic introspection vs CSV parsing
   - **Impact**: Maintainability and performance trade-offs
   - **Resolution Needed**: Design phase should evaluate options with prototypes

2. **Response Model Design**: Separate models vs reuse existing response models
   - **Impact**: Type safety and code organization
   - **Resolution Needed**: Design phase should review existing response model patterns

3. **Discovery Mode Data Source**: Embedded metadata vs runtime introspection vs CSV parsing
   - **Impact**: Code complexity and synchronization risk
   - **Resolution Needed**: Design phase should analyze maintenance burden

4. **Template Pattern Implementation**: Regex vs string matching vs dedicated parser
   - **Impact**: Performance and correctness guarantees
   - **Resolution Needed**: Design phase should benchmark alternatives

### 14.3 Dependencies on External Artifacts

**Required Inputs for Design Phase**:

1. **`mcp-list.csv`**: Source of truth for resource metadata
2. **`resources.py`**: Service function signatures and patterns
3. **`responses.py`**: Existing response model patterns
4. **FastMCP Documentation**: Framework capabilities and constraints

**Validation Artifacts**:

1. Existing resource integration tests (baseline for data consistency)
2. Performance benchmarks for resources (baseline for overhead budget)
3. Error message examples from resources (pattern for error responses)

### 14.4 Transition to Design Phase

**Design Phase Objectives** (04-phases.md):

- Break implementation into incremental phases
- Define deliverables and success criteria for each phase
- Identify dependencies between phases
- Plan "pre-factoring" opportunities

**Next Document**: `04-phases.md` will define implementation phases based on these specifications.

**Design Phase Constraints**:

- Cannot modify specifications (immutable after approval)
- Must implement all requirements from specifications
- Must achieve all success metrics defined here
- Must respect all architectural contracts

---

**Document Status**: ✅ Complete - Ready for Human Review

**Approval Gate**: Human review required before proceeding to phases breakdown (04-phases.md)

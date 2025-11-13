# Requirements Document: get-resource Tool for Legacy MCP Clients

**Issue Reference**: GitHub Issue #233 - get-resource tool
**Branch**: `233-get-resource-tool`
**Status**: Requirements Analysis

## Problem Statement

The Quilt MCP server currently exposes static lists and configuration data through MCP resources (e.g., `auth://status`, `athena://databases`, `admin://users`). This works well with modern MCP clients like Claude Code that support the resources protocol feature. However, older MCP clients such as Claude Desktop and Cursor do not support resources, preventing users on these platforms from accessing this valuable static data.

This creates a compatibility gap where:

1. Users on older MCP clients cannot access authentication status, permissions, or configuration data
2. Documentation and troubleshooting workflows assume resource availability
3. Feature parity across MCP client implementations is inconsistent
4. There is no fallback mechanism for clients without resource support

## User Stories

### US1: Legacy MCP Client Compatibility

**As a** user of Claude Desktop or Cursor
**I want** to access resource data through a tool interface
**So that** I can view authentication status, permissions, and configuration without upgrading my MCP client

**Acceptance Criteria:**

1. A new tool `get_resource` is available in all MCP client environments
2. The tool accepts a resource URI parameter (e.g., `auth://status`)
3. The tool returns the same data structure as the corresponding resource would
4. The tool works identically across all transport modes (stdio, HTTP, SSE)
5. Tool documentation clearly explains its purpose as a compatibility layer
6. Error messages guide users to valid resource URIs when an invalid URI is provided

### US2: Resource URI Discovery

**As a** user discovering available resources
**I want** to call `get_resource()` with no arguments
**So that** I can see all available resource URIs and their descriptions

**Acceptance Criteria:**

1. Calling `get_resource()` with no URI returns a list of all available resources
2. The list includes resource URIs, names, and descriptions
3. The list indicates which resources require authentication or admin privileges
4. The list matches the current resource definitions in `mcp-list.csv`
5. Response format is structured and machine-readable (JSON)
6. Resource URIs with templates (e.g., `metadata://templates/{template}`) are clearly marked

### US3: Consistent Data Access

**As a** developer building tools that work across MCP clients
**I want** `get_resource` to return identical data to the resource protocol
**So that** my code works consistently regardless of client capabilities

**Acceptance Criteria:**

1. Data returned by `get_resource("auth://status")` matches `auth://status` resource
2. Data returned by `get_resource("athena://databases")` matches `athena://databases` resource
3. All resource URIs defined in resources.py are accessible via the tool
4. Response format (JSON serialization) is identical to resource responses
5. Error handling matches resource error behavior
6. Performance characteristics are comparable to direct resource access

### US4: Template Resource Support

**As a** user working with parameterized resources
**I want** to pass template variables to `get_resource`
**So that** I can access resources like `metadata://templates/{template}` with specific values

**Acceptance Criteria:**

1. Template URIs (containing `{variable}`) are supported
2. Template variables can be passed as part of the URI string
3. Invalid template variable values return helpful error messages
4. Template expansion follows the same rules as MCP resource protocol
5. Documentation examples show both static and template resource usage
6. The resource list clearly indicates which URIs accept template variables

### US5: Error Handling and User Guidance

**As a** user encountering errors with `get_resource`
**I want** clear error messages with actionable guidance
**So that** I can quickly resolve issues and continue my workflow

**Acceptance Criteria:**

1. Invalid resource URIs return a list of valid URIs with descriptions
2. Authentication errors explain how to authenticate (refer to auth tools)
3. Authorization errors (admin-only resources) explain privilege requirements
4. Network/service errors distinguish between transient and persistent failures
5. Error messages include recovery suggestions appropriate to the error type
6. Error response format matches other tool error formats for consistency

## Numbered Acceptance Criteria

1. **Tool Signature**: The tool MUST be named `get_resource` and accept an optional `uri` parameter of type `str`

2. **Resource Coverage**: The tool MUST support all 19 resource URIs currently defined in the MCP server:
   - 4 auth resources (`auth://status`, `auth://catalog/info`, `auth://filesystem/status`)
   - 3 athena resources (`athena://databases`, `athena://workgroups`, `athena://query/history`)
   - 4 admin resources (`admin://users`, `admin://roles`, `admin://config/sso`, `admin://config/tabulator`)
   - 4 metadata resources (`metadata://templates`, `metadata://examples`, `metadata://troubleshooting`, `metadata://templates/{template}`)
   - 2 permissions resources (`permissions://discover`, `permissions://recommendations`)
   - 1 tabulator resource (`tabulator://buckets`)
   - 2 workflow resources (`workflow://workflows`, `workflow://workflows/{workflow_id}/status`)

3. **Discovery Mode**: When called with no arguments or empty string, the tool MUST return a structured list of all available resources with their URIs, names, descriptions, and template information

4. **Data Consistency**: The tool MUST return identical data structures to the corresponding resource implementations in `src/quilt_mcp/resources.py`

5. **Template Expansion**: The tool MUST support URI templates (e.g., `metadata://templates/standard`) by extracting and validating template variables

6. **Error Response Format**: Error responses MUST follow the standard tool error format with:
   - `error` field containing error type
   - `message` field with human-readable description
   - `details` field with actionable recovery suggestions
   - `valid_uris` field (when applicable) listing available resource URIs

7. **Authentication Passthrough**: The tool MUST use the same authentication context as resources, inheriting Quilt login state and AWS credentials

8. **Authorization Handling**: The tool MUST gracefully handle authorization failures for admin-only resources, providing clear guidance without failing catastrophically

9. **Performance Requirements**: The tool MUST complete within the same time bounds as direct resource access (typically <2 seconds)

10. **Documentation Requirements**: The tool MUST include comprehensive docstring with:
    - Purpose and use case explanation
    - Parameter descriptions with examples
    - Return value documentation
    - List of valid resource URIs in the description or examples
    - Clear indication that this is for legacy client compatibility

## Success Metrics

1. **Compatibility**: Successfully works in Claude Desktop and Cursor (100% of tested legacy clients)

2. **Coverage**: All 19 resource URIs accessible via the tool (100% resource coverage)

3. **Consistency**: Data returned by tool matches resource data in 100% of test cases

4. **Discovery**: Users can discover available resources without external documentation (0 external lookups needed)

5. **Error Recovery**: Users can resolve common errors using only the tool's error messages (95%+ self-service resolution)

6. **Performance**: 95th percentile response time within 10% of direct resource access time

## Open Questions

1. **URI Validation**: Should the tool validate URI format strictly (must match resource patterns) or permissively (try to match ignoring case/punctuation)?

2. **Caching Strategy**: Should resource data be cached when accessed via the tool, or should each call fetch fresh data?

3. **Deprecation Timeline**: Should this tool be marked as a compatibility layer with potential future deprecation when legacy clients are updated?

4. **Async vs Sync**: Should the tool implementation be async (matching most resources) or sync (simpler for legacy clients)?

5. **Response Format Extensions**: Should the tool response include metadata about the resource (e.g., timestamp, cache status, source) beyond the resource data itself?

6. **Batch Access**: Should there be a `get_resources` (plural) tool that accepts multiple URIs for efficient batch access?

7. **Resource Monitoring**: Should the tool track which resources are accessed most frequently to guide future optimization?

8. **URI Scheme Handling**: Should the tool support both scheme://path format and plain path format (e.g., both `auth://status` and `auth/status`)?

## Implementation Approach

The implementation will:

1. Create a new tool in an appropriate module (likely `src/quilt_mcp/tools/resources.py`)
2. Map resource URIs to their implementation functions in `src/quilt_mcp/resources.py`
3. Extract and parse template variables from URIs when present
4. Call the corresponding resource function and return its data
5. Provide a discovery mode that generates resource metadata from `mcp-list.csv` or introspects registered resources
6. Follow existing tool patterns for error handling, response formatting, and documentation
7. Add comprehensive tests covering all resource URIs and error cases

## Dependencies and Constraints

- **Resource Stability**: Implementation depends on stable resource function signatures in `resources.py`
- **CSV Synchronization**: Discovery mode relies on `tests/fixtures/mcp-list.csv` being current
- **FastMCP Compatibility**: Must work within FastMCP framework constraints
- **No Breaking Changes**: Cannot modify existing resource implementations
- **Transport Neutrality**: Must work across all transport modes without special handling
- **Backward Compatibility**: Future resource additions must be automatically accessible via this tool

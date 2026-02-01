# Requirements Document

## Introduction

The QuiltService abstraction layer in the Quilt MCP server requires a fundamental architectural redesign to support
multiple backends. The current implementation is "quilt3-shaped" - built as a wrapper around quilt3 primitives rather
than a proper abstraction layer. This architectural flaw prevents supporting alternative backends like Platform/GraphQL
for HTTP/JWT authentication mode, limiting the system's flexibility and scalability.

This redesign will transform the service from a quilt3 wrapper into a true domain-driven abstraction that can
seamlessly support both quilt3 library operations (stdio mode) and Platform GraphQL operations (HTTP mode) while
maintaining backward compatibility with existing tools.

## Glossary

- **QuiltService**: Current service implementation that wraps quilt3 library operations
- **QuiltOps**: New abstraction layer that provides backend-agnostic Quilt operations
- **Backend**: Implementation layer (quilt3 library or Platform GraphQL) that performs actual operations
- **Quilt3_Backend**: Backend implementation using the quilt3 Python library for stdio mode
- **Platform_Backend**: Backend implementation using Platform GraphQL API for HTTP mode
- **Quilt_Object**: Backend-agnostic data structure representing Quilt concepts (packages, buckets, etc.)
- **MCP_Tool**: Model Context Protocol tool that consumes the service interface
- **Authentication_Mode**: Either stdio (quilt3 sessions) or HTTP (JWT bearer tokens)
- **Package_Info**: Quilt package information independent of backend implementation
- **Content_Info**: Quilt content/file information independent of backend implementation

## Requirements

### Requirement 1: Domain-Driven Interface Design

**User Story:** As an MCP tool developer, I want to work with Quilt concepts rather than backend-specific types,
so that my tools remain functional regardless of the underlying backend implementation.

#### Acceptance Criteria

1. WHEN an MCP tool requests package search, THE QuiltOps SHALL return Package_Info objects independent of backend implementation
2. WHEN an MCP tool requests content browsing, THE QuiltOps SHALL return Content_Info objects that
   abstract away backend-specific URLs and identifiers
3. WHEN an MCP tool performs bucket operations, THE QuiltOps SHALL provide consistent bucket metadata
   regardless of whether data comes from quilt3 or Platform GraphQL
4. THE QuiltOps SHALL expose methods named after Quilt operations (search_packages, browse_content,
   list_buckets) rather than backend operations
5. THE QuiltOps SHALL never expose quilt3-specific types (Package instances, sessions) or Platform-specific
   types (GraphQL responses) in its public interface

### Requirement 2: Multi-Backend Architecture Support

**User Story:** As a system architect, I want the service to support both quilt3 library and Platform GraphQL
backends, so that users can authenticate and operate in either stdio or HTTP mode seamlessly.

#### Acceptance Criteria 1

1. WHEN the system detects quilt3 session credentials, THE QuiltOps SHALL route operations to the Quilt3_Backend
2. WHEN the system detects JWT bearer tokens, THE QuiltOps SHALL route operations to the Platform_Backend
3. WHEN both authentication modes are available, THE QuiltOps SHALL prioritize the most appropriate backend
   based on operation type and performance characteristics
4. THE QuiltOps SHALL provide identical functionality through both backends for all supported operations
5. WHEN a backend is unavailable or fails, THE QuiltOps SHALL provide clear error messages indicating the
   specific backend and failure reason

### Requirement 3: Authentication Integration and Routing

**User Story:** As a user, I want the system to automatically detect my authentication method and route operations
appropriately, so that I don't need to manually configure backend selection.

#### Acceptance Criteria 2

1. WHEN JWT bearer tokens are present, THE QuiltOps SHALL validate them and configure the Platform_Backend, OR error out if JWT is invalid
2. WHEN JWT is not present AND quilt3 session files are present, THE QuiltOps SHALL validate the session and configure the Quilt3_Backend, OR error out if session is invalid
3. WHEN neither JWT nor quilt3 session is present, THE QuiltOps SHALL error out with clear messages indicating required authentication methods
4. WHEN authentication validation fails, THE QuiltOps SHALL provide specific error messages indicating which authentication method failed and why
5. THE QuiltOps SHALL follow this priority order strictly: JWT first, then quilt3 session, then error

### Requirement 4: Backend Operation Equivalence

**User Story:** As an end user, I want identical functionality regardless of which backend is being used, so that my
workflows remain consistent across different authentication modes.

#### Acceptance Criteria 3

1. WHEN searching for packages, THE results SHALL contain equivalent metadata fields regardless of backend (name,
   description, tags, modified date)
2. WHEN browsing package contents, THE file listings SHALL provide equivalent information (paths, sizes, types)
   regardless of backend
3. WHEN accessing file contents, THE system SHALL provide equivalent download mechanisms regardless of backend
4. WHEN creating or modifying packages, THE operations SHALL have equivalent validation and error handling regardless
   of backend
5. WHEN listing buckets, THE metadata SHALL include equivalent access permissions and configuration details regardless
   of backend

### Requirement 5: Error Handling and Diagnostics

**User Story:** As a developer debugging integration issues, I want clear error messages that indicate which backend
failed and why, so that I can quickly resolve authentication and configuration problems.

#### Acceptance Criteria 4

1. WHEN a backend operation fails, THE QuiltOps SHALL include the backend type (quilt3 or Platform) in error
   messages
2. WHEN authentication fails, THE QuiltOps SHALL specify which authentication method was attempted and provide
   remediation steps
3. WHEN network operations fail, THE QuiltOps SHALL distinguish between connectivity issues and API errors
4. THE QuiltOps SHALL provide debug logging that traces operation routing decisions and backend selection logic
5. WHEN operations succeed on one backend but fail on another, THE QuiltOps SHALL log comparative information to
   aid in troubleshooting

### Requirement 6: Testing and Validation Framework

**User Story:** As a quality assurance engineer, I want comprehensive testing that validates backend equivalence,
so that I can ensure consistent behavior across all supported backends.

#### Acceptance Criteria 5

1. THE test suite SHALL include property-based tests that verify identical outputs from both backends for equivalent
   inputs
2. WHEN testing authentication scenarios, THE test suite SHALL validate both stdio and HTTP authentication flows
3. THE test suite SHALL include integration tests that exercise complete workflows through both backends
4. WHEN backends produce different results, THE test suite SHALL flag these as equivalence violations requiring
   investigation
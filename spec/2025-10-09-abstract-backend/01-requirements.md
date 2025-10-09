<!-- markdownlint-disable MD013 -->
# Requirements - Backend Abstraction Layer

**GitHub Issue**: TBD (to be created)
**Branch**: `2025-10-09-abstract-backend`
**Date**: 2025-10-09

## Problem Statement

The MCP server underwent a complete architectural transformation from quilt3 SDK-based implementation (v0.6.13) to a pure GraphQL/JWT-only architecture (commit ff37931). This transformation removed all abstraction layers and tightly coupled the codebase to a single backend implementation. Users now lack the flexibility to:

1. Choose between quilt3 SDK and GraphQL backends based on deployment environment
2. Support legacy systems that require quilt3 SDK functionality
3. Migrate gradually between backend implementations
4. Deploy in environments where GraphQL may not be available

The current architecture makes it impossible to switch backends without major refactoring of 75+ Python files that directly import GraphQL/JWT runtime components.

## User Stories

### Story 1: Environment-Based Backend Selection

**As a** deployment engineer
**I want** to select between quilt3 and GraphQL backends via environment variable
**So that** I can deploy the MCP server in different environments without code changes

**Acceptance Criteria**:
1. Server accepts `QUILT_BACKEND` environment variable with values: `graphql`, `quilt3`
2. Default backend is `graphql` (current production behavior)
3. Backend selection happens at server startup, not per-request
4. Invalid backend values result in clear error messages with available options
5. Backend selection is logged at startup for troubleshooting

### Story 2: Consistent API Across Backends

**As a** MCP tool developer
**I want** a unified interface for all catalog operations
**So that** I can write tools that work with any backend implementation

**Acceptance Criteria**:
1. All backends implement the same protocol interface
2. Method signatures are identical across backends
3. Return types are consistent and documented
4. Error handling follows the same patterns
5. No backend-specific imports in tool code

### Story 3: GraphQL Backend Preservation

**As a** production user
**I want** the current GraphQL/JWT implementation to remain unchanged
**So that** my existing deployments continue working without regression

**Acceptance Criteria**:
1. GraphQL backend behavior is identical to current implementation
2. Performance characteristics remain the same
3. JWT authentication flow is preserved
4. All existing tests pass without modification
5. No breaking changes to deployed systems

### Story 4: Quilt3 SDK Backend Support

**As a** legacy system operator
**I want** to use the quilt3 SDK backend
**So that** I can support environments without GraphQL infrastructure

**Acceptance Criteria**:
1. Quilt3 backend implements full protocol interface
2. Restores functionality from commit ff37931^ (before removal)
3. Supports quilt3 session-based authentication
4. Handles package operations identically to original implementation
5. Passes comprehensive test suite for SDK operations

### Story 5: Backend-Specific Test Isolation

**As a** quality assurance engineer
**I want** separate test suites for each backend
**So that** I can validate each implementation independently

**Acceptance Criteria**:
1. Test suites can run against specific backends
2. Common behavioral tests run against all backends
3. Backend-specific tests clearly marked and isolated
4. CI/CD pipeline tests both backends
5. Test failures clearly indicate which backend failed

### Story 6: Documentation and Migration Guide

**As a** developer
**I want** clear documentation on backend architecture and usage
**So that** I can understand, maintain, and extend the system

**Acceptance Criteria**:
1. Architecture documentation explains protocol pattern
2. Migration guide shows how to switch between backends
3. Developer guide for adding new backend implementations
4. Performance comparison between backends documented
5. Troubleshooting guide for common backend issues

## High-Level Implementation Approach

### Protocol-Based Architecture

Implement a Protocol (Python typing) that defines the contract for all backend implementations. This provides compile-time type checking without runtime overhead or multiple inheritance complexity.

### Factory Pattern

Use factory function (`get_backend()`) with environment-based selection to instantiate the appropriate backend. This centralizes backend selection logic and makes testing easier.

### Minimal Refactoring Strategy

Wrap existing GraphQL implementation into protocol class with minimal changes. Restore quilt3 implementation from git history (commit ff37931^) and adapt to protocol interface.

### Gradual Tool Migration

Refactor tools incrementally to use backend abstraction, starting with high-value/high-risk tools. Maintain backward compatibility during migration period.

## Success Criteria

1. **Functional**: Both backends pass comprehensive test suites covering all operations
2. **Performance**: GraphQL backend maintains current performance characteristics
3. **Compatibility**: Existing deployments work without configuration changes
4. **Flexibility**: Backend switch requires only environment variable change
5. **Maintainability**: New backend implementations require only protocol implementation
6. **Documentation**: Complete architecture and usage documentation available
7. **Testing**: 85%+ test coverage for all backend implementations
8. **Quality**: All linting, type checking, and quality gates pass

## Out of Scope

1. **Runtime backend switching**: Backend selection is at startup only, not per-request
2. **Backend mixing**: Single backend per server instance, no hybrid operations
3. **New backends**: Only GraphQL and quilt3 backends in initial implementation
4. **Performance optimization**: Focus on functional equivalence, not performance improvements
5. **API changes**: No changes to MCP tool interfaces or external APIs

## Open Questions

1. **Deployment Strategy**: How will production systems configure backend selection?
   - Via environment variables in deployment configs?
   - Via configuration files?
   - Via Claude Desktop settings?

2. **Testing Infrastructure**: Do we have sufficient test infrastructure for both backends?
   - Integration test environment with quilt3?
   - Separate CI/CD pipelines per backend?
   - Shared test fixtures across backends?

3. **Migration Timeline**: What is the urgency for quilt3 backend support?
   - Immediate need for production deployment?
   - Gradual migration over weeks/months?
   - Optional feature for future flexibility?

4. **Backward Compatibility Requirements**: What level of compatibility is required?
   - Must support existing quilt3-based workflows?
   - Can we require users to update configurations?
   - What is the deprecation policy for old patterns?

5. **Performance Requirements**: Are there specific performance targets?
   - Must GraphQL backend maintain exact current performance?
   - What is acceptable performance overhead for abstraction?
   - Are there latency or throughput requirements?

6. **Administrative Operations**: How should admin operations be handled?
   - Are quilt3 admin APIs available in GraphQL?
   - Should admin operations be backend-specific?
   - What is the fallback behavior if not supported?

## Dependencies

- **quilt3 SDK**: Must remain available as dependency
- **GraphQL Infrastructure**: Current JWT/GraphQL implementation
- **Test Infrastructure**: Ability to test both backends independently
- **Documentation**: Architecture documentation and migration guides

## Risks and Mitigation

### Risk 1: Breaking Existing Deployments

**Probability**: Medium
**Impact**: High
**Mitigation**: Default to GraphQL backend, comprehensive regression testing, gradual rollout

### Risk 2: Incomplete Protocol Coverage

**Probability**: Medium
**Impact**: High
**Mitigation**: Analyze all 75+ tool files for backend usage patterns, comprehensive interface design review

### Risk 3: Performance Degradation

**Probability**: Low
**Impact**: Medium
**Mitigation**: Benchmark current performance, compare protocol-wrapped implementation, optimize hotspots

### Risk 4: Maintenance Burden

**Probability**: High
**Impact**: Medium
**Mitigation**: Clear documentation, automated testing, minimize abstraction complexity

### Risk 5: Authentication Incompatibility

**Probability**: Medium
**Impact**: High
**Mitigation**: Careful analysis of JWT vs quilt3 auth patterns, adapter pattern for auth layer

## Acceptance Test Scenarios

### Scenario 1: GraphQL Backend Default Behavior

```bash
# Start server without QUILT_BACKEND variable
$ uv run quilt-mcp
# Server should:
# - Use GraphQL backend by default
# - Log "Using GraphQL backend"
# - Accept JWT tokens
# - All current functionality works
```

### Scenario 2: Explicit Backend Selection

```bash
# Start with quilt3 backend
$ QUILT_BACKEND=quilt3 uv run quilt-mcp
# Server should:
# - Use quilt3 backend
# - Log "Using quilt3 backend"
# - Use quilt3 session authentication
# - All package operations work
```

### Scenario 3: Invalid Backend Rejection

```bash
# Start with invalid backend
$ QUILT_BACKEND=invalid uv run quilt-mcp
# Server should:
# - Exit with clear error message
# - List available backends: graphql, quilt3
# - Provide example usage
# - Return non-zero exit code
```

### Scenario 4: Tool Backend Transparency

```python
# In any MCP tool
from quilt_mcp.backends import get_backend

backend = get_backend()
packages = backend.list_packages(registry="s3://my-bucket")
# Should work identically regardless of QUILT_BACKEND setting
```

### Scenario 5: Test Suite Backend Selection

```bash
# Run tests against GraphQL backend
$ QUILT_BACKEND=graphql make test

# Run tests against quilt3 backend
$ QUILT_BACKEND=quilt3 make test

# Both should pass with same assertions
```

## Appendix: Historical Context

### Version 0.6.13 (Sept 22, 2025)

- Had `QuiltService` class (688 lines) wrapping quilt3 SDK
- Used as abstraction layer for 84+ MCP tools
- Designed for "future backend flexibility"

### Commit ff37931 (GraphQL Migration)

- **Deleted** entire `QuiltService` abstraction (688 lines removed)
- Migrated to pure GraphQL/JWT-only architecture
- Removed all quilt3 imports across codebase
- 80+ insertions, 760+ deletions in services layer

### Commit 32fcd6c (Stateless Runtime)

- Adopted stateless runtime and catalog clients
- Created `clients/` module with catalog client
- Added bearer auth service for JWT
- Comprehensive refactoring: 3,898 additions, 4,994 deletions

### Current State (impl/remote-mcp-deployment)

- Pure GraphQL implementation
- No abstraction layer exists
- 75+ tool files directly import GraphQL/JWT runtime
- Search module has `SearchBackend` protocol pattern (proven concept)

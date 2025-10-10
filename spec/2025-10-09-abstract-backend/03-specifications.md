<!-- markdownlint-disable MD013 -->
# Specifications - Backend Abstraction for Branch Merge Strategy

**Requirements**: [01-requirements.md](./01-requirements.md)
**Analysis**: [02-analysis.md](./02-analysis.md)
**Date**: 2025-10-09

## Executive Summary

This document specifies the desired end state for backend abstraction in the quilt-mcp-server codebase. The abstraction enables flexible backend implementations (quilt3 SDK, GraphQL) without requiring tool refactoring, establishes a clean merge path for divergent branches, and positions the codebase for future architectural evolution.

**Key Insight from Analysis**: Both `main` and `impl/remote-mcp-deployment` branches use quilt3 SDK consistently. This means we are **enhancing an existing abstraction**, not resurrecting deleted code. The search module already demonstrates the protocol pattern we need.

## Goals and Objectives

### Primary Goals

1. **Enable Clean Branch Merge**: Merge `impl/remote-mcp-deployment` (Docker, Terraform, multi-transport) into `main` (admin operations) without functionality loss or conflicts

2. **Backend Flexibility**: Support multiple backend implementations (quilt3, GraphQL) through protocol-based abstraction without tool refactoring

3. **Preserve All Functionality**: Union of capabilities from both branches - no feature regression

4. **Maintain Merge-Friendly Architecture**: Future branch merges require minimal conflict resolution

### Secondary Goals

1. **Zero Performance Degradation**: Backend abstraction adds negligible overhead (<5%)

2. **Backward Compatibility**: v0.8.0 remains compatible with v0.7.x configurations

3. **Clear Migration Path**: Documentation enables future GraphQL backend implementation

4. **Operational Transparency**: Backend selection visible in logs for troubleshooting

## Architectural Specifications

### 1. Backend Protocol Definition

#### QuiltBackend Protocol

A Python `Protocol` class that defines the complete contract for backend implementations:

**Interface Categories**:

1. **Authentication & Configuration**
   - Authentication status checking
   - Catalog information retrieval
   - Session management

2. **Package Operations**
   - Package listing and browsing
   - Package creation and deletion
   - Package revision management
   - Package metadata operations

3. **Bucket Operations**
   - Bucket creation and management
   - Object listing and manipulation
   - S3 operations integration

4. **Search Operations**
   - Search API access
   - Backend-specific search capabilities
   - Elasticsearch/GraphQL query routing

5. **Admin Operations** (conditional availability)
   - User management
   - Role administration
   - SSO configuration
   - Tabulator administration

**Design Principles**:

- **Structural subtyping** via Protocol (not inheritance)
- **Minimal surface area** - only essential operations
- **Backend-agnostic** - no quilt3-specific assumptions
- **Future-extensible** - can add operations without breaking existing implementations
- **Optional capabilities** - admin operations discoverable at runtime

#### Success Criteria

- ✅ Protocol covers 100% of current QuiltService public interface
- ✅ Protocol enables both quilt3 and GraphQL implementations
- ✅ No implementation-specific details leak into protocol
- ✅ Static type checkers (mypy, pyright) validate protocol compliance
- ✅ Protocol documented with clear semantic contracts

### 2. Quilt3Backend Implementation

#### Wrapper Architecture

A concrete implementation that wraps the existing QuiltService:

**Implementation Strategy**:

```python
# Signature only - implementation in later phases
class Quilt3Backend:
    """Backend implementation using quilt3 SDK."""

    def __init__(self):
        # Delegates to existing QuiltService
        ...

    # All protocol methods delegate to QuiltService
    ...
```

**Design Constraints**:

- **Thin delegation layer** - no business logic in wrapper
- **No performance overhead** - direct pass-through to QuiltService
- **100% functionality preservation** - all QuiltService capabilities exposed
- **Admin operations included** - conditional availability based on credentials
- **Backward compatible** - existing tests pass without modification

#### Success Criteria

- ✅ All existing tests pass with Quilt3Backend
- ✅ No measurable performance degradation (<5% overhead)
- ✅ Zero functionality loss from current QuiltService
- ✅ Admin operations work identically through wrapper
- ✅ Protocol compliance validated by type checkers

### 3. Backend Factory Pattern

#### Factory Function Design

Environment-based backend selection mechanism:

**Interface Specification**:

```python
# Signature only - implementation in later phases
def get_backend() -> QuiltBackend:
    """
    Return appropriate backend based on environment configuration.

    Configuration:
        QUILT_BACKEND: Backend type selection
            - "quilt3" (default): Use quilt3 SDK backend
            - "graphql": Use GraphQL-only backend (future)

    Returns:
        Backend instance implementing QuiltBackend protocol

    Raises:
        ValueError: Unknown backend type
        ConfigurationError: Backend unavailable
    """
    ...
```

**Configuration Specification**:

- **Default behavior**: Returns Quilt3Backend when no env var set
- **Explicit selection**: `QUILT_BACKEND=quilt3` or `QUILT_BACKEND=graphql`
- **Logging**: Backend selection logged at INFO level on startup
- **Error handling**: Clear error messages for invalid/unavailable backends
- **Singleton behavior**: Factory may cache backend instance for performance

#### Success Criteria

- ✅ Default behavior returns Quilt3Backend
- ✅ Environment variable successfully controls backend selection
- ✅ Backend selection logged clearly for troubleshooting
- ✅ Invalid backend types produce actionable error messages
- ✅ Factory performance negligible (<1ms per call)

### 4. Tool Migration Pattern

#### Current State

Tools currently import and use QuiltService directly:

```python
# Current pattern across 20 tool files
from quilt_mcp.services.quilt_service import QuiltService

def some_tool_function():
    service = QuiltService()
    packages = service.list_packages(registry="s3://bucket")
```

#### Desired End State

Tools use backend abstraction via factory:

```python
# Target pattern for all tools
from quilt_mcp.backends import get_backend

def some_tool_function():
    backend = get_backend()
    packages = backend.list_packages(registry="s3://bucket")
```

**Migration Strategy**:

- **Incremental migration** - tools updated one at a time
- **No behavioral changes** - tool functionality remains identical
- **Backward compatible** - unmigrated tools continue working during migration
- **Testing coverage maintained** - each tool migration validated by existing tests

#### Success Criteria

- ✅ All 20 tool files migrated to use get_backend()
- ✅ No direct QuiltService imports remain in tool files
- ✅ All tool tests pass after migration
- ✅ Tool functionality unchanged (validated by integration tests)
- ✅ Migration pattern documented for future tool additions

### 5. Feature Integration Specifications

#### Admin Operations (from main v0.7.0)

**Operations to Preserve**:

1. User Management (10 methods)
   - User creation, deletion, retrieval
   - User status management (active/inactive, admin)
   - Email updates
   - Password resets

2. Role Management (4 methods)
   - Role listing
   - Role addition/removal from users
   - Role-based access control

3. SSO Configuration (3 methods)
   - SSO configuration get/set/remove
   - Authentication provider integration

4. Tabulator Administration (6 methods)
   - Table creation, deletion, listing
   - Open query status management
   - Tabulator configuration

**Integration Requirements**:

- ✅ All 27 admin methods integrated into merged QuiltService
- ✅ Admin operations accessible through Quilt3Backend
- ✅ Dynamic admin credential checking preserved
- ✅ Admin tool registration filtering maintained
- ✅ Existing admin tests pass without modification

#### Containerization Features (from impl/remote-mcp-deployment)

**Infrastructure to Preserve**:

1. Docker Support
   - Multi-stage Dockerfile with uv builds
   - ECR publishing automation
   - Container health checks
   - HTTP transport configuration

2. Terraform Modules
   - ECS service deployment
   - ALB integration and routing
   - CloudWatch logging setup
   - Security group configuration

3. Multi-Transport Support
   - stdio (default, MCPB compatible)
   - HTTP (container/remote deployment)
   - SSE (server-sent events streaming)
   - CORS middleware for browser clients

**Integration Requirements**:

- ✅ All Docker/Terraform files merged to main
- ✅ Multi-transport support functional on main
- ✅ Container deployment documentation included
- ✅ HTTP/SSE transports tested and validated
- ✅ CORS middleware working correctly

#### Version Management

**Target Version**: v0.8.0 on main branch

**Version Semantics**:
- Minor version bump (v0.7.x → v0.8.0)
- No breaking changes to public APIs
- Additive features only (backend abstraction, containerization)
- Backward compatible with v0.7.x configurations

**Success Criteria**:

- ✅ Version correctly tagged as v0.8.0 after merge
- ✅ CHANGELOG documents all changes from both branches
- ✅ Release notes explain backend abstraction and deployment features
- ✅ Migration guide provided for v0.7.x users (if needed)

### 6. Quality Gates and Validation

#### Test Coverage Requirements

**Minimum Coverage**: 85% overall, matching current standards

**Coverage Breakdown**:

1. **Backend Abstraction** (90%+ coverage)
   - Protocol definition (documentation coverage)
   - Quilt3Backend wrapper (100% method coverage)
   - Factory function (100% branch coverage)
   - Error handling paths

2. **Tool Migration** (maintain existing coverage)
   - Each migrated tool maintains current coverage
   - Integration tests validate backend switching
   - Backward compatibility tests

3. **Feature Integration** (maintain existing coverage)
   - Admin operations (existing tests from main)
   - Docker/deployment (existing tests from impl branch)
   - Multi-transport (existing transport tests)

**Success Criteria**:

- ✅ Overall coverage ≥85%
- ✅ No coverage regression in existing modules
- ✅ New backend module coverage ≥90%
- ✅ All backend switching paths covered

#### Performance Benchmarks

**Baseline Performance**: Current QuiltService operation latency

**Acceptable Overhead**:
- Backend factory call: <1ms
- Protocol dispatch: <5% overhead vs direct call
- Overall tool operation: <5% increase in latency

**Measurement Approach**:
- Benchmark common operations (list_packages, browse_package)
- Compare Quilt3Backend vs direct QuiltService
- Test with realistic package/bucket sizes

**Success Criteria**:

- ✅ Factory overhead <1ms measured
- ✅ Quilt3Backend operations within 5% of direct QuiltService
- ✅ No memory leaks in factory singleton
- ✅ Backend switching overhead negligible

#### Integration Testing

**Test Scenarios**:

1. **Backend Switching**
   - Default backend selection (no env var)
   - Explicit quilt3 backend selection
   - Invalid backend type error handling

2. **Tool Functionality**
   - All tools work with Quilt3Backend
   - Tool behavior identical to pre-migration
   - Error handling preserved

3. **Admin Operations**
   - Admin tools work through abstraction
   - Non-admin users excluded from admin tools
   - Admin credential checking works correctly

4. **Multi-Transport**
   - stdio transport works (MCPB compatibility)
   - HTTP transport works (container deployment)
   - SSE transport works (streaming responses)
   - CORS middleware functional

**Success Criteria**:

- ✅ All integration tests pass with Quilt3Backend
- ✅ Backend switching validated programmatically
- ✅ Multi-transport scenarios covered by tests
- ✅ Admin operations validated end-to-end

## Technical Constraints and Requirements

### 1. Language and Typing

**Python Version**: 3.11+ (maintain current requirement)

**Type Checking**:
- `Protocol` from `typing` module (structural subtyping)
- Full type hints on all backend interfaces
- mypy/pyright validation required
- No `Any` types in protocol definition

### 2. Dependency Management

**Core Dependencies**:
- `quilt3` SDK (existing, maintained)
- No new external dependencies for abstraction layer
- Protocol implementation uses standard library only

**Optional Dependencies**:
- GraphQL backend may add new dependencies (future work)
- All optional dependencies must be isolatable

### 3. Backward Compatibility

**API Compatibility**:
- All existing tool interfaces unchanged
- QuiltService remains importable (for legacy code)
- Configuration variables additive only
- No breaking changes to MCP tool contracts

**Deployment Compatibility**:
- v0.8.0 works with v0.7.x configuration files
- Environment variables optional (default behavior preserved)
- MCPB packages compatible with existing installations

### 4. Error Handling

**Error Categories**:

1. **Configuration Errors**
   - Invalid backend type specified
   - Backend unavailable for environment
   - Missing credentials

2. **Runtime Errors**
   - Backend operation failures
   - Network/connectivity issues
   - Authentication failures

**Error Handling Requirements**:

- ✅ Clear, actionable error messages
- ✅ Backend selection errors logged with guidance
- ✅ Errors include troubleshooting hints
- ✅ Error context preserved across abstraction layer

### 5. Logging and Observability

**Logging Requirements**:

1. **Startup Logging**
   - Backend selection logged at INFO level
   - Configuration source logged (env var/default)
   - Backend initialization status

2. **Operation Logging**
   - Backend operations logged at DEBUG level
   - Performance metrics for slow operations
   - Error details with full context

3. **Troubleshooting Support**
   - Backend type visible in all error messages
   - Request correlation IDs preserved
   - Session ID tracking maintained

**Success Criteria**:

- ✅ Backend selection always visible in logs
- ✅ Error messages include backend context
- ✅ Debug logging enables troubleshooting
- ✅ No PII/secrets in logs

## Integration Points and API Contracts

### 1. MCP Tool Integration

**Current Tool Interface**:
- Tools receive parsed arguments from FastMCP
- Tools return structured responses (dicts, lists)
- Errors raised as exceptions (FastMCP handles)

**Backend Abstraction Integration**:
- Tools call `get_backend()` to obtain backend instance
- Backend operations identical to current QuiltService
- Error handling unchanged (exceptions propagate)
- Return types unchanged (tool consumers unaffected)

**Contract Guarantees**:

- ✅ Tool signatures unchanged
- ✅ Tool return types unchanged
- ✅ Error semantics preserved
- ✅ No behavioral changes visible to tool consumers

### 2. Service Layer Integration

**QuiltService Role**:
- Remains the quilt3 SDK abstraction
- Used by Quilt3Backend wrapper
- May evolve independently of protocol

**Backend Protocol Role**:
- Defines contract for all backend implementations
- Enables multiple implementations
- No implementation coupling

**Integration Contract**:

- ✅ QuiltService implements protocol implicitly
- ✅ Quilt3Backend wraps QuiltService explicitly
- ✅ Protocol can evolve with versioning
- ✅ QuiltService maintains semantic versioning

### 3. Transport Layer Integration

**Transport Independence**:
- Backend abstraction orthogonal to transport layer
- stdio, HTTP, SSE all work with any backend
- CORS middleware unaffected by backend choice

**Session Management**:
- Session IDs preserved across backend boundary
- Authentication state managed per backend
- Transport-level session correlation maintained

**Success Criteria**:

- ✅ All transports work with Quilt3Backend
- ✅ Backend switching doesn't affect transport
- ✅ Session management works correctly
- ✅ CORS/authentication unaffected

### 4. Admin Operations Integration

**Admin Tool Contract**:
- Admin tools use same backend abstraction
- Admin capability discovery at runtime
- Non-admin users excluded from admin tools

**Dynamic Admin Detection**:
- Backend exposes `is_admin_available()` method
- Admin tool registration conditioned on admin status
- Graceful degradation when admin unavailable

**Success Criteria**:

- ✅ Admin tools work through abstraction
- ✅ Admin detection works correctly
- ✅ Non-admin users properly excluded
- ✅ Admin operations fully functional

## Success Metrics and Validation

### Functional Success Metrics

1. **Feature Completeness**: 100% of features from both branches present in v0.8.0
2. **Test Pass Rate**: 100% of existing tests pass on merged branch
3. **Coverage Maintenance**: ≥85% coverage maintained through merge
4. **Backend Abstraction**: Quilt3Backend passes all QuiltService tests
5. **Tool Migration**: All 20 tools successfully use get_backend()

### Performance Success Metrics

1. **Factory Overhead**: <1ms per get_backend() call
2. **Protocol Dispatch**: <5% overhead vs direct method calls
3. **Memory Usage**: No memory leaks from factory singleton
4. **Integration Latency**: <5% increase in end-to-end tool operations

### Quality Success Metrics

1. **Type Safety**: 100% type check coverage (mypy/pyright)
2. **Linting**: All code passes ruff formatting and linting
3. **Documentation**: Complete API documentation for all public interfaces
4. **Error Messages**: All error paths have clear, actionable messages

### Strategic Success Metrics

1. **Merge Completion**: Clean merge of impl/remote-mcp-deployment into main
2. **Version Release**: v0.8.0 successfully tagged and released
3. **Backward Compatibility**: v0.7.x configurations work with v0.8.0
4. **Future-Proofing**: GraphQL backend can be added without tool refactoring

## Risks, Uncertainties, and Mitigation Strategies

### Technical Risks

#### 1. Protocol Coverage Incompleteness

**Risk**: Protocol doesn't cover all necessary operations

**Uncertainty**: Are there hidden dependencies in current QuiltService?

**Mitigation**:
- Comprehensive analysis of all tool imports
- Static analysis to find all QuiltService method calls
- Integration testing with real workflows
- Phased rollout with escape hatch to direct service

**Validation**: Static analysis confirms all QuiltService public methods covered by protocol

#### 2. Performance Degradation

**Risk**: Abstraction layer introduces unacceptable overhead

**Uncertainty**: What is the real-world performance impact?

**Mitigation**:
- Early performance benchmarking
- Profile critical paths before/after abstraction
- Optimize factory singleton behavior
- Consider direct delegation for hot paths

**Validation**: Benchmark suite confirms <5% overhead across operations

#### 3. Type System Limitations

**Risk**: Python Protocol doesn't provide sufficient typing guarantees

**Uncertainty**: Will static type checkers catch all interface violations?

**Mitigation**:
- Comprehensive type checking in CI/CD
- Runtime type validation in factory (if needed)
- Explicit protocol conformance tests
- Consider runtime_checkable if necessary

**Validation**: mypy/pyright pass with strict settings on all backend code

### Integration Risks

#### 4. Merge Conflict Resolution

**Risk**: Conflicts during merge result in feature loss

**Uncertainty**: Are there subtle semantic conflicts between branches?

**Mitigation**:
- Phased approach reduces conflict surface
- Cherry-pick admin operations carefully
- Comprehensive test suite catches regressions
- Manual validation of merged feature set

**Validation**: Feature inventory checklist confirms 100% functionality preserved

#### 5. Test Suite Compatibility

**Risk**: Existing tests assume direct QuiltService usage

**Uncertainty**: Do tests break when tools use abstraction?

**Mitigation**:
- Tests should be backend-agnostic
- Mock backend protocol, not concrete service
- Integration tests validate end-to-end behavior
- Gradual tool migration preserves test compatibility

**Validation**: All existing tests pass with Quilt3Backend

### Architectural Risks

#### 6. Premature Abstraction

**Risk**: Backend abstraction adds complexity without clear value

**Uncertainty**: Will GraphQL backend actually be implemented?

**Mitigation**:
- Protocol provides value even with single backend (testing, modularity)
- Abstraction enables branch merge regardless of GraphQL plans
- Thin wrapper minimizes complexity overhead
- Documentation clarifies use cases

**Validation**: v0.8.0 delivers value from abstraction (clean branch merge) even without GraphQL

#### 7. Authentication Complexity

**Risk**: Different backends require incompatible authentication

**Uncertainty**: Can protocol abstract over session vs JWT auth?

**Mitigation**:
- Protocol defines behavior, not mechanism
- Each backend handles auth internally
- Factory ensures backend properly initialized
- Session correlation preserved at transport layer

**Validation**: Auth works identically through Quilt3Backend as with direct QuiltService

### Operational Risks

#### 8. Configuration Complexity

**Risk**: Backend selection adds configuration burden

**Uncertainty**: Will users understand backend selection?

**Mitigation**:
- Sensible defaults (quilt3 backend automatic)
- Clear documentation of env var usage
- Verbose logging of backend selection
- Configuration validation at startup

**Validation**: Default behavior requires no configuration changes

#### 9. Backward Compatibility Break

**Risk**: v0.8.0 breaks existing deployments

**Uncertainty**: Are there edge cases that break compatibility?

**Mitigation**:
- Default behavior identical to v0.7.x
- All existing configurations work without changes
- Backward compatibility test suite
- Migration guide for any edge cases

**Validation**: v0.7.x configuration files work unchanged with v0.8.0

### Mitigation Success Criteria

For each risk category above:

- ✅ Mitigation strategy defined and documented
- ✅ Uncertainty quantified and addressed in design phase
- ✅ Validation approach specified with clear pass/fail criteria
- ✅ Rollback plan defined if mitigation fails

## Out of Scope

### Explicitly Excluded from v0.8.0

1. **GraphQL Backend Implementation**
   - Rationale: Optional future work, not required for branch merge
   - Can be added in v0.9.0 without disruption
   - Protocol design enables future implementation

2. **Breaking API Changes**
   - Rationale: Semantic versioning requires backward compatibility
   - Minor version bump (v0.7.x → v0.8.0)
   - All changes must be additive

3. **Performance Optimization**
   - Rationale: Focus on functional merge, not optimization
   - Acceptable overhead: <5%
   - Optimization opportunities identified for future work

4. **Alternative Backend Implementations**
   - Rationale: quilt3 and (future) GraphQL are sufficient
   - Protocol designed for extensibility if needed
   - No current requirement for additional backends

5. **Backward Compatibility Break**
   - Rationale: v0.8.0 must work with v0.7.x configurations
   - No configuration migration required
   - Existing deployments work without changes

## Documentation Requirements

### API Documentation

1. **Backend Protocol**
   - Complete docstrings for all protocol methods
   - Semantic contracts (preconditions, postconditions)
   - Error handling specifications
   - Example usage patterns

2. **Factory Function**
   - Configuration options documented
   - Environment variable semantics
   - Error cases and troubleshooting
   - Performance characteristics

3. **Migration Guide**
   - Tool migration pattern examples
   - Backend selection guide
   - Troubleshooting common issues
   - FAQ for developers

### Architecture Documentation

1. **Design Decisions**
   - Why protocol over inheritance
   - Factory pattern rationale
   - Performance tradeoff analysis
   - Future extensibility design

2. **Integration Patterns**
   - Tool → backend → service flow
   - Transport layer integration
   - Admin operations handling
   - Error propagation

3. **Testing Strategy**
   - Protocol conformance testing
   - Backend switching validation
   - Performance benchmarking approach
   - Integration test coverage

### Operational Documentation

1. **Deployment Guide**
   - Backend selection configuration
   - Logging and monitoring
   - Troubleshooting procedures
   - Performance tuning

2. **Migration Guide**
   - v0.7.x → v0.8.0 upgrade process
   - Configuration changes (if any)
   - Testing validation steps
   - Rollback procedures

## Next Steps

This specifications document establishes the desired end state and engineering constraints for backend abstraction. The next document (04-phases.md) will break down the implementation into incremental phases with clear deliverables and dependencies.

**Key Specifications Summary**:

1. ✅ Backend protocol abstracts over quilt3/GraphQL implementations
2. ✅ Quilt3Backend wraps existing QuiltService (thin delegation)
3. ✅ Factory function provides environment-based backend selection
4. ✅ All 20 tools migrate to use get_backend()
5. ✅ Admin operations and containerization features fully integrated
6. ✅ v0.8.0 on main includes union of capabilities from both branches
7. ✅ <5% performance overhead, ≥85% test coverage maintained
8. ✅ Backward compatible with v0.7.x configurations

**Success Gate for Phase Progression**: This document must be reviewed and approved before proceeding to 04-phases.md (phase breakdown planning).

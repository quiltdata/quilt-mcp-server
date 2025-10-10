<!-- markdownlint-disable MD013 -->
# Implementation Phases - Backend Abstraction

**Requirements**: [01-requirements.md](./01-requirements.md)
**Analysis**: [02-analysis.md](./02-analysis.md)
**Specifications**: [03-specifications.md](./03-specifications.md)
**Date**: 2025-10-09

## Executive Summary

This document breaks down the backend abstraction implementation into 4 incremental phases, each deliverable as an independent PR with clear success criteria. Each phase builds on the previous one, maintaining a working state throughout development and enabling early validation of the abstraction pattern.

**Key Principle**: Each phase delivers testable, working functionality that can be independently reviewed and merged. The phases follow a "make the change easy, then make the easy change" approach, establishing abstractions before migrating consumers.

## Phase Overview

### Phase 1: Backend Protocol and Foundation (3-4 days)
**Goal**: Establish backend abstraction layer without disrupting existing code

**Deliverables**:
- QuiltBackend protocol definition
- Quilt3Backend implementation (wrapping existing QuiltService)
- get_backend() factory with environment-based selection
- Basic backend selection tests
- Documentation of backend pattern

**Success Criteria**:
- ✅ Protocol covers 100% of QuiltService public interface
- ✅ Quilt3Backend passes all existing QuiltService tests
- ✅ Factory returns Quilt3Backend by default
- ✅ Backend selection works via QUILT_BACKEND env var
- ✅ No existing code changes required (additive only)

### Phase 2: Tool Migration - High-Value Tools (2-3 days)
**Goal**: Validate abstraction pattern with 5 representative tools

**Deliverables**:
- Migrate 5 high-value tools to use get_backend()
- Update tool tests for backend abstraction
- Validate performance overhead is acceptable
- Document tool migration pattern

**Tools Selected**:
1. `list_packages` - Core package listing
2. `browse_package` - Package content browsing
3. `create_package` - Package creation
4. `search_packages` - Search integration
5. `get_catalog_info` - Catalog information

**Success Criteria**:
- ✅ All 5 tools work identically through abstraction
- ✅ Tool tests pass without modification
- ✅ Performance overhead <5% measured
- ✅ Migration pattern validated and documented

### Phase 3: Complete Tool Migration (2-3 days)
**Goal**: Migrate all remaining tools to backend abstraction

**Deliverables**:
- Migrate remaining 15 tools to use get_backend()
- Remove all direct QuiltService imports from tools
- Update all tool tests for abstraction
- Validate end-to-end functionality

**Success Criteria**:
- ✅ All 20 tools use get_backend()
- ✅ No direct QuiltService imports in tool files
- ✅ 100% of tool tests pass
- ✅ Integration tests validate end-to-end workflows
- ✅ Coverage maintained ≥85%

### Phase 4: Admin Operations Integration (2-3 days)
**Goal**: Cherry-pick admin operations from main and integrate through abstraction

**Deliverables**:
- Cherry-pick admin operations from main branch
- Integrate admin methods into current QuiltService
- Extend QuiltBackend protocol with admin operations
- Update Quilt3Backend to expose admin operations
- Validate admin tools work through abstraction

**Success Criteria**:
- ✅ All 27 admin methods from main integrated
- ✅ Admin operations work through Quilt3Backend
- ✅ Admin tool registration filtering works
- ✅ Non-admin users properly excluded
- ✅ Admin tests pass

**Total Timeline**: 9-13 days

## Phase 1: Backend Protocol and Foundation

### Objectives

1. Define the backend abstraction contract
2. Wrap existing QuiltService in new abstraction
3. Create factory for backend selection
4. Validate pattern without disrupting existing code

### Detailed Work Items

#### 1.1 Create Backend Protocol Definition

**File**: `src/quilt_mcp/backends/protocol.py`

**Requirements**:
- Define QuiltBackend Protocol class
- Cover all QuiltService public methods
- Use structural typing (Protocol, not inheritance)
- Full type hints with no Any types
- Complete docstrings for all methods

**Method Categories**:

1. **Authentication & Configuration** (5 methods)
   - `is_authenticated() -> bool`
   - `get_catalog_info() -> Dict[str, Any]`
   - `get_session() -> Any`
   - `get_registry_url(bucket: str) -> str`
   - `verify_connection() -> bool`

2. **Package Operations** (15 methods)
   - `list_packages(registry: str) -> Iterator[str]`
   - `browse_package(package_name: str, registry: str, ...) -> Any`
   - `create_package_revision(...) -> Dict[str, Any]`
   - `delete_package(package_name: str, registry: str) -> None`
   - `get_package_versions(...) -> List[str]`
   - `get_package_metadata(...) -> Dict[str, Any]`
   - `set_package_metadata(...) -> None`
   - `install_package(...) -> None`
   - `push_package(...) -> None`
   - `fetch_package(...) -> Any`
   - Additional package operations from QuiltService

3. **Bucket Operations** (8 methods)
   - `create_bucket(bucket_uri: str) -> Any`
   - `list_buckets() -> List[str]`
   - `list_objects(bucket: str, prefix: str) -> Iterator[Dict[str, Any]]`
   - `get_object(bucket: str, key: str) -> bytes`
   - `put_object(bucket: str, key: str, data: bytes) -> None`
   - `delete_object(bucket: str, key: str) -> None`
   - Additional S3 operations

4. **Search Operations** (3 methods)
   - `get_search_api() -> Any`
   - `search_packages(query: str, ...) -> List[Dict[str, Any]]`
   - `get_search_backend_type() -> str`

5. **Admin Operations** (optional - added in Phase 4)
   - `is_admin_available() -> bool`
   - User management methods
   - Role management methods
   - SSO configuration methods
   - Tabulator administration methods

**Success Criteria**:
- ✅ Protocol compiles and type checks pass (mypy/pyright)
- ✅ All QuiltService public methods covered
- ✅ Documentation complete with semantic contracts
- ✅ No implementation-specific details in protocol

#### 1.2 Create Quilt3Backend Implementation

**File**: `src/quilt_mcp/backends/quilt3_backend.py`

**Requirements**:
- Thin wrapper delegating to QuiltService
- Zero business logic in wrapper
- Maintain all QuiltService functionality
- Preserve error handling semantics

**Implementation Pattern**:
```python
class Quilt3Backend:
    """Backend implementation using quilt3 SDK."""

    def __init__(self):
        from quilt_mcp.services.quilt_service import QuiltService
        self._service = QuiltService()

    def list_packages(self, registry: str) -> Iterator[str]:
        return self._service.list_packages(registry)

    def browse_package(self, package_name: str, registry: str, ...) -> Any:
        return self._service.browse_package(package_name, registry, ...)

    # ... all other protocol methods delegate to self._service
```

**Success Criteria**:
- ✅ All protocol methods implemented
- ✅ All existing QuiltService tests pass with Quilt3Backend
- ✅ No performance regression (<5% overhead)
- ✅ Type checking passes with protocol compliance

#### 1.3 Create Backend Factory

**File**: `src/quilt_mcp/backends/factory.py`

**Requirements**:
- Environment-based backend selection
- Clear logging of backend choice
- Sensible defaults (quilt3)
- Error handling for invalid backends

**Implementation Approach**:
```python
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
    """
    backend_type = os.getenv("QUILT_BACKEND", "quilt3")

    logger.info(f"Selecting Quilt backend: {backend_type}")

    if backend_type == "quilt3":
        from .quilt3_backend import Quilt3Backend
        return Quilt3Backend()
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")
```

**Success Criteria**:
- ✅ Default returns Quilt3Backend
- ✅ QUILT_BACKEND env var works
- ✅ Backend selection logged at startup
- ✅ Invalid backends raise clear errors
- ✅ Factory overhead <1ms

#### 1.4 Create Package Initialization

**File**: `src/quilt_mcp/backends/__init__.py`

**Requirements**:
- Export public API cleanly
- Re-export protocol and factory
- Maintain clean namespace

**Implementation**:
```python
"""Backend abstraction layer for Quilt catalog operations."""

from .protocol import QuiltBackend
from .factory import get_backend
from .quilt3_backend import Quilt3Backend

__all__ = ["QuiltBackend", "get_backend", "Quilt3Backend"]
```

#### 1.5 Write Backend Tests

**File**: `tests/unit/backends/test_backend_factory.py`

**Test Coverage**:
1. Default backend selection (no env var)
2. Explicit quilt3 backend selection
3. Invalid backend type error handling
4. Backend selection logging
5. Factory performance (<1ms)

**File**: `tests/unit/backends/test_quilt3_backend.py`

**Test Coverage**:
1. Protocol compliance (all methods present)
2. Delegation to QuiltService works
3. Error propagation correct
4. Type checking passes
5. Performance overhead <5%

**File**: `tests/integration/backends/test_backend_integration.py`

**Test Coverage**:
1. End-to-end backend operations
2. Backend switching works
3. Real AWS operations (with mocking)

### Phase 1 Dependencies

**Prerequisites**:
- None (builds on existing code)

**Enables**:
- Phase 2 (tool migration pattern established)
- Phase 3 (all tools can migrate)
- Phase 4 (admin operations can use abstraction)

### Phase 1 Testing Strategy

**Test-Driven Development**:
1. Write failing tests for protocol definition
2. Implement protocol
3. Write failing tests for Quilt3Backend
4. Implement Quilt3Backend wrapper
5. Write failing tests for factory
6. Implement factory
7. Refactor for quality

**Test Categories**:
- Unit tests: Protocol, factory, wrapper
- Integration tests: Real backend operations
- Performance tests: Overhead measurement
- Type tests: Protocol compliance validation

### Phase 1 Success Criteria

**Functional**:
- ✅ Backend abstraction layer exists
- ✅ Quilt3Backend works identically to QuiltService
- ✅ Factory selects backend based on environment
- ✅ All tests pass (existing + new)

**Quality**:
- ✅ Type checking passes (mypy/pyright)
- ✅ Code coverage ≥90% for new backend module
- ✅ Performance overhead <5% measured
- ✅ Documentation complete

**Validation**:
- ✅ Can import and use get_backend()
- ✅ Default behavior unchanged (backward compatible)
- ✅ Logging shows backend selection
- ✅ No existing code broken

### Phase 1 Deliverables

**Code**:
- `src/quilt_mcp/backends/__init__.py`
- `src/quilt_mcp/backends/protocol.py`
- `src/quilt_mcp/backends/quilt3_backend.py`
- `src/quilt_mcp/backends/factory.py`

**Tests**:
- `tests/unit/backends/test_backend_factory.py`
- `tests/unit/backends/test_quilt3_backend.py`
- `tests/integration/backends/test_backend_integration.py`

**Documentation**:
- Backend abstraction architecture doc
- API documentation for protocol
- Migration guide for tool developers

### Phase 1 Risk Mitigation

**Risk**: Protocol doesn't cover all QuiltService methods
**Mitigation**: Static analysis to identify all public methods; comprehensive test coverage

**Risk**: Performance overhead unacceptable
**Mitigation**: Benchmark early; thin wrapper design; profile hot paths

**Risk**: Type system limitations
**Mitigation**: Use Protocol (structural typing); runtime_checkable if needed; comprehensive type tests

## Phase 2: Tool Migration - High-Value Tools

### Objectives

1. Validate abstraction pattern with real tools
2. Establish migration pattern for Phase 3
3. Measure performance impact
4. Document lessons learned

### Tool Selection Rationale

**Selected Tools** (5 tools):

1. **`list_packages`** (`tools/packages.py`)
   - Rationale: Core functionality, high usage
   - Complexity: Simple read operation
   - Validates: Basic backend operations

2. **`browse_package`** (`tools/packages.py`)
   - Rationale: Complex package inspection
   - Complexity: Multiple service calls
   - Validates: Nested operations, error handling

3. **`create_package`** (`tools/packages.py`)
   - Rationale: Write operations critical
   - Complexity: Multi-step package creation
   - Validates: Stateful operations

4. **`search_packages`** (`tools/search.py`)
   - Rationale: Integration with search backends
   - Complexity: Multiple backend types
   - Validates: Backend interoperability

5. **`get_catalog_info`** (`tools/auth.py`)
   - Rationale: Authentication dependency
   - Complexity: Session management
   - Validates: Auth integration

**Coverage**: Read, write, search, auth operations

### Detailed Work Items

#### 2.1 Migrate list_packages Tool

**File**: `src/quilt_mcp/tools/packages.py`

**Current Implementation**:
```python
from quilt_mcp.services.quilt_service import QuiltService

@mcp.tool()
def list_packages(registry: str):
    service = QuiltService()
    return service.list_packages(registry)
```

**Target Implementation**:
```python
from quilt_mcp.backends import get_backend

@mcp.tool()
def list_packages(registry: str):
    backend = get_backend()
    return backend.list_packages(registry)
```

**TDD Approach**:
1. Write test expecting backend usage
2. Update tool to use get_backend()
3. Verify existing tests pass
4. Refactor if needed

#### 2.2 Migrate browse_package Tool

**Similar pattern** to list_packages, but validates:
- Complex return types
- Error handling paths
- Performance with large packages

#### 2.3 Migrate create_package Tool

**Validates**:
- Write operations
- Stateful operations
- Transaction semantics

#### 2.4 Migrate search_packages Tool

**Validates**:
- Integration with search backends
- Multiple backend types
- Error handling across boundaries

#### 2.5 Migrate get_catalog_info Tool

**Validates**:
- Authentication integration
- Session management
- Configuration handling

#### 2.6 Update Tool Tests

**For each migrated tool**:
1. Verify tests pass without modification
2. Add backend mocking if needed
3. Validate error handling preserved
4. Check performance acceptable

#### 2.7 Performance Benchmarking

**Benchmark Suite**:
```python
# tests/performance/test_backend_overhead.py

def test_list_packages_performance():
    # Direct QuiltService
    start = time.time()
    service = QuiltService()
    service.list_packages(registry)
    direct_time = time.time() - start

    # Via backend abstraction
    start = time.time()
    backend = get_backend()
    backend.list_packages(registry)
    abstraction_time = time.time() - start

    overhead = (abstraction_time - direct_time) / direct_time
    assert overhead < 0.05  # <5% overhead
```

#### 2.8 Document Migration Pattern

**Migration Guide**:
1. Identify QuiltService imports
2. Replace with get_backend() import
3. Replace service instance with backend
4. Run tests to validate
5. Check performance if critical path

### Phase 2 Dependencies

**Prerequisites**:
- Phase 1 complete (backend abstraction exists)

**Enables**:
- Phase 3 (pattern validated for all tools)

### Phase 2 Testing Strategy

**For Each Tool**:
1. Write test that tool uses backend (if not already covered)
2. Migrate tool to use get_backend()
3. Verify all existing tests pass
4. Add backend-specific tests if needed
5. Measure performance impact

**Integration Tests**:
- End-to-end workflows with migrated tools
- Backend switching during operation
- Error handling across abstraction boundary

### Phase 2 Success Criteria

**Functional**:
- ✅ All 5 tools work through backend abstraction
- ✅ Tool behavior unchanged (validated by tests)
- ✅ Error handling preserved
- ✅ Integration tests pass

**Quality**:
- ✅ Performance overhead <5% per tool
- ✅ All tool tests pass
- ✅ Coverage maintained
- ✅ Migration pattern documented

**Validation**:
- ✅ Tools work with Quilt3Backend
- ✅ Can switch backends via env var
- ✅ Logging shows backend usage
- ✅ No functionality regression

### Phase 2 Deliverables

**Code**:
- Updated 5 tool files using get_backend()
- Updated tool tests (if needed)

**Documentation**:
- Tool migration pattern guide
- Performance benchmark results
- Lessons learned document

**Validation**:
- Integration test suite for migrated tools
- Performance benchmark suite

### Phase 2 Risk Mitigation

**Risk**: Performance overhead unacceptable in real tools
**Mitigation**: Early benchmarking; optimize hot paths; profile critical operations

**Risk**: Tool tests break with abstraction
**Mitigation**: Tests should be backend-agnostic; update mocking if needed; maintain test semantics

**Risk**: Migration pattern doesn't scale
**Mitigation**: Document challenges; refine pattern before Phase 3; validate with diverse tool types

## Phase 3: Complete Tool Migration

### Objectives

1. Migrate all remaining tools to backend abstraction
2. Remove all direct QuiltService imports from tools
3. Validate end-to-end functionality
4. Achieve complete tool migration

### Remaining Tools (15 tools)

**Packages** (`tools/packages.py`):
- Additional package operations beyond Phase 2
- Package version management
- Package metadata operations

**Buckets** (`tools/buckets.py`):
- Bucket creation and management
- Object listing and manipulation
- S3 operations

**Search** (`tools/search.py`):
- Additional search operations beyond Phase 2
- Search backend selection
- Query optimization

**Auth** (`tools/auth.py`):
- Additional auth operations beyond Phase 2
- Permission verification
- Credential management

**Admin** (`tools/admin/*.py` - if present):
- Will be updated in Phase 4 after admin integration

### Detailed Work Items

#### 3.1 Migrate Remaining Package Tools

**Tools**:
- `delete_package`
- `get_package_versions`
- `get_package_metadata`
- `set_package_metadata`
- `install_package`
- `push_package`
- `fetch_package`

**Migration Pattern**: Same as Phase 2

#### 3.2 Migrate Bucket Tools

**Tools**:
- `create_bucket`
- `list_buckets`
- `list_objects`
- `get_object`
- `put_object`
- `delete_object`

**Migration Pattern**: Same as Phase 2

#### 3.3 Migrate Remaining Search Tools

**Tools**:
- Advanced search operations
- Search backend selection
- Search result processing

**Migration Pattern**: Same as Phase 2

#### 3.4 Migrate Remaining Auth Tools

**Tools**:
- Permission checks
- Credential validation
- Session management

**Migration Pattern**: Same as Phase 2

#### 3.5 Remove Direct QuiltService Imports

**Validation**:
```bash
# Ensure no direct imports remain
grep -r "from quilt_mcp.services.quilt_service import QuiltService" src/quilt_mcp/tools/
# Should return no results
```

#### 3.6 Update All Tool Tests

**For each tool**:
1. Verify tests pass with backend abstraction
2. Update mocking if needed
3. Add integration tests for critical paths

#### 3.7 End-to-End Integration Testing

**Test Scenarios**:
1. Complete package lifecycle (create, browse, update, delete)
2. Multi-bucket operations
3. Search across multiple backends
4. Authentication and authorization flows
5. Error handling and recovery

### Phase 3 Dependencies

**Prerequisites**:
- Phase 2 complete (migration pattern validated)

**Enables**:
- Phase 4 (admin tools can be added)
- Complete backend abstraction coverage

### Phase 3 Testing Strategy

**Per-Tool Testing**:
- Follow Phase 2 pattern for each tool
- Batch similar tools for efficiency
- Validate incrementally

**Integration Testing**:
- Complete workflows across multiple tools
- Backend switching mid-operation
- Error propagation across tool boundaries

**Regression Testing**:
- Run full test suite after each batch
- Validate no existing functionality broken
- Check coverage maintained

### Phase 3 Success Criteria

**Functional**:
- ✅ All 20 tools use get_backend()
- ✅ No direct QuiltService imports in tools
- ✅ All tool tests pass
- ✅ Integration tests validate workflows

**Quality**:
- ✅ Coverage ≥85% maintained
- ✅ Performance overhead <5% overall
- ✅ No functionality regression
- ✅ Type checking passes

**Validation**:
- ✅ Static analysis confirms no direct imports
- ✅ Integration tests cover major workflows
- ✅ Backend switching works across all tools
- ✅ Documentation updated

### Phase 3 Deliverables

**Code**:
- All 20 tool files updated to use get_backend()
- Tool tests updated (if needed)
- Integration tests for workflows

**Documentation**:
- Updated tool documentation
- Complete migration guide
- Architecture diagram showing backend flow

**Validation**:
- Comprehensive integration test suite
- Migration validation script
- Performance benchmark results

### Phase 3 Risk Mitigation

**Risk**: Migration introduces subtle behavioral changes
**Mitigation**: Comprehensive test coverage; integration testing; careful review of each migration

**Risk**: Performance degrades across multiple tools
**Mitigation**: Performance monitoring; identify hot paths; optimize critical operations

**Risk**: Test maintenance burden increases
**Mitigation**: Refactor common test patterns; share fixtures; document testing approach

## Phase 4: Admin Operations Integration

### Objectives

1. Cherry-pick admin operations from main branch
2. Integrate admin methods into current QuiltService
3. Extend backend abstraction for admin operations
4. Validate admin tools work through abstraction

### Admin Operations from Main

**User Management** (10 methods):
- `create_user(username: str, email: str, ...) -> Dict`
- `delete_user(username: str) -> None`
- `get_user(username: str) -> Dict`
- `list_users() -> List[Dict]`
- `set_user_active(username: str, active: bool) -> None`
- `set_user_admin(username: str, admin: bool) -> None`
- `update_user_email(username: str, email: str) -> None`
- `reset_user_password(username: str) -> str`
- Additional user operations

**Role Management** (4 methods):
- `list_roles() -> List[str]`
- `add_role_to_user(username: str, role: str) -> None`
- `remove_role_from_user(username: str, role: str) -> None`
- `get_user_roles(username: str) -> List[str]`

**SSO Configuration** (3 methods):
- `get_sso_config() -> Dict`
- `set_sso_config(config: Dict) -> None`
- `remove_sso_config() -> None`

**Tabulator Administration** (6 methods):
- `create_table(table_name: str, ...) -> Dict`
- `delete_table(table_name: str) -> None`
- `list_tables() -> List[str]`
- `get_table_status(table_name: str) -> Dict`
- `enable_open_query(table_name: str) -> None`
- `disable_open_query(table_name: str) -> None`

**Administrative Utilities**:
- `is_admin_available() -> bool` - Dynamic admin detection
- `get_admin_credentials() -> Dict` - Credential checking
- Admin tool registration filtering

### Detailed Work Items

#### 4.1 Cherry-Pick Admin Operations from Main

**Process**:
1. Identify commits on main with admin operations
2. Cherry-pick admin method additions
3. Resolve conflicts (prefer additive merge)
4. Validate admin functionality preserved

**Git Commands**:
```bash
# On 2025-10-09-abstract-backend branch
git checkout main -- src/quilt_mcp/services/quilt_service.py

# Manually merge with current QuiltService
# Keep all methods from both versions (union)
```

#### 4.2 Integrate Admin Methods into QuiltService

**Requirements**:
- Add all 27 admin methods to current QuiltService
- Preserve dynamic admin detection
- Maintain admin credential checking
- Keep admin tool filtering logic

**Success Criteria**:
- ✅ All admin methods present
- ✅ No functional regression from main
- ✅ Admin detection works correctly
- ✅ Backward compatible

#### 4.3 Extend QuiltBackend Protocol

**File**: `src/quilt_mcp/backends/protocol.py`

**Add Admin Methods**:
```python
class QuiltBackend(Protocol):
    # ... existing methods ...

    # Admin Operations (optional)
    def is_admin_available(self) -> bool: ...

    # User Management
    def create_user(self, username: str, email: str, ...) -> Dict: ...
    def delete_user(self, username: str) -> None: ...
    def get_user(self, username: str) -> Dict: ...
    def list_users(self) -> List[Dict]: ...
    # ... remaining user methods

    # Role Management
    def list_roles(self) -> List[str]: ...
    # ... remaining role methods

    # SSO Configuration
    def get_sso_config(self) -> Dict: ...
    # ... remaining SSO methods

    # Tabulator Administration
    def create_table(self, table_name: str, ...) -> Dict: ...
    # ... remaining tabulator methods
```

#### 4.4 Update Quilt3Backend for Admin Operations

**File**: `src/quilt_mcp/backends/quilt3_backend.py`

**Add Admin Method Delegation**:
```python
class Quilt3Backend:
    # ... existing methods ...

    def is_admin_available(self) -> bool:
        return self._service.is_admin_available()

    def create_user(self, username: str, email: str, ...) -> Dict:
        return self._service.create_user(username, email, ...)

    # ... delegate all 27 admin methods
```

#### 4.5 Migrate Admin Tools (if present)

**If admin tools exist in tools/admin/**:
1. Update to use get_backend()
2. Validate admin detection works
3. Test with admin and non-admin credentials

**Tool Registration Filtering**:
```python
# Only register admin tools if admin available
backend = get_backend()
if backend.is_admin_available():
    register_admin_tools(mcp)
```

#### 4.6 Update Admin Tests

**Test Categories**:

1. **Admin Operation Tests**:
   - All 27 admin methods work
   - Error handling correct
   - Admin detection accurate

2. **Backend Integration Tests**:
   - Admin operations work through Quilt3Backend
   - Non-admin users properly excluded
   - Admin tool registration conditional

3. **End-to-End Admin Tests**:
   - User lifecycle (create, update, delete)
   - Role management workflows
   - SSO configuration
   - Tabulator administration

### Phase 4 Dependencies

**Prerequisites**:
- Phase 3 complete (all tools migrated)

**Enables**:
- Complete feature set for v0.8.0
- Admin functionality through abstraction

### Phase 4 Testing Strategy

**TDD Approach**:
1. Write failing tests for admin operations
2. Cherry-pick admin methods from main
3. Extend protocol with admin operations
4. Update Quilt3Backend delegation
5. Validate all admin tests pass

**Test Coverage**:
- Unit tests: Each admin method
- Integration tests: Admin workflows
- Security tests: Admin access control
- Backward compatibility: main tests pass

### Phase 4 Success Criteria

**Functional**:
- ✅ All 27 admin methods integrated
- ✅ Admin operations work through Quilt3Backend
- ✅ Admin detection works correctly
- ✅ Non-admin users excluded properly

**Quality**:
- ✅ All admin tests from main pass
- ✅ Coverage maintained ≥85%
- ✅ No security regressions
- ✅ Documentation complete

**Validation**:
- ✅ Admin tools work through abstraction
- ✅ Backend switching works for admin ops
- ✅ Integration tests validate admin workflows
- ✅ Backward compatible with main v0.7.0

### Phase 4 Deliverables

**Code**:
- Enhanced QuiltService with admin operations
- Extended QuiltBackend protocol
- Updated Quilt3Backend with admin delegation
- Migrated admin tools (if present)

**Tests**:
- Admin operation unit tests
- Admin workflow integration tests
- Security/access control tests

**Documentation**:
- Admin operation documentation
- Backend abstraction with admin ops
- Migration guide from main v0.7.0

### Phase 4 Risk Mitigation

**Risk**: Cherry-pick conflicts with current code
**Mitigation**: Manual merge favoring union of capabilities; comprehensive testing; careful review

**Risk**: Admin detection breaks
**Mitigation**: Preserve exact logic from main; test with admin and non-admin credentials; validate tool registration

**Risk**: Security vulnerabilities in admin ops
**Mitigation**: Security review of admin methods; access control testing; audit logging

## Cross-Phase Considerations

### Continuous Integration

**After Each Phase**:
1. Run full test suite (`make test`)
2. Run linting and type checking (`make lint`)
3. Check code coverage (`make coverage`)
4. Review IDE diagnostics
5. Update documentation

### Git Strategy

**Branch Management**:
- Work on `impl/backend-abstraction` branch (from `2025-10-09-abstract-backend`)
- One commit per logical change
- Follow conventional commit format
- Push after each phase completion

**Commit Pattern**:
```
Phase 1:
- feat: add QuiltBackend protocol definition
- feat: implement Quilt3Backend wrapper
- feat: add get_backend() factory
- test: add backend abstraction tests
- docs: add backend abstraction documentation

Phase 2:
- feat: migrate list_packages to backend abstraction
- feat: migrate browse_package to backend abstraction
- feat: migrate create_package to backend abstraction
- feat: migrate search_packages to backend abstraction
- feat: migrate get_catalog_info to backend abstraction
- test: add backend performance benchmarks
- docs: add tool migration guide

Phase 3:
- feat: migrate remaining package tools to backend
- feat: migrate bucket tools to backend
- feat: migrate remaining search tools to backend
- feat: migrate remaining auth tools to backend
- refactor: remove direct QuiltService imports from tools
- test: add end-to-end integration tests
- docs: update architecture documentation

Phase 4:
- feat: cherry-pick admin operations from main
- feat: extend QuiltBackend protocol with admin ops
- feat: update Quilt3Backend for admin operations
- feat: migrate admin tools to backend abstraction
- test: add admin operation tests
- docs: add admin operations documentation
```

### Documentation Updates

**Continuous Documentation**:
- Update CLAUDE.md with learnings after each phase
- Document gotchas and patterns discovered
- Update architecture diagrams
- Keep API documentation current

### Testing Strategy

**Test Layers**:

1. **Unit Tests**: Individual components
   - Protocol compliance
   - Factory behavior
   - Backend delegation

2. **Integration Tests**: Component interaction
   - Backend switching
   - Tool workflows
   - Admin operations

3. **Performance Tests**: Overhead measurement
   - Factory latency
   - Protocol dispatch overhead
   - End-to-end timing

4. **Backward Compatibility Tests**: v0.7.x compatibility
   - Configuration compatibility
   - API compatibility
   - Behavior preservation

### Quality Gates

**Before Each Phase Completion**:
- ✅ All tests pass (100%)
- ✅ Coverage ≥85%
- ✅ Type checking passes (mypy/pyright)
- ✅ Linting passes (ruff)
- ✅ IDE diagnostics clean
- ✅ Documentation updated
- ✅ Performance benchmarks acceptable

**Before Final PR**:
- ✅ All phases complete
- ✅ Comprehensive test suite passes
- ✅ Integration tests cover major workflows
- ✅ Admin operations validated
- ✅ Documentation complete
- ✅ CHANGELOG updated

## Success Metrics

### Phase Completion Metrics

**Phase 1**:
- Backend abstraction layer created
- Quilt3Backend working
- Factory functional
- Tests passing

**Phase 2**:
- 5 tools migrated
- Migration pattern validated
- Performance acceptable
- Documentation complete

**Phase 3**:
- All 20 tools migrated
- No direct imports remain
- Integration tests passing
- Full coverage maintained

**Phase 4**:
- Admin operations integrated
- Backend abstraction complete
- All features from both branches present
- Ready for merge to main

### Overall Success Criteria

**Functional**:
- ✅ Backend abstraction layer complete
- ✅ All tools use get_backend()
- ✅ Admin operations integrated
- ✅ All tests pass

**Quality**:
- ✅ Coverage ≥85%
- ✅ Performance overhead <5%
- ✅ Type checking passes
- ✅ Documentation complete

**Strategic**:
- ✅ Ready to merge to main as v0.8.0
- ✅ Backend switching works
- ✅ Backward compatible with v0.7.x
- ✅ Future GraphQL backend enabled

## Timeline Summary

| Phase | Duration | Dependencies | Deliverables |
|-------|----------|--------------|--------------|
| Phase 1: Backend Protocol | 3-4 days | None | Protocol, wrapper, factory, tests |
| Phase 2: High-Value Tools | 2-3 days | Phase 1 | 5 tools migrated, pattern validated |
| Phase 3: Complete Migration | 2-3 days | Phase 2 | All 20 tools migrated, complete |
| Phase 4: Admin Integration | 2-3 days | Phase 3 | Admin ops integrated, ready for merge |
| **Total** | **9-13 days** | Sequential | Complete backend abstraction |

## Next Steps

1. **Human Review**: Review this phases document for approval
2. **Create Implementation Branch**: `impl/backend-abstraction` from current branch
3. **Begin Phase 1**: Start with protocol definition (TDD)
4. **Iterate Through Phases**: Complete each phase sequentially
5. **Create PR**: After Phase 4 completion, create PR to `2025-10-09-abstract-backend`

**Success Gate**: This document must be reviewed and approved before implementation begins.

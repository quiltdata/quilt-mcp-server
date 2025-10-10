# Requirements - Refactor QuiltService to Match Original Specification

**Problem Statement**: The current `QuiltService` implementation deviates significantly from the original architectural specification (Issue #155). Instead of abstracting operations, it exposes raw quilt3 modules and provides "getter" methods that leak implementation details. This prevents the service from fulfilling its intended purpose: enabling backend swapping and providing a clean abstraction layer.

## Original Specification Intent (Issue #155)

From [03-specifications.md](./03-specifications.md):

> **Purpose**: Centralize all quilt3 API access behind a unified interface

The specification envisioned operational methods like:

```python
class QuiltService:
    # Package Operations
    def list_packages(self, registry: str) -> Iterator[PackageInfo]
    def get_package(self, package_name: str, registry: str) -> Package
    def create_package(self, package_name: str, **kwargs) -> PackageResult

    # AWS Client Access
    def get_s3_client(self) -> S3Client
    def get_sts_client(self) -> STSClient
```

## Current Reality - Anti-Patterns

The current implementation provides **module getters** instead of **operational abstractions**:

```python
# CURRENT (WRONG): Returns raw quilt3 modules
def get_users_admin(self) -> Any:
    """Get users admin module."""
    import quilt3.admin.users
    return quilt3.admin.users

# Usage still directly calls quilt3 APIs:
users_admin = service.get_users_admin()
users_admin.list_users()  # Caller uses quilt3 API directly!
```

This violates the specification's core goals:
1. ❌ **Doesn't abstract operations** - just tests if imports work
2. ❌ **Doesn't provide unified interface** - returns raw quilt3 modules
3. ❌ **Leaks implementation details** - callers use quilt3 APIs directly
4. ❌ **Doesn't enable backend swapping** - the whole point of the service layer!

## User Requirements

### 1. Operational Abstraction

**Requirement**: Service methods should abstract complete operations, not expose internal modules.

**Example**:
```python
# RIGHT (per spec):
users = service.list_users()  # Returns data, not module
user = service.get_user(name="john")  # Service handles the operation
service.create_user(name="jane", email="jane@example.com", role="admin")
```

### 2. Backend Swappability

**Requirement**: Service interface must be implementation-agnostic to enable future backend swapping.

**Rationale**: The original spec's goal was to support:
- Local development using quilt3
- Remote deployment using stack-native APIs
- Testing with mock implementations

### 3. Zero Module Exposure

**Requirement**: Service should never return raw quilt3 modules or objects that expose quilt3 APIs.

**Rationale**: Callers should interact with service abstractions, not quilt3 directly.

### 4. Functional Equivalence

**Requirement**: All existing functionality must be preserved exactly during refactoring.

**Quality Gates**:
- All existing tests pass without modification
- 100% test coverage maintained
- No performance degradation
- Tool interfaces remain unchanged

## Problem Analysis

### Current Usage Pattern (35+ calls)

The most heavily-used methods are the problematic "getter" patterns:

1. **`get_users_admin()`** - 11 calls across governance.py and admin.py
2. **`get_tabulator_admin()`** - 8 calls in governance.py and tabulator.py
3. **`get_sso_config_admin()`** - 4 calls in governance.py
4. **`get_roles_admin()`** - 2 calls in governance.py

All of these follow the anti-pattern:
```python
# Service just returns the module
admin = service.get_users_admin()
# Caller uses quilt3 API directly
result = admin.list_users()
```

### Impact Scope

**Files Requiring Changes**:
- `src/quilt_mcp/services/quilt_service.py` (689 lines) - Core refactoring
- `src/quilt_mcp/tools/governance.py` - 11+ admin method calls
- `src/quilt_mcp/tools/tabulator.py` - 8+ admin method calls
- `src/quilt_mcp/resources/admin.py` - Resource implementations
- All test files that mock or use QuiltService

**Estimated Lines of Code Impact**: ~2000-3000 lines across 10+ files

## Constraints

1. **Zero Breaking Changes**: All MCP tool interfaces must remain unchanged
2. **Test Coverage**: Must maintain 100% coverage throughout refactoring
3. **TDD Required**: All changes must follow Red-Green-Refactor cycle
4. **Performance**: No degradation in performance characteristics
5. **Backwards Compatibility**: Existing tool behavior must be preserved exactly

## Success Criteria

### 1. Architectural Alignment

- ✅ Service provides operational methods, not module getters
- ✅ No raw quilt3 modules or objects exposed in return values
- ✅ Service interface is implementation-agnostic
- ✅ Backend swapping is architecturally possible

### 2. Code Quality

- ✅ All tests pass without modification to test assertions
- ✅ 100% test coverage maintained
- ✅ No direct quilt3 API calls in tool modules (except through service)
- ✅ Service methods return typed data structures, not `Any`

### 3. Functional Equivalence

- ✅ All 84+ MCP tools function identically
- ✅ Error handling patterns preserved
- ✅ Performance characteristics maintained
- ✅ Tool interfaces unchanged

### 4. Documentation

- ✅ Service API fully documented with operational semantics
- ✅ Migration patterns documented for future reference
- ✅ Architecture decision records updated

## Non-Goals

1. **Backend Implementation**: This refactoring focuses on interface design, not implementing alternative backends
2. **Environment Detection**: Backend selection logic is out of scope
3. **Performance Optimization**: Maintain current performance, don't optimize
4. **Feature Addition**: No new functionality, only architectural cleanup

## Risk Assessment

### High Risk Areas

1. **Admin Operations** (35+ call sites)
   - Most heavily used problematic pattern
   - Requires careful migration of governance.py
   - Complex error handling patterns to preserve

2. **Package Creation** (689 lines of logic)
   - Large, complex method with 10 helper functions
   - Heavily tested but intricate logic
   - Potential for subtle behavior changes

3. **GraphQL Operations** (12 uses)
   - Session management is delicate
   - Authentication patterns must be preserved exactly
   - Error handling is complex

### Mitigation Strategies

1. **Incremental Migration**: Refactor one operation category at a time
2. **Parallel Implementation**: Keep old methods during transition
3. **Comprehensive Testing**: Add behavioral tests before refactoring
4. **Rollback Plan**: Each phase should be independently committable

## Implementation Approach

### Phase 1: Admin Operations Refactoring
Focus on highest-impact area first (35+ calls).

### Phase 2: Package Operations
Extract package creation logic into specialized service.

### Phase 3: Session & GraphQL
Migrate session management to operational methods.

### Phase 4: Cleanup & Deprecation
Remove old getter methods, update documentation.

## Acceptance Criteria

- [ ] All service methods return typed data structures, not raw modules
- [ ] No `Any` return types in public service methods
- [ ] All callers use operational methods instead of module getters
- [ ] All tests pass with 100% coverage
- [ ] No performance degradation measured
- [ ] Specification alignment verified by code review
- [ ] Documentation updated to reflect new patterns

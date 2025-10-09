<!-- markdownlint-disable MD013 -->
# Requirements - Backend Abstraction for Branch Merge Strategy

**GitHub Issue**: TBD (to be created)
**Branch**: `2025-10-09-abstract-backend` (based on `impl/remote-mcp-deployment`)
**Target**: Merge `impl/remote-mcp-deployment` features into `main` (v0.8.0) with backend abstraction
**Date**: 2025-10-09

## Problem Statement

The `impl/remote-mcp-deployment` branch contains 26 commits of valuable improvements (Docker, remote deployment, multi-transport) that need to be merged into `main` for the v0.8.0 release. However, the branches have diverged:

- **main** (v0.7.0+): Has comprehensive quilt3-based `QuiltService` with full admin operations (1,281 lines)
- **impl/remote-mcp-deployment**: Has streamlined `QuiltService` (688 lines) plus containerization and remote deployment infrastructure

**Current Blocker**: Cannot simply merge because:
1. Different QuiltService implementations will conflict
2. Need to preserve admin operations from `main`
3. Need to preserve containerization from `impl/remote-mcp-deployment`
4. Want to add backend abstraction to enable future GraphQL migration without disruption

**Desired Outcome**: Create v0.8.0 on `main` that:
- ✅ Includes ALL improvements from `impl/remote-mcp-deployment` (Docker, Terraform, multi-transport)
- ✅ Preserves ALL QuiltService admin operations from `main` v0.7.0
- ✅ Adds backend abstraction layer for future flexibility (quilt3 vs GraphQL)
- ✅ Establishes clean merge path for future `impl/remote-mcp-deployment` changes

## Strategic Goal

**Enable ongoing development in `impl/remote-mcp-deployment` branch while maintaining ability to merge back to `main`.**

This requires:
1. **Backend abstraction layer**: Decouple tools from specific backend implementation
2. **Consistent interface**: Both branches can evolve independently but share protocol
3. **Merge-friendly architecture**: Future merges don't require massive refactoring
4. **Backward compatibility**: Existing v0.7.x deployments continue working

## User Stories

### Story 1: Seamless Branch Merge

**As a** repository maintainer
**I want** to merge `impl/remote-mcp-deployment` into `main` without conflicts
**So that** v0.8.0 includes both deployment improvements and admin features

**Acceptance Criteria**:
1. All 26 commits from `impl/remote-mcp-deployment` successfully merge into `main`
2. No functionality loss from either branch
3. QuiltService contains union of capabilities (admin ops + container support)
4. All tests pass on merged `main` branch
5. Version bumped to v0.8.0 in merged branch

### Story 2: Backend Abstraction Foundation

**As a** developer
**I want** tools to use a backend abstraction layer instead of direct QuiltService imports
**So that** we can switch between quilt3 and GraphQL implementations without refactoring tools

**Acceptance Criteria**:
1. `QuiltBackend` protocol defines contract for backend implementations
2. `Quilt3Backend` wraps existing QuiltService (preserves all functionality)
3. `get_backend()` factory returns appropriate backend based on configuration
4. Environment variable `QUILT_BACKEND` controls backend selection (default: `quilt3`)
5. Backend selection logged at startup for troubleshooting

### Story 3: Preserve Deployment Improvements

**As a** deployment engineer
**I want** Docker and remote deployment features from `impl/remote-mcp-deployment` in main
**So that** production deployments benefit from containerization improvements

**Acceptance Criteria**:
1. Dockerfile and Docker scripts merged to `main`
2. Terraform modules for ECS deployment available on `main`
3. Multi-transport support (stdio, HTTP, SSE) works on `main`
4. CORS middleware and session handling preserved
5. All Docker/deployment documentation included

### Story 4: Preserve Admin Operations

**As a** Quilt admin
**I want** user management, SSO, and tabulator admin operations from `main` v0.7.0
**So that** administrative functionality isn't lost in the merge

**Acceptance Criteria**:
1. All 27 admin methods from `main` QuiltService preserved
2. User management operations work identically
3. SSO configuration methods available
4. Tabulator administration functions preserved
5. Dynamic admin credential checking maintained

### Story 5: Future-Proof GraphQL Migration

**As a** platform architect
**I want** backend abstraction that enables future GraphQL-only implementation
**So that** we can migrate to GraphQL without breaking existing code

**Acceptance Criteria**:
1. Protocol supports adding `GraphQLBackend` without changing tools
2. Backend implementations isolated - adding GraphQL doesn't affect quilt3
3. Clear migration path documented for GraphQL implementation
4. No premature optimization - GraphQL backend is optional future work
5. Backend switching doesn't require tool refactoring

### Story 6: Ongoing Development Flow

**As a** developer working on `impl/remote-mcp-deployment`
**I want** a clear process for merging future changes back to `main`
**So that** branches don't diverge irreconcilably

**Acceptance Criteria**:
1. Clear branching strategy documented
2. Regular merge cadence established (e.g., per release)
3. CI/CD validates both branches independently
4. Merge conflicts minimized through shared abstractions
5. Documentation explains when to develop in each branch

## High-Level Implementation Approach

### Phase 1: Establish Backend Abstraction on This Branch

Working on `2025-10-09-abstract-backend` (based on `impl/remote-mcp-deployment`):

1. **Extract Protocol**: Define `QuiltBackend` protocol from current QuiltService
2. **Wrap Current Service**: Create `Quilt3Backend` delegating to QuiltService
3. **Add Factory**: Implement `get_backend()` with env var selection
4. **Migrate Tools**: Update tools to use `get_backend()` instead of direct imports
5. **Validate**: Ensure all tests pass with abstraction layer

### Phase 2: Backport Admin Operations from Main

Still on `2025-10-09-abstract-backend`:

1. **Cherry-pick**: Bring admin operations from `main` QuiltService (1,281 lines)
2. **Integrate**: Add admin methods to our QuiltService
3. **Update Protocol**: Extend `QuiltBackend` protocol with admin operations
4. **Test**: Validate admin operations work through abstraction layer

### Phase 3: Merge to Main as v0.8.0

1. **Create PR**: `2025-10-09-abstract-backend` → `main`
2. **Review**: Comprehensive review of merged capabilities
3. **Release**: Tag as v0.8.0 with combined feature set
4. **Merge Back**: Sync `main` v0.8.0 to `impl/remote-mcp-deployment`

### Phase 4: Establish Ongoing Merge Strategy

1. **Document Flow**: Define when to develop in each branch
2. **Automation**: CI/CD checks for merge compatibility
3. **Cadence**: Regular merges to keep branches in sync

## Success Criteria

### Functional Requirements

1. **Complete Feature Set**: v0.8.0 on `main` includes:
   - ✅ All Docker/containerization from `impl/remote-mcp-deployment`
   - ✅ All Terraform/deployment from `impl/remote-mcp-deployment`
   - ✅ All multi-transport support from `impl/remote-mcp-deployment`
   - ✅ All admin operations from `main` v0.7.0
   - ✅ Backend abstraction layer (new)

2. **Backend Abstraction Works**:
   - ✅ `Quilt3Backend` passes all existing tests
   - ✅ `get_backend()` factory works with env var
   - ✅ Tools successfully use abstraction layer
   - ✅ No functionality regression

3. **Clean Merge Path**:
   - ✅ Merge completes without unresolved conflicts
   - ✅ No test failures on merged branch
   - ✅ No deployment regressions
   - ✅ Version correctly tagged as v0.8.0

### Quality Requirements

1. **Test Coverage**: Maintain 85%+ coverage through merge
2. **Performance**: No performance degradation from abstraction
3. **Documentation**: Complete architecture and merge strategy docs
4. **Compatibility**: Existing v0.7.x deployments work with v0.8.0

### Strategic Requirements

1. **Merge-Friendly**: Future `impl/remote-mcp-deployment` merges don't require major refactoring
2. **Backend Flexibility**: Can add `GraphQLBackend` in future without disruption
3. **Branch Strategy**: Clear guidelines for which branch to develop in
4. **CI/CD Integration**: Both branches validated independently

## Scope

### In Scope

1. **Backend Abstraction**:
   - Define `QuiltBackend` protocol
   - Implement `Quilt3Backend` wrapper
   - Create `get_backend()` factory
   - Migrate tools to use abstraction

2. **Feature Merge**:
   - Cherry-pick admin operations from `main`
   - Preserve all containerization from `impl/remote-mcp-deployment`
   - Resolve conflicts in favor of union of capabilities
   - Test merged functionality

3. **Documentation**:
   - Architecture documentation for backend abstraction
   - Merge strategy guide for ongoing development
   - Migration path for future GraphQL backend

### Out of Scope

1. **GraphQL Backend Implementation**: Optional future work, not required for v0.8.0
2. **API Changes**: No breaking changes to MCP tool interfaces
3. **Performance Optimization**: Focus on functional merge, not optimization
4. **Rewriting History**: No rebasing, preserve commit history
5. **Backward Compatibility Break**: v0.8.0 must be compatible with v0.7.x configs

## Branch Strategy

### Current State

```
main (v0.7.0+)
├── Comprehensive QuiltService (1,281 lines)
├── Admin operations (user mgmt, SSO, tabulator)
├── Standard MCPB/stdio deployment
└── No containerization

impl/remote-mcp-deployment (+26 commits)
├── Streamlined QuiltService (688 lines)
├── Docker/containerization
├── Terraform/ECS deployment
├── Multi-transport (stdio, HTTP, SSE)
└── CORS middleware
```

### Target State (v0.8.0)

```
main (v0.8.0)
├── Backend Abstraction Layer
│   ├── QuiltBackend protocol
│   ├── Quilt3Backend implementation
│   └── get_backend() factory
├── Complete QuiltService (union of both branches)
│   ├── All admin operations from main
│   ├── All core operations
│   └── Container-aware functionality
├── Containerization Infrastructure
│   ├── Dockerfile + Docker scripts
│   ├── Terraform modules
│   └── Multi-transport support
└── Merge-friendly architecture for future updates
```

### Future Flow

```
1. Develop new features in appropriate branch:
   - Deployment/infrastructure → impl/remote-mcp-deployment
   - Backend/admin features → main
   - Tools/capabilities → either (merged regularly)

2. Regular merge cadence:
   - After each release tag on main
   - Before starting major features
   - When branches diverge significantly

3. Backend abstraction enables:
   - Independent backend evolution
   - Minimal merge conflicts
   - GraphQL migration when ready
```

## Implementation Phases

### Phase 1: Backend Abstraction (3-4 days)

**Branch**: `2025-10-09-abstract-backend` (current)

1. Define `QuiltBackend` protocol from existing QuiltService interface
2. Create `Quilt3Backend` wrapper (thin delegation layer)
3. Implement `get_backend()` factory with env var selection
4. Update 5 high-value tools to validate pattern
5. Run test suite to ensure no regression

**Deliverables**:
- `src/quilt_mcp/backends/protocol.py` - Protocol definition
- `src/quilt_mcp/backends/quilt3_backend.py` - Implementation
- `src/quilt_mcp/backends/factory.py` - Factory function
- Updated tool files using `get_backend()`
- Passing test suite

### Phase 2: Cherry-Pick Admin Operations (2-3 days)

**Branch**: `2025-10-09-abstract-backend`

1. Cherry-pick admin operation commits from `main`
2. Integrate into current QuiltService
3. Update `QuiltBackend` protocol with admin methods
4. Update `Quilt3Backend` to expose admin operations
5. Validate admin operations through abstraction

**Deliverables**:
- Enhanced QuiltService with admin ops
- Extended protocol interface
- Passing admin operation tests

### Phase 3: Complete Tool Migration (2-3 days)

**Branch**: `2025-10-09-abstract-backend`

1. Migrate remaining 15 tools to use `get_backend()`
2. Remove direct QuiltService imports from tools
3. Update all tests for abstraction layer
4. Run comprehensive test suite
5. Update documentation

**Deliverables**:
- All 20 tools using backend abstraction
- No direct QuiltService imports in tools
- 85%+ test coverage maintained
- Updated developer documentation

### Phase 4: Merge and Release (1-2 days)

**Target**: `main` branch → v0.8.0

1. Create PR: `2025-10-09-abstract-backend` → `main`
2. Comprehensive review and testing
3. Resolve any final conflicts
4. Merge to `main`
5. Tag v0.8.0 release
6. Update CHANGELOG

**Deliverables**:
- Merged `main` branch with all features
- v0.8.0 release tag
- Updated CHANGELOG
- Release notes

### Phase 5: Sync Back to Development Branch (1 day)

**Target**: `impl/remote-mcp-deployment`

1. Merge `main` v0.8.0 back to `impl/remote-mcp-deployment`
2. Resolve any conflicts (should be minimal)
3. Validate tests pass
4. Document ongoing merge strategy

**Deliverables**:
- Synced `impl/remote-mcp-deployment` branch
- Documented merge workflow
- CI/CD validation for both branches

**Total Estimate**: 9-13 days

## Open Questions

1. **Release Timing**: When should v0.8.0 be released?
   - Immediately after merge?
   - After additional QA period?
   - Coordinate with other planned features?

2. **Branch Lifecycle**: What happens to `impl/remote-mcp-deployment` after v0.8.0?
   - Continue using for deployment-focused work?
   - Retire and work directly on `main`?
   - Keep as experimental branch?

3. **GraphQL Backend**: When should GraphQL implementation happen?
   - Part of v0.8.0 (extends timeline)?
   - Future v0.9.0 feature?
   - Only if/when needed?

4. **Breaking Changes**: Are any breaking changes acceptable in v0.8.0?
   - Semantic versioning says no (minor version)
   - Backend abstraction should be transparent
   - Configuration changes acceptable?

5. **Testing Infrastructure**: Do we need additional test infrastructure?
   - Separate CI/CD for backend variants?
   - Integration tests for Docker deployment?
   - Admin operation test suite?

6. **Migration for Existing Deployments**: How do v0.7.x users upgrade to v0.8.0?
   - Automatic (no config changes)?
   - Requires config updates?
   - Migration guide needed?

## Dependencies

- **Both Branches**: Access to `main` and `impl/remote-mcp-deployment` branches
- **quilt3 SDK**: Must remain available as dependency
- **Test Infrastructure**: Ability to test merged functionality
- **CI/CD**: GitHub Actions workflows for both branches
- **Review Resources**: Comprehensive code review for merge

## Risks and Mitigation

### Risk 1: Merge Conflicts

**Probability**: High
**Impact**: Medium
**Mitigation**:
- Phase approach reduces conflict surface
- Backend abstraction isolates changes
- Manual conflict resolution with preference for union of capabilities

### Risk 2: Test Failures After Merge

**Probability**: Medium
**Impact**: High
**Mitigation**:
- Comprehensive test suite runs before merge
- Integration testing of merged features
- Rollback plan if critical issues found

### Risk 3: Incomplete Feature Set

**Probability**: Low
**Impact**: High
**Mitigation**:
- Checklist of all features from both branches
- Validation testing for each feature category
- User acceptance testing

### Risk 4: Branch Divergence Recurrence

**Probability**: Medium
**Impact**: Medium
**Mitigation**:
- Document clear branch strategy
- Regular merge cadence
- Automated checks for merge compatibility
- Shared abstractions minimize coupling

### Risk 5: Backend Abstraction Overhead

**Probability**: Low
**Impact**: Low
**Mitigation**:
- Thin wrapper (delegation pattern)
- Benchmark performance before/after
- Protocol has zero runtime cost

## Acceptance Test Scenarios

### Scenario 1: Merged Features Work

```bash
# On main v0.8.0 branch after merge
$ make docker-build  # From impl/remote-mcp-deployment
$ make test          # Admin operations from main v0.7.0
# Both should succeed
```

### Scenario 2: Backend Abstraction Transparent

```python
# In any MCP tool on v0.8.0
from quilt_mcp.backends import get_backend

backend = get_backend()  # Returns Quilt3Backend by default
packages = backend.list_packages(registry="s3://my-bucket")
# Works identically to v0.7.0 behavior
```

### Scenario 3: Admin Operations Preserved

```python
# Admin functionality from main v0.7.0
from quilt_mcp.backends import get_backend

backend = get_backend()
users = backend.list_users()  # Admin operation from main
# Works through abstraction layer
```

### Scenario 4: Containerization Works

```bash
# Docker deployment from impl/remote-mcp-deployment
$ FASTMCP_TRANSPORT=http docker run quilt-mcp-server
# Container starts with HTTP transport
```

### Scenario 5: Future Merge is Clean

```bash
# After v0.8.0, make change in impl/remote-mcp-deployment
$ git checkout impl/remote-mcp-deployment
$ # Make deployment improvement
$ git commit -m "feat: improve docker caching"

# Merge to main should be clean
$ git checkout main
$ git merge impl/remote-mcp-deployment
# No conflicts due to backend abstraction
```

## Appendix: Feature Inventory

### From `impl/remote-mcp-deployment` (+26 commits)

**Must Include in v0.8.0**:
- Docker container support (Dockerfile, scripts)
- Multi-transport support (stdio, HTTP, SSE)
- CORS middleware for HTTP clients
- Session ID handling
- Terraform ECS deployment module
- Docker build automation
- Container health checks
- Remote deployment documentation
- HTTP proxy configuration
- SSE streaming support

### From `main` v0.7.0

**Must Preserve in v0.8.0**:
- Complete QuiltService (1,281 lines)
- User management (10 methods)
- Role management (4 methods)
- SSO configuration (3 methods)
- Tabulator administration (6 methods)
- Package operations (delete_package, etc.)
- Dynamic admin credential checking
- Comprehensive test coverage
- Admin tool registration filtering

### New in v0.8.0

**Must Add**:
- `QuiltBackend` protocol definition
- `Quilt3Backend` implementation
- `get_backend()` factory function
- Backend abstraction documentation
- Merge strategy documentation
- Updated architecture diagrams
- Migration guide for future backends

## Success Metrics

1. **Merge Success**: v0.8.0 on `main` includes 100% of identified features from both branches
2. **Test Pass Rate**: 100% of existing tests pass on merged branch
3. **Coverage**: Maintain ≥85% test coverage through merge
4. **Performance**: Backend abstraction adds <5% overhead
5. **Documentation**: Complete merge strategy and architecture docs
6. **Future Merges**: Demonstrate clean merge from `impl/remote-mcp-deployment` after v0.8.0

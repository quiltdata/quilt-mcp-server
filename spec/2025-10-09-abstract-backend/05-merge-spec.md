<!-- markdownlint-disable MD013 -->
# Merge Specification - Backend Abstraction to Main

**Parent Specification**: [04-phases.md](./04-phases.md)
**Date**: 2025-10-10
**Branch**: `2025-10-09-abstract-backend` → `main`

## Executive Summary

This document specifies the merge strategy for integrating the backend abstraction work (v0.8.0) from the `2025-10-09-abstract-backend` branch into `main`. The backend abstraction branch diverged from main at commit `5ea1f04` (after v0.6.12) and needs to incorporate changes from main's v0.7.0-v0.7.2 releases while preserving all backend abstraction work.

**Key Challenge**: Main has progressed from v0.6.12 → v0.7.2 (3 releases) while the backend abstraction branch implemented v0.8.0 features. We need to merge these parallel development streams into a unified v0.8.0 release.

## Divergence Analysis

### Common Ancestor
- **Commit**: `5ea1f04` - "fix: include MCPB file directly in GitHub release assets (#194)"
- **Date**: Immediately after v0.6.12 release
- **State**: Both branches share this foundation

### Main Branch Progress (v0.6.12 → v0.7.2)

**v0.6.13** (2025-09-22):
- Docker container support with HTTP transport
- FastMCP transport flexibility (`FASTMCP_TRANSPORT` environment variable)
- ECR publishing automation
- Docker developer tooling (`make docker-build`, `make docker-run`, `make docker-test`)

**v0.6.14** (2025-09-24):
- Health check endpoint (`/health`) for container orchestration
- Transport-aware endpoint registration

**v0.7.0** (Unreleased on main, tagged):
- **Major architectural overhaul**: QuiltService refactoring (Issue #155)
- 27 new operational methods (user management, role management, SSO, tabulator admin)
- Dynamic admin credential checking via `has_admin_credentials()`
- MCP Resource Framework (9 resource providers)
- Tool consolidation - list functions migrated to MCP resources
- Removed module getter anti-patterns
- **Breaking changes**: No backward compatibility for removed functions

**v0.7.1** (2025-09-XX):
- Production deployment bug fixes
- Athena query fixes for hyphenated database names

**v0.7.2** (Latest on main):
- Additional stability improvements
- `uv.lock` updates

### Backend Abstraction Branch (v0.8.0)

Diverged at v0.6.12, implemented:
- **Backend abstraction layer**: Complete protocol-based architecture
- `QuiltBackend` protocol (31 methods)
- `Quilt3Backend` implementation wrapping QuiltService
- `get_backend()` factory with environment-based selection
- All 20 tool files migrated to use backend abstraction
- Admin operations integration (governance, tabulator)
- 92 new BDD tests for backend abstraction
- Zero performance impact (<5% overhead)

**Also includes Docker/HTTP work from merge with `impl/feature-docker-container`**:
- Docker support
- HTTP transport
- Health check endpoint
- CORS middleware
- SSE transport support

## Conflict Areas

### 1. Version Number (HIGH PRIORITY)
**File**: `pyproject.toml`
- **Main**: `version = "0.7.2"`
- **Branch**: `version = "0.6.13"`
- **Resolution**: Use `0.8.0` (backend abstraction is a major feature release)

### 2. CHANGELOG.md (HIGH PRIORITY)
**Conflict Type**: Both branches added substantial content at the top
- **Main**: v0.7.0, v0.6.14, v0.6.13 entries
- **Branch**: v0.8.0 entry (backend abstraction + Docker)
- **Resolution**: Combine entries, reorder versions chronologically

### 3. PyTest Configuration (MINOR)
**File**: `pyproject.toml`
- **Main**: `asyncio_mode = "auto"` (flat in pytest.ini_options)
- **Branch**: `[tool.pytest.ini_options.asyncio]` section with `mode = "auto"`
- **Resolution**: Keep main's approach (simpler, equivalent)

### 4. Scripts (POTENTIAL)
**Files**: `scripts/docker.py`, `scripts/tests/test_scripts.py`
- **Main**: May have updates from v0.7.x work
- **Branch**: Has Docker implementation work
- **Resolution**: Review both, prefer branch's Docker implementation if more complete

### 5. Makefiles (POTENTIAL)
**Files**: `Makefile`, `make.dev`, `make.deploy`
- **Main**: May have updates for v0.7.x features
- **Branch**: Has Docker-related targets
- **Resolution**: Merge both sets of targets

## Merge Strategy

### Phase 1: Preparation (Pre-Merge Analysis)

#### 1.1 Create Test Branch
```bash
# From 2025-10-09-abstract-backend branch
git checkout -b merge/backend-to-main
```

#### 1.2 Attempt Test Merge
```bash
# Test merge to identify all conflicts
git merge main --no-commit --no-ff
```

#### 1.3 Document All Conflicts
- List all conflicting files
- Categorize by severity (high/medium/low)
- Identify auto-mergeable vs. manual resolution needed

### Phase 2: Conflict Resolution

#### 2.1 Version Number Resolution
**File**: `pyproject.toml`

**Strategy**: Set version to `0.8.0`

**Rationale**:
- Backend abstraction is a major architectural change (warrants minor version bump)
- Incorporates all v0.7.x changes plus new features
- Clear semantic versioning: v0.8.0 > v0.7.2

**Implementation**:
```toml
[project]
name = "quilt-mcp"
version = "0.8.0"
```

#### 2.2 CHANGELOG Resolution
**File**: `CHANGELOG.md`

**Strategy**: Combine and reorder entries

**Structure**:
```markdown
## [0.8.0] - 2025-10-10

### Added - Backend Abstraction
[Keep all v0.8.0 backend abstraction content from branch]

### Added - Docker Support (from v0.6.13)
[Incorporate Docker support from main v0.6.13]

### Added - Health Check (from v0.6.14)
[Incorporate health check from main v0.6.14]

### Added - QuiltService Refactoring (from v0.7.0)
[Incorporate major refactoring work from main v0.7.0]

### Changed
[Merge changes from all versions]

### Removed
[Merge removals from all versions]

## [0.7.2] - [Date]
[Keep from main - historical record]

## [0.7.1] - [Date]
[Keep from main - historical record]

## [0.7.0] - [Date]
[Keep from main - historical record]

## [0.6.14] - 2025-09-24
[Keep from main - historical record]

## [0.6.13] - 2025-09-22
[Keep from main - historical record]

[Continue with earlier versions...]
```

**Rationale**:
- v0.8.0 encompasses all features from v0.7.x plus backend abstraction
- Historical v0.7.x entries preserved for version history clarity
- Chronological ordering maintained
- All features properly attributed

#### 2.3 PyTest Configuration Resolution
**File**: `pyproject.toml`

**Strategy**: Use main's flat configuration

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Rationale**:
- Simpler configuration structure
- Functionally equivalent to nested section
- Consistent with pytest best practices

#### 2.4 Scripts Resolution
**Files**: `scripts/docker.py`, `scripts/tests/test_scripts.py`, others

**Strategy**:
1. Review both versions of each changed script
2. Prefer branch version if it includes Docker implementation
3. Cherry-pick any bug fixes from main's versions
4. Ensure all tests pass after merge

**Implementation**:
```bash
# For each conflicting script:
git show main:scripts/docker.py > /tmp/main-version.py
git show HEAD:scripts/docker.py > /tmp/branch-version.py
diff /tmp/main-version.py /tmp/branch-version.py

# Make informed decision based on diff
# Prefer branch, but incorporate main's bug fixes if any
```

#### 2.5 Makefile Resolution
**Files**: `Makefile`, `make.dev`, `make.deploy`

**Strategy**: Union merge - combine targets from both branches

**Implementation**:
1. Keep all Docker targets from branch
2. Keep all v0.7.x targets from main
3. Resolve duplicate targets by preferring more recent implementation
4. Ensure `make help` displays all targets correctly
5. Test key targets after merge

### Phase 3: QuiltService Compatibility Check

#### 3.1 Admin Methods Integration

**Critical Check**: Main's v0.7.0 added 27 admin methods to QuiltService

**Verification Required**:
- Confirm `Quilt3Backend` exposes all 27 admin methods
- Verify admin credential checking works through backend abstraction
- Ensure MCP resource framework integrates with backend abstraction

**Files to Check**:
- `src/quilt_mcp/backends/protocol.py` - Should include admin methods
- `src/quilt_mcp/backends/quilt3_backend.py` - Should delegate admin methods
- `src/quilt_mcp/services/quilt_service.py` - Should have admin methods from v0.7.0

**Test Strategy**:
```bash
# After merge, verify admin operations work:
make test-unit  # Run all unit tests
grep -r "list_users\|create_user" tests/unit/backends/  # Verify admin method tests exist
```

#### 3.2 MCP Resources Compatibility

**Check**: Main's v0.7.0 introduced MCP Resource Framework

**Verification**:
- Confirm MCP resources work with backend abstraction
- Verify resource providers use `get_backend()` instead of direct QuiltService
- Ensure resource URIs resolve correctly

**Files to Check**:
- `src/quilt_mcp/resources/` - Should exist from main
- Resources should use backend abstraction pattern

**Migration Needed**:
If MCP resources still use direct `QuiltService()`:
```python
# Before (main v0.7.0):
service = QuiltService()
users = service.list_users()

# After (v0.8.0):
backend = get_backend()
users = backend.list_users()
```

### Phase 4: Testing and Validation

#### 4.1 Pre-Merge Test Suite
```bash
# On merge/backend-to-main branch after conflict resolution

# Unit tests
make test-unit

# Integration tests
make test-integration

# Full test suite
make test

# Coverage check
make coverage

# Linting
make lint
```

**Success Criteria**:
- ✅ All unit tests pass (750+ tests)
- ✅ All integration tests pass
- ✅ Coverage ≥85%
- ✅ No linting errors
- ✅ Type checking passes

#### 4.2 Functional Validation

**Key Operations to Test**:
1. **Backend Abstraction**:
   - Environment variable switching (`QUILT_BACKEND=quilt3`)
   - Tool operations through backend
   - Admin operations through backend

2. **Docker Support**:
   - `make docker-build`
   - `make docker-run`
   - Health check endpoint

3. **Admin Operations** (from v0.7.0):
   - User management through backend
   - Role management through backend
   - MCP resources with backend

4. **Core Functionality**:
   - Package listing
   - Package creation
   - Bucket operations
   - Search operations

#### 4.3 Documentation Validation

**Files to Review**:
- `README.md` - Should mention v0.8.0 features
- `CHANGELOG.md` - Should have complete v0.8.0 entry
- `docs/` - Should document backend abstraction
- `spec/2025-10-09-abstract-backend/` - Should be complete

### Phase 5: Merge Execution

#### 5.1 Final Merge Steps
```bash
# Ensure merge branch is clean and tested
git checkout merge/backend-to-main
make test  # Final test run
make lint  # Final lint check

# Merge to main
git checkout main
git merge --no-ff merge/backend-to-main -m "feat: Release v0.8.0 - Backend Abstraction Layer

Complete architectural refactoring introducing backend abstraction layer
while incorporating all v0.7.x improvements (QuiltService refactoring,
Docker support, health checks).

- Backend abstraction layer with QuiltBackend protocol
- All tools migrated to use get_backend()
- Admin operations integration through abstraction
- Docker container support with HTTP transport
- Health check endpoint for orchestration
- MCP Resource Framework integration
- 92 new BDD tests, zero regressions

Closes #158, #208
Incorporates v0.7.0-v0.7.2 features from main

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

#### 5.2 Post-Merge Validation
```bash
# On main branch after merge
make test       # Verify all tests pass
make coverage   # Verify coverage ≥85%
make lint       # Verify no linting issues

# Tag the release
git tag v0.8.0 -m "Release v0.8.0 - Backend Abstraction Layer"
git push origin main --tags
```

#### 5.3 Release Creation
```bash
# Create GitHub release
gh release create v0.8.0 \
  --title "v0.8.0 - Backend Abstraction Layer" \
  --notes-file CHANGELOG.md \
  --latest

# CI/CD will handle:
# - Building MCPB package
# - Publishing to PyPI
# - Building and pushing Docker image
```

## Risk Mitigation

### Risk 1: QuiltService Method Mismatch
**Risk**: Main's v0.7.0 QuiltService has methods that backend abstraction doesn't know about

**Mitigation**:
- Review main's QuiltService API comprehensively
- Update `QuiltBackend` protocol if missing methods found
- Update `Quilt3Backend` to delegate new methods
- Add tests for any newly discovered methods

**Detection**:
```bash
# Compare QuiltService methods between branches
grep -E "^\s+def " src/quilt_mcp/services/quilt_service.py | wc -l  # Count methods
```

### Risk 2: Test Failures Post-Merge
**Risk**: Merged code has incompatibilities causing test failures

**Mitigation**:
- Comprehensive pre-merge testing on `merge/backend-to-main`
- Fix all tests before merging to main
- Keep merge branch for debugging if issues found

**Recovery**:
```bash
# If tests fail on main after merge
git revert HEAD  # Revert the merge commit
# Fix on merge/backend-to-main
# Re-test thoroughly
# Attempt merge again
```

### Risk 3: Performance Regression
**Risk**: Combined features cause performance issues

**Mitigation**:
- Run performance benchmarks pre and post-merge
- Compare backend abstraction overhead measurements
- Profile critical paths if slowdowns detected

**Validation**:
```bash
# Performance benchmarks (if implemented)
pytest tests/performance/ -v
```

### Risk 4: Docker/Health Check Integration Issues
**Risk**: Docker features from main conflict with branch's Docker implementation

**Mitigation**:
- Test Docker build and run after merge
- Verify health check endpoint works
- Ensure HTTP transport configuration correct

**Validation**:
```bash
make docker-test  # Run Docker integration tests
```

## Success Criteria

### Functional Success
- ✅ All 750+ tests pass on merged main
- ✅ Backend abstraction works (environment variable switching)
- ✅ Docker support works (`make docker-build`, `make docker-run`)
- ✅ Health check endpoint responds correctly
- ✅ Admin operations work through backend abstraction
- ✅ MCP resources work with backend abstraction

### Quality Success
- ✅ Code coverage ≥85%
- ✅ No linting errors (ruff passes)
- ✅ Type checking passes (mypy/pyright)
- ✅ No IDE diagnostics errors
- ✅ Performance overhead <5% (backend abstraction)

### Documentation Success
- ✅ CHANGELOG.md complete with v0.8.0 entry
- ✅ README.md references v0.8.0
- ✅ Specification documents complete
- ✅ Migration guides available

### Release Success
- ✅ Version tagged as v0.8.0
- ✅ GitHub release created
- ✅ MCPB package published
- ✅ PyPI package published
- ✅ Docker image pushed to ECR

## Timeline

**Estimated Duration**: 4-6 hours

| Phase | Duration | Activities |
|-------|----------|------------|
| Phase 1: Preparation | 1 hour | Create merge branch, test merge, document conflicts |
| Phase 2: Conflict Resolution | 2-3 hours | Resolve all conflicts methodically |
| Phase 3: Compatibility Check | 1 hour | Verify QuiltService compatibility, MCP resources |
| Phase 4: Testing & Validation | 1-2 hours | Run full test suite, functional validation |
| Phase 5: Merge Execution | 30 min | Final merge, tag, release creation |

## Checklist

### Pre-Merge
- [ ] Create `merge/backend-to-main` branch
- [ ] Test merge with `git merge main --no-commit --no-ff`
- [ ] Document all conflicts
- [ ] Resolve version number to `0.8.0`
- [ ] Merge CHANGELOG entries
- [ ] Resolve pytest configuration
- [ ] Review and resolve script conflicts
- [ ] Review and resolve Makefile conflicts

### Compatibility Verification
- [ ] Verify `Quilt3Backend` has all 27 admin methods from v0.7.0
- [ ] Verify MCP resources use backend abstraction
- [ ] Verify admin credential checking works
- [ ] Check no direct QuiltService imports in tools
- [ ] Review QuiltService API for missing methods

### Testing
- [ ] Run `make test-unit` - all pass
- [ ] Run `make test-integration` - all pass
- [ ] Run `make test` - full suite passes
- [ ] Run `make coverage` - ≥85%
- [ ] Run `make lint` - no errors
- [ ] Test Docker build (`make docker-build`)
- [ ] Test Docker run (`make docker-run`)
- [ ] Test health check endpoint
- [ ] Test backend switching (`QUILT_BACKEND=quilt3`)

### Functional Validation
- [ ] Package listing works
- [ ] Package creation works
- [ ] Bucket operations work
- [ ] Search operations work
- [ ] Admin user management works
- [ ] Admin role management works
- [ ] MCP resources accessible

### Documentation
- [ ] CHANGELOG.md updated with v0.8.0 entry
- [ ] Version history preserved (v0.7.0-v0.7.2)
- [ ] README.md references v0.8.0
- [ ] Specification documents complete

### Merge Execution
- [ ] Checkout main branch
- [ ] Merge with `--no-ff` and descriptive commit message
- [ ] Run `make test` on main
- [ ] Run `make coverage` on main
- [ ] Run `make lint` on main
- [ ] Tag release `v0.8.0`
- [ ] Push main with tags
- [ ] Create GitHub release
- [ ] Verify CI/CD publishes packages

## Post-Merge Actions

### Immediate
1. Monitor CI/CD pipelines for successful builds
2. Verify PyPI package published
3. Verify Docker image in ECR
4. Update project board/issues

### Follow-Up
1. Announce v0.8.0 release
2. Update documentation site (if exists)
3. Archive merge branch after 30 days
4. Delete merge branch after 90 days

## Appendix A: Key File Conflicts

### High Priority Conflicts

#### `pyproject.toml`
- **Lines**: 1-10 (version and metadata)
- **Resolution**: Version to `0.8.0`, asyncio config from main

#### `CHANGELOG.md`
- **Lines**: 1-200 (top entries)
- **Resolution**: Combine all version entries, chronological order

### Medium Priority Conflicts

#### `Makefile`, `make.dev`, `make.deploy`
- **Resolution**: Union merge of targets

#### `scripts/docker.py`
- **Resolution**: Prefer branch, incorporate main bug fixes

### Low Priority Conflicts

#### `scripts/tests/test_scripts.py`
- **Resolution**: Combine test cases from both

## Appendix B: Backend Protocol Completeness Check

**Required Methods** (from v0.7.0 QuiltService):

**User Management** (10):
- `list_users()`
- `get_user(username)`
- `create_user(username, email, ...)`
- `delete_user(username)`
- `set_user_email(username, email)`
- `set_user_role(username, role)`
- `set_user_active(username, active)`
- `set_user_admin(username, admin)`
- `add_user_roles(username, roles)`
- `remove_user_roles(username, roles)`

**Role Management** (4):
- `list_roles()`
- `get_role(role_name)`
- `create_role(role_name, ...)`
- `delete_role(role_name)`

**SSO Configuration** (3):
- `get_sso_config()`
- `set_sso_config(config)`
- `remove_sso_config()`

**Tabulator Administration** (6):
- `get_tabulator_access()`
- `set_tabulator_access(enabled)`
- `list_tabulator_tables(bucket)`
- `create_tabulator_table(bucket, table_name, ...)`
- `delete_tabulator_table(bucket, table_name)`
- `rename_tabulator_table(bucket, old_name, new_name)`

**Verification Command**:
```bash
# Check protocol includes these methods
grep -E "^\s+def (list_users|get_user|create_user|list_roles|get_sso_config|list_tabulator_tables)" \
  src/quilt_mcp/backends/protocol.py
```

## Appendix C: MCP Resources Migration Pattern

If MCP resources need migration to backend abstraction:

```python
# Before (main v0.7.0):
from quilt_mcp.services.quilt_service import QuiltService

class AdminUsersResource:
    def fetch(self):
        service = QuiltService()
        return service.list_users()

# After (v0.8.0):
from quilt_mcp.backends import get_backend

class AdminUsersResource:
    def fetch(self):
        backend = get_backend()
        return backend.list_users()
```

**Files to Check**:
- `src/quilt_mcp/resources/*.py` - All resource providers
- Search for `QuiltService()` instantiation
- Replace with `get_backend()`

## Notes for Human Review

**Critical Decision Points**:

1. **Version Number**: Confirmed v0.8.0 is appropriate
   - Backend abstraction is a major architectural change
   - Incorporates all v0.7.x improvements
   - Clear semantic versioning progression

2. **CHANGELOG Structure**: Preserving v0.7.x history
   - Users upgrading from v0.7.2 need migration path
   - v0.8.0 encompasses all v0.7.x features
   - Historical entries preserved for clarity

3. **QuiltService Compatibility**: Must verify admin methods
   - v0.7.0 added 27 admin methods
   - Backend protocol must expose all of them
   - Critical for admin operations functionality

4. **MCP Resources**: May need migration
   - v0.7.0 introduced MCP resource framework
   - Resources likely use direct QuiltService
   - Should migrate to use `get_backend()`

**Questions for Review**:
- Is v0.8.0 the appropriate version number?
- Should v0.7.x versions be preserved in CHANGELOG?
- Are there other files we should check for conflicts?
- Should we create a migration guide for v0.7.x → v0.8.0?

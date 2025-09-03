# GitHub Actions Optimization Implementation Checklist

> **Reference**: This checklist implements the optimal structure defined in [spec/a02-github-actions-optimal-structure.md](spec/a02-github-actions-optimal-structure.md)

## Phase 1: Critical Fixes (Immediate - Day 1)

### ✅ Task 1.1: Fix staging-deploy.yml Path References

**Priority**: CRITICAL (workflow currently fails)

- [ ] **1.1.a** Update `staging-deploy.yml` line 118: `cd build-dxt` → `cd tools/dxt`
- [ ] **1.1.b** Update `staging-deploy.yml` line 123: `cd build-dxt` → `cd tools/dxt`  
- [ ] **1.1.c** Update `staging-deploy.yml` line 128: `cd build-dxt` → `cd tools/dxt`
- [ ] **1.1.d** Update `staging-deploy.yml` line 194: `cd build-dxt` → `cd tools/dxt`
- [ ] **1.1.e** Update artifact paths: `build-dxt/dist/` → `tools/dxt/dist/`
- [ ] **1.1.f** Test staging workflow runs without path errors

**Acceptance Criteria**:

- [ ] `staging-deploy.yml` workflow completes successfully
- [ ] All DXT operations reference correct `tools/dxt/` directory
- [ ] No references to obsolete `build-dxt` directory remain

**Files to Modify**: `.github/workflows/staging-deploy.yml`

---

### ✅ Task 1.2: Standardize Package Manager to UV

**Priority**: HIGH (consistency and performance)

- [ ] **1.2.a** Replace pip setup in `staging-deploy.yml` lines 57-59 with uv setup
- [ ] **1.2.b** Replace pip installation commands with uv equivalents
- [ ] **1.2.c** Update Python installation to use `uv python install`
- [ ] **1.2.d** Replace manual uv installation (lines 103-105) with `astral-sh/setup-uv@v3`
- [ ] **1.2.e** Standardize Python version to 3.11 for DXT operations
- [ ] **1.2.f** Test all workflows use consistent dependency management

**Acceptance Criteria**:

- [ ] All workflows use `astral-sh/setup-uv@v3` action
- [ ] No pip commands remain in any workflow
- [ ] Dependency installation is faster and more reliable
- [ ] All workflows complete successfully with uv

**Files to Modify**: `.github/workflows/staging-deploy.yml`

---

### ✅ Task 1.3: Create Setup Environment Composite Action

**Priority**: MEDIUM (foundation for further optimization)

- [ ] **1.3.a** Create directory `.github/actions/setup-environment/`
- [ ] **1.3.b** Create `action.yml` with inputs for python-version, node-version
- [ ] **1.3.c** Implement standardized setup steps:
  - Checkout (optional)
  - Install uv
  - Set up Python
  - Set up Node.js (optional)
  - Install DXT CLI (optional)
- [ ] **1.3.d** Add timeout configurations for each step
- [ ] **1.3.e** Test composite action in staging workflow
- [ ] **1.3.f** Update one workflow to use composite action

**Acceptance Criteria**:

- [ ] Reusable composite action reduces setup duplication
- [ ] Action works with different Python/Node versions
- [ ] Setup time is equivalent or faster than individual steps
- [ ] Action includes proper error handling and timeouts

**Files to Create**:

- `.github/actions/setup-environment/action.yml`

---

## Phase 2: Structure Optimization (Week 1)

### ✅ Task 2.1: Create DXT Build Composite Action

**Priority**: HIGH (eliminate DXT duplication)

- [ ] **2.1.a** Create directory `.github/actions/build-dxt/`
- [ ] **2.1.b** Create `action.yml` with inputs:
  - `operation`: build, test, validate, release
  - `version`: optional version override
  - `working-directory`: default to repository root
- [ ] **2.1.c** Implement operations using top-level Makefile:
  - `make dxt` for building
  - `make validate-dxt` for validation  
  - `make test-dxt` for testing (when available)
- [ ] **2.1.d** Add artifact collection for DXT packages
- [ ] **2.1.e** Include proper error handling and logging
- [ ] **2.1.f** Test with both `dxt.yml` and `staging-deploy.yml`

**Acceptance Criteria**:

- [ ] Single action handles all DXT operations consistently
- [ ] Both workflows use same composite action
- [ ] DXT build time is equivalent or faster
- [ ] Error messages are clear and actionable

**Files to Create**:

- `.github/actions/build-dxt/action.yml`

---

### ✅ Task 2.2: Implement Centralized Configuration

**Priority**: MEDIUM (foundation for maintainability)

- [ ] **2.2.a** Create `.github/config/shared-config.yml`
- [ ] **2.2.b** Define standard Python version matrix:
  - Unit tests: `["3.11", "3.12", "3.13"]`
  - Integration tests: `["3.11", "3.12"]`
  - Production: `"3.11"`
- [ ] **2.2.c** Define standard timeouts for all operations
- [ ] **2.2.d** Define Node.js version: `"18"`
- [ ] **2.2.e** Document secret organization and usage patterns
- [ ] **2.2.f** Create helper script to read config in workflows

**Acceptance Criteria**:

- [ ] Single source of truth for all version configurations
- [ ] Easy to update Python/Node versions across all workflows
- [ ] Configuration is documented and version controlled
- [ ] Helper utilities make config consumption simple

**Files to Create**:

- `.github/config/shared-config.yml`
- `.github/scripts/read-config.sh` (optional)

---

### ✅ Task 2.3: Optimize Job Dependencies and Caching

**Priority**: MEDIUM (performance improvement)

- [ ] **2.3.a** Analyze current job dependency chains
- [ ] **2.3.b** Identify opportunities for parallel execution
- [ ] **2.3.c** Implement consistent caching strategy:
  - uv cache: `~/.cache/uv`
  - pip cache: `~/.cache/pip`
  - npm cache: `~/.npm`
- [ ] **2.3.d** Add cache keys based on lock files and OS
- [ ] **2.3.e** Update job dependencies for optimal parallelism
- [ ] **2.3.f** Measure and document performance improvements

**Acceptance Criteria**:

- [ ] Workflow execution time reduced by 20-30%
- [ ] Jobs run in parallel where possible
- [ ] Cache hit rates >80% for dependency installation
- [ ] No unnecessary job blocking relationships

**Files to Modify**: All workflow files

---

## Phase 3: Advanced Features (Week 2)

### ✅ Task 3.1: Create Test Execution Composite Action

**Priority**: MEDIUM (standardize testing)

- [ ] **3.1.a** Create directory `.github/actions/run-tests/`
- [ ] **3.1.b** Create `action.yml` with inputs:
  - `test-type`: unit, integration, aws, search, all
  - `coverage-required`: boolean, default true
  - `timeout-minutes`: configurable timeout
  - `python-version`: default from config
- [ ] **3.1.c** Implement test execution logic
- [ ] **3.1.d** Add coverage reporting and artifact upload
- [ ] **3.1.e** Include secret injection for AWS/Quilt config
- [ ] **3.1.f** Test with multiple test types and configurations

**Acceptance Criteria**:

- [ ] Single action handles all test execution patterns
- [ ] Consistent test reporting across workflows
- [ ] Proper secret handling and environment setup
- [ ] Coverage reporting works reliably

**Files to Create**:

- `.github/actions/run-tests/action.yml`

---

### ✅ Task 3.2: Implement Enhanced Monitoring

**Priority**: LOW (observability improvement)

- [ ] **3.2.a** Create directory `.github/actions/notify-team/`
- [ ] **3.2.b** Create notification composite action
- [ ] **3.2.c** Add failure notifications to all critical workflows
- [ ] **3.2.d** Implement performance monitoring and alerts
- [ ] **3.2.e** Add workflow duration tracking
- [ ] **3.2.f** Create dashboard or summary reporting

**Acceptance Criteria**:

- [ ] Team receives timely notifications on workflow failures
- [ ] Performance regressions are detected automatically
- [ ] Workflow health metrics are tracked over time
- [ ] Notification fatigue is minimized with smart filtering

**Files to Create**:

- `.github/actions/notify-team/action.yml`

---

### ✅ Task 3.3: Optimize Artifact Management

**Priority**: LOW (cleanup and organization)

- [ ] **3.3.a** Audit current artifact usage and retention
- [ ] **3.3.b** Implement standardized artifact naming conventions
- [ ] **3.3.c** Set appropriate retention policies:
  - Test results: 7 days
  - Coverage reports: 30 days
  - DXT packages: 90 days
  - Release artifacts: permanent
- [ ] **3.3.d** Create artifact cleanup automation
- [ ] **3.3.e** Implement artifact compression where appropriate
- [ ] **3.3.f** Add artifact download links to PR comments

**Acceptance Criteria**:

- [ ] Storage costs reduced through appropriate retention
- [ ] Artifacts are well-organized and easily discoverable
- [ ] No storage space issues from abandoned artifacts
- [ ] Download experience is improved for developers

**Files to Modify**: All workflows with artifact uploads

---

## Phase 4: Documentation & Validation (Week 3)

### ✅ Task 4.1: Update Workflow Documentation

**Priority**: HIGH (maintainability)

- [ ] **4.1.a** Document each workflow's purpose and triggers
- [ ] **4.1.b** Create troubleshooting guide for common failures
- [ ] **4.1.c** Document secret requirements and setup
- [ ] **4.1.d** Create developer guide for adding new workflows
- [ ] **4.1.e** Update README with workflow status badges
- [ ] **4.1.f** Document performance characteristics and SLAs

**Acceptance Criteria**:

- [ ] New team members can understand and modify workflows
- [ ] Common issues have documented solutions
- [ ] Secret setup process is clearly documented
- [ ] Workflow architecture is well-explained

**Files to Create/Update**:

- `.github/README.md`
- `docs/github-actions-guide.md`
- Update main `README.md`

---

### ✅ Task 4.2: Comprehensive Testing & Validation

**Priority**: CRITICAL (ensure no regressions)

- [ ] **4.2.a** Test all workflows in parallel with existing ones
- [ ] **4.2.b** Validate secret access and permissions
- [ ] **4.2.c** Test failure scenarios and recovery
- [ ] **4.2.d** Validate artifact generation and access
- [ ] **4.2.e** Test cross-workflow dependencies
- [ ] **4.2.f** Performance test with realistic workloads

**Acceptance Criteria**:

- [ ] All workflows complete successfully in test environment
- [ ] No functionality regressions identified
- [ ] Performance meets or exceeds current benchmarks
- [ ] Error handling works as expected

**Validation Steps**: Create test PRs exercising all workflow paths

---

### ✅ Task 4.3: Migration and Cleanup

**Priority**: HIGH (complete the transition)

- [ ] **4.3.a** Create migration plan with rollback strategy
- [ ] **4.3.b** Schedule maintenance window for critical changes
- [ ] **4.3.c** Migrate workflows one by one with validation
- [ ] **4.3.d** Remove deprecated workflow files
- [ ] **4.3.e** Clean up unused secrets and environments
- [ ] **4.3.f** Monitor workflows for 48 hours post-migration

**Acceptance Criteria**:

- [ ] All workflows use optimized structure
- [ ] No legacy code or configurations remain
- [ ] Team is trained on new structure
- [ ] Performance improvements are realized

**Files to Remove**: Old workflow versions (after successful migration)

---

## Pre-Implementation Checklist

Before starting implementation, ensure:

- [ ] **Backup Strategy**: All current workflows are backed up
- [ ] **Testing Environment**: Branch protection allows testing new workflows
- [ ] **Secret Audit**: All required secrets are available and documented
- [ ] **Team Alignment**: Implementation plan is reviewed and approved
- [ ] **Rollback Plan**: Clear process to revert to current workflows if needed

## Success Validation

After each phase, validate:

- [ ] **Functionality**: All workflows complete successfully
- [ ] **Performance**: Build times meet or exceed targets
- [ ] **Reliability**: No increase in failure rates
- [ ] **Maintainability**: Configuration changes are easy to make
- [ ] **Security**: No secret exposure or permission issues

## Risk Mitigation

### High-Risk Areas

1. **Secret Migration**: Test thoroughly in isolated environment
2. **Job Dependencies**: Validate parallel execution doesn't break functionality
3. **Path Changes**: Double-check all file references are updated
4. **Tool Migration**: Ensure uv migration doesn't break any workflows

### Rollback Triggers

- Any workflow failure rate >10%
- Build time increases >50%
- Critical functionality broken
- Security issues identified

### Communication Plan

- [ ] Announce implementation timeline to team
- [ ] Daily updates during migration phases
- [ ] Post-migration review and lessons learned
- [ ] Documentation updates and training completion

---

## Implementation Timeline

| Phase | Duration | Focus | Success Criteria |
|-------|----------|-------|------------------|
| Phase 1 | 1 day | Critical fixes | No broken workflows |
| Phase 2 | 1 week | Structure optimization | Reusable components working |
| Phase 3 | 1 week | Advanced features | Enhanced monitoring active |
| Phase 4 | 1 week | Documentation & validation | Full migration complete |

**Total Duration**: 3-4 weeks
**Effort Level**: Medium (requires careful testing and validation)
**Risk Level**: Medium (high impact changes, but good rollback options)

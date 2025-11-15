# GitHub Actions Single Workflow Migration Checklist

> **Reference**: This checklist migrates from the current 5 workflows to the single workflow defined in [spec/a02-github-actions-optimal-structure.md](a02-github-actions-optimal-structure.md)

## Current State Issues

- ❌ **5 separate workflows** with duplicated setup logic
- ❌ `staging-deploy.yml` uses obsolete `build-dxt` paths → broken
- ❌ `staging-deploy.yml` uses `pip` instead of `uv` → inconsistent tooling
- ❌ Complex develop→staging→main branch flow adds overhead
- ❌ Python/Node setup repeated 15+ times across workflows
- ❌ Secret configuration duplicated in every workflow
- ❌ Different Python versions tested in different contexts

## Target State

- ✅ **1 single workflow** (`ci.yml`) handles everything
- ✅ **Conditional execution** based on trigger context
- ✅ **Consistent environment** across all operations
- ✅ **No composite actions** needed
- ✅ **Standard GitHub flow** (feature → main → release)

## Migration Steps

### Phase 1: Deploy New Workflow (Day 1)

#### Create Single Workflow
- [ ] Deploy `ci.yml` to repository
- [ ] Test workflow on feature branch
- [ ] Validate all conditional paths work:
  - [ ] PR → unit tests only
  - [ ] Main push → unit + integration tests
  - [ ] Version tag → full tests + DXT build + release
  - [ ] Manual dispatch → integration tests

#### Validate Functionality
- [ ] Test matrix builds (Python 3.11, 3.12, 3.13)
- [ ] Verify secret access works correctly
- [ ] Test DXT build on version tag
- [ ] Validate GitHub release creation
- [ ] Check artifact uploads work

### Phase 2: Remove Obsolete Workflows (Day 2)

#### Delete Old Workflows
- [ ] Remove `staging-deploy.yml` (broken, obsolete)
- [ ] Remove `nightly-build.yml` (obsolete branch model)
- [ ] Remove `integration-test.yml` (consolidated into ci.yml)
- [ ] Remove `test.yml` (consolidated into ci.yml)
- [ ] Remove `dxt.yml` (consolidated into ci.yml)

#### Clean Up Repository
- [ ] Update branch protection rules if needed
- [ ] Remove any staging branch references
- [ ] Clean up workflow artifacts from old workflows

### Phase 3: Validation (Week 1)

#### Test All Scenarios
- [ ] Create test PR → verify unit tests run
- [ ] Merge to main → verify integration tests run
- [ ] Create version tag → verify full release flow
- [ ] Add `test:integration` label → verify integration tests on PR
- [ ] Test manual workflow dispatch

#### Performance Validation
- [ ] Compare workflow execution times
- [ ] Verify cache hit rates improved
- [ ] Confirm parallel matrix execution works
- [ ] Test failure scenarios and recovery

## Success Criteria

### Functionality
- [ ] All test scenarios pass with single workflow
- [ ] DXT builds and releases work correctly
- [ ] No broken functionality from migration
- [ ] Secret access preserved across all operations

### Performance
- [ ] Reduced total workflow execution time
- [ ] Improved cache utilization
- [ ] Faster feedback on PRs (unit tests only)
- [ ] Efficient resource usage with matrix builds

### Maintainability
- [ ] Single file to maintain instead of 5
- [ ] Consistent environment across all operations
- [ ] Clear conditional logic easy to understand
- [ ] No composite actions to debug

## Rollback Plan

### Triggers
- Single workflow fails for any scenario
- Performance significantly degraded
- Any critical functionality broken

### Process
1. **Immediate**: Re-enable `test.yml` for basic PR testing
2. **Short-term**: Restore other workflows as needed
3. **Analysis**: Debug issues with single workflow approach
4. **Decision**: Fix single workflow or revert to multi-workflow

## Key Benefits Achieved

### Simplification
- **From 5 workflows → 1 workflow**
- **From ~500 lines of YAML → ~130 lines**
- **From complex orchestration → simple conditionals**
- **From inconsistent environments → single consistent setup**

### Performance
- **Shared setup costs** across operations
- **Optimal caching** with single strategy
- **No workflow orchestration overhead**
- **Matrix parallelization** for all operations

### Consistency
- **Same Python versions** for all test types
- **Same environment setup** for all operations
- **Same secret injection** patterns
- **Same caching strategy** throughout

### Developer Experience
- **Single workflow to understand**
- **Clear trigger → action mapping**
- **Fast feedback** with conditional execution
- **Easy debugging** with consolidated logic
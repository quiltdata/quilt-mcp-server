<!-- markdownlint-disable MD013 -->
# Phase 3A Implementation Checklist: Script Migration

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Phase**: 3A - Script Migration  
**Branch**: `100-feature-cleanup-repomake`  
**Based on**: [09-review.md](./09-review.md)

## Overview

This checklist addresses the critical script migration tasks identified in the Phase 3 review. Currently only 1/6 Phase 3A tasks are completed (17% success rate). This checklist ensures systematic completion of all remaining script migration requirements.

## Critical Context

**Current State** (from review):
- ✅ `bin/` directory exists
- ❌ Only `common.sh` in `bin/` (should have 4 scripts)
- ❌ 4 scripts still in `tools/` that should be moved to `bin/`
- ❌ GitHub Actions and Makefile still reference old `tools/` paths

**Impact**: Broken CI/CD pipeline and Makefile targets until completion.

## Phase 3A: Script Migration Tasks

### Task 1: Move check-env.sh → test-prereqs.sh
- [ ] **Action**: `git mv tools/check-env.sh bin/test-prereqs.sh`
- [ ] **Verify**: File exists at `bin/test-prereqs.sh`
- [ ] **Verify**: File no longer exists at `tools/check-env.sh`
- [ ] **Test**: Script executes correctly from new location

### Task 2: Move release.sh → release.sh  
- [ ] **Action**: `git mv tools/release.sh bin/release.sh`
- [ ] **Verify**: File exists at `bin/release.sh`
- [ ] **Verify**: File no longer exists at `tools/release.sh`
- [ ] **Test**: Script executes correctly from new location

### Task 3: Move test-endpoint.sh → test-endpoint.sh
- [ ] **Action**: `git mv tools/test-endpoint.sh bin/test-endpoint.sh`
- [ ] **Verify**: File exists at `bin/test-endpoint.sh`
- [ ] **Verify**: File no longer exists at `tools/test-endpoint.sh`
- [ ] **Test**: Script executes correctly from new location

### Task 4: Move version.sh → version.sh
- [ ] **Action**: `git mv tools/version.sh bin/version.sh`
- [ ] **Verify**: File exists at `bin/version.sh`
- [ ] **Verify**: File no longer exists at `tools/version.sh`
- [ ] **Test**: Script executes correctly from new location

### Task 5: Clean up tools/ directory structure
- [ ] **Verify**: Only `tools/dxt/` directory remains in `tools/`
- [ ] **Action**: Remove empty script files if any remain
- [ ] **Decision**: Keep `tools/` directory (contains `dxt/` from Phase 2)

### Task 6: Update any script cross-references
- [ ] **Check**: Scan all scripts for references to old paths
- [ ] **Update**: Fix any internal script references to moved files
- [ ] **Test**: Verify all scripts work with updated references

## Verification Commands

### Pre-Migration State Check
```bash
ls -la tools/        # Should show: check-env.sh, release.sh, test-endpoint.sh, version.sh, dxt/
ls -la bin/          # Should show: common.sh
```

### Post-Migration State Check  
```bash
ls -la bin/          # Should show: common.sh, test-prereqs.sh, release.sh, test-endpoint.sh, version.sh
ls -la tools/        # Should show: dxt/ (only)
```

### Script Execution Tests
```bash
# Test each script executes without errors
./bin/test-prereqs.sh --help || echo "test-prereqs.sh failed"
./bin/release.sh --help || echo "release.sh failed"
./bin/test-endpoint.sh --help || echo "test-endpoint.sh failed"  
./bin/version.sh || echo "version.sh failed"
```

## Success Criteria

### Functional Requirements
- [ ] All 4 scripts execute correctly from `bin/` location
- [ ] No broken script cross-references
- [ ] All file moves tracked properly in git history

### Organizational Requirements  
- [ ] Scripts located in standard `bin/` directory (not `tools/`)
- [ ] Clean directory structure: `tools/` contains only `dxt/`
- [ ] Proper script renaming: `check-env.sh` → `test-prereqs.sh`

### Quality Requirements
- [ ] 100% of Phase 3A checklist items completed (6/6 tasks)
- [ ] All git moves preserve file history
- [ ] No script functionality broken during migration

## Dependencies

**Blocks**: Phase 3B (Makefile fixes) and Phase 3C (GitHub Actions fixes)  
**Requires**: None - can be executed immediately

## Commit Strategy

```bash
# Single commit with all moves to preserve atomicity
git add .
git commit -m "feat: migrate scripts from tools/ to bin/ (Phase 3A)

- Move check-env.sh → bin/test-prereqs.sh  
- Move release.sh → bin/release.sh
- Move test-endpoint.sh → bin/test-endpoint.sh
- Move version.sh → bin/version.sh
- Preserve tools/dxt/ structure from Phase 2
- All scripts tested and functional in new locations

Resolves Phase 3A requirements from issue #100"
```

## Next Steps

After Phase 3A completion:
1. **Phase 3B**: Fix Makefile references in `make.deploy`
2. **Phase 3C**: Fix GitHub Actions path references  
3. **Integration Testing**: Verify complete workflow functionality

---

**Status**: Ready for execution  
**Risk Level**: Low (file moves with git history preservation)  
**Estimated Time**: 15 minutes
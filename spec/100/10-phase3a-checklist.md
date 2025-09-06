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

- [x] **Action**: `git mv tools/check-env.sh bin/test-prereqs.sh`
- [x] **Verify**: File exists at `bin/test-prereqs.sh`
- [x] **Verify**: File no longer exists at `tools/check-env.sh`
- [x] **Test**: Script executes correctly from new location

### Task 2: Move release.sh → release.sh  

- [x] **Action**: `git mv tools/release.sh bin/release.sh`
- [x] **Verify**: File exists at `bin/release.sh`
- [x] **Verify**: File no longer exists at `tools/release.sh`
- [x] **Test**: Script executes correctly from new location

### Task 3: Move test-endpoint.sh → test-endpoint.sh

- [x] **Action**: `git mv tools/test-endpoint.sh bin/test-endpoint.sh`
- [x] **Verify**: File exists at `bin/test-endpoint.sh`
- [x] **Verify**: File no longer exists at `tools/test-endpoint.sh`
- [x] **Test**: Script executes correctly from new location

### Task 4: Move version.sh → version.sh

- [x] **Action**: `git mv tools/version.sh bin/version.sh`
- [x] **Verify**: File exists at `bin/version.sh`
- [x] **Verify**: File no longer exists at `tools/version.sh`
- [x] **Test**: Script executes correctly from new location

### Task 5: Clean up tools/ directory structure

- [x] **Verify**: Only `tools/dxt/` directory remains in `tools/`
- [x] **Action**: Remove empty script files if any remain
- [x] **Decision**: Keep `tools/` directory (contains `dxt/` from Phase 2)

### Task 6: Update any script cross-references

- [x] **Check**: Scan all scripts for references to old paths
- [x] **Update**: Fix any internal script references to moved files
- [x] **Test**: Verify all scripts work with updated references

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

- [x] All 4 scripts execute correctly from `bin/` location
- [x] No broken script cross-references
- [x] All file moves tracked properly in git history

### Organizational Requirements  

- [x] Scripts located in standard `bin/` directory (not `tools/`)
- [x] Clean directory structure: `tools/` contains only `dxt/`
- [x] Proper script renaming: `check-env.sh` → `test-prereqs.sh`

### Quality Requirements

- [x] 100% of Phase 3A checklist items completed (6/6 tasks)
- [x] All git moves preserve file history
- [x] No script functionality broken during migration

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

**Status**: ✅ COMPLETED  
**Risk Level**: Low (file moves with git history preservation)  
**Completion Time**: All tasks completed successfully

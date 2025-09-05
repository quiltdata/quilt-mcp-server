<!-- markdownlint-disable MD013 -->
# Phase 3 Implementation Checklist: Fix Broken GitHub Actions & Script Organization

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Based on**: [07-phase3-design.md](./07-phase3-design.md)  
**Implementation Branch**: `100c-phase3-fix-actions`

## Overview

This checklist implements Phase 3: fixing broken GitHub Actions that reference non-existent `tools/dxt/` paths and duplicate Makefile logic. Move scripts to `bin/` and eliminate CI/CD duplication.

**Execution Notes:**

- Commit after every phase
- Test after every commit (and fix if needed)  
- Total estimated time: 45 minutes

## Step 1: Pre-Implementation Validation

### Verify Current State

- [ ] **Check script locations**: `ls -la tools/` (should show 4 scripts)
- [ ] **Test script execution**: `./tools/check-env.sh --help` (should work)
- [ ] **Find broken Actions**: `grep -r "tools/dxt" .github/` (should show broken references)
- [ ] **Test Makefile targets**: `make release-package` (should work locally)

### Create Implementation Branch

- [ ] **Create branch**: `git checkout -b 100c-phase3-fix-actions`
- [ ] **Verify branch**: `git branch` (should show new branch active)

## Step 2: Script Migration (Phase A)

### Move Scripts to bin/

- [ ] **Create bin/ directory**: `mkdir bin`
- [ ] **Move check-env.sh**: `git mv tools/check-env.sh bin/test-prereqs.sh`
- [ ] **Move release.sh**: `git mv tools/release.sh bin/release.sh`
- [ ] **Move test-endpoint.sh**: `git mv tools/test-endpoint.sh bin/test-endpoint.sh`
- [ ] **Move version.sh**: `git mv tools/version.sh bin/version.sh`
- [ ] **Remove empty tools/**: `rmdir tools`

### Verify Migration

- [ ] **Check bin/ contents**: `ls -la bin/` (should show 4 scripts)
- [ ] **Test script works**: `./bin/test-prereqs.sh --help` (should execute)
- [ ] **Verify tools/ gone**: `ls -la | grep tools` (should show nothing)

### Commit Phase A

- [ ] **Stage changes**: `git add .`
- [ ] **Commit**: `git commit -m "Phase A: Move scripts from tools/ to bin/ directory"`

## Step 3: Fix Makefile References (Phase B)

### Update make.deploy

- [ ] **Edit line 119**: Change `@./tools/release.sh release` to `@./bin/release.sh release`
- [ ] **Edit line 123**: Change `@./tools/release.sh dev` to `@./bin/release.sh dev`

### Test & Commit Phase B

- [ ] **Verify changes**: `grep -n "bin/release.sh" make.deploy` (should show 2 lines)
- [ ] **Test make tag**: `make tag` (should work without errors)
- [ ] **Stage changes**: `git add make.deploy`
- [ ] **Commit**: `git commit -m "Phase B: Update Makefile to use bin/ script paths"`

## Step 4: Fix GitHub Actions (Phase C)

### Fix create-release Action

**Edit `.github/actions/create-release/action.yml`:**

- [ ] **Delete broken manifest step** (lines 24-30): Remove "Extract manifest version" step entirely
- [ ] **Delete broken release package step** (lines 32-42): Remove manual release package creation
- [ ] **Add working step**: Replace with single line `run: make release-package`
- [ ] **Fix artifact path** (line 59): Update `path:` to use correct build output location
- [ ] **Update files reference**: Change zip filename to match `make release-package` output

### Test & Commit Phase C

- [ ] **Verify YAML syntax**: `yamllint .github/actions/create-release/action.yml`
- [ ] **Test make release-package**: `make release-package` (should work locally)
- [ ] **Stage changes**: `git add .github/actions/create-release/action.yml`
- [ ] **Commit**: `git commit -m "Phase C: Fix GitHub Actions to use make targets instead of broken paths"`

## Step 5: Final Validation & Documentation (Phase D)

### Validate All Changes

- [ ] **Test all scripts**: `./bin/test-prereqs.sh --help` and others work
- [ ] **Test make targets**: `make tag` and `make release-package` work
- [ ] **Check no broken refs**: `grep -r "tools/.*\.sh" .` (should find no unexpected results)

### Update Documentation

- [ ] **Update CLAUDE.md**: Change script references from `tools/` to `bin/`
- [ ] **Check for other docs**: Search for any remaining `tools/` script references

### Final Commit & Push

- [ ] **Stage all changes**: `git add .`
- [ ] **Final commit**: `git commit -m "Phase D: Update documentation for new script locations"`
- [ ] **Push branch**: `git push -u origin 100c-phase3-fix-actions`

## Success Criteria

After completion, verify:

### Functional Requirements

- [ ] All scripts execute from `bin/` location
- [ ] `make tag` and `make tag-dev` work correctly  
- [ ] GitHub Actions use `make release-package` instead of broken manual logic
- [ ] No broken `tools/dxt/` references remain in Actions

### Organizational Requirements

- [ ] Scripts in standard `bin/` directory
- [ ] No duplication between Makefiles and Actions  
- [ ] Clean directory structure (no empty `tools/` directory)
- [ ] Documentation reflects new structure

## Rollback Plan

If issues occur:

1. **Revert commits**: `git revert HEAD~3..HEAD` (reverts all 4 commits)
2. **Force reset**: `git reset --hard HEAD~4` (nuclear option)
3. **Restore from backup**: `git checkout 100-feature-cleanup-repomake -- tools/` if needed

## Next Steps

After implementation:

- [ ] Create PR with branch `100c-phase3-fix-actions`
- [ ] Test CI/CD pipeline works correctly
- [ ] Proceed to Phase 4: Validation Simplification

---

**Total Time**: 45 minutes across 5 steps with 4 commits

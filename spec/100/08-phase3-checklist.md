<!-- markdownlint-disable MD013 -->
# Phase 3 Implementation Checklist: Fix Broken GitHub Actions & Script Organization

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Based on**: [07-phase3-design.md](./07-phase3-design.md)  
**Branch**: `100c-phase3-fix-actions`

## Overview

This checklist implements Phase 3: fixing broken GitHub Actions that reference non-existent `tools/dxt/` paths and duplicate Makefile logic. Move scripts to `bin/` and eliminate CI/CD duplication.

## Pre-Implementation Validation

### Current State Verification

- [ ] **Verify broken Actions**: Confirm `.github/actions/create-release/action.yml` references non-existent `tools/dxt/` paths
- [ ] **Check script locations**: Confirm 4 scripts exist in `tools/` directory
- [ ] **Verify Makefile targets**: Confirm `make release-package` works locally
- [ ] **Document current CI/CD state**: Note what's broken vs working

### Baseline Testing

- [ ] **Test local builds**: Run `make dxt-package` and `make release-package` to confirm they work
- [ ] **Check current CI status**: Document any failing Actions
- [ ] **Verify script functionality**: Test all 4 scripts execute correctly from `tools/`

## Phase 3A: Script Migration (15 minutes)

### Step 1: Create bin/ Directory

- [ ] **Create directory**: `mkdir bin`
- [ ] **Verify creation**: `ls -la | grep bin`

### Step 2: Move Scripts with Rename

- [ ] **Move check-env.sh**: `git mv tools/check-env.sh bin/test-prereqs.sh`
- [ ] **Move release.sh**: `git mv tools/release.sh bin/release.sh`
- [ ] **Move test-endpoint.sh**: `git mv tools/test-endpoint.sh bin/test-endpoint.sh`
- [ ] **Move version.sh**: `git mv tools/version.sh bin/version.sh`

### Step 3: Verify Migration

- [ ] **Check bin/ contents**: `ls -la bin/` (should show 4 scripts)
- [ ] **Check tools/ is empty**: `ls -la tools/` (should be empty)
- [ ] **Verify permissions**: `ls -la bin/*.sh` (all should be executable)
- [ ] **Test script execution**: `./bin/test-prereqs.sh --help` (should work)

### Step 4: Remove Empty tools/ Directory

- [ ] **Remove directory**: `rmdir tools`
- [ ] **Verify removal**: `ls -la | grep -v tools` (tools should be gone)

## Phase 3B: Fix Makefile References (5 minutes)

### Update make.deploy

- [ ] **Edit make.deploy line 119**: Change `@./tools/release.sh release` to `@./bin/release.sh release`
- [ ] **Edit make.deploy line 123**: Change `@./tools/release.sh dev` to `@./bin/release.sh dev`
- [ ] **Verify changes**: `grep -n "bin/release.sh" make.deploy` (should show 2 lines)

### Test Makefile Updates

- [ ] **Test tag target**: `make tag` (should work without errors)
- [ ] **Test tag-dev target**: `make tag-dev` (should work without errors)

## Phase 3C: Fix GitHub Actions (20 minutes)

### Identify Broken References

- [ ] **Find all tools/dxt references**: `grep -r "tools/dxt" .github/`
- [ ] **Document broken paths**: List all references in `.github/actions/create-release/action.yml`

### Fix create-release Action

**Edit `.github/actions/create-release/action.yml`:**

- [ ] **Remove broken manifest extraction** (lines 24-30):
  ```yaml
  # DELETE:
  - name: Extract manifest version
    id: manifest
    shell: bash
    run: |
      MANIFEST_VERSION=$(python3 -c "import json; print(json.load(open('tools/dxt/build/manifest.json'))['version'])")
      echo "manifest_version=$MANIFEST_VERSION" >> $GITHUB_OUTPUT
  ```

- [ ] **Replace broken release package creation** (lines 32-42):
  ```yaml
  # DELETE:
  - name: Create release package
    shell: bash
    run: |
      mkdir -p release-package
      cp tools/dxt/dist/quilt-mcp-${{ steps.manifest.outputs.manifest_version }}.dxt release-package/
      cp tools/dxt/assets/README.md release-package/
      cp tools/dxt/assets/check-prereqs.sh release-package/
      cd release-package
      zip -r ../quilt-mcp-${{ inputs.tag-version }}.zip .
  ```

- [ ] **Add working release package step**:
  ```yaml
  # ADD:
  - name: Create release package
    shell: bash
    run: make release-package
  ```

- [ ] **Fix artifact upload path** (line 59):
  ```yaml
  # CHANGE FROM:
  path: tools/dxt/dist/*.dxt
  # CHANGE TO:
  path: tools/dxt/dist/*.dxt  # This path is created by make.deploy
  ```

- [ ] **Update release file reference**:
  ```yaml
  # In files section, change from:
  quilt-mcp-${{ inputs.tag-version }}.zip
  # To:
  tools/dxt/dist/quilt-mcp-*-release.zip
  ```

### Verify Action Syntax

- [ ] **Check YAML syntax**: Use `yamllint .github/actions/create-release/action.yml`
- [ ] **Verify no undefined variables**: Check all `${{ }}` references are valid

## Phase 3D: Validation & Testing (5 minutes)

### Local Testing

- [ ] **Test release-package target**: `make release-package` (should create proper bundle)
- [ ] **Check output location**: Verify release bundle created in correct location
- [ ] **Test script functionality**: Run each script from `bin/` to ensure they work

### Documentation Updates

- [ ] **Update CLAUDE.md**: Change any references from `tools/` to `bin/` for scripts
- [ ] **Update README**: Change script path references if any exist
- [ ] **Check spec docs**: Update any remaining `tools/` script references

### Git Status Check

- [ ] **Review changes**: `git status` (should show modified files and moved scripts)
- [ ] **Check for broken references**: `grep -r "tools/.*\.sh" .` (should only show `make.deploy` and expected paths)

## Commit & Branch Management

### Create Implementation Branch

- [ ] **Create new branch**: `git checkout -b 100c-phase3-fix-actions`
- [ ] **Verify branch**: `git branch` (should show new branch active)

### Commit Changes

- [ ] **Stage all changes**: `git add .`
- [ ] **Commit with message**:
  ```bash
  git commit -m "feat: Phase 3 - Fix broken GitHub Actions and move scripts to bin/

  - Move 4 scripts from tools/ to bin/ (rename check-env.sh → test-prereqs.sh)  
  - Fix make.deploy references to use bin/ paths
  - Fix GitHub Actions to use make release-package instead of broken manual logic
  - Remove duplication between Makefiles and Actions
  - Eliminate references to non-existent tools/dxt/ paths

  🤖 Generated with [Claude Code](https://claude.ai/code)

  Co-Authored-By: Claude <noreply@anthropic.com>"
  ```

### Push and Create PR

- [ ] **Push branch**: `git push -u origin 100c-phase3-fix-actions`
- [ ] **Create PR**: 
  ```bash
  gh pr create --title "Phase 3: Fix Broken GitHub Actions & Script Organization" \
    --body "$(cat <<'EOF'
  ## Summary

  Fixes critical Phase 3 issues:
  - GitHub Actions reference non-existent `tools/dxt/` paths (removed in Phase 2)
  - Actions duplicate `make release-package` logic instead of using it
  - Scripts need proper organization in `bin/` directory

  ## Changes Made

  ### Script Organization
  - Moved 4 scripts from `tools/` to `bin/` 
  - Renamed `check-env.sh` → `test-prereqs.sh` for clarity
  - Updated `make.deploy` references to use `bin/` paths
  - Removed empty `tools/` directory

  ### GitHub Actions Fixes
  - Removed broken manual release package creation
  - Replaced with `make release-package` call (DRY principle)
  - Fixed all references to non-existent `tools/dxt/` paths
  - Eliminated duplication between Makefiles and Actions

  ## Test Plan

  - [x] Local testing: `make tag`, `make tag-dev`, `make release-package` all work
  - [x] Script functionality: All scripts execute correctly from `bin/`
  - [x] GitHub Actions syntax: YAML validates correctly
  - [ ] CI/CD integration: Actions use correct Makefile targets

  🤖 Generated with [Claude Code](https://claude.ai/code)
  EOF
  )" --base 100-feature-cleanup-repomake
  ```

## Verification Checklist

### Final State Verification

- [ ] **Directory structure correct**: `bin/` contains 4 scripts, `tools/` removed
- [ ] **Makefile references updated**: `make.deploy` uses `bin/` paths
- [ ] **Actions use Makefiles**: No manual duplication of build logic
- [ ] **No broken path references**: No remaining `tools/dxt/` references in Actions
- [ ] **All targets work**: `make tag`, `make release-package`, etc. function correctly

### PR Status

- [ ] **Branch created**: `100c-phase3-fix-actions`
- [ ] **PR opened**: Against `100-feature-cleanup-repomake` base branch
- [ ] **CI passes**: GitHub Actions run successfully (may require merge to test fully)

## Success Criteria

### Functional Requirements ✅

- All scripts execute from `bin/` location
- `make tag` and `make tag-dev` work correctly  
- GitHub Actions use `make release-package` instead of broken manual logic
- CI/CD creates proper release packages

### Organizational Requirements ✅

- Scripts in standard `bin/` directory
- No duplication between Makefiles and Actions
- Actions use correct paths (not non-existent `tools/dxt/`)
- Clean directory structure without empty `tools/`

## Rollback Plan

If issues occur:

1. **Immediate rollback**: `git revert HEAD` on the branch
2. **Full reset**: `git checkout 100-feature-cleanup-repomake && git branch -D 100c-phase3-fix-actions`
3. **Restore tools/**: `git checkout HEAD~1 -- tools/` if needed

## Next Steps

After PR approval and merge:
- [ ] **Verify CI/CD works**: Test complete release workflow
- [ ] **Update documentation**: Ensure all references reflect new structure  
- [ ] **Proceed to Phase 4**: Validation Simplification

---

**Estimated Total Time**: 45 minutes  
**Critical Path**: Fixing broken GitHub Actions → Eliminating CI/CD duplication → Proper script organization
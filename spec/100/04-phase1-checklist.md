<!-- markdownlint-disable MD013 -->
# Phase 1 Implementation Checklist: Makefile Consolidation

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Based on**: [03-phase1-design.md](./03-phase1-design.md)

**Implementation Branch**: `100a-phase1-makefile-consolidation`  
**Target Branch**: `100-feature-cleanup-repomake`

## Pre-Implementation Validation

### Dependency Analysis

- [ ] **Audit Makefile target references**: Search codebase for hardcoded Make target calls
  - [ ] `grep -r "make app" --exclude-dir=.git --exclude-dir=.venv .`
  - [ ] `grep -r "make dxt" --exclude-dir=.git --exclude-dir=.venv .`
  - [ ] `grep -r "make validate-" --exclude-dir=.git --exclude-dir=.venv .`
  - [ ] `grep -r "make test-" --exclude-dir=.git --exclude-dir=.venv .`

- [ ] **Review GitHub Actions workflows**: Check for Make target dependencies
  - [ ] `.github/workflows/test.yml`
  - [ ] `.github/workflows/release.yml`
  - [ ] `.github/workflows/integration.yml`
  - [ ] Any other workflow files

- [ ] **Documentation audit**: Find all Make command references
  - [ ] `grep -r "make " docs/ --include="*.md"`
  - [ ] `grep -r "make " README.md CLAUDE.md`
  - [ ] Check for any installation/build instructions

## Core Implementation Tasks

### 1. Create Include-Based Makefile Structure

- [ ] **Backup existing Makefiles**
  - [ ] `cp Makefile Makefile.backup`
  - [ ] `cp app/Makefile app/Makefile.backup`
  - [ ] `cp tools/dxt/Makefile tools/dxt/Makefile.backup`

- [ ] **Create make.dev** (~40 lines)
  - [ ] Development workflow targets from `app/Makefile`
  - [ ] `test`, `test-unit`, `test-integration`, `test-ci`
  - [ ] `lint`, `coverage`, `run`, `run-inspector`
  - [ ] `dev-clean` (Python cache cleanup)

- [ ] **Create make.deploy** (~40 lines)
  - [ ] Production/packaging targets from `tools/dxt/Makefile`
  - [ ] `build`, `package`, `dxt-package`, `validate-package`
  - [ ] `deploy-clean` (build artifacts cleanup)

- [ ] **Rewrite main Makefile** (~30 lines)
  - [ ] Include directives: `include make.dev` and `include make.deploy`
  - [ ] Coordination targets: `help`, `clean`, `release`
  - [ ] Remove all delegated targets

- [ ] **Remove old Makefiles**
  - [ ] `rm app/Makefile`
  - [ ] `rm tools/dxt/Makefile`

### 2. Script Migration (Complex Workflows)

- [ ] **Create tools/release.sh** (consolidate release workflows)
  - [ ] Migrate logic from `Makefile:tag`, `Makefile:tag-dev`
  - [ ] Include `check-clean-repo` functionality
  - [ ] Handle version management and Git operations
  - [ ] Make executable: `chmod +x tools/release.sh`

### 3. Target Verification

- [ ] **Test core development targets**
  - [ ] `make help` - Shows all targets organized by category
  - [ ] `make test` - Runs tests with proper PYTHONPATH
  - [ ] `make test-unit` - Fast unit tests only
  - [ ] `make lint` - Code formatting and type checking
  - [ ] `make run` - Starts development server
  - [ ] `make clean` - Coordinates cleanup across includes

- [ ] **Test production/packaging targets**
  - [ ] `make build` - Prepares production environment
  - [ ] `make package` - Creates Python package
  - [ ] `make dxt-package` - Creates DXT package
  - [ ] `make validate-package` - Validates packages

- [ ] **Test coordination targets**
  - [ ] `make release` - Full release workflow
  - [ ] Cross-include cleanup works properly

## Supporting File Updates

### Documentation Updates

- [ ] **Update CLAUDE.md**
  - [ ] Revise "Repository-Specific Commands" section
  - [ ] Remove references to `app/Makefile`, `tools/dxt/Makefile`
  - [ ] Update pre-approved Makefile targets list
  - [ ] Update testing command examples

- [ ] **Update README.md**
  - [ ] Change `make app` references to `make run`
  - [ ] Update installation/build instructions
  - [ ] Revise development workflow documentation
  - [ ] Update testing instructions

- [ ] **Update docs/developer/ files** (if any exist)
  - [ ] Update build/test command references
  - [ ] Revise developer onboarding instructions
  - [ ] Update contribution guidelines

### GitHub Actions Updates

- [ ] **Update .github/workflows/test.yml**
  - [ ] Replace any `make validate-*` with new validation approach
  - [ ] Update test execution commands if needed
  - [ ] Verify CI workflow compatibility

- [ ] **Update .github/workflows/release.yml**
  - [ ] Use `make release` instead of manual steps
  - [ ] Remove direct Makefile path references
  - [ ] Update package building steps

- [ ] **Update .github/workflows/integration.yml**
  - [ ] Use `make test-integration` for AWS tests
  - [ ] Update any target name references

### Configuration File Updates

- [ ] **Check tool dependencies** (should be unchanged)
  - [ ] `pyproject.toml` - No changes needed
  - [ ] `.gitignore` - No changes needed
  - [ ] `uv.lock` - No changes needed

## Post-Implementation Validation

### Functionality Testing

- [ ] **Development workflow verification**
  - [ ] `make run` starts server successfully
  - [ ] `make test` executes all tests
  - [ ] `make test-unit` runs fast subset
  - [ ] `make test-integration` runs AWS tests
  - [ ] `make lint` formats and type-checks code
  - [ ] `make coverage` generates coverage reports

- [ ] **Production workflow verification**
  - [ ] `make build` prepares environment
  - [ ] `make package` creates Python distribution
  - [ ] `make dxt-package` creates DXT file
  - [ ] `make validate-package` validates outputs

- [ ] **Release workflow verification**
  - [ ] `tools/release.sh` handles version management
  - [ ] Git tagging works correctly
  - [ ] Release coordination functions properly

- [ ] **Cross-platform testing**
  - [ ] Test on macOS (current environment)
  - [ ] Verify compatibility with CI environment
  - [ ] Check Windows compatibility if applicable

### Integration Testing

- [ ] **GitHub Actions verification**
  - [ ] All workflows pass with new targets
  - [ ] No broken Make target references
  - [ ] Release workflow functions end-to-end

- [ ] **Documentation verification**
  - [ ] All commands in README.md work
  - [ ] Installation instructions are accurate
  - [ ] Developer onboarding process works

### Performance and Quality

- [ ] **Build performance**
  - [ ] New targets execute at same speed or faster
  - [ ] No unnecessary rebuilds or redundant operations
  - [ ] Clean targets remove all artifacts properly

- [ ] **Code quality**
  - [ ] Makefile syntax is valid and follows conventions
  - [ ] Include directives work cross-platform
  - [ ] Error handling is appropriate

## Success Criteria

### Quantitative Metrics

- [ ] **Line reduction**: 484 lines → ~110 lines (-77%)
- [ ] **Target reduction**: ~58 targets → ~15 targets (-74%)
- [ ] **Redundancy elimination**: ~20 duplicate targets removed
- [ ] **All essential functionality preserved**

### Qualitative Improvements

- [ ] **Single entry point**: `make help` shows all available targets
- [ ] **Clear organization**: Development vs production workflows separated
- [ ] **No duplication**: Each target exists in exactly one place
- [ ] **Obvious location**: Developers know where to find each target

## Rollback Plan

### If Implementation Fails

- [ ] **Restore backup Makefiles**
  - [ ] `cp Makefile.backup Makefile`
  - [ ] `cp app/Makefile.backup app/Makefile`
  - [ ] `cp tools/dxt/Makefile.backup tools/dxt/Makefile`

- [ ] **Remove new files**
  - [ ] `rm make.dev make.deploy`
  - [ ] `rm tools/release.sh`

- [ ] **Revert documentation changes**
  - [ ] Use git to restore modified documentation files
  - [ ] Verify all workflows return to original state

## Commit Strategy

### Incremental Commits

- [ ] **Commit 1**: "spec: Add Phase 1 implementation checklist"
- [ ] **Commit 2**: "feat: Create make.dev with development targets"
- [ ] **Commit 3**: "feat: Create make.deploy with production targets" 
- [ ] **Commit 4**: "feat: Rewrite main Makefile with includes"
- [ ] **Commit 5**: "feat: Add tools/release.sh for complex workflows"
- [ ] **Commit 6**: "refactor: Remove old app/Makefile and tools/dxt/Makefile"
- [ ] **Commit 7**: "docs: Update CLAUDE.md and README.md for new targets"
- [ ] **Commit 8**: "ci: Update GitHub Actions for new Make targets"
- [ ] **Commit 9**: "test: Verify all workflows function correctly"

### Final Validation Commit

- [ ] **Final commit**: "feat: Complete Phase 1 Makefile consolidation"
  - [ ] All tests passing
  - [ ] All documentation updated
  - [ ] All workflows verified
  - [ ] Success metrics achieved
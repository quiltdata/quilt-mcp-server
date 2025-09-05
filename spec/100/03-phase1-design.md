<!-- markdownlint-disable MD013 -->
# Phase 1 Design: Makefile Consolidation

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Based on**: [02-specifications.md](./02-specifications.md)

**Note**: This document specifies **what** changes should be made to the Makefile structure, without implementing the actual code. Implementation details should be determined during the development phase.

## Current State Audit

### Existing Makefiles

**Root `Makefile`** (199 lines, 26 targets):

- Orchestration: `help`, `validate`, `clean`, `release management`
- Delegation: `app`, `dxt`, `test-*`, `validate-*`
- Server operations: `run-app*`, `inspect-app-tunnel`
- Utilities: `check-env`, `coverage`, `update-cursor-rules`

**`app/Makefile`** (137 lines, 19 targets):

- Development: `run`, `test*`, `coverage*`, `lint`
- Validation: `validate`, `verify`, `test-endpoint`
- Utilities: `clean`, `config`, `init`, `zero`
- IDE integration: `run-inspector`, `update-cursor-rules`

**`tools/dxt/Makefile`** (148 lines, 13 targets):

- Build pipeline: `build`, `test`, `validate`, `release`
- DXT operations: `contents`, `assess`, `bootstrap`
- Utilities: `clean`, `debug`, `check-tools`

## Target Reorganization

### Main `Makefile` Targets (~30 lines)

**Coordination targets** (keep):

- `help` - Display all available targets by category
- `clean` - Coordinate cleanup across all includes  
- `release` - Full release workflow (test → build → package)

**Remove from main** (delegate to includes):

- All phase-specific targets (`app`, `dxt`, `test-*`, `validate-*`)
- Server operations (`run-app*`, `inspect-app-tunnel`)
- Direct utility calls (`coverage`, `check-env`)

### `make.dev` Targets (~40 lines)

**Development workflow targets** (migrate from app/Makefile):
- `test` ← `app/Makefile:test`
- `test-unit` ← `app/Makefile:test-unit` 
- `test-integration` ← `app/Makefile:test` (full AWS tests)
- `test-ci` ← `app/Makefile:test-ci`
- `lint` ← `app/Makefile:lint`
- `coverage` ← `app/Makefile:coverage`
- `run` ← `app/Makefile:run`
- `run-inspector` ← `app/Makefile:run-inspector`
- `dev-clean` ← `app/Makefile:clean`

**Remove as redundant**:
- `app/Makefile:coverage-unit` (covered by `coverage`)
- `app/Makefile:verify` (covered by `test-endpoint`)
- `app/Makefile:zero` (process management, not build system responsibility)
- `app/Makefile:config` (should be automatic in `run`)
- `app/Makefile:init` (dependency checking, not build responsibility)

### `make.deploy` Targets (~40 lines)

**Production/packaging targets** (migrate from tools/dxt/Makefile + root):
- `build` ← `tools/dxt/Makefile:build` (preparation)
- `package` ← `tools/dxt/Makefile:release` (Python package)
- `dxt-package` ← `tools/dxt/Makefile:build` + `tools/dxt/Makefile:validate` (DXT creation)
- `validate-package` ← `tools/dxt/Makefile:validate`
- `deploy-clean` ← `tools/dxt/Makefile:clean`

**Merge complex workflows**:
- `tag-release` ← `Makefile:tag` + `Makefile:tag-dev` (into `tools/release.sh`)
- `check-clean-repo` ← `Makefile:check-clean-repo` (into `tools/release.sh`)

**Remove as developer utilities**:
- `tools/dxt/Makefile:debug` (development debugging, not build workflow)
- `tools/dxt/Makefile:contents` (internal step, not user target)
- `tools/dxt/Makefile:assess` (covered by `check-prereqs.sh`)
- `tools/dxt/Makefile:bootstrap` (internal testing, not user workflow)

## Target Mapping

### Targets Removed (Redundant/Internal)

**From Root Makefile**:
- `app`, `dxt` → Use `run`, `package` instead
- `test-app`, `test-dxt` → Use `test`, `test-integration`
- `validate-app`, `validate-dxt` → Use `validate-package`
- `run-app-tunnel`, `inspect-app-tunnel` → Complex networking, remove
- `test-endpoint-tunnel` → Complex networking, remove
- `update-cursor-rules` → Development utility, not build system

**From app/Makefile**:
- `coverage-unit` → Covered by `coverage`
- `verify` → Covered by `test-endpoint` 
- `zero` → Process management, not build
- `config` → Should be automatic
- `init` → Dependency management, not build
- `update-cursor-rules` → Duplicate of root target

**From tools/dxt/Makefile**:
- `debug` → Development utility
- `contents` → Internal build step
- `assess` → Replaced by `tools/check-prereqs.sh`
- `bootstrap` → Internal testing
- `check-tools` → Covered by prerequisite checking

### Targets Merged

**Release workflows**:
- `Makefile:tag` + `Makefile:tag-dev` + `Makefile:check-clean-repo` → `tools/release.sh`

**DXT workflows**:
- `tools/dxt/Makefile:build` + `tools/dxt/Makefile:validate` → `dxt-package`

**Test workflows**:
- `app/Makefile:test` (with AWS) → `test-integration`
- `app/Makefile:test` (without AWS) → `test`

### Targets Moved

**Root → make.dev**:
- `coverage` → Moved to development workflows

**app/Makefile → make.dev**:
- `run`, `test*`, `lint`, `coverage` → Core development targets
- `run-inspector` → Development utility

**app/Makefile → make.deploy**:
- None (app focuses on development)

**tools/dxt/Makefile → make.deploy**:
- `build` → `build` (preparation)
- `release` → `package` (Python packaging)
- `validate` → `validate-package`
- `clean` → `deploy-clean`

**Root → tools/release.sh**:
- `tag`, `tag-dev`, `check-clean-repo` → Complex release orchestration

## File Changes

### Files Removed
- `app/Makefile` (137 lines) → Logic moved to `make.dev`
- `tools/dxt/Makefile` (148 lines) → Logic moved to `make.deploy`

### Files Modified
- `Makefile` (199 lines) → ~30 lines (coordination only)

### Files Created
- `make.dev` (~40 lines) → Development workflow targets
- `make.deploy` (~40 lines) → Production/packaging targets

## Success Metrics

**Quantitative changes**:
- **Total lines**: 484 → ~110 (-77%)
- **Total files**: 3 → 3 (same count, different organization)
- **Total targets**: ~58 → ~15 (-74%)
- **Redundant targets eliminated**: ~20 duplicate/internal targets removed

**Qualitative improvements**:

- **Single entry point**: `make help` shows all targets
- **Clear separation**: Development vs production workflows
- **No duplication**: Each target exists in exactly one place
- **Focused responsibility**: Each file has single, clear purpose

## Supporting File Changes

### Documentation Updates Required

**CLAUDE.md**:

- Update "Repository-Specific Commands" section to reflect new target names
- Remove references to phase-specific Makefiles (`app/Makefile`, `tools/dxt/Makefile`)
- Update testing command examples (`make test`, `make test-integration`)
- Revise "Pre-approved Makefile targets" list

**README.md**:

- Update installation/build instructions to use new target names
- Change `make app` references to `make run`
- Update testing instructions to use `make test`
- Revise development workflow documentation

**docs/developer/** files:

- Update any build/test command references
- Revise developer onboarding instructions
- Update contribution guidelines with new Make targets

### GitHub Actions Workflow Updates

**.github/workflows/test.yml**:

- Change `make test-ci` calls (if target renamed)
- Update any `make validate-*` references to new validation approach
- Revise build/test step commands

**.github/workflows/release.yml**:

- Update release workflow to use `make release` instead of manual steps
- Remove direct calls to `app/Makefile` or `tools/dxt/Makefile`
- Update package building steps to use new targets

**.github/workflows/integration.yml**:

- Update integration test commands to use `make test-integration`
- Revise AWS test execution if target names change

### Configuration File Updates

**pyproject.toml**:

- No changes required (tool configuration remains the same)

**.gitignore**:

- No changes required (build artifacts remain the same)

**uv.lock**:

- No changes required (dependencies unchanged)

### Script Dependencies

**tools/ scripts** (if any reference Make targets):

- Update any internal calls to Make targets
- Ensure scripts use new target names
- Verify no hardcoded references to old Makefile paths

### IDE Configuration

**.cursor/rules** and **.claude/agents**:

- Update any references to specific Make targets
- Revise development workflow documentation
- Update command examples in agent prompts

## Validation Requirements

### Pre-implementation Validation

**Dependency Analysis**:

- Audit all files for hardcoded Make target references
- Search codebase for `make app`, `make dxt`, etc.
- Identify any external scripts calling removed targets

**Documentation Audit**:

- Grep for Makefile references across all `.md` files
- Check all workflow documentation for outdated commands
- Verify installation instructions remain accurate

**CI/CD Impact Assessment**:

- Review all GitHub Actions for Make target usage
- Ensure no workflows depend on removed targets
- Verify release process compatibility

### Post-implementation Validation

**Functionality Testing**:

- Verify all essential workflows still work
- Test development workflow (`make run`, `make test`)
- Validate production workflow (`make build`, `make package`)
- Confirm release process works end-to-end

**Documentation Verification**:

- Test all commands in README.md
- Verify developer onboarding instructions work
- Confirm contribution guidelines are accurate
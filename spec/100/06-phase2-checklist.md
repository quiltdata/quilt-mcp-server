<!-- markdownlint-disable MD013 -->
# Phase 2 Implementation Checklist: Directory Restructuring

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Based on**: [05-phase2-design.md](./05-phase2-design.md)

## Pre-Execution Validation

**CRITICAL**: Before executing any steps, verify current repository state:

- [ ] Run `git status` to ensure clean working tree
- [ ] Run `ls -la` to confirm current directory structure
- [ ] Run `make test-unit` to ensure current system is working

**If any expected files/directories are missing, STOP and ask user for clarification.**

## Atomic Commit Steps (Execute in Order)

### Step 1A: Update pyproject.toml

**Commit**: `"refactor: update pyproject.toml for src/ structure"`

- [ ] **Action**: Update `pyproject.toml`: Change `where = ["app"]` to `where = ["src"]`
- [ ] **Test**: Run `python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['tool']['setuptools']['packages']['find']['where'])"`
- [ ] **Expected**: Output shows `['src']`
- [ ] **Rollback**: If test fails, revert `pyproject.toml` change

### Step 1B: Update Makefile PYTHONPATH

**Commit**: `"refactor: update Makefile PYTHONPATH for src/ structure"`

- [ ] **Action**: Update all Makefile PYTHONPATH references: `app` → `src`
- [ ] **Test**: Run `grep -n "PYTHONPATH.*=" Makefile`
- [ ] **Expected**: All PYTHONPATH entries show `src`, none show `app`
- [ ] **Test**: Run `make test-unit` (should work with current `app/` structure)
- [ ] **Expected**: Tests pass (configuration prepared but structure unchanged)
- [ ] **Rollback**: If test fails, revert Makefile PYTHONPATH changes

### Step 1C: Update GitHub Actions

**Commit**: `"refactor: update GitHub Actions PYTHONPATH for src/ structure"`

- [ ] **Action**: Update GitHub Actions workflows: PYTHONPATH environment variables `app` → `src`
- [ ] **Test**: Run `grep -r "PYTHONPATH.*app" .github/`
- [ ] **Expected**: No matches found (all changed to `src`)
- [ ] **Test**: Run `grep -r "PYTHONPATH.*src" .github/`
- [ ] **Expected**: All PYTHONPATH entries show `src`
- [ ] **Rollback**: If validation fails, revert workflow changes

### Step 1D: Update Claude Agents Configuration

**Commit**: `"refactor: update Claude agents for src/ structure"`

- [ ] **Action**: Update `.claude/agents/` configurations: hardcoded `app/quilt_mcp` paths → `src/quilt_mcp`
- [ ] **Test**: Run `grep -r "app/quilt_mcp" .claude/`
- [ ] **Expected**: No matches found
- [ ] **Test**: Run `grep -r "src/quilt_mcp" .claude/`
- [ ] **Expected**: All references updated to `src/quilt_mcp`
- [ ] **Rollback**: If validation fails, revert agent configuration changes

### Step 1E: Validate Configuration Changes

**Commit**: `"test: verify configuration changes with current structure"`

- [ ] **Test**: Run `make test-unit`
- [ ] **Expected**: All tests pass (configurations updated but files still in `app/`)
- [ ] **Test**: Run `make lint`
- [ ] **Expected**: No syntax errors, all checks pass
- [ ] **Rollback**: If any test fails, revert all Step 1 configuration changes

### Step 2: Create Directory Structure

**Commit**: `"feat: create consolidated directory structure"`

- [ ] **Action**: Run `mkdir -p src/deploy`
- [ ] **Test**: Run `ls -ld src/deploy`
- [ ] **Expected**: Directory exists with proper permissions
- [ ] **Action**: Run `mkdir -p build`
- [ ] **Test**: Run `ls -ld build`
- [ ] **Expected**: Directory exists with proper permissions
- [ ] **Action**: Run `mkdir -p docs/archive`
- [ ] **Test**: Run `ls -ld docs/archive`
- [ ] **Expected**: Directory exists with proper permissions
- [ ] **Rollback**: If any directory creation fails, remove created directories

### Step 3A: Move Core Application Files

**Commit**: `"refactor: move core application files to src/"`

- [ ] **Pre-check**: Run `ls -la app/quilt_mcp/`
- [ ] **Expected**: Directory exists and contains files
- [ ] **Action**: Run `git mv app/quilt_mcp/ src/quilt_mcp/`
- [ ] **Test**: Run `ls -la src/quilt_mcp/`
- [ ] **Expected**: All files present in new location
- [ ] **Test**: Run `git status | grep "renamed:.*app/quilt_mcp.*src/quilt_mcp"`
- [ ] **Expected**: Git tracks as rename (preserves history)
- [ ] **Rollback**: If test fails, run `git mv src/quilt_mcp/ app/quilt_mcp/`

### Step 3B: Move Main Entry Point

**Commit**: `"refactor: move main.py to src/"`

- [ ] **Pre-check**: Run `ls -la app/main.py`
- [ ] **Expected**: File exists
- [ ] **Action**: Run `git mv app/main.py src/main.py`
- [ ] **Test**: Run `ls -la src/main.py`
- [ ] **Expected**: File exists in new location
- [ ] **Test**: Run `git status | grep "renamed:.*app/main.py.*src/main.py"`
- [ ] **Expected**: Git tracks as rename
- [ ] **Rollback**: If test fails, run `git mv src/main.py app/main.py`

### Step 3C: Move and Rename Bootstrap

**Commit**: `"refactor: move bootstrap to src/deploy/ with DXT naming"`

- [ ] **Pre-check**: Run `ls -la app/bootstrap.py`
- [ ] **Expected**: File exists
- [ ] **Action**: Run `git mv app/bootstrap.py src/deploy/dxt_bootstrap.py`
- [ ] **Test**: Run `ls -la src/deploy/dxt_bootstrap.py`
- [ ] **Expected**: File exists in new location with new name
- [ ] **Test**: Run `git status | grep "renamed:.*app/bootstrap.py.*src/deploy/dxt_bootstrap.py"`
- [ ] **Expected**: Git tracks as rename
- [ ] **Rollback**: If test fails, run `git mv src/deploy/dxt_bootstrap.py app/bootstrap.py`

### Step 3D: Validate Python Module Relationships

**Commit**: `"test: validate Python imports work with new structure"`

- [ ] **Test**: Run `PYTHONPATH=src python -c "import quilt_mcp; print('Import successful')"`
- [ ] **Expected**: Import successful message
- [ ] **Test**: Run `PYTHONPATH=src python -c "import sys; sys.path.insert(0, 'src'); exec(open('src/main.py').read())"`
- [ ] **Expected**: No import errors (may fail on functionality, but imports should work)
- [ ] **Rollback**: If imports fail, investigate and fix import issues before proceeding

### Step 4A: Check DXT Assets Exist

**Pre-flight check**: `"verify: check DXT assets before move"`

- [ ] **Pre-check**: Run `ls -la tools/dxt/assets/`
- [ ] **Expected**: Directory exists with files, OR does not exist
- [ ] **Decision**: If directory doesn't exist, skip Step 4 entirely
- [ ] **Action**: If exists, proceed to Step 4B

### Step 4B: Move DXT Assets (Conditional)

**Commit**: `"refactor: consolidate DXT assets to src/deploy/"` (only if assets exist)

- [ ] **Action**: For each file in `tools/dxt/assets/`, run `git mv tools/dxt/assets/[file] src/deploy/[file]`
- [ ] **Test**: Run `ls -la src/deploy/`
- [ ] **Expected**: All DXT asset files present
- [ ] **Test**: Run `ls -la tools/dxt/assets/`
- [ ] **Expected**: Directory empty or does not exist
- [ ] **Test**: Run `git status | grep "renamed:.*tools/dxt/assets"`
- [ ] **Expected**: All moves tracked as renames
- [ ] **Rollback**: If conflicts occur, restore each file individually with `git mv`

### Step 5A: Move Essential Scripts

**Commit**: `"refactor: move essential scripts to tools/"`

- [ ] **Pre-check**: Run `ls -la shared/version.sh shared/test-endpoint.sh shared/check-env.sh`
- [ ] **Expected**: Files exist OR some don't exist (handle gracefully)
- [ ] **Action** (if exists): Run `git mv shared/version.sh tools/version.sh`
- [ ] **Test**: Run `ls -la tools/version.sh` (if file existed)
- [ ] **Action** (if exists): Run `git mv shared/test-endpoint.sh tools/validate-endpoint.sh`
- [ ] **Test**: Run `ls -la tools/validate-endpoint.sh` (if file existed)
- [ ] **Action** (if exists): Run `git mv shared/check-env.sh tools/check-prereqs.sh`
- [ ] **Test**: Run `ls -la tools/check-prereqs.sh` (if file existed)
- [ ] **Rollback**: Reverse successful moves if any step fails

### Step 5B: Remove Scripts Directory

**Commit**: `"refactor: remove obsolete scripts directory"`

- [ ] **Pre-check**: Run `ls -la scripts/`
- [ ] **Expected**: Directory exists OR does not exist
- [ ] **Action** (if exists): Run `git rm -r scripts/`
- [ ] **Test**: Run `ls -la scripts/`
- [ ] **Expected**: Directory does not exist
- [ ] **Test**: Run `git status | grep "deleted:.*scripts/"`
- [ ] **Expected**: All script deletions tracked
- [ ] **Rollback**: If issues occur, run `git checkout scripts/`

### Step 5C: Remove Remaining Shared Files

**Commit**: `"refactor: remove remaining shared directory files"`

- [ ] **Pre-check**: Run `ls -la shared/`
- [ ] **Expected**: Directory exists with remaining files OR is empty/missing
- [ ] **Action** (if files exist): For each remaining file, run `git rm shared/[file]`
- [ ] **Action** (if directory empty): Run `rmdir shared/`
- [ ] **Test**: Run `ls -la shared/`
- [ ] **Expected**: Directory does not exist
- [ ] **Rollback**: If issues occur, restore deleted files with `git checkout`

### Step 6: Archive Analysis Documents

**Commit**: `"docs: archive historical analysis documents"`

- [ ] **Pre-check**: Run `ls -la analysis/`
- [ ] **Expected**: Directory exists OR does not exist
- [ ] **Action** (if exists): Run `git mv analysis/ docs/archive/analysis/`
- [ ] **Test**: Run `ls -la docs/archive/analysis/`
- [ ] **Expected**: All analysis files present in new location
- [ ] **Test**: Run `ls -la analysis/`
- [ ] **Expected**: Directory does not exist
- [ ] **Test**: Run `git status | grep "renamed:.*analysis.*docs/archive/analysis"`
- [ ] **Expected**: Move tracked as rename
- [ ] **Rollback**: If issues occur, run `git mv docs/archive/analysis/ analysis/`

### Step 7A: Remove Configs Directory

**Commit**: `"refactor: remove obsolete configs directory"`

- [ ] **Pre-check**: Run `ls -la configs/`
- [ ] **Expected**: Directory exists OR does not exist
- [ ] **Action** (if exists): Run `git rm -r configs/`
- [ ] **Test**: Run `ls -la configs/`
- [ ] **Expected**: Directory does not exist
- [ ] **Test**: Run `git status | grep "deleted:.*configs/"`
- [ ] **Expected**: Deletion tracked
- [ ] **Rollback**: If issues occur, run `git checkout configs/`

### Step 7B: Move Test Results (Conditional)

**Commit**: `"refactor: move test results to build/"` (only if exists)

- [ ] **Pre-check**: Run `ls -la app/test-results/`
- [ ] **Expected**: Directory exists OR does not exist
- [ ] **Action** (if exists): Run `git mv app/test-results/ build/test-results/`
- [ ] **Test**: Run `ls -la build/test-results/` (if directory existed)
- [ ] **Expected**: All test result files present
- [ ] **Test**: Run `git status | grep "renamed:.*app/test-results.*build/test-results"`
- [ ] **Expected**: Move tracked as rename
- [ ] **Rollback**: If issues occur, run `git mv build/test-results/ app/test-results/`

### Step 7C: Remove Empty App Directory

**Commit**: `"cleanup: remove empty app directory"`

- [ ] **Pre-check**: Run `ls -la app/`
- [ ] **Expected**: Directory is empty OR does not exist
- [ ] **Action** (if empty): Run `rmdir app/`
- [ ] **Test**: Run `ls -la app/`
- [ ] **Expected**: Directory does not exist
- [ ] **Rollback**: If directory not empty, investigate remaining files

### Step 8A: Update .gitignore

**Commit**: `"build: update .gitignore for new structure"`

- [ ] **Action**: Read current `.gitignore` with `Read` tool
- [ ] **Action**: Edit `.gitignore` with `Edit` tool:
  - Remove: `app/test-results/`, `scripts/`, `shared/`, `analysis/`, `configs/`
  - Add: `build/`
  - Update: `app/test-results/` → `build/test-results/`
- [ ] **Test**: Run `grep -E "(app/test-results|scripts|shared|analysis|configs)" .gitignore`
- [ ] **Expected**: No matches (obsolete entries removed)
- [ ] **Test**: Run `grep "build/" .gitignore`
- [ ] **Expected**: Entry found
- [ ] **Rollback**: If validation fails, restore original `.gitignore`

### Step 8B: Update Makefile Clean Target

**Commit**: `"build: update Makefile clean target for new structure"`

- [ ] **Action**: Read current `Makefile` with `Read` tool
- [ ] **Action**: Edit `make clean` target with `Edit` tool:
  - Add: `rm -rf build/`
  - Add: `rm -rf build/test-results/`
  - Ensure comprehensive cleanup
- [ ] **Test**: Run `make clean`
- [ ] **Expected**: Command executes without errors
- [ ] **Test**: Run `ls -la build/` (if build/ existed)
- [ ] **Expected**: Directory cleaned or removed
- [ ] **Rollback**: If make clean fails, restore original Makefile

### Step 9: Update Import Paths

**Commit**: `"fix: update import paths for new structure"`

- [ ] **Test**: Run `PYTHONPATH=src make test-unit`
- [ ] **Expected**: Tests run with new PYTHONPATH (may have failures, but should attempt to run)
- [ ] **Action**: Fix any import path issues discovered in tests
- [ ] **Test**: Run `PYTHONPATH=src python -c "import src.quilt_mcp; print('Imports working')"`
- [ ] **Expected**: Successful import
- [ ] **Rollback**: If critical import issues found, address before proceeding

### Step 10A: Test Build System

**Commit**: `"test: validate build system with new structure"`

- [ ] **Test**: Run `make test`
- [ ] **Expected**: Tests execute (record results, some failures acceptable)
- [ ] **Test**: Run `make build`
- [ ] **Expected**: Build process completes successfully
- [ ] **Action**: Fix any critical build failures discovered
- [ ] **Rollback**: If build system completely broken, address issues

### Step 10B: Test DXT Packaging

**Commit**: `"test: validate DXT packaging with new structure"`

- [ ] **Test**: Run `make dxt-package`
- [ ] **Expected**: DXT package creation succeeds
- [ ] **Test**: Verify DXT package contains expected files from `src/deploy/`
- [ ] **Expected**: Package includes DXT assets and bootstrap
- [ ] **Action**: Fix any DXT packaging issues
- [ ] **Rollback**: If DXT packaging broken, investigate and fix

### Step 10C: Test Clean Process

**Commit**: `"test: validate clean process removes all artifacts"`

- [ ] **Test**: Run `make clean`
- [ ] **Expected**: Command completes successfully
- [ ] **Test**: Run `ls -la build/` (should not exist)
- [ ] **Expected**: Directory not found or empty
- [ ] **Test**: Verify no temporary artifacts remain
- [ ] **Expected**: Clean repository state
- [ ] **Action**: Fix clean target if issues found

### Step 10D: Test MCP Server Start

**Commit**: `"test: validate MCP server starts with new structure"`

- [ ] **Test**: Run `timeout 10s make run` (auto-stop after 10 seconds)
- [ ] **Expected**: Server starts without import errors (timeout is expected)
- [ ] **Alternative**: Run `make run` manually, then stop with Ctrl+C
- [ ] **Expected**: Server initializes successfully before manual stop
- [ ] **Action**: Fix any server startup issues
- [ ] **Rollback**: If server won't start, investigate critical issues

## Detailed Implementation Tasks

### Directory Movement Mapping

```text
# Source Code
app/quilt_mcp/                     → src/quilt_mcp/
app/main.py                        → src/main.py
app/bootstrap.py                   → src/deploy/dxt_bootstrap.py

# DXT Assets
tools/dxt/assets/                  → src/deploy/

# Essential Scripts
shared/version.sh                  → tools/version.sh
shared/test-endpoint.sh            → tools/validate-endpoint.sh
shared/check-env.sh                → tools/check-prereqs.sh

# Documentation Archive
analysis/                          → docs/archive/analysis/

# Build Artifacts
app/test-results/                  → build/test-results/
```

### Files/Directories to Remove

```text
# Obsolete Scripts (17 files total)
scripts/                           → Remove entire directory
shared/common.sh                   → Remove
shared/tunnel-endpoint.sh          → Remove
shared/test-tools.json             → Remove

# Obsolete Configuration
configs/                           → Remove entire directory

# Container Directories (after moves)
app/                               → Remove (should be empty)
analysis/                          → Remove (after archiving)
```

### Configuration File Updates

**pyproject.toml**:

```toml
[tool.setuptools.packages.find]
where = ["src"]  # Changed from "app"
```

**Makefile targets** (update PYTHONPATH):

```makefile
export PYTHONPATH := src  # Changed from app
```

**GitHub Actions** (.github/workflows/):

```yaml
env:
  PYTHONPATH: src  # Changed from app
```

### Post-Move Validation Checklist

**Build System**:

- [ ] All `make` targets execute successfully
- [ ] `make clean` removes all temporary directories
- [ ] `make test` passes with new structure
- [ ] `make run` starts MCP server correctly
- [ ] DXT packaging works with new asset location

**Import Resolution**:

- [ ] All Python imports resolve correctly
- [ ] Test imports work with new PYTHONPATH
- [ ] No hardcoded `app.quilt_mcp` references remain

**Repository State**:

- [ ] No empty directories remain
- [ ] Git history preserved for moved files
- [ ] `.gitignore` covers all temporary locations
- [ ] All obsolete paths removed from configuration

**Documentation**:

- [ ] README.md installation instructions work
- [ ] Developer onboarding guides reference correct paths
- [ ] API documentation examples use correct imports
- [ ] CLAUDE.md updated with new structure knowledge

## Success Metrics

**Quantitative Improvements**:

- Root directories: 16 → 8 (-50%)
- Script files: 17 → 4 (-76%)
- Maximum depth: 8+ levels → 4 levels (-50%)

**Qualitative Improvements**:

- Single source location: All Python code in `src/quilt_mcp/`
- Focused tools: Only essential build scripts in `tools/`
- Clean repository: No empty directories, comprehensive gitignore
- Simplified imports: Consistent `quilt_mcp.*` throughout

## Risk Mitigation

**Pre-execution validation**:

- [ ] Verify all tests pass before starting moves
- [ ] Create backup of current working state
- [ ] Confirm branch is pushed to remote for safety

**Incremental verification**:

- [ ] Test build system after each configuration change
- [ ] Verify imports after each source move
- [ ] Run subset of tests after major structural changes

**Rollback preparation**:

- [ ] Each commit represents atomic, reversible change
- [ ] Git history preserved for all moved files
- [ ] Configuration changes committed separately from moves

## Implementation Notes

**Essential principles**:

- Execute commits in exact order specified
- **Use `ls` and `find` to verify file existence before operations**
- **Use `git mv` for all file moves to preserve history**
- **Use `git rm` for all deletions to track in git**
- Test after each major structural change
- Remove empty directories immediately after moves
- Update configuration before executing moves

**Critical validations**:

- **Check file existence with `ls` before attempting moves**
- PYTHONPATH changes must be tested with `make test-unit` before file moves
- All imports must resolve before considering step complete
- Build system must work after each configuration update
- DXT packaging must work with new asset locations
- **Handle gracefully if expected files/directories don't exist**

**Cleanup requirements**:

- No orphaned directories after completion
- Comprehensive `.gitignore` coverage
- `make clean` removes all temporary artifacts
- Repository in pristine, maintainable state

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

## Commit Steps (Execute in Order)

### Step 1: Pre-Move Configuration Updates

**Commit**: `"refactor: update build system for src/ structure"`

- [ ] Update `pyproject.toml`: Change `where = ["app"]` to `where = ["src"]`
- [ ] Update all Makefile PYTHONPATH references: `app` → `src`
- [ ] Update GitHub Actions workflows: PYTHONPATH environment variables
- [ ] Update `.claude/agents/` configurations: hardcoded `app/quilt_mcp` paths
- [ ] Run `make test-unit` to verify configuration changes don't break current structure
- [ ] Run `make lint` to ensure no syntax errors introduced

### Step 2: Directory Structure Creation

**Commit**: `"feat: create consolidated directory structure"`

- [ ] Run `mkdir -p src/deploy` to create src and deploy directories
- [ ] Run `mkdir -p build` to create build directory
- [ ] Run `mkdir -p docs/archive` to create archive directory
- [ ] Run `mkdir -p tests/docs` to create tests/docs if needed
- [ ] Verify with `ls -la src/ build/ docs/archive/ tests/docs/`

### Step 3: Source Code Moves

**Commit**: `"refactor: move application source to src/"`

- [ ] Use `git mv` to move `app/quilt_mcp/` → `src/quilt_mcp/` (preserves git history)
- [ ] Use `git mv` to move `app/main.py` → `src/main.py`
- [ ] Use `git mv` to move `app/bootstrap.py` → `src/deploy/dxt_bootstrap.py`
- [ ] Verify all Python module relationships preserved

**Note**: Use git mv commands to preserve file history during moves

### Step 4: DXT Assets Consolidation

**Commit**: `"refactor: consolidate DXT assets to src/deploy/"`

- [ ] Use `git mv` for each file in `tools/dxt/assets/` → `src/deploy/`
- [ ] Update DXT build references to new location
- [ ] Update any hardcoded paths in DXT configuration

**Warning**: Handle potential conflicts if `src/deploy/` already contains moved bootstrap.py

### Step 5: Script Consolidation

**Commit**: `"refactor: consolidate essential scripts in tools/"`

**Move essential scripts**:

- [ ] Use `git mv shared/version.sh tools/version.sh`
- [ ] Use `git mv shared/test-endpoint.sh tools/validate-endpoint.sh`  
- [ ] Use `git mv shared/check-env.sh tools/check-prereqs.sh`

**Remove obsolete scripts**:

- [ ] Use `git rm -r scripts/` to remove directory and track deletion
- [ ] Use `git rm` for remaining `shared/` files individually
- [ ] Remove `shared/` directory (should be empty after git rm)

### Step 6: Documentation Reorganization

**Commit**: `"docs: archive historical analysis documents"`

- [ ] Create `docs/archive/` directory if not exists
- [ ] Use `git mv analysis/ docs/archive/analysis/`
- [ ] Update documentation index references

**Note**: git mv handles directory moves atomically

### Step 7: Configuration Cleanup

**Commit**: `"refactor: remove obsolete configuration directories"`

- [ ] Use `git rm -r configs/` to remove directory
- [ ] Create `build/` directory if not exists
- [ ] Use `git mv app/test-results/ build/test-results/` (if exists)
- [ ] Remove `app/` directory (should be empty after moves)

**Warning**: Check if `app/test-results/` exists before attempting move

### Step 8: Build Artifact Management

**Commit**: `"build: update gitignore and clean targets"`

- [ ] Read current `.gitignore` with `Read` tool
- [ ] Edit `.gitignore` with `Edit` tool:
  - Remove obsolete entries: `app/test-results/`, references to `scripts/`, `shared/`, `analysis/`, `configs/`
  - Add `build/` (comprehensive coverage)
  - Update `app/test-results/` → `build/test-results/`
  - Prune duplicate patterns
- [ ] Read current `Makefile` with `Read` tool
- [ ] Edit `make clean` target with `Edit` tool:
  - Add `build/` removal
  - Add `build/test-results/` removal
  - Ensure comprehensive temporary file cleanup

### Step 9: Import Path Updates

**Commit**: `"fix: update import paths for new structure"`

- [ ] Update test files: Verify imports work with new PYTHONPATH
- [ ] Update documentation code examples
- [ ] Update any hardcoded import paths in scripts

### Step 10: Validation and Testing

**Commit**: `"test: verify restructured codebase functionality"`

- [ ] Run full test suite: `make test` (expect some failures initially)
- [ ] Test build process: `make build`
- [ ] Test DXT packaging: `make dxt-package`
- [ ] Test clean process: `make clean`
- [ ] Start MCP server briefly: `make run` (then stop with Ctrl+C)

**Note**: Some tests may fail until all import paths are fully updated

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

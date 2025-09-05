<!-- markdownlint-disable MD013 -->
# Phase 2 Implementation Checklist: Directory Restructuring

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Based on**: [05-phase2-design.md](./05-phase2-design.md)

## Commit Steps (Execute in Order)

### Step 1: Pre-Move Configuration Updates
**Commit**: `"refactor: update build system for src/ structure"`

- [ ] Update `pyproject.toml`: Change `where = ["app"]` to `where = ["src"]`
- [ ] Update all Makefile PYTHONPATH references: `app` → `src`
- [ ] Update GitHub Actions workflows: PYTHONPATH environment variables
- [ ] Update `.claude/agents/` configurations: hardcoded `app/quilt_mcp` paths
- [ ] Test that configuration changes don't break current structure

### Step 2: Directory Structure Creation
**Commit**: `"feat: create consolidated directory structure"`

- [ ] Create `src/` directory
- [ ] Create `src/deploy/` directory (for DXT assets)
- [ ] Create `build/` directory structure
- [ ] Create `docs/archive/` directory
- [ ] Create `tests/docs/` directory (if not exists)

### Step 3: Source Code Moves
**Commit**: `"refactor: move application source to src/"`

- [ ] Move `app/quilt_mcp/` → `src/quilt_mcp/` (entire package structure)
- [ ] Move `app/main.py` → `src/main.py`
- [ ] Move `app/bootstrap.py` → `src/deploy/dxt_bootstrap.py` (rename)
- [ ] Verify all Python module relationships preserved

### Step 4: DXT Assets Consolidation
**Commit**: `"refactor: consolidate DXT assets to src/deploy/"`

- [ ] Move `tools/dxt/assets/` → `src/deploy/`
- [ ] Update DXT build references to new location
- [ ] Update any hardcoded paths in DXT configuration

### Step 5: Script Consolidation
**Commit**: `"refactor: consolidate essential scripts in tools/"`

**Move essential scripts**:
- [ ] Move `shared/version.sh` → `tools/version.sh`
- [ ] Move `shared/test-endpoint.sh` → `tools/validate-endpoint.sh`
- [ ] Move `shared/check-env.sh` → `tools/check-prereqs.sh`

**Remove obsolete scripts**:
- [ ] Remove `scripts/` directory (all 8 files)
- [ ] Remove remaining `shared/` files
- [ ] Remove `shared/` directory

### Step 6: Documentation Reorganization
**Commit**: `"docs: archive historical analysis documents"`

- [ ] Move `analysis/` → `docs/archive/analysis/`
- [ ] Remove `analysis/` directory
- [ ] Update documentation index references

### Step 7: Configuration Cleanup
**Commit**: `"refactor: remove obsolete configuration directories"`

- [ ] Remove `configs/` directory
- [ ] Move `app/test-results/` → `build/test-results/`
- [ ] Remove `app/` directory (should be empty)

### Step 8: Build Artifact Management
**Commit**: `"build: update gitignore and clean targets"`

- [ ] Update `.gitignore`:
  - Remove obsolete entries: `app/test-results/`, `scripts/`, `shared/`, `analysis/`, `configs/`
  - Add `build/` (comprehensive coverage)
  - Update `app/test-results/` → `build/test-results/`
  - Prune duplicate patterns
- [ ] Update `make clean` target:
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

- [ ] Run full test suite: `make test`
- [ ] Test build process: `make build`
- [ ] Test DXT packaging: `make dxt-package`
- [ ] Test clean process: `make clean`
- [ ] Verify MCP server starts: `make run`

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
- Test after each major structural change
- Preserve git history for all file moves
- Remove empty directories immediately after moves
- Update configuration before executing moves

**Critical validations**:
- PYTHONPATH changes must be tested before file moves
- All imports must resolve before considering step complete
- Build system must work after each configuration update
- DXT packaging must work with new asset locations

**Cleanup requirements**:
- No orphaned directories after completion
- Comprehensive `.gitignore` coverage
- `make clean` removes all temporary artifacts
- Repository in pristine, maintainable state
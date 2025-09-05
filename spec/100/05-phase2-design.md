<!-- markdownlint-disable MD013 -->
# Phase 2 Design: Directory Restructuring

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Based on**: [02-specifications.md](./02-specifications.md)

**Note**: This document specifies **what** changes should be made to the directory structure, without implementing the actual moves. Implementation details should be determined during the development phase.

## Current State Analysis

### Existing Directory Structure (16 Root Directories)

**Source Code Directories**:

- `app/quilt_mcp/` - Main Python package (13 modules, 8 subdirectories)
- `app/` - Container directory with additional files (`main.py`, egg-info, test-results)

**Utility Directories**:

- `scripts/` - 8 Python/shell scripts for optimization, validation, demos
- `shared/` - 6 shell scripts for common operations (env, endpoint testing)
- `tools/dxt/` - DXT packaging tools and assets

**Analysis and Documentation**:

- `analysis/` - 15 markdown analysis files (historical documentation)
- `docs/` - 8 subdirectories of user/developer documentation
- `spec/` - Specification documents (current and historical)

**Build and Configuration**:

- `configs/` - AWS configuration templates
- `tests/` - Test files and fixtures

**Development Environment**:

- `.venv/`, `.pytest_cache/`, `.ruff_cache/` - Tool-generated directories
- `.claude/`, `.cursor/`, `.github/` - IDE/CI configuration

**Build Artifacts** (gitignored):

- `build/`, `dist/`, `quilt_mcp_server.egg-info/` - Python packaging artifacts
- Generated during build process, not source-controlled

## Target Directory Structure (8 Root Directories)

### New Consolidated Structure

```tree
src/           # Consolidated source code
├── quilt_mcp/ # Moved from app/quilt_mcp/ (all modules and subdirectories)
└── main.py    # Moved from app/main.py (entry point)

tests/         # All test files
├── docs/      # Non-code artifacts to plan testing (new)
└── fixtures/  # Test utilities and fixtures

docs/          # Documentation (no changes)
├── api/, architecture/, developer/, user/ # Existing structure
└── archive/   # Historical documentation

tools/         # Essential build tools only
├── version.sh     # Consolidated version management (from shared/version.sh)
├── release.sh     # Complete release workflow (already created)
├── test-endpoint.sh # Endpoint validation (from shared/test-endpoint.sh)
├── check-prereqs.sh     # Environment validation (from shared/check-env.sh)

.claude/       # Claude configuration (no changes)
.github/       # CI/CD workflows (no changes)
.venv/         # Python virtual environment (gitignored, no changes)
build/         # Build artifacts and test results (gitignored)
dist/          # Package distribution (gitignored, no changes)
```

## Directory Movement Decisions

### Directories Consolidated

**`app/quilt_mcp/` → `src/quilt_mcp/`**:

- Move entire Python package structure
- Preserve all module relationships and subdirectories
- Flatten source hierarchy by one level

**`app/main.py` → `src/main.py`**:

- Move application entry point to consolidated source directory
- Maintain single entry point for the application

**DXT bootstrap file (needs renaming)**:

- Current bootstrap.py is peer of main.py for DXT packaging
- Should be renamed to better reflect its DXT-specific purpose
- Move to `src/deploy/` with other DXT assets

### Directories Removed

**`app/` (container directory)**:

- Remove after moving contents to `src/`
- Eliminates unnecessary nesting level
- `app/quilt_mcp_server.egg-info/` → Remove (build artifact)
- `app/test-results/` → Move to `build/test-results/` (gitignored test artifact)

**`scripts/` (8 files) → Selective consolidation**:

- Essential scripts move to `tools/`
- Demo/validation scripts removed as obsolete
- Optimization utilities integrated into main codebase

**`shared/` (6 files) → Integrate into `tools/`**:

- `common.sh` → Remove (functionality integrated into individual scripts)
- `version.sh` → `tools/version.sh`
- `test-endpoint.sh` → `tools/validate-endpoint.sh`
- `check-env.sh` → `tools/check-prereqs.sh`
- `tunnel-endpoint.sh` → Remove (complex networking, not core workflow)
- `test-tools.json` → Remove (obsolete individual tool testing configuration)

**`analysis/` (15 files)**:

- Historical analysis documents → `docs/archive/`
- Remove from root to reduce cognitive load
- Preserve as documentation reference

**`configs/` → Remove**:

- AWS configuration templates integrated into application
- Environment-specific configs managed through `.env` files

### Directories Preserved

**`tests/` (minimal changes)**:

- Maintain existing test structure and organization
- All test files continue to work with updated import paths

**`docs/` (minimal changes)**:

- Preserve existing documentation structure
- Update references to moved source files in documentation

**`tools/dxt/assets` → `src/deploy/`**:

- Move DXT packaging assets to consolidated deploy location
- Essential for Claude Desktop Extension creation
- Maintains packaging structure under new source organization

**IDE/CI configuration**:

- `.claude/`, `.cursor/`, `.github/` remain unchanged
- Update any hardcoded path references in configuration

## File Movement Mapping

### Source Code Moves

**Application Entry Point**:

```text
app/main.py                        → src/main.py
app/bootstrap.py                   → src/deploy/dxt_bootstrap.py (rename)
```

**DXT Assets Consolidation**:

```text
tools/dxt/assets/                  → src/deploy/
```

### Script Consolidation

**Essential Scripts (move to tools/)**:

```text
shared/version.sh                  → tools/version.sh
shared/test-endpoint.sh            → tools/validate-endpoint.sh
shared/check-env.sh                → tools/check-prereqs.sh
scripts/version-utils.py           → Remove (functionality consolidated into existing tools/release.sh)
```

**Scripts Removed (obsolete/integrated)**:

```text
scripts/optimize_mcp.py            → Remove (functionality in main codebase)
scripts/real_mcp_validation.py     → Remove (covered by tools/validate-endpoint.sh)
scripts/demo_unified_search.py     → Remove (demo utility, not build tool)
scripts/check_all_readme.py        → Remove (validation utility, not essential)
scripts/cellxgene-mcp-wrapper.sh   → Remove (specific use case, not general)
scripts/start_mcp_optimized.sh     → Remove (replaced by make run)
scripts/start-quilt-mcp.sh         → Remove (replaced by make run)
shared/common.sh                   → Remove (functionality distributed)
shared/tunnel-endpoint.sh          → Remove (complex networking, not core)
shared/test-tools.json             → Remove (obsolete tool testing config)
```

### Documentation Consolidation

**Analysis Documents**:

```text
analysis/*.md                      → docs/archive/analysis/
```

**Configuration Removal**:

```text
configs/aws/                       → Remove (integrated into application)
```

## Import Path Changes

### Python Import Updates Required

**Test Files** (47 files need updates):

```python
# Before
from quilt_mcp.tools import auth
from quilt_mcp.utils import validate_bucket

# After (no change - imports remain the same)
from quilt_mcp.tools import auth
from quilt_mcp.utils import validate_bucket
```

### Build System Updates

**PYTHONPATH Changes Required**:

```bash
# Before
export PYTHONPATH="app"

# After  
export PYTHONPATH="src"
```

**Make targets requiring updates**:

- `make.dev:run` - Update PYTHONPATH from "app" to "src"
- `make.dev:test*` - Update PYTHONPATH references
- `make.deploy:build` - Update source directory references

**DXT packaging updates**:

- `src/deploy/dxt_main.py` - Update import paths if hardcoded
- DXT build process - Update source directory references to `src/`

## Configuration File Updates

### Build Configuration

**pyproject.toml**:

```toml
# Before
[tool.setuptools.packages.find]
where = ["app"]

# After
[tool.setuptools.packages.find]
where = ["src"]
```

**GitHub Actions Workflows**:

```yaml
# Update PYTHONPATH references:
run: export PYTHONPATH="src" && make test
```

### IDE Configuration Updates

**.claude/agents/** - Update any hardcoded path references:

```text
app/quilt_mcp → src/quilt_mcp
```

**.cursor/rules** - Update workspace configuration if needed

### Documentation Updates

**Files requiring path updates**:

- `README.md` - Installation and development instructions
- `docs/developer/` - Developer onboarding guides
- `docs/api/` - API documentation with code examples
- `CLAUDE.md` - Repository-specific commands and permissions

## Success Metrics

### Quantitative Improvements

**Directory Reduction**:

- **Root directories**: 16 → 8 (-50%)
- **Maximum depth**: 8+ levels → 4 levels (-50%)
- **Script files**: 17 → 4 (-76%)

**File Organization**:

- **Source code centralization**: All Python code in single `src/` directory
- **Build tool focus**: Only essential tools in `tools/`
- **Documentation clarity**: Historical analysis moved to archive
- **Clean repository**: No empty directories, updated gitignore, comprehensive `make clean`

### Qualitative Improvements

**Single Source Location**:

- All application code in `src/quilt_mcp/`
- Clear entry point at `src/main.py`
- No confusion about which directory contains source

**Focused Tools Directory**:

- Only essential build/release scripts
- Scripts co-located with their purpose
- Shell-first approach for simple orchestration

**Reduced Cognitive Load**:

- Fewer root directories to navigate
- Clear separation of source, tests, docs, tools
- No duplicate or obsolete utilities

**Import Path Simplification**:

- Consistent `quilt_mcp.*` imports throughout
- Single PYTHONPATH configuration
- No nested `app.quilt_mcp` references

## Risks and Mitigation

### Risk: Breaking Import Paths

**Impact**: Test files and tools may fail to import modules

**Mitigation**:

- Update PYTHONPATH in all Make targets before moving files
- Batch update all import references in single commit
- Test import resolution before and after changes

### Risk: Build System Disruption

**Impact**: CI/CD pipelines may fail with new directory structure

**Mitigation**:

- Update GitHub Actions workflows simultaneously with moves
- Test build process in development branch before merging
- Update DXT packaging to reference new source location

### Risk: Development Workflow Interruption

**Impact**: Developers may use outdated paths or commands

**Mitigation**:

- Update CLAUDE.md and README.md with new structure
- Provide migration guide for common development tasks
- Update IDE configurations to reference new paths

### Risk: Loss of Historical Context

**Impact**: Analysis documents may become harder to find

**Mitigation**:

- Move analysis files to `docs/archive/` instead of deleting
- Update documentation index to reference archived content
- Preserve git history for moved files

## Cleanup Requirements

### Directory Maintenance

**Empty Directory Removal**:

- Remove all empty directories created by moves (e.g., `app/` after contents moved)
- Ensure no orphaned directory structures remain
- Verify git properly tracks directory removals

**Build Artifact Management**:

- Update `make clean` target to remove all temporary folders:
  - `build/` (including `build/test-results/`)
  - `dist/`
  - `*.egg-info/` directories
  - `.pytest_cache/`, `.ruff_cache/`
- Ensure clean build environment after restructure

**Gitignore Maintenance**:

- Remove obsolete gitignore entries for moved/deleted paths:
  - `app/test-results/` → update to `build/test-results/`
  - Remove entries for deleted `scripts/`, `shared/`, `analysis/`, `configs/`
- Add new gitignore entries for consolidated structure:
  - `build/` (comprehensive coverage)
  - Verify `src/` is not accidentally ignored
- Prune irrelevant or duplicate gitignore patterns

## Validation Requirements

### Pre-Move Validation

**Dependency Analysis**:

- Audit all Python imports for hardcoded paths
- Check build scripts for directory references
- Verify no absolute paths in configuration

**Tool Integration Check**:

- Ensure essential script functionality preserved
- Verify no external dependencies on removed scripts
- Test that consolidated tools maintain all required features

### Post-Move Validation

**Build System Testing**:

- Verify all Make targets work with new structure
- Test `make clean` removes all temporary directories
- Test DXT packaging with updated paths
- Confirm CI/CD pipelines pass with new configuration
- Verify no empty directories remain after moves

**Import Resolution Testing**:

- Run full test suite to verify all imports resolve
- Test interactive Python sessions with new PYTHONPATH
- Verify MCP server starts correctly with new entry point

**Documentation Accuracy**:

- Test all commands in updated README.md
- Verify developer onboarding instructions work
- Confirm API documentation references are correct

## Implementation Dependencies

### External Tool Compatibility

**Python Packaging**:

- `uv` must recognize new source directory structure
- `setuptools` configuration updated for new package location
- Virtual environment imports work with new PYTHONPATH

**Development Tools**:

- IDE configurations updated for new directory structure
- Linting tools (ruff, mypy) configured for new source location
- Test runners find tests and source with updated paths

### Internal Dependencies

**Documentation Updates**:

- All `.md` files updated to reference new paths
- Code examples in documentation use correct import paths
- Developer guides reflect new directory organization

**Configuration Management**:

- Environment setup scripts use new PYTHONPATH
- Build scripts reference correct source directories
- Release workflows package from new location

**Repository Maintenance**:

- Update `.gitignore` to reflect new directory structure
- Ensure `make clean` target covers all new temporary locations
- Remove empty directories created by file moves
- Verify git history preservation for moved files

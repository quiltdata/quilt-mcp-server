<!-- markdownlint-disable MD013 -->
# Specifications: Repository/Makefile Cleanup

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Based on**: [01-requirements.md](./01-requirements.md)

**Note**: This document specifies **what** the simplified structure should accomplish and **what** each component should do, without implementing the actual code. Implementation details should be determined during the development phase.

## Current State Analysis

**Note**: As of September 2025, Phases 1 and 2 have been completed. The current state reflects the partially-implemented cleanup.

### Repository Structure Complexity

**Original Directory Depth**: Up to 8+ levels deep (e.g., `.venv/lib/python3.12/site-packages/...`)
**Original Root Directories**: 16 major folders plus numerous config files and artifacts
**Current Root Directories**: 14 directories (Phase 2 partially complete - `app/`, `scripts/`, `shared/` removed)

### Makefile Redundancy Issues

#### 1. **Multiple Makefiles with Overlapping Responsibilities** (COMPLETED - Phase 1)

- **Original Root `Makefile`** (199 lines): Phase coordinator with delegation patterns
- **Original `app/Makefile`** (137 lines): App-specific build and test commands  
- **Original `tools/dxt/Makefile`** (148 lines): DXT packaging and validation
- **Current Consolidated System** (274 lines total): Main `Makefile` + `make.dev` + `make.deploy`

#### 2. **Redundant Targets Across Makefiles**

- `clean` target exists in all 3 Makefiles with different scopes
- `test` variations scattered: `test`, `test-unit`, `test-ci`, `test-endpoint`
- `validate` targets in root and phase-specific Makefiles
- Multiple `help` targets with inconsistent information

#### 3. **Complex Delegation Patterns**

- Root Makefile delegates to phase-specific Makefiles using `$(MAKE) -C <dir>`
- Inconsistent variable passing between Makefiles
- Phase-specific environment setup duplicated

### Helper Script Proliferation (PARTIALLY ADDRESSED - Phase 2)

#### Original Scripts Directory (10 files) - REMOVED

- `optimize_mcp.py`, `real_mcp_validation.py` - Optimization utilities
- `cellxgene-mcp-wrapper.sh`, `start_mcp_optimized.sh`, `start-quilt-mcp.sh` - Multiple startup scripts
- `check_all_readme.py`, `demo_unified_search.py` - Demo/validation utilities
- `version-utils.py` - Version management utility

#### Original Shared Directory (7 files) - REMOVED

- `common.sh`, `test-endpoint.sh`, `tunnel-endpoint.sh` - Endpoint utilities
- `check-env.sh`, `version.sh` - Environment utilities
- `test-tools.json` - Configuration file

#### Original App-Specific Scripts - REMOVED

- `app/app.sh` - App configuration and validation

#### Current Tools Directory (4 files) - NEEDS PHASE 3 REFINEMENT

- `tools/check-env.sh` - Environment validation (needs refinement to `bin/check-prereqs.sh`)
- `tools/release.sh` - Release workflow (needs refinement)
- `tools/test-endpoint.sh` - Endpoint testing (needs refinement to `bin/validate-endpoint.sh`)
- `tools/version.sh` - Version management (needs refinement)

### Excessive Validation Attempts

#### Multiple Test Commands

- `make test`, `make test-unit`, `make test-ci`, `make test-endpoint`
- `make coverage`, `make coverage-unit`
- `make validate`, `make validate-app`, `make validate-dxt`
- `make verify` (in app Makefile)

#### Redundant Validation Scripts

- `scripts/real_mcp_validation.py`
- `shared/test-endpoint.sh`
- `app/app.sh validate`

## Proposed Simplified Structure

### 1. **Unified Makefile with Includes Strategy**

**Target**: Single entry point `Makefile` that includes concern-specific makefiles:

**Main Makefile** (~30 lines) - Entry point and coordination:

- `help` - Display all available targets organized by category
- `clean` - Coordinate cleanup across all phases
- `release` - Full release workflow (test → build → package)

**make.dev** (~40 lines) - Development workflow targets:

- `test` - Run all tests with appropriate PYTHONPATH setup
- `test-unit` - Run unit tests only (fast subset)
- `test-integration` - Run integration tests with external dependencies
- `lint` - Run code formatting and type checking
- `coverage` - Generate test coverage reports
- `run` - Start local development server
- `dev-clean` - Clean development artifacts (Python cache, etc.)

**make.deploy** (~40 lines) - Production/packaging workflow targets:

- `build` - Prepare production build environment
- `package` - Create Python package distribution
- `dxt-build` - Prepare DXT package build directory
- `dxt-package` - Create Claude Desktop Extension (.dxt) package
- `deploy-clean` - Clean build and distribution artifacts

### 2. **Simplified Directory Structure**

**Before** (16+ root directories):

```tree
app/ analysis/ build/ configs/ dist/ docs/ quilt_mcp_server.egg-info/
scripts/ shared/ spec/ tests/ tools/ .claude/ .cursor/ .github/
.pytest_cache/ .ruff_cache/ .venv/
```

**After** (8 root directories):

```tree
src/           # Consolidated source code (merge app/quilt_mcp)
tests/         # All test files
docs/          # Documentation
bin/           # Essential build tools only  
.github/       # CI/CD workflows
.venv/         # Python virtual environment (gitignored)
dist/          # Build artifacts (gitignored)
.claude/       # Claude configuration
```

### 3. **Focused Scripts Strategy**

**Replace 17 scripts with focused, single-purpose shell tools co-located with what they affect**:

**Essential Scripts Only** (all co-located in `bin/`):

- `bin/version.sh` - Version management and tagging (simplify complex git/toml logic)
- `bin/release.sh` - Complete release workflow (Python package + DXT package + tagging)
- `bin/test-endpoint.sh` - Endpoint validation (remove complex curl/retry logic)
- `bin/test-prereqs.sh` - Environment validation (multi-tool checking)

### 4. **Streamlined Testing Strategy**

**Replace 8+ test commands with 3 clear targets**:

1. **`make test`** - Fast unit tests for development
2. **`make test-integration`** - Full integration tests with AWS
3. **`make test-ci`** - CI-optimized test suite

## Implementation Plan

### Phase 1: Makefile Consolidation ✅ COMPLETED

1. **Audit current targets** - Map all targets across 3 Makefiles ✅
2. **Identify truly unique functionality** - Separate essential from redundant ✅
3. **Create include-based structure** - Main `Makefile` + `make.dev` + `make.deploy` ✅
4. **Migrate targets by concern** - Development vs production workflows ✅
5. **Test compatibility** - Ensure all workflows continue working ✅

### Phase 2: Directory Restructuring ✅ COMPLETED

1. **Move `app/quilt_mcp/` → `src/quilt_mcp/`** - Flatten source structure ✅
2. **Consolidate scripts** - Merge related functionality ✅ (moved to `tools/`)
3. **Remove redundant directories** - Clean up build artifacts and temporary dirs ✅
4. **Update import paths** - Fix Python imports for new structure ✅

### Phase 3: Script Refactoring 🚧 IN PROGRESS

1. **Refine existing scripts** - Convert `tools/` scripts to focused `bin/` scripts following Unix philosophy
2. **Rename and reorganize** - Move `tools/` → `bin/` and standardize interfaces
3. **Convert to shell where appropriate** - Use shell for simple orchestration, Python only when needed
4. **Remove obsolete functionality** - Clean up unused automation within existing scripts
5. **Test each script independently** - Ensure each tool works in isolation

**Current Status**: 4 scripts exist in `tools/` but need refinement to match specifications

### Phase 4: Validation Simplification ⏳ PENDING

1. **Streamline test targets** - Clear separation of concerns
2. **Remove redundant validation** - Single validation path per use case
3. **Optimize CI/CD integration** - Simplified GitHub Actions workflows

**Current Status**: Awaiting completion of Phase 3

## Success Metrics

### Quantitative Targets

- **Makefile complexity**: 484 lines across 3 files → 274 lines across 3 files (-43%) ✅ ACHIEVED (better than target)
- **Build entry points**: 3 separate Makefiles → 1 unified entry point with includes ✅ ACHIEVED
- **Scripts**: 17 → 4 essential tools (-76%) 🚧 IN PROGRESS (4 scripts exist, need refinement)
- **Root directories**: 16 → 14 → 8 (-50%) 🚧 PARTIAL (14 currently, targeting 8)
- **Make targets**: ~40 → ~15 (-62%) ℹ️ NEEDS AUDIT
- **Maximum directory depth**: 8+ → 4 (-50%) ℹ️ NEEDS VERIFICATION

### Qualitative Improvements

- **Single entry point** (`make help`) for all build operations
- **Clear separation of concerns** (development vs production workflows)
- **Unix philosophy compliance** - Each script does one thing well
- **Co-location principle** - Scripts placed near what they affect
- **Shell-first approach** - Simple orchestration in shell, Python when needed
- **Obvious location** for every file and operation
- **Reduced cognitive load** with focused, smaller tools
- **Cross-platform compatibility** using standard `include` directive
- **Improved maintainability** with no duplication between files
- **Independent testability** - Each tool can be tested in isolation

## Risks and Mitigation

### Risk: Breaking Existing Workflows

**Mitigation**: Implement incrementally with backward compatibility aliases

### Risk: Loss of Phase-Specific Functionality  

**Mitigation**: Preserve essential phase logic in consolidated structure

### Risk: Disruption to CI/CD Pipelines

**Mitigation**: Update GitHub Actions workflows simultaneously with structure changes

## Dependencies

### External Tool Requirements

- Maintain compatibility with `uv`, `gh`, `npx`
- Preserve integration with GitHub Actions
- Keep DXT packaging workflow functional

### Internal Dependencies

- Update CLAUDE.md development guidelines
- Modify WORKFLOW.md to reflect new structure
- Update documentation references to old paths

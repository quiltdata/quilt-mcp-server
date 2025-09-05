# Specifications: Repository/Makefile Cleanup

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Based on**: [01-requirements.md](./01-requirements.md)

## Current State Analysis

### Repository Structure Complexity

**Current Directory Depth**: Up to 8+ levels deep (e.g., `.venv/lib/python3.12/site-packages/...`)
**Current Root Directories**: 16 major folders plus numerous config files and artifacts

### Makefile Redundancy Issues

#### 1. **Multiple Makefiles with Overlapping Responsibilities**

- **Root `Makefile`** (199 lines): Phase coordinator with delegation patterns
- **`app/Makefile`** (137 lines): App-specific build and test commands  
- **`tools/dxt/Makefile`** (148 lines): DXT packaging and validation

#### 2. **Redundant Targets Across Makefiles**

- `clean` target exists in all 3 Makefiles with different scopes
- `test` variations scattered: `test`, `test-unit`, `test-ci`, `test-endpoint`
- `validate` targets in root and phase-specific Makefiles
- Multiple `help` targets with inconsistent information

#### 3. **Complex Delegation Patterns**

- Root Makefile delegates to phase-specific Makefiles using `$(MAKE) -C <dir>`
- Inconsistent variable passing between Makefiles
- Phase-specific environment setup duplicated

### Helper Script Proliferation

#### Scripts Directory (10 files)

- `optimize_mcp.py`, `real_mcp_validation.py` - Optimization utilities
- `cellxgene-mcp-wrapper.sh`, `start_mcp_optimized.sh`, `start-quilt-mcp.sh` - Multiple startup scripts
- `check_all_readme.py`, `demo_unified_search.py` - Demo/validation utilities
- `version-utils.py` - Version management utility

#### Shared Directory (7 files)

- `common.sh`, `test-endpoint.sh`, `tunnel-endpoint.sh` - Endpoint utilities
- `check-env.sh`, `version.sh` - Environment utilities
- `test-tools.json` - Configuration file

#### App-Specific Scripts

- `app/app.sh` - App configuration and validation

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

### 1. **Single Makefile Strategy**

**Target**: Consolidate into one root `Makefile` with clear sections:

```makefile
# Root Makefile (simplified)
.PHONY: help install dev test lint clean build package release

# Development
dev: install
test: unit-test integration-test
lint: format typecheck

# Production
build: clean test lint
package: build
release: package

# Utilities  
clean:
install:
format:
typecheck:
unit-test:
integration-test:
```

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
tools/         # Essential build tools only  
.github/       # CI/CD workflows
.venv/         # Python virtual environment (gitignored)
dist/          # Build artifacts (gitignored)
.claude/       # Claude configuration
```

### 3. **Consolidated Scripts Strategy**

**Replace 17 scripts with 3 essential utilities**:

1. **`tools/dev.py`** - Development utilities (replaces 8 scripts)
   - Server startup/shutdown
   - Environment validation
   - Development workflows

2. **`tools/build.py`** - Build and packaging (replaces 4 scripts)
   - Version management
   - DXT packaging
   - Release preparation

3. **`tools/test.py`** - Testing utilities (replaces 5 scripts)
   - Test execution
   - Coverage reporting
   - Endpoint validation

### 4. **Streamlined Testing Strategy**

**Replace 8+ test commands with 3 clear targets**:

1. **`make test`** - Fast unit tests for development
2. **`make test-integration`** - Full integration tests with AWS
3. **`make test-ci`** - CI-optimized test suite

## Implementation Plan

### Phase 1: Makefile Consolidation

1. **Audit current targets** - Map all targets across 3 Makefiles
2. **Identify truly unique functionality** - Separate essential from redundant
3. **Create unified Makefile** - Single source of truth for all operations  
4. **Test compatibility** - Ensure all workflows continue working

### Phase 2: Directory Restructuring  

1. **Move `app/quilt_mcp/` → `src/quilt_mcp/`** - Flatten source structure
2. **Consolidate scripts** - Merge related functionality
3. **Remove redundant directories** - Clean up build artifacts and temporary dirs
4. **Update import paths** - Fix Python imports for new structure

### Phase 3: Script Consolidation

1. **Merge startup scripts** - Single server startup utility
2. **Consolidate validation scripts** - Single testing/validation utility  
3. **Combine build utilities** - Single packaging/release script
4. **Remove obsolete scripts** - Clean up unused automation

### Phase 4: Validation Simplification

1. **Streamline test targets** - Clear separation of concerns
2. **Remove redundant validation** - Single validation path per use case
3. **Optimize CI/CD integration** - Simplified GitHub Actions workflows

## Success Metrics

### Quantitative Targets

- **Makefiles**: 3 → 1 (-67%)
- **Scripts**: 17 → 3 (-82%)
- **Root directories**: 16 → 8 (-50%)
- **Make targets**: ~40 → ~15 (-62%)
- **Maximum directory depth**: 8+ → 4 (-50%)

### Qualitative Improvements

- **Single source of truth** for all build operations
- **Obvious location** for every file and operation
- **Reduced cognitive load** for new contributors
- **Improved maintainability** with less duplication
- **Faster onboarding** with simplified structure

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

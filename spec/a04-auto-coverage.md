<!-- markdownlint-disable MD013 -->
# A04: Automated Coverage Reporting and CI Optimization

**Status:** Draft
**Date:** 2025-01-19
**Author:** Claude Code

## Overview

This specification defines an enhanced CI/CD architecture that separates fast Pull Request validation from comprehensive main branch testing, while implementing multi-suite coverage analysis with detailed reporting.

## Requirements

### Functional Requirements

- **FR-1**: Pull Request updates receive fast feedback (< 5 minutes) with single Python version testing (and make test-ci) and dev releases, if tagged
- **FR-2**: Main branch pushes get comprehensive testing across all Python versions (3.11, 3.12, 3.13) (and one 'make coverage'), and prod release, if tagged
- **FR-3**: Individual test suites (unit, integration, e2e) create uniquely-named coverage reports
- **FR-4**: 'make coverage' summarizes those in an export to CSV format with file-level granularity
- **FR-5**: Reusable GitHub Actions eliminate workflow duplication

### Non-Functional Requirements

- **NFR-1**: Reduce CI costs by minimizing unnecessary matrix builds on PRs
- **NFR-2**: Maintain existing test coverage thresholds (≥85%)
- **NFR-3**: Preserve artifact upload functionality for debugging

## Current State Analysis

### Existing CI Workflow Issues

- Single monolithic `ci.yml` runs full matrix for both PRs and main pushes
- Coverage reporting duplicated across test targets
- No visibility into which test suites cover which code paths
- Unnecessary CI minutes consumed on PR validation

### Current Test Structure

```tree
make.dev:
├── test (defaults to test-unit)
├── test-all (comprehensive)
├── test-unit (fast, mocked)
├── test-integration (AWS/external)
├── test-e2e (end-to-end workflows)
├── test-ci (CI optimized)
└── coverage (threshold checking)
```

## Proposed Architecture

### 1. CI Workflow Split

The architecture uses two primary workflows that handle testing and conditional release creation within the same workflow for reliability.

#### Pull Request Workflow (`pr.yml`)

**Purpose**: Fast PR validation with optional dev releases

**Triggers**:

- Pull requests against any branch
- Conditional dev release for `dev-*` branches or labeled PRs

**Behavior**:

- Run fast tests (`make test-ci`) on Python 3.11 only
- If PR is on `dev-*` branch or has `dev-release` label:
  - After tests pass, create dev GitHub release directly (no separate workflow needed)

#### Main Branch Workflow (`push.yml`)

**Purpose**: Comprehensive testing with conditional production release

**Triggers**:

- Pushes to main branch
- Tag pushes (`v*` pattern)
- Merge group events

**Behavior**:

- **For main branch pushes**: Run comprehensive tests across Python versions (3.11, 3.12, 3.13)
- **For tag pushes**:
  1. Run comprehensive tests FIRST
  2. IF tests pass AND tag matches production pattern (`v*` but not `v*-dev-*`)
  3. THEN build and create GitHub release within same workflow
- **Coverage analysis**: Generate multi-suite coverage reports and CSV analysis

#### Release Strategy

**Dev Releases**:

- Triggered by `dev-*` branch PRs or `dev-release` label
- Flow: PR tests pass → create dev GitHub release directly within `pr.yml`
- Safety: Release creation only after PR tests pass, no separate workflows

**Production Releases**:

- Triggered by production tag pushes (`v*` but not `v*-dev-*`)
- Flow: Tag push → run tests in main workflow → IF tests pass THEN create GitHub release
- Safety: Release creation happens within same workflow as testing
- No separate release workflow - everything in `push.yml`

### 2. Reusable GitHub Actions

#### Test Execution Action (`run-tests`)

```yaml
# .github/actions/run-tests/action.yml
name: 'Run Tests'
inputs:
  test-target:
    description: 'Make target to execute'
    required: true
  upload-artifacts:
    description: 'Upload test artifacts'
    default: 'true'
runs:
  using: 'composite'
  steps:
    - name: Execute tests
      shell: bash
      run: make ${{ inputs.test-target }}
    - name: Upload artifacts
      if: inputs.upload-artifacts == 'true'
      uses: actions/upload-artifact@v4
      # ... artifact configuration
```

#### Coverage Reporting Action (`coverage-report`)

```yaml
# .github/actions/coverage-report/action.yml
name: 'Coverage Analysis'
inputs:
  python-version:
    description: 'Python version for artifact naming'
    required: true
runs:
  using: 'composite'
  steps:
    - name: Run comprehensive coverage
      shell: bash
      run: make coverage
    - name: Generate coverage analysis
      shell: bash
      run: python scripts/coverage_analysis.py
    - name: Upload coverage artifacts
      uses: actions/upload-artifact@v4
      # ... coverage-specific artifacts
```

#### Release Creation Action (`create-release`)

```yaml
# .github/actions/create-release/action.yml
name: 'Create Release'
description: 'Build DXT package and create GitHub release with bundle'
inputs:
  tag-version:
    description: 'Version from git tag (e.g., 0.5.9-dev-20250904075318)'
    required: true
runs:
  using: 'composite'
  steps:
    - name: Build DXT package
      shell: bash
      run: make dxt
    - name: Validate DXT package
      shell: bash
      run: make dxt-validate
    - name: Create release bundle
      shell: bash
      run: make release-zip
    - name: Create GitHub Release
      uses: softprops/action-gh-release@v2
      with:
        name: "Quilt MCP DXT v${{ inputs.tag-version }}"
        files: dist/*-release.zip
        prerelease: ${{ contains(inputs.tag-version, '-') }}
        generate_release_notes: true
```

### 3. Enhanced Make Targets

#### Enhanced Coverage Implementation

The `coverage` target now runs multiple test suites and generates comprehensive analysis:

```makefile
coverage:
 @echo "Running comprehensive coverage analysis..."
 @$(MAKE) test-unit
 @$(MAKE) test-integration
 @$(MAKE) test-e2e
 @echo "Generating coverage analysis report..."
 @uv sync --group test
 @export PYTHONPATH="src" && uv run python scripts/coverage_analysis.py
```

#### Release System Integration

The release system separates tag creation from GitHub release creation:

- **`make release`** - Creates and pushes git tags using `bin/release.sh`
- **`make release-dev`** - Creates and pushes dev tags using `bin/release.sh`
- **`create-release` action** - Builds packages and creates GitHub releases (triggered by tag pushes)

**Key insight**: `make release` creates git tags, NOT GitHub releases. GitHub releases are created by the `create-release` action when workflows detect tag pushes.

#### Coverage File Organization

```tree
build/test-results/
├── coverage-unit.xml       # Unit test coverage
├── coverage-integration.xml # Integration test coverage
├── coverage-e2e.xml        # E2E test coverage
├── coverage-all.xml         # Combined coverage (test-all)
├── coverage.xml             # CI coverage (test-ci)
├── coverage-analysis.csv    # Generated analysis
└── results.xml              # JUnit test results
```

### 4. Coverage Analysis Script

#### Script Specification (`scripts/coverage_analysis.py`)

```python
"""
Coverage Analysis Script

Parses XML coverage reports from multiple test suites and generates
comparative analysis in CSV format.

Input Files:
- build/test-results/coverage-unit.xml
- build/test-results/coverage-integration.xml
- build/test-results/coverage-e2e.xml

Output:
- build/test-results/coverage-analysis.csv

CSV Columns:
- file: Source file path
- unit_coverage: Unit test coverage percentage
- integration_coverage: Integration test coverage percentage
- e2e_coverage: E2E test coverage percentage
- combined_coverage: Overall coverage percentage
- lines_total: Total lines in file
- lines_covered: Lines covered by any test
- coverage_gaps: Lines only covered by specific test types

Error Handling:
- Missing XML files: Log warning and continue with available files
- Malformed XML: Skip invalid files and report parsing errors
- Empty coverage data: Generate CSV with zero values but maintain file structure
- Write failures: Exit with error code 1 and clear error message
"""
```

#### CSV Output Format

```csv
file,unit_coverage,integration_coverage,e2e_coverage,combined_coverage,lines_total,lines_covered,coverage_gaps
src/quilt_mcp/tools/auth.py,85.2,45.3,12.1,92.1,145,133,unit-only:67;integration-only:23
src/quilt_mcp/tools/buckets.py,72.4,89.1,34.5,95.2,234,223,e2e-only:12;integration-only:45
```

## Implementation Phases

### Phase 1: Workflow Split

1. Create new workflow files (pr.yml, push.yml, release.yml)
2. Configure workflow_run dependencies for release workflow
3. Test with sample PR and main branch push
4. Verify workflow dependency triggers work correctly
5. Verify artifact generation and upload
6. Deprecate existing ci.yml

### Phase 2: Reusable Actions

1. Create run-tests action
2. Create coverage-report action
3. Update workflows to use new actions
4. Test action reusability

### Phase 3: Enhanced Coverage

1. Implement coverage_analysis.py script
2. Update coverage make target
3. Verify CSV generation and format
4. Test coverage threshold validation

### Phase 4: Integration & Cleanup

1. Update documentation
2. Clean up deprecated files
3. Performance validation
4. Final integration testing

## Testing Strategy

### Unit Testing

- Test coverage_analysis.py with sample XML files
- Verify CSV parsing and generation logic
- Test error handling for malformed inputs

### Integration Testing

- Execute full workflow on test branch
- Verify workflow_run dependency triggers
- Verify artifact uploads and downloads
- Test matrix builds across Python versions
- Test release workflow dependency behavior

### Performance Testing

- Measure PR feedback time (target: < 5 minutes)
- Validate coverage analysis execution time
- **CI Cost Validation**: Document current matrix builds per month, measure 60% reduction target
- **Build Minutes Tracking**: Compare PR vs main branch CI minutes consumed before/after split

## Risk Assessment

### High Risk

- **Breaking existing CI**: Mitigation through gradual rollout and thorough testing
- **Coverage regression**: Maintain existing thresholds and add validation

### Medium Risk

- **Action marketplace issues**: Use composite actions to avoid external dependencies
- **Artifact size limits**: Implement compression and cleanup policies

### Low Risk

- **CSV parsing errors**: Comprehensive error handling and fallback logic
- **Make target evolution**: Update interfaces for enhanced functionality

## Success Metrics

### Performance Metrics

- PR feedback time: < 5 minutes (vs current ~15 minutes)
- CI cost reduction: 60% fewer builds on PRs
- Coverage analysis time: < 2 minutes additional overhead

### Quality Metrics

- Maintain ≥85% overall coverage threshold
- Zero regression in test coverage
- 100% artifact upload success rate

### Usability Metrics

- Clear coverage gap identification in CSV reports
- Actionable feedback on coverage improvements
- Simplified workflow maintenance

## Corrected Release Understanding

**CRITICAL CORRECTION**: The original spec confused tag creation with GitHub release creation. Here's the correct flow:

### Tag Creation (Local/Make Targets)

- `make release` → calls `bin/release.sh release` → creates git tags → pushes to GitHub
- `make release-dev` → calls `bin/release.sh dev` → creates dev tags → pushes to GitHub

### GitHub Release Creation (GitHub Actions)

- Tag push triggers workflow (`.github/workflows/release.yml` or `dev-release.yml`)
- Workflow runs tests FIRST
- ONLY if tests pass, workflow calls `.github/actions/create-release`
- `create-release` action builds DXT package and creates GitHub release

### Key Principles

1. **Never call `make release` in CI** - it creates tags, not GitHub releases
2. **Use `create-release` action in workflows** - it creates actual GitHub releases
3. **Tests must pass before release creation** - happens within the same workflow
4. **Release creation follows tag creation** - two separate operations with safety gates

## Dependencies

### External

- GitHub Actions marketplace availability
- pytest-cov XML output format stability
- uv package manager compatibility

### Internal

- Existing make.dev structure
- Current test suite organization
- Build artifact directory conventions

## Future Enhancements

### Planned

- Coverage trend analysis over time
- Integration with GitHub PR comments
- Automated coverage improvement suggestions

### Potential

- Coverage visualization dashboards
- Integration with external coverage services
- Parallel test execution optimization

---

## Appendix A: File Structure

```tree
.github/
├── workflows/
│   ├── pr.yml              # NEW - Fast PR validation
│   ├── push.yml            # NEW - Comprehensive main testing
│   ├── release.yml         # NEW - Tag-based releases
│   └── ci.yml              # DEPRECATED - Remove after migration
└── actions/
    ├── setup-build-env/    # EXISTING - Keep as-is
    ├── run-tests/          # NEW - Common test execution
    └── coverage-report/    # NEW - Coverage analysis

scripts/
└── coverage_analysis.py    # NEW - Multi-suite coverage analysis

make.dev                    # MODIFIED - Enhanced coverage target

build/test-results/         # ENHANCED - Structured coverage files
├── coverage-*.xml          # Per-suite coverage files
├── coverage-analysis.csv   # Generated comparative analysis
└── results.xml            # JUnit results
```

## Release Understanding

**CRITICAL CORRECTION**: Eliminate separate `release.yml` workflow. Use reliable same-workflow approach.

### Simplified Architecture

- **Two workflows only**: `pr.yml` and `push.yml`
- **No auxiliary workflows** - everything handled within the two main workflows
- **No separate release workflows** - both dev and production releases handled inline

### Reliable Release Flow

1. **Production tags** (`v*` not `v*-dev-*`) trigger `push.yml`
2. **Same workflow** runs tests first
3. **IF tests pass** THEN create GitHub release
4. **No `workflow_run` dependencies** - everything in one reliable workflow

## Appendix B: Migration Checklist

- [ ] Create workflow files (pr.yml, push.yml) - NO release.yml, NO dev-release.yml
- [ ] Remove workflow_run dependencies - use conditional logic within push.yml
- [ ] Implement reusable actions (run-tests, coverage-report, create-release)
- [ ] Develop coverage_analysis.py script
- [ ] Update make.dev coverage target
- [ ] Test PR workflow with sample branch
- [ ] Test push workflow with main branch AND tag pushes
- [ ] Test same-workflow release creation (tag → test → release)
- [ ] Validate coverage CSV generation
- [ ] Update project documentation
- [ ] Remove deprecated ci.yml
- [ ] Monitor performance and adjust thresholds

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

The architecture uses three separate workflows with smart dependencies to optimize CI performance while ensuring release safety.

#### Pull Request Workflow (`pr.yml`)

```yaml
name: Pull Request Validation
on:
  pull_request:
    branches: ['**']
  push:
    branches-ignore: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/setup-build-env
        with:
          python-version: '3.11'
      - uses: ./.github/actions/run-tests
        with:
          test-target: 'test-ci'
          upload-artifacts: true

  dev-release:
    runs-on: ubuntu-latest
    needs: test
    if: github.event_name == 'push' && github.ref != 'refs/heads/main'
    steps:
      - uses: ./.github/actions/setup-build-env
        with:
          python-version: '3.11'
      - name: Create Dev Release
        run: make release-dev
```

#### Main Branch Workflow (`push.yml`)

```yaml
name: Main Branch Validation
on:
  push:
    branches: [main]
  merge_group:
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: ./.github/actions/setup-build-env
        with:
          python-version: ${{ matrix.python-version }}
      - uses: ./.github/actions/coverage-report
        with:
          python-version: ${{ matrix.python-version }}
```

#### Production Release Workflow (`release.yml`)

```yaml
name: Production Release
on:
  workflow_run:
    workflows: ["Main Branch Validation"]
    types: [completed]
    branches: [main]
  push:
    tags: ['v*']
    tags-ignore: ['v*-dev-*']
jobs:
  prod-release:
    runs-on: ubuntu-latest
    # Workflow_run takes precedence: only run if main tests passed OR direct emergency tag push (production tags only)
    if: ${{ (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success') || (github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v') && !contains(github.ref, '-dev-')) }}
    steps:
      - uses: ./.github/actions/setup-build-env
        with:
          python-version: '3.11'
      - name: Create Production Release
        run: make release
```

#### Dev Release Workflow (`dev-release.yml`)

```yaml
name: Development Release
on:
  push:
    tags: ['v*-dev-*']
jobs:
  dev-release:
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/setup-build-env
        with:
          python-version: '3.11'
      - name: Create Development Release
        uses: ./.github/actions/create-release
        with:
          prerelease: true
```

#### Release Strategy

The architecture supports both development and production releases with appropriate safety gates:

**Dev Releases (PR Workflow)**:

- **Trigger**: Any push to PR branches (not main)
- **Dependency**: Requires successful PR test completion (`make test-ci`)
- **Target**: `make release-dev` creates timestamped dev tags (`v*-dev-*`)
- **Safety**: Only after fast PR validation passes
- **Workflow**: Separate dev release workflow triggered by dev tag pattern

**Production Releases (Release Workflow)**:

- **Trigger**: Main branch merges or production tag pushes (excluding dev tags)
- **Dependency**: Requires successful main branch validation via `workflow_run`
- **Target**: `make release` creates production tags (`v*` but not `v*-dev-*`)
- **Safety**: Only after comprehensive main branch testing
- **Manual Override**: Direct production tag pushes for emergency releases

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

### 3. Enhanced Make Targets

#### New Coverage Implementation

```makefile
coverage:
 @echo "Running comprehensive coverage analysis..."
 @$(MAKE) test-unit
 @$(MAKE) test-integration
 @$(MAKE) test-e2e
 @echo "Generating coverage analysis report..."
 @uv sync --group test
 @export PYTHONPATH="src" && uv run python scripts/coverage_analysis.py
 @echo "Checking coverage threshold..."
 @export PYTHONPATH="src" && uv run python -m pytest tests/ --cov=quilt_mcp --cov-fail-under=85 --cov-report= -q
```

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

## Appendix B: Migration Checklist

- [ ] Create workflow files (pr.yml, push.yml, release.yml)
- [ ] Configure workflow_run dependencies for release safety
- [ ] Implement reusable actions (run-tests, coverage-report)
- [ ] Develop coverage_analysis.py script
- [ ] Update make.dev coverage target
- [ ] Test PR workflow with sample branch
- [ ] Test push workflow with main branch
- [ ] Test workflow dependency triggers
- [ ] Validate coverage CSV generation
- [ ] Update project documentation
- [ ] Remove deprecated ci.yml
- [ ] Monitor performance and adjust thresholds

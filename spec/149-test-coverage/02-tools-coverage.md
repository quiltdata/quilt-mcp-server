<!-- markdownlint-disable MD013 -->
# Split Coverage Tracking Design (Revised)

**GitHub Issue**: [#149 - Improve test coverage in highest-leverage areas - Target: 85%+ overall coverage](https://github.com/quiltdata/quilt-mcp-server/issues/149)

**Parent Spec**: [01-requirements.md](./01-requirements.md)

**Implementation Branch**: `149-test-coverage`

**Created**: 2025-09-12  
**Revised**: 2025-09-12

## Problem Statement

Currently, the quilt-mcp-server has a unified test coverage system that doesn't distinguish between unit tests (focused on error scenarios, edge cases, and isolated component behavior) and integration tests (focused on end-to-end workflow validation with real external services). This makes it difficult to:

1. **Ensure balanced coverage** - We need both comprehensive unit testing for error handling AND integration testing for golden path workflows
2. **Optimize development workflow** - Unit tests should be fast for TDD cycles, integration tests can be slower but more comprehensive
3. **Track progress systematically** - Different coverage targets are appropriate for unit (100%) vs integration (85%+) testing

## Design Overview

### Simple Coverage Split with File-Level Reporting

```text
📊 Coverage Tools System
├── Unit Coverage (Target: 100%)
│   ├── Tests marked: "not aws and not search"
│   ├── Fast execution, mocked dependencies
│   └── Error scenarios & edge cases
│
├── Integration Coverage (Target: 85%+)
│   ├── Tests marked: "aws or search"  
│   ├── Real external services
│   └── End-to-end workflows
│
└── File-Level Split Reporting
    ├── Coverage by source file
    ├── Reuses existing coverage infrastructure
    └── Single command execution
```

### Test Classification (No File Moves Required)

**Existing Markers** (already in `pyproject.toml`):

- `aws`: Tests requiring AWS credentials and network access
- `search`: Tests requiring search functionality  

**Simple Classification**:

- **Unit tests**: All tests WITHOUT `aws` or `search` markers
- **Integration tests**: All tests WITH `aws` or `search` markers

*No new markers needed. No file reorganization required.*

## Design Decisions

### Coverage Granularity: File Level

**Decision**: Track coverage by source file rather than by individual MCP tool functions.

**Rationale**:

- **Simplicity**: Leverages existing coverage infrastructure without complex tool discovery
- **Actionable Insights**: File-level coverage shows exactly which modules need attention
- **Maintainable**: No dependency on MCP tool discovery or function-level attribution
- **Immediate Value**: Works with standard coverage XML output without custom parsing

**File Identification**:

- **Source**: All `.py` files under `src/quilt_mcp/`
- **Detection Method**: Standard coverage XML parsing by file path
- **Examples**: `src/quilt_mcp/tools/auth.py`, `src/quilt_mcp/tools/buckets.py`

### Coverage Implementation Strategy

**Design Options**:

1. **Separate Coverage Targets** (Selected Approach)
   - Create distinct `coverage-unit` and `coverage-integration` targets
   - Make main `coverage` target depend on both unit and integration coverage
   - Make `coverage-tools` depend on both XML outputs for processing
   - **Pros**: Clear separation, explicit dependencies, reuses infrastructure
   - **Cons**: Requires new Makefile targets

2. **Single Coverage Target with Split Processing** (Rejected)
   - Use existing single coverage target and split results post-hoc
   - **Pros**: Minimal Makefile changes
   - **Cons**: Less clear separation, harder to debug individual coverage types

**Decision**: Create separate `coverage-unit` and `coverage-integration` targets with explicit dependencies.

### Coverage Display Requirements

**Output Format**: Markdown table in PR artifacts (markdown lint compliant)

**Required Columns**:

- **Source File**: File path relative to project root (e.g., `src/quilt_mcp/tools/auth.py`)
- **Unit Coverage**: Percentage + line counts for error scenarios
- **Integration Coverage**: Percentage + line counts for end-to-end workflows  
- **Combined**: Overall coverage percentage
- **Status**: ✅/❌ based on targets (100% unit, 85%+ integration)

**Key Design Requirements**:

- **Scannable**: Quickly identify which files need attention
- **Actionable**: Clear guidance on whether to add unit vs integration tests
- **Trackable**: Show progress over time in PR artifacts
- **Focused**: Highlight 0% coverage files as highest priority
- **Lint Compliant**: Follows markdownlint rules for table formatting

### Implementation Architecture

**Components Required**:

1. **Separate Coverage Targets** (`make.dev`)
   - `coverage-unit`: Runs tests with `"not aws and not search"` markers, outputs `coverage-unit.xml`
   - `coverage-integration`: Runs tests with `"aws or search"` markers, outputs `coverage-integration.xml`
   - `coverage`: Depends on both `coverage-unit` and `coverage-integration`

2. **Coverage Tools Script** (`bin/coverage-tools`)
   - Simple Python script that processes both XML files
   - Depends on `coverage-unit.xml` and `coverage-integration.xml` existing
   - No complex tool discovery - just file-level coverage analysis

3. **Coverage XML Processing**  
   - Parse pytest-cov XML output from separate unit and integration runs
   - Extract file-level coverage statistics from both XML files
   - Handle missing coverage gracefully (0% attribution)

4. **Report Generation**
   - Generate markdown table with file-level breakdown
   - Include overall statistics and pass/fail status
   - Save to `build/test-results/coverage-summary.md` for PR artifacts
   - Ensure markdown lint compliance

**Integration Points**:

- **Makefile**: Explicit dependency chain: `coverage-tools` → `coverage` → `coverage-unit` + `coverage-integration`
- **CI Pipeline**: Run `make coverage-tools` which automatically runs all dependencies
- **PR Artifacts**: Existing artifact upload includes all three coverage files

### Design Constraints & Simplifications

**Simplified Approach**:

- **File-Level Only**: No tool discovery or function-level analysis required
- **Reuse Existing Infrastructure**: Leverages proven `coverage` and `test-unit` targets
- **Standard XML Processing**: Uses well-established coverage XML format
- **Minimal Dependencies**: No new test markers or complex parsing logic

**Acceptable Trade-offs**:

- **File vs Function Granularity**: File-level provides sufficient actionability
- **Simplicity vs Precision**: Immediate value without complex tooling
- **Maintainability**: Standard coverage workflow with minimal custom code

### Success Metrics

**Immediate Value**:

- ✅ Every PR shows file-level coverage breakdown
- ✅ Developers can identify low-coverage files instantly  
- ✅ Clear guidance on unit vs integration test priorities
- ✅ No disruption to existing workflow (reuses current infrastructure)
- ✅ Markdown lint compliance for professional presentation

## Implementation Requirements

### Technical Requirements

1. **Makefile Targets** (`make.dev`)
   - Add `coverage-unit` target: runs unit tests with coverage, outputs `coverage-unit.xml`
   - Add `coverage-integration` target: runs integration tests with coverage, outputs `coverage-integration.xml`  
   - Update `coverage` target: depends on both `coverage-unit` and `coverage-integration`
   - Add `coverage-tools` target: depends on `coverage`, processes both XML files

2. **Python Script** (`bin/coverage-tools`)
   - Process both `coverage-unit.xml` and `coverage-integration.xml` files
   - Generate markdown table with file-level breakdown
   - Handle edge cases (missing files, 0 coverage, parsing errors)
   - Ensure markdown lint compliance in output

3. **CI Integration** (`.github/workflows/ci.yml`)
   - Minimal changes to existing coverage workflow
   - Add `make coverage-tools` to generate all coverage reports with dependencies
   - Leverage existing artifact upload mechanism

### Expected Output Table

The generated `coverage-summary.md` will show:

```markdown
# Split Coverage Report by Source File

| Source File | Unit Coverage | Integration Coverage | Combined | Status |
|-------------|---------------|---------------------|----------|--------|
| src/quilt_mcp/tools/auth.py | 85.5% (123/144) | 92.1% (132/143) | 92.1% | ❌ |
| src/quilt_mcp/tools/buckets.py | 0.0% (0/87) | 78.2% (68/87) | 78.2% | ❌ |
| src/quilt_mcp/tools/packages.py | 12.3% (8/65) | 95.4% (62/65) | 95.4% | ❌ |
| src/quilt_mcp/server.py | 100.0% (42/42) | 88.1% (37/42) | 100.0% | ✅ |
| src/quilt_mcp/utils/config.py | 45.2% (67/148) | 23.0% (34/148) | 45.2% | ❌ |
| **TOTAL** | **52.1%** (240/486) | **84.7%** (333/485) | **68.4%** | ❌ |

## Coverage Targets

- **Unit Coverage**: 100% (error scenarios, mocked dependencies)  
- **Integration Coverage**: 85%+ (end-to-end workflows, real services)

## Current Status

- Unit: 52.1% (❌ FAIL - Target: 100%)
- Integration: 84.7% (❌ FAIL - Target: 85%+)  
- Combined: 68.4%

## Test Classification

- **Unit Tests**: Tests marked with `not aws and not search`
- **Integration Tests**: Tests marked with `aws or search`

## Priority Actions

- **Focus unit testing** on files with 0% unit coverage
- **Focus integration testing** on files with <85% integration coverage
- **High Priority**: Files with 0% in either category
```

## Existing Infrastructure Leveraged

**Current Makefile Targets** (from `make.dev`):

- ✅ `test-unit`: Already runs tests with `"not aws and not search"` markers
- ✅ `coverage`: Will be updated to depend on both unit and integration coverage
- ✅ `test-ci`: Already has coverage infrastructure for CI integration
- ✅ No new markers or test infrastructure required

**New Makefile Targets** (to be added):

- ➕ `coverage-unit`: Runs unit tests with coverage, outputs `coverage-unit.xml`
- ➕ `coverage-integration`: Runs integration tests with coverage, outputs `coverage-integration.xml`
- ➕ `coverage-tools`: Depends on `coverage`, processes both XML files to generate summary

**Existing Configuration** (from `pyproject.toml`):

- ✅ `aws` marker exists for AWS integration tests
- ✅ `search` marker exists for search functionality tests  
- ✅ No configuration changes required

## Success Criteria

### Infrastructure Reuse

- ✅ `make coverage-tools` extends existing coverage infrastructure
- ✅ Uses existing test markers (`aws`, `search`) for classification
- ✅ Reuses proven `test-unit` and `coverage` targets from `make.dev`
- ✅ Minimal new code - just XML processing and report generation

### Coverage Tracking

- ✅ **Unit coverage**: Lines covered by tests without `aws` or `search` markers
- ✅ **Integration coverage**: Lines covered by tests with `aws` or `search` markers
- ✅ **File-level granularity**: Clear actionability without complex tool discovery
- ✅ **Progress monitoring**: Clear visibility into both coverage dimensions

## Benefits

### Immediate Value

- **See coverage gaps clearly**: File-level unit vs integration breakdown
- **No disruption**: Reuses existing test infrastructure and markers
- **Simple execution**: Single `make coverage-tools` command
- **Strategic guidance**: Know whether to add unit tests (errors) or integration tests (workflows)
- **PR Visibility**: Coverage reports available as artifacts in every PR
- **Lint Compliant**: Professional markdown output that passes quality checks

### Long-term Impact

- **Balanced testing**: Ensures both error scenarios and golden paths are covered
- **Progress tracking**: Monitor improvement in both coverage dimensions
- **Quality foundation**: Establishes sustainable pattern for test development
- **Team Awareness**: Split coverage visible to all reviewers in PR artifacts
- **Maintainable**: Simple design that doesn't require complex tooling or discovery

## CI Integration Strategy

### Current CI Coverage

From `make.dev` line 41:

```makefile
--cov=quilt_mcp --cov-report=xml:src/coverage.xml
```

### Enhanced CI Integration

**Minimal Changes Required**:

1. **Add coverage-tools target** to existing CI workflow
2. **Reuse existing artifact upload** mechanism  
3. **No new CI infrastructure** or complex setup required

**Implementation**:

```yaml
# Add after existing coverage step in ci.yml:
- name: Generate split coverage reports
  run: make coverage-tools
  
# Existing artifact upload automatically includes our new files:
- name: Upload test results
  uses: actions/upload-artifact@v4  
  with:
    name: test-results-py${{ matrix.python-version }}
    path: build/test-results/  # Already includes coverage files
```

### PR Artifact Contents

When viewing PR artifacts, reviewers will see:

- `build/test-results/coverage-unit.xml` - Machine-readable unit test coverage
- `build/test-results/coverage-integration.xml` - Machine-readable integration test coverage  
- `build/test-results/coverage-summary.md` - **File-by-file coverage table** showing exactly where to focus effort

**Dependency Chain**:
```
coverage-tools → coverage → coverage-unit + coverage-integration
                    ↓           ↓                 ↓
                generates:  coverage-unit.xml  coverage-integration.xml
                    ↓
            coverage-summary.md
```

## Implementation Plan

### Phase 1: Core Implementation

1. **Add Makefile targets** - Create `coverage-unit`, `coverage-integration`, update `coverage`
2. **Create `bin/coverage-tools`** - Simple Python script for processing both XML files
3. **Add `coverage-tools` target** - Depends on `coverage`, processes XML files  
4. **Test locally** - Verify all targets work and generate expected files

### Phase 2: Integration

1. **Update CI workflow** - Add coverage-tools to artifact generation
2. **Validate PR artifacts** - Ensure coverage reports appear correctly
3. **Document usage** - Add coverage-tools to help system

**Result**: Every PR shows a clear table of unit vs integration coverage by source file, making it obvious where testing effort should be focused while reusing all existing infrastructure.

---

*This revised design maximizes reuse of existing infrastructure while providing clear, actionable coverage insights at the file level.*

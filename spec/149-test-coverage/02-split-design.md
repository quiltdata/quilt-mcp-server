<!-- markdownlint-disable MD013 -->
# Separate Coverage Tracking Design (Simplified)

**GitHub Issue**: [#149 - Improve test coverage in highest-leverage areas - Target: 85%+ overall coverage](https://github.com/quiltdata/quilt-mcp-server/issues/149)

**Parent Spec**: [01-requirements.md](./01-requirements.md)

**Implementation Branch**: `149-test-coverage`

**Created**: 2025-09-12

## Problem Statement

Currently, the quilt-mcp-server has a unified test coverage system that doesn't distinguish between unit tests (focused on error scenarios, edge cases, and isolated component behavior) and integration tests (focused on end-to-end workflow validation with real external services). This makes it difficult to:

1. **Ensure balanced coverage** - We need both comprehensive unit testing for error handling AND integration testing for golden path workflows
2. **Optimize development workflow** - Unit tests should be fast for TDD cycles, integration tests can be slower but more comprehensive
3. **Track progress systematically** - Different coverage targets are appropriate for unit (100%) vs integration (85%+) testing

## Design Overview

### Simple Coverage Split

```text
📊 Test Coverage System
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
└── Split Reporting
    ├── Separate coverage metrics
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

### Coverage Granularity: MCP Tool Level

**Decision**: Track coverage by individual MCP tool functions rather than by module/file.

**Rationale**:

- **Business Value Alignment**: Each MCP tool represents a distinct user capability (e.g., `bucket_objects_list`, `auth_status`)
- **Actionable Insights**: Developers can see exactly which tools lack unit vs integration coverage
- **Strategic Focus**: Prioritize testing effort on high-value tools vs low-impact helper functions

**MCP Tool Identification**:

- **Source**: `src/quilt_mcp/tools/*.py` files contain MCP tool definitions  
- **Detection Method**: Use existing `tool_modules = get_tool_modules()` function for discovery
- **Examples**: `auth_status`, `bucket_objects_list`, `package_browse`, `catalog_info`

### Coverage Attribution Challenge

**Problem**: Standard coverage XML reports file-level coverage, but we need tool-level granularity.

**Design Options**:

1. **File-Level Attribution** (Current Feasible Approach)
   - Attribute entire file coverage to each tool within that file
   - **Pros**: Works with existing coverage tooling, no annotations required
   - **Cons**: Less precise when multiple tools share a file

2. **Function-Level Annotation** (Future Enhancement)
   - Add coverage annotations at function boundaries  
   - **Pros**: Precise tool-level coverage attribution
   - **Cons**: Requires significant tooling changes or manual annotations

3. **Test-Driven Attribution** (Alternative Approach)
   - Map test files to specific tools they exercise
   - **Pros**: More accurate attribution based on actual test targets
   - **Cons**: Requires test naming conventions or annotations

**Decision**: Start with File-Level Attribution (Option 1) for immediate value, with clear path to Function-Level enhancement.

### Coverage Display Requirements

**Output Format**: Markdown table in PR artifacts

**Required Columns**:

- **MCP Tool**: Function name (e.g., `bucket_objects_list`)
- **Unit Coverage**: Percentage + line counts for error scenarios
- **Integration Coverage**: Percentage + line counts for end-to-end workflows  
- **Status**: ✅/❌ based on targets (100% unit, 85%+ integration)

**Key Design Requirements**:

- **Scannable**: Quickly identify which tools need attention
- **Actionable**: Clear guidance on whether to add unit vs integration tests
- **Trackable**: Show progress over time in PR artifacts
- **Focused**: Highlight 0% coverage tools as highest priority

### Implementation Architecture

**Components Required**:

1. **MCP Tool Discovery** (`bin/coverage-summary.py`)
   - Use existing `tool_modules = get_tool_modules()` function for MCP tool enumeration
   - Leverage established tool discovery mechanism rather than custom AST parsing
   - Build mapping: `{file_path: [tool_names]}`

2. **Coverage XML Processing**  
   - Parse pytest-cov XML output for unit and integration runs
   - Map file-level coverage to tool-level coverage
   - Handle missing coverage gracefully (0% attribution)

3. **Report Generation**
   - Generate markdown table with tool-level breakdown
   - Include overall statistics and pass/fail status
   - Save to `build/test-results/coverage-summary.md` for PR artifacts

**Integration Points**:

- **Makefile**: `coverage-split` target runs tests and generates report
- **CI Pipeline**: Replace single coverage with split coverage in GitHub Actions
- **PR Artifacts**: Existing artifact upload includes new coverage files

### Design Constraints & Limitations

**Current Limitations**:

- **File-Level Attribution**: Tools sharing a file share same coverage percentage
- **No Function Boundaries**: Cannot distinguish coverage between tools in same file
- **Static Analysis Only**: No runtime coverage attribution to specific tools

**Acceptable Trade-offs**:

- **Precision vs Simplicity**: File-level attribution provides 80% of value with 20% of complexity
- **Perfect vs Good**: Immediate actionable insights more valuable than perfect accuracy
- **Evolution Path**: Design allows future enhancement to function-level attribution

### Success Metrics

**Immediate Value** (Phase 1):

- ✅ Every PR shows tool-level coverage breakdown
- ✅ Developers can identify 0% coverage tools instantly  
- ✅ Clear guidance on unit vs integration test priorities
- ✅ No disruption to existing workflow (uses current test markers)

**Future Enhancements** (Phase 2+):

- Function-level coverage attribution for shared files
- Test-to-tool mapping for more accurate attribution
- Historical coverage trends by tool
- Integration with coverage quality gates per tool

## Implementation Requirements

### Technical Requirements

1. **Python Script** (`bin/coverage-summary.py`)
   - Use existing `tool_modules = get_tool_modules()` function to discover MCP tools
   - Process pytest-cov XML files for unit and integration coverage
   - Generate markdown table with tool-level breakdown
   - Handle edge cases (missing files, 0 coverage, parsing errors)

2. **Makefile Integration** (`make.dev`)
   - Add `coverage-split` target that runs unit tests, integration tests, and report generation
   - Use existing test markers (`aws`, `search`) for test classification
   - Output coverage files to `build/test-results/` for CI artifact upload

3. **CI Integration** (`.github/workflows/ci.yml`)
   - Replace existing coverage command with `make coverage-split`
   - Leverage existing artifact upload mechanism
   - No additional CI setup required

### Expected Output Table

The generated `coverage-summary.md` will show:

```markdown
# Split Coverage Report by MCP Tool

| MCP Tool | Unit Coverage | Integration Coverage | Combined | Status |
|----------|---------------|---------------------|----------|--------|
| `auth_status` | 85.5% (123/144) | 92.1% (132/143) | 92.1% | ❌ |
| `bucket_objects_list` | 0.0% (0/87) | 78.2% (68/87) | 78.2% | ❌ |  
| `bucket_object_info` | 12.3% (8/65) | 95.4% (62/65) | 95.4% | ❌ |
| `catalog_info` | 100.0% (42/42) | 88.1% (37/42) | 100.0% | ✅ |
| `package_browse` | 45.2% (67/148) | 23.0% (34/148) | 45.2% | ❌ |
| **TOTAL** | **52.1%** (240/486) | **84.7%** (333/485) | - | ❌ |

## Targets
- **Unit Coverage**: 100% (error scenarios, mocked dependencies)  
- **Integration Coverage**: 85%+ (end-to-end workflows, real services)

## Current Status  
- Unit: 52.1% (❌ FAIL)
- Integration: 84.7% (❌ FAIL)

## Notes
- Each MCP tool function is listed separately (e.g., `bucket_objects_list`, `auth_status`)
- Coverage shows which specific tools need unit vs integration tests
- Focus unit testing on tools with 0% unit coverage  
- Focus integration testing on tools with <85% integration coverage
```

## Existing Configuration Works

The current `pyproject.toml` already has the markers we need:

- ✅ `aws` marker exists
- ✅ `search` marker exists  
- ✅ No changes required

## Success Criteria

### Simple Infrastructure

- ✅ `make coverage-split` generates separate unit vs integration coverage reports
- ✅ Uses existing test markers (`aws`, `search`) for classification
- ✅ No file moves, no new configuration required
- ✅ Single command provides both coverage metrics

### Coverage Tracking

- ✅ **Unit coverage**: Lines covered by tests without `aws` or `search` markers
- ✅ **Integration coverage**: Lines covered by tests with `aws` or `search` markers
- ✅ **Separate targets**: 100% unit, 85%+ integration
- ✅ **Progress monitoring**: Clear visibility into both dimensions

## Benefits

### Immediate Value

- **See coverage gaps clearly**: Unit vs integration breakdown shows where to focus
- **No disruption**: Uses existing tests and markers, no file moves
- **Simple execution**: Single `make coverage-split` command
- **Strategic guidance**: Know whether to add unit tests (errors) or integration tests (workflows)
- **PR Visibility**: Coverage reports available as artifacts in every PR

### Long-term Impact

- **Balanced testing**: Ensures both error scenarios and golden paths are covered
- **Progress tracking**: Monitor improvement in both coverage dimensions via PR artifacts
- **Quality foundation**: Establishes pattern for future test development
- **Team Awareness**: Split coverage visible to all reviewers in PR artifacts

## CI Integration Strategy

### Current CI Coverage (`.github/workflows/ci.yml:37-38`)

```yaml
--cov=quilt_mcp --cov-report=xml:src/coverage.xml
```

### Enhanced CI with Split Coverage

```yaml
# Replace existing coverage line in ci.yml with:
- name: Run tests with split coverage
  run: make coverage-split
  
# Existing artifact upload automatically includes our new files:
- name: Upload test results
  uses: actions/upload-artifact@v4  
  with:
    name: test-results-py${{ matrix.python-version }}
    path: build/test-results/  # Already includes our coverage files
```

### PR Artifact Contents

When viewing PR artifacts, reviewers will see:

- `coverage-unit.xml` - Machine-readable unit test coverage
- `coverage-integration.xml` - Machine-readable integration test coverage  
- `coverage-summary.md` - **Module-by-module coverage table** showing exactly where to focus effort

## Next Steps (Single Phase Implementation)

1. **Create `bin/coverage-summary.py`** - Copy the Python script above  
2. **Add `coverage-split` to `make.dev`** - Copy the Makefile target above
3. **Update `.github/workflows/ci.yml`** - Replace coverage command with `make coverage-split`
4. **Test locally** - Run `make coverage-split` to verify table generation
5. **View results in PRs** - Coverage table automatically appears in PR artifacts

**Result**: Every PR shows a clear table of unit vs integration coverage by module (aws, tools, optimization, etc.), making it obvious where testing effort should be focused.

---

*This simplified design eliminates complexity while preserving the core value: separate visibility into unit vs integration test coverage to guide strategic testing improvements.*

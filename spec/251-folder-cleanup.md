# Test Folder Structure Cleanup Specification

**Issue**: #251 - Simplify test folder organization and improve maintainability

## Current State Analysis

### Existing Directory Structure

The current test structure has **16 directories** containing **50 Python files**:

```tree
tests/
├── __init__.py                     # Package marker
├── conftest.py                     # Pytest configuration
├── aws/                            # 1 file (single-file directory)
│   └── test_athena_service.py
├── configs/                        # Empty directory
├── fixtures/                       # 13 files (mixed test runners and data)
│   ├── *.json                     # Test data files
│   ├── *_test_runner.py           # Integration test runners
│   └── test_athena_connection.py  # Connection tests
├── results/                        # Empty directory
├── search/                         # 1 file (single-file directory)
│   └── test_elasticsearch_backend.py
├── services/                       # 1 file (single-file directory)
│   ├── __init__.py
│   └── test_quilt_service.py
├── tools/                          # 1 file (single-file directory)
│   └── test_auth_migration.py
├── utilities/aws/                  # Empty nested directories
└── 30+ root-level test files
```

### Test Type Classification

Based on markers and dependencies analysis:

**Unit Tests** (mocked, no external dependencies):

- `test_formatting.py`
- `test_governance.py`
- `test_helpers.py`
- `test_metadata_examples.py`
- `test_selector_fn.py`
- `test_utils.py` (mocked parts only, AWS parts moved to integration)
- `test_version_sync.py`
- `test_visualization.py`
- `services/test_quilt_service.py`
- `aws/test_athena_service.py`

**Integration Tests** (require AWS/external services):

- `test_integration_athena.py` (`@pytest.mark.aws`, `@pytest.mark.slow`)
- `test_integration.py` (`@pytest.mark.aws`)
- `test_bucket_tools.py` (`@pytest.mark.aws`)
- `test_athena_glue.py` (`@pytest.mark.aws`)
- `test_permissions.py` (`@pytest.mark.aws`)
- `test_s3_package.py` (`@pytest.mark.aws`)
- All files in `fixtures/` directory

**Mixed/Hybrid Tests** (both unit and integration - **NEED SPLITTING**):

- `test_mcp_server.py` (smoke tests with `@pytest.mark.aws`) - Split AWS parts to integration
- `test_utils.py` (has both mocked and AWS-dependent tests) - Split AWS parts to integration

## Problems Identified

1. **Unnecessary Nesting**: 4 directories contain only a single test file
2. **Empty Directories**: `configs/`, `results/`, `utilities/aws/` are empty
3. **Unclear Separation**: No clear distinction between unit vs integration tests
4. **Mixed Purpose**: `fixtures/` contains both test data and actual test runners
5. **Poor Discoverability**: Related tests scattered across root and subdirectories
6. **Inconsistent Patterns**: No clear naming convention for test categories

## Proposed Solution

### New Directory Structure

```tree
tests/
├── __init__.py
├── conftest.py
├── unit/                           # Unit tests (fast, mocked)
│   ├── __init__.py
│   ├── test_formatting.py
│   ├── test_governance.py
│   ├── test_helpers.py
│   ├── test_metadata_examples.py
│   ├── test_selector_fn.py
│   ├── test_utils.py               # Mocked parts only
│   ├── test_version_sync.py
│   ├── test_visualization.py
│   ├── test_athena_service.py      # From aws/
│   ├── test_quilt_service.py       # From services/
│   └── test_mcp_server.py          # Unit parts only
├── integration/                    # Integration tests (includes smoke tests)
│   ├── __init__.py
│   ├── test_athena_integration.py  # Renamed for consistency
│   ├── test_athena_glue.py
│   ├── test_bucket_tools.py
│   ├── test_integration.py
│   ├── test_permissions.py
│   ├── test_s3_package.py
│   ├── test_auth_migration.py      # From tools/
│   ├── test_elasticsearch_backend.py  # From search/
│   ├── test_mcp_server_integration.py  # AWS parts from test_mcp_server.py
│   └── test_utils_integration.py   # AWS parts from test_utils.py
├── e2e/                           # End-to-end workflow tests
│   ├── __init__.py
│   ├── test_buckets_migration.py
│   ├── test_formatting_integration.py
│   ├── test_governance_integration.py
│   ├── test_optimization.py
│   ├── test_package_management.py
│   ├── test_package_ops.py
│   ├── test_packages_migration.py
│   ├── test_quilt_summary.py
│   ├── test_quilt_tools.py
│   ├── test_readme.py
│   ├── test_search_phase2.py
│   ├── test_selector_debug.py
│   ├── test_tabulator.py
│   ├── test_unified_package.py
│   ├── test_unified_search.py
│   └── test_mcp_client.py
├── fixtures/                      # Test data and shared utilities only
│   ├── data/                      # JSON test data files
│   │   ├── advanced_workflow_test_cases.json
│   │   ├── ccle_computational_biology_test_cases.json
│   │   ├── mcp_test_results.json
│   │   └── *.json
│   ├── runners/                   # Separated test runner utilities
│   │   ├── __init__.py
│   │   ├── ccle_computational_biology_test_runner.py
│   │   ├── ccle_direct_test_runner.py
│   │   ├── direct_mcp_test.py
│   │   ├── interactive_mcp_test.py
│   │   ├── llm_mcp_test.py
│   │   ├── mcp_comprehensive_test_simulation.py
│   │   ├── mock_llm_mcp_test.py
│   │   ├── sail_user_stories_real_test.py
│   │   └── sail_user_stories_test.py
│   └── test_athena_connection.py   # Connection test utility
└── configs/                       # Test configuration files (if needed)
    └── pytest.ini                 # If project-specific config needed
```

### Test Category Definitions

**Unit Tests** (`tests/unit/`):

- Fast execution (< 1 second per test)
- No external dependencies (AWS, network, filesystem)
- Use mocking for all external calls
- Test individual functions/classes in isolation
- Should run in any environment

**Integration Tests** (`tests/integration/`):

- Test interaction with external services (AWS, Elasticsearch)
- Require real credentials and network access
- Marked with `@pytest.mark.aws` or similar
- May be slower (< 30 seconds per test)

**Integration Tests** (`tests/integration/`) - **EXPANDED DEFINITION**:

- Test interaction with external services (AWS, Elasticsearch)
- Require real credentials and network access
- Marked with `@pytest.mark.aws` or similar
- May be slower (< 30 seconds per test)
- **Includes smoke tests**: Basic "does it connect/start" health checks
- **Rationale**: Smoke tests are just lightweight integration tests

**End-to-End Tests** (`tests/e2e/`):

- Complete workflow testing
- Multiple components working together
- May require complex setup/teardown
- Test user-facing scenarios

## Migration Plan

### Phase 1: Create New Structure

1. Create new directory structure with `__init__.py` files
2. Set up proper imports in `__init__.py` files

### Phase 2: Move Unit Tests

1. Move clearly identified unit tests to `tests/unit/`
2. Ensure all external calls are properly mocked
3. Verify tests run quickly (< 1s each)

### Phase 3: Move Integration Tests

1. Move AWS-dependent tests to `tests/integration/`
2. Ensure proper `@pytest.mark.aws` markers
3. Update any import paths

### Phase 4: Categorize Remaining Tests

1. Move complex workflow tests to `tests/e2e/`
2. Reorganize fixtures directory
3. Split mixed test files (move AWS parts to integration)

### Phase 5: Update Tooling

1. Update Makefile test targets
2. Update CI/CD configuration
3. Update documentation

### Phase 6: Cleanup

1. Remove empty directories
2. Remove duplicate test files
3. Verify all tests still pass

## Impact on Tooling

### Makefile Updates Required

Current test targets in `make.dev`:

```makefile
test-unit:
    @export PYTHONPATH="src" && uv run python -m pytest tests/ -v -m "not aws and not search"

test-integration:
    @export PYTHONPATH="src" && uv run python -m pytest tests/ -v
```

Proposed updates:

```makefile
test-unit:
    @export PYTHONPATH="src" && uv run python -m pytest tests/unit/ -v

test-integration:
    @export PYTHONPATH="src" && uv run python -m pytest tests/integration/ -v -m "aws"

test-e2e:
    @export PYTHONPATH="src" && uv run python -m pytest tests/e2e/ -v

test:
    @export PYTHONPATH="src" && uv run python -m pytest tests/ -v
```

### CI/CD Updates

Update GitHub Actions and CI scripts to use new paths:

- Unit tests can run in parallel without AWS credentials
- Integration tests require AWS setup
- Different timeout values for different test categories

## Benefits

1. **Clear Separation**: Obvious distinction between test types
2. **Faster Feedback**: Unit tests can run quickly in development
3. **Better CI/CD**: Different test categories can have different requirements
4. **Easier Maintenance**: Related tests grouped logically
5. **Improved Discoverability**: Developers can easily find relevant tests
6. **Reduced Complexity**: No more single-file directories
7. **Scalability**: Structure supports growth as test suite expands

## Risks and Mitigation

## Additional Considerations

### Source Folder Structure

The `src/` folder also contains similar organizational issues:

- **Empty directories**: `config/`, `operations/`, `operations/quilt3/`, `utilities/`, `utilities/aws/`
- **Single-file directory**: `search/utils/` (1 file)

**Decision**: Keep current src structure unchanged during this cleanup because:

- Empty directories may be architectural placeholders for future features
- Module restructuring affects import paths across entire codebase
- This cleanup is focused on tests (issue #251), mixing concerns could complicate migration
- Source refactoring should be separate initiative if needed

### Risk: Import Path Changes

**Mitigation**: Use relative imports and proper `__init__.py` setup

### Risk: Test Discovery Issues

**Mitigation**: Maintain pytest conventions and test existing discovery

### Risk: CI/CD Breakage

**Mitigation**: Update all automation in same commit as file moves

### Risk: Developer Confusion

**Mitigation**: Update documentation and provide clear migration guide

## Success Criteria

1. **Zero Test Failures**: All existing tests pass after migration
2. **Faster Unit Test Execution**: Unit test suite runs in < 30 seconds
3. **Clear Categories**: Each test file has obvious category placement
4. **No Empty Directories**: All directories contain relevant files
5. **Updated Tooling**: All Makefile targets and CI/CD work correctly
6. **Developer Productivity**: Easier to find and run relevant tests

## Implementation Notes

### File Movement Strategy

- Move files in small batches to track any issues
- Test each batch before proceeding
- Maintain git history where possible using `git mv`

### Import Updates

- Use find/replace for common import patterns
- Verify no relative import issues
- Test import paths in isolated environment

### Validation Steps

- Run full test suite after each phase
- Verify CI/CD pipeline functionality
- Check test discovery with `pytest --collect-only`
- Validate coverage reporting still works

## Naming Convention Standardization

**Current Inconsistencies:**

- `test_integration_athena.py` → proposed `test_athena_integration.py`
- Mixed prefixes: `test_integration_*` vs `test_*_integration`
- Inconsistent service vs function naming patterns

**Proposed Standards:**

**Unit Tests**: `test_<component>.py`

- Examples: `test_formatting.py`, `test_helpers.py`, `test_governance.py`

**Integration Tests**: `test_<service>_integration.py`

- Examples: `test_athena_integration.py`, `test_elasticsearch_integration.py`
- **Rationale**: Service name first for grouping, then type

**End-to-End Tests**: `test_<workflow>.py`

- Examples: `test_package_creation_workflow.py`, `test_search_workflow.py`
- **Rationale**: Workflow name describes the user scenario being tested

**Benefits:**

- Consistent, predictable naming
- Clear indication of test category and scope
- Easy to find related tests
- Supports IDE autocomplete and filtering

This restructuring will significantly improve the maintainability and clarity of the test suite while preserving all existing functionality.

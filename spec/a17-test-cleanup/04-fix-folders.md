# Test Folder Reorganization Plan

## Problem Statement

**The test directory structure is fundamentally broken across all three test directories.** This plan addresses three critical issues:

### Issue A: Tests in Wrong Folders (ALL directories affected)

**tests/func/** (should be mocked multi-module) → ~40% are REAL integration tests with no mocks
**tests/e2e/** (should be real end-to-end) → ~90% are MOCKED integration tests
**tests/unit/** (should be single-module isolated) → ~40-50% are multi-module integration tests

This violates the documented structure in [TESTING.md:7-13](TESTING.md#L7-L13):

```
tests/
├── unit/     # Single-module tests, no network
├── func/     # Mocked multi-module tests
├── e2e/      # End-to-end workflows with real services
```

### Issue B: Mock-Only Tests Without Business Logic Validation

Multiple tests only verify mock interactions without testing actual behavior:
- `test_auth_service_factory.py` - Tests fixture creation, not auth behavior
- `test_tabulator.py` (unit) - Tests mock call arguments, not query execution
- `test_health_endpoint.py` - Tests mock patterns, not real health checks
- Multiple others that need refactoring or removal

### Issue C: test-e2e-platform Misconfiguration

The `test-e2e-platform` Make target does NOT properly configure the environment for Platform backend tests:

**Current (broken):**
```makefile
test-e2e-platform:
    export PLATFORM_TEST_ENABLED=true && export TEST_BACKEND_MODE=platform && \
    uv run python -m pytest tests/e2e/ -v -m "not admin"
```

**Should be (like test-func-platform):**
```makefile
test-e2e-platform:
    export PLATFORM_TEST_ENABLED=true && \
    export TEST_BACKEND_MODE=platform && \
    eval "$$(uv run python scripts/quilt_config_env.py)" && \
    uv run python -m pytest tests/e2e/ -v -m "not admin"
```

Missing: `quilt_config_env.py` which sets AWS credentials, Quilt registry URLs, and other essential environment variables.

## Current State Analysis

### tests/func/ Reality Check

**Expected:** Mocked multi-module tests
**Actual:** ~40% are REAL integration tests with zero mocking

**Files using REAL services (should be in e2e/):**

| File | Evidence | External Dependencies |
|------|----------|----------------------|
| `test_tabulator_integration.py` | "NO MOCKING of backend methods" | Real QuiltOps backend |
| `test_athena.py` | "NO MOCKING - tests full stack with real AWS" | AWS Athena |
| `test_elasticsearch_package_scope.py` | "No mocks. Real AWS. Real Elasticsearch." | Elasticsearch + AWS |
| `test_elasticsearch_package_scope_extended.py` | Real Elasticsearch queries | Elasticsearch |
| `test_elasticsearch_index_discovery.py` | Real index discovery | Elasticsearch |
| `test_elasticsearch_index_discovery_async.py` | Async real discovery | Elasticsearch |
| `test_docker_container.py` | Builds/runs Docker containers, `@pytest.mark.slow` | Docker daemon |
| `test_docker_container_mcp.py` | MCP server in container | Docker daemon |
| `test_s3_package_integration.py` | Real S3 operations | AWS S3 |
| `test_search_catalog_real_data.py` | "Real data" catalog search | Quilt catalog |
| `test_integration.py` | Real AWS credentials required | AWS + Quilt |
| `test_integration_package_diff.py` | Real backend operations | Quilt backend |
| `test_search_catalog_integration.py` | Real catalog integration | Quilt catalog |
| `test_bucket_tools_text.py` | Real bucket text operations | AWS S3 |
| `test_bucket_tools_versions.py` | Real S3 versioning | AWS S3 |
| `test_bucket_tools_version_edge_cases.py` | S3 version edge cases | AWS S3 |

**Files that ARE properly mocked (should stay in func/):**

- `test_mcp_server.py` - Heavy use of `@patch` decorators
- `test_auth_isolation.py` - Mocked context isolation
- `test_auth_modes.py` - Mocked IAM/JWT auth
- `test_multiuser_access.py` - Stubbed auth services
- `test_resources.py` - MCP registration tests
- `test_jwt_integration.py` - JWT integration

### tests/e2e/ Reality Check

**Expected:** End-to-end workflows with real services
**Actual:** Primarily MOCKED integration tests

**Files using MOCKS (should be in func/):**

| File | Evidence | Mock Usage |
|------|----------|------------|
| `test_tabulator.py` | `@patch('QuiltOpsFactory.create')` | All backend methods mocked |
| `test_error_recovery.py` | Unit tests with mocked helpers | Mock() objects |
| `test_optimization.py` | `Mock(spec=TelemetryCollector)` | All optimization framework mocked |
| `test_formatting_integration.py` | `@patch('AthenaQueryService')` | Mocked service classes |
| `test_quilt_summary.py` | Mocked matplotlib | Mock() for plot generation |
| `test_backend_status.py` | Mocked engine/registry | Partial mocking |
| `test_governance_integration.py` | `@patch('governance')` | Optional real calls |
| `test_backend_lazy_init.py` | Mixed: some real checks | Light mocking |
| `test_readme.py` | Utility test (no features) | N/A (utility) |
| `test_selector_debug.py` | Empty file | DELETE |

**Files that ARE proper E2E (should stay in e2e/):**

- `test_mcp_client.py` - True E2E: connects to real MCP server

## Migration Plan

### Phase 1: Move Real Integration Tests (func → e2e)

**16 files to move:**

```bash
tests/func/test_tabulator_integration.py → tests/e2e/test_tabulator_integration.py
tests/func/test_athena.py → tests/e2e/test_athena.py
tests/func/test_elasticsearch_package_scope.py → tests/e2e/test_elasticsearch_package_scope.py
tests/func/test_elasticsearch_package_scope_extended.py → tests/e2e/test_elasticsearch_package_scope_extended.py
tests/func/test_elasticsearch_index_discovery.py → tests/e2e/test_elasticsearch_index_discovery.py
tests/func/test_elasticsearch_index_discovery_async.py → tests/e2e/test_elasticsearch_index_discovery_async.py
tests/func/test_docker_container.py → tests/e2e/test_docker_container.py
tests/func/test_docker_container_mcp.py → tests/e2e/test_docker_container_mcp.py
tests/func/test_s3_package_integration.py → tests/e2e/test_s3_package_integration.py
tests/func/test_search_catalog_real_data.py → tests/e2e/test_search_catalog_real_data.py
tests/func/test_integration.py → tests/e2e/test_integration.py
tests/func/test_integration_package_diff.py → tests/e2e/test_integration_package_diff.py
tests/func/test_search_catalog_integration.py → tests/e2e/test_search_catalog_integration.py
tests/func/test_bucket_tools_text.py → tests/e2e/test_bucket_tools_text.py
tests/func/test_bucket_tools_versions.py → tests/e2e/test_bucket_tools_versions.py
tests/func/test_bucket_tools_version_edge_cases.py → tests/e2e/test_bucket_tools_version_edge_cases.py
```

**Mixed files requiring review:**
- `tests/func/test_bucket_tools_basic.py` - Has one mocked test, rest are real (MOVE TO E2E)
- `tests/func/test_packages_integration.py` - Patches session but hits real backend (MOVE TO E2E)
- `tests/func/test_utils_integration.py` - Review needed
- `tests/func/test_permission_isolation.py` - Review needed

### Phase 2: Move Mocked Tests (e2e → func)

**9 files to move:**

```bash
tests/e2e/test_tabulator.py → tests/func/test_tabulator.py
tests/e2e/test_error_recovery.py → tests/func/test_error_recovery.py
tests/e2e/test_optimization.py → tests/func/test_optimization.py
tests/e2e/test_formatting_integration.py → tests/func/test_formatting_integration.py
tests/e2e/test_quilt_summary.py → tests/func/test_quilt_summary.py
tests/e2e/test_backend_status.py → tests/func/test_backend_status.py
tests/e2e/test_governance_integration.py → tests/func/test_governance_integration.py
tests/e2e/test_backend_lazy_init.py → tests/func/test_backend_lazy_init.py
tests/e2e/test_readme.py → tests/func/test_readme.py
```

**Files to delete:**
- `tests/e2e/test_selector_debug.py` - Empty file

### Phase 3: Update Fixture Configuration

**tests/func/conftest.py** - Should enable mocking:
```python
# Current: Provides real backend fixtures (requires_catalog, test_bucket)
# After: Should provide mocking fixtures like e2e does
```

**tests/e2e/conftest.py** - Should require real services:
```python
# Current: Provides mocking fixtures
# After: Should provide real integration fixtures like func does
```

**Action:** Swap the conftest.py files' fixture purposes.

### Phase 4: Update Helper Files

**tests/func/search_catalog_helpers.py** - Review if still needed after moving search tests to e2e

### Phase 5: Update Make Targets & CI

**Makefile changes:**
- `make test-func` - Should run faster (all mocked now)
- `make test-e2e` - Will be slower (all real integration now)
- `make test-ci` - May need to skip more e2e tests

**GitHub Actions (.github/workflows/prod.yml):**
- Review test-func runtime expectations (should be faster)
- Review test-e2e requirements (needs AWS credentials, Docker, Elasticsearch)

## Implementation Steps

### Step 1: Create Migration Script

Create `scripts/migrate_tests.sh`:

```bash
#!/bin/bash
# Migrate tests between func and e2e directories

set -euo pipefail

# Create backup
BACKUP_DIR="tests_backup_$(date +%Y%m%d_%H%M%S)"
cp -r tests "$BACKUP_DIR"
echo "Backup created: $BACKUP_DIR"

# Phase 1: Move real integration tests (func → e2e)
FUNC_TO_E2E=(
    "test_tabulator_integration.py"
    "test_athena.py"
    "test_elasticsearch_package_scope.py"
    "test_elasticsearch_package_scope_extended.py"
    "test_elasticsearch_index_discovery.py"
    "test_elasticsearch_index_discovery_async.py"
    "test_docker_container.py"
    "test_docker_container_mcp.py"
    "test_s3_package_integration.py"
    "test_search_catalog_real_data.py"
    "test_integration.py"
    "test_integration_package_diff.py"
    "test_search_catalog_integration.py"
    "test_bucket_tools_text.py"
    "test_bucket_tools_versions.py"
    "test_bucket_tools_version_edge_cases.py"
    "test_bucket_tools_basic.py"
    "test_packages_integration.py"
)

for file in "${FUNC_TO_E2E[@]}"; do
    if [ -f "tests/func/$file" ]; then
        git mv "tests/func/$file" "tests/e2e/$file"
        echo "✓ Moved func → e2e: $file"
    else
        echo "⚠ File not found: tests/func/$file"
    fi
done

# Phase 2: Move mocked tests (e2e → func)
E2E_TO_FUNC=(
    "test_tabulator.py"
    "test_error_recovery.py"
    "test_optimization.py"
    "test_formatting_integration.py"
    "test_quilt_summary.py"
    "test_backend_status.py"
    "test_governance_integration.py"
    "test_backend_lazy_init.py"
    "test_readme.py"
)

for file in "${E2E_TO_FUNC[@]}"; do
    if [ -f "tests/e2e/$file" ]; then
        git mv "tests/e2e/$file" "tests/func/$file"
        echo "✓ Moved e2e → func: $file"
    else
        echo "⚠ File not found: tests/e2e/$file"
    fi
done

# Phase 3: Delete empty files
if [ -f "tests/e2e/test_selector_debug.py" ]; then
    git rm "tests/e2e/test_selector_debug.py"
    echo "✓ Deleted empty file: test_selector_debug.py"
fi

echo ""
echo "Migration complete! Summary:"
echo "  - Moved ${#FUNC_TO_E2E[@]} files from func → e2e"
echo "  - Moved ${#E2E_TO_FUNC[@]} files from e2e → func"
echo "  - Backup: $BACKUP_DIR"
```

### Step 2: Swap conftest.py Fixture Purposes

**Manual review required** - The conftest.py files need fixture logic changes, not just file swaps.

**tests/func/conftest.py** after migration:
- Remove `requires_catalog`, `test_bucket`, `test_registry` (real integration fixtures)
- Add mocking setup fixtures similar to current e2e conftest

**tests/e2e/conftest.py** after migration:
- Add `requires_catalog`, `test_bucket`, `test_registry` (from current func conftest)
- Remove mocking-specific fixtures

### Step 3: Run Migration

```bash
cd /Users/ernest/GitHub/quilt-mcp-server
bash scripts/migrate_tests.sh
```

### Step 4: Update Test Imports

Some tests may have imports that reference the old directory structure in comments or docstrings. Review and update as needed.

### Step 5: Update Documentation

**Files to update:**
- [TESTING.md](TESTING.md) - Verify structure documentation is accurate
- [CLAUDE.md](CLAUDE.md) - Update any test structure references
- [README.md](README.md) - Update testing section if present

## Verification Plan

### Phase 1: Verify Test Discovery

```bash
# Should discover only mocked tests (faster)
uv run pytest tests/func/ --collect-only

# Should discover only real integration tests (slower, requires credentials)
uv run pytest tests/e2e/ --collect-only
```

### Phase 2: Run Test Suites

```bash
# Should be fast (all mocked)
make test-func

# Should be slow (real AWS/Elasticsearch/Docker)
make test-e2e

# Should pass (all tests still work)
make test-all
```

### Phase 3: Verify CI Behavior

```bash
# Should be fast and not require external services
make test-ci
```

### Phase 4: Check Coverage

```bash
make coverage
```

Verify coverage reports still include all test files in the correct categories.

### Phase 5: Validate Test Categorization

Create validation script `scripts/validate_test_structure.py`:

```python
#!/usr/bin/env python3
"""Validate test structure matches expected patterns."""

import ast
import sys
from pathlib import Path

def check_for_mocks(test_file: Path) -> bool:
    """Check if test file uses mocking."""
    content = test_file.read_text()
    mock_indicators = [
        "@patch",
        "Mock(",
        "MagicMock(",
        "mock.patch",
        "unittest.mock",
        "from unittest import mock",
    ]
    return any(indicator in content for indicator in mock_indicators)

def check_for_real_services(test_file: Path) -> bool:
    """Check if test file requires real services."""
    content = test_file.read_text()
    real_service_indicators = [
        "NO MOCKING",
        "Real AWS",
        "Real Elasticsearch",
        "requires_catalog",
        "requires_docker",
        "@pytest.mark.slow",
    ]
    return any(indicator in content for indicator in real_service_indicators)

def validate_func_tests():
    """Validate func/ tests are properly mocked."""
    func_tests = Path("tests/func").glob("test_*.py")
    issues = []

    for test_file in func_tests:
        if test_file.name == "conftest.py":
            continue

        has_mocks = check_for_mocks(test_file)
        has_real = check_for_real_services(test_file)

        if has_real and not has_mocks:
            issues.append(f"❌ {test_file.name}: Uses real services (should be in e2e/)")

    return issues

def validate_e2e_tests():
    """Validate e2e/ tests use real services."""
    e2e_tests = Path("tests/e2e").glob("test_*.py")
    issues = []

    for test_file in e2e_tests:
        if test_file.name == "conftest.py":
            continue

        has_mocks = check_for_mocks(test_file)
        has_real = check_for_real_services(test_file)

        if has_mocks and not has_real:
            issues.append(f"❌ {test_file.name}: Uses only mocks (should be in func/)")

    return issues

if __name__ == "__main__":
    print("Validating test structure...")

    func_issues = validate_func_tests()
    e2e_issues = validate_e2e_tests()

    if func_issues:
        print("\ntests/func/ issues:")
        for issue in func_issues:
            print(f"  {issue}")

    if e2e_issues:
        print("\ntests/e2e/ issues:")
        for issue in e2e_issues:
            print(f"  {issue}")

    if func_issues or e2e_issues:
        sys.exit(1)
    else:
        print("\n✓ All tests are in the correct directories!")
        sys.exit(0)
```

Run validation:

```bash
uv run python scripts/validate_test_structure.py
```

## Success Criteria

- [ ] All real integration tests are in `tests/e2e/`
- [ ] All mocked tests are in `tests/func/`
- [ ] `make test-func` runs quickly (<30s) with no external dependencies
- [ ] `make test-e2e` runs with real services (requires credentials)
- [ ] `make test-all` passes with 100% of previous coverage
- [ ] CI pipeline `make test-ci` runs quickly (func tests only)
- [ ] Test structure validation script passes
- [ ] Documentation updated to reflect new structure

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tests break after move | High | Create backup before migration, git allows easy revert |
| Import paths change | Medium | Tests use relative imports, should be minimal impact |
| Fixture incompatibility | High | Manual review of conftest.py changes required |
| CI pipeline breaks | High | Test locally with `make test-ci` before pushing |
| Coverage drops | Medium | Validate coverage before/after with `make coverage` |

## Timeline Estimate

*Note: No time estimates per guidelines. Steps are sequential and dependent.*

1. Create migration script
2. Review conftest.py changes (requires careful analysis)
3. Run migration
4. Fix any import issues
5. Update fixtures
6. Run verification
7. Update documentation
8. Commit and push

## Related Work

- **A17 Test Cleanup**: This is part of the broader test cleanup initiative
- **Coverage Analysis**: [scripts/coverage_analysis.py](../../scripts/coverage_analysis.py)
- **Test Runner**: [scripts/test-runner.py](../../scripts/test-runner.py)

# Testing Refactor: Strategic Improvements

**Status:** Proposal
**Date:** 2026-02-04
**Related:** [GitHub Issue #238](https://github.com/quiltdata/quilt-mcp-server/issues/238), [01-testing-issues.md](01-testing-issues.md)
**Goal:** Improve test coverage from 55.7% to 75%+ while addressing architectural issues

---

## Executive Summary

This document proposes strategic improvements to the test suite building on:

1. **Issue #238** - Coverage gaps and over-mocking analysis
2. **01-testing-issues.md** - Organizational and complexity issues

The proposal focuses on:

- **Test folder reorganization** (addressing #238 comment)
- **Coverage-driven refactoring** (targeting the 75% goal)
- **Reducing technical debt** (mocking, fixtures, complexity)
- **Developer experience** (speed, clarity, CI integration)

---

## Part 1: Test Folder Reorganization

### Current State (Problematic)

```
tests/
├── unit/           # "Single module, mocked" - but unclear boundary
├── integration/    # "Multi-module" - but what about AWS calls?
├── e2e/           # "Real-world" - but actually well-mocked (2.6s runtime)
├── stateless/     # Docker-based, unclear relationship to other categories
├── security/      # Rarely run, purpose unclear
├── performance/   # Rarely run, purpose unclear
├── load/          # Rarely run, purpose unclear
└── fixtures/      # Data + test runners (confusing)
```

**Problems:**

- "Integration" is ambiguous (multi-module? Real AWS? Both?)
- E2E tests are faster than integration tests (contradiction)
- No clear distinction between mocked vs. real infrastructure
- Specialized suites (security/performance/load) not integrated into workflow

### Proposed Structure (Aligned with #238 Comment)

```
tests/
├── unit/          # Single module, no network, all mocks
├── func/          # Multi-module, no network, functional logic
├── e2e/           # Real AWS/network, no mocks, full workflows
├── platform/      # Requires platform authentication (formerly marked by tag)
├── slow/          # Tests taking >1s (for CI exclusion during rapid iteration)
├── stateless/     # Docker-based, read-only filesystem tests
├── fixtures/      # Shared test data and helpers (no test runners)
└── helpers/       # Shared test utilities (moved from conftest complexity)
```

**Key Changes:**

1. **`integration/` → `func/` (functional)**
   - Clear name: tests multiple modules working together
   - No network access (mocked AWS/HTTP clients)
   - Focus: Business logic across module boundaries
   - Example: Testing that package service correctly calls backend service

2. **`e2e/` → truly end-to-end**
   - Real AWS services (S3, Athena, etc.)
   - Real HTTP calls to catalog
   - No mocks except external services beyond our control
   - Example: Full workflow from MCP request → AWS → response

3. **`platform/` → explicit directory**
   - Tests requiring platform authentication
   - Replaces scattered `PLATFORM_TEST_ENABLED` checks
   - Clear opt-in for platform-specific tests
   - Can be skipped entirely in CI without platform access

4. **`slow/` → explicit directory**
   - Tests taking >1 second
   - Can be excluded during rapid development iteration
   - Run in CI before merge
   - Example: Cache expiration tests, large data processing

5. **Remove ambiguous suites**
   - `security/` → Merge into `unit/` or `e2e/` depending on nature
   - `performance/` → Move to `slow/` or document as benchmarks
   - `load/` → Document as manual load testing (not CI)

### Migration Strategy

**Phase 1: Categorize existing tests** (1-2 days)

```bash
# Audit each test file and categorize
for file in tests/integration/*.py; do
    # Does it make network calls?
    if grep -q "boto3\|httpx" "$file" && ! grep -q "@mock\|@patch" "$file"; then
        echo "$file → tests/e2e/"
    else
        echo "$file → tests/func/"
    fi
done
```

**Phase 2: Move files gradually** (2-3 days)

- Move files to new structure
- Update imports
- Update CI configuration
- Update documentation

**Phase 3: Validate** (1 day)

- Run full suite in new structure
- Verify coverage numbers unchanged
- Update developer documentation

---

## Part 2: Test Tagging Strategy

### Design Principle: Simplicity First

**Per GitHub Issue #238 comment:** Keep markers minimal. Use **directory structure** for test
categorization (unit/func/e2e), and **markers only for CI control**.

### Proposed Pytest Markers (Minimal)

```python
# pytest.ini or conftest.py
markers =
    platform: Requires platform authentication (skip if PLATFORM_TEST_ENABLED=false)
    slow: Tests taking >1 second (skip with -m "not slow" during rapid iteration)
```

**Why only 2 markers?**

- Test type (unit/func/e2e) determined by **directory location**
- Infrastructure requirements (AWS, Docker) determined by **skip conditions in tests**
- Simple to understand and maintain
- Less cognitive overhead for developers

### Usage in Tests

```python
# Unit test - no markers needed, location defines it
# tests/unit/test_parser.py
def test_parse_package_name():
    assert parse_package_name("user/pkg") == ("user", "pkg")

# Functional test - no markers needed
# tests/func/test_package_service.py
def test_package_service_calls_backend(mock_backend):
    service = PackageService(mock_backend)
    service.get_package("user/pkg")
    mock_backend.get_package.assert_called_once()

# E2E test that's slow - mark as slow
# tests/e2e/test_full_workflow.py
@pytest.mark.slow
def test_full_package_workflow():
    # Real S3, real Athena, real package operations
    package = browse_package("s3://quilt-example/user/pkg")
    assert len(package.entries) > 0

# Platform test - mark as platform
# tests/platform/test_search.py
@pytest.mark.platform
def test_platform_search():
    results = search_catalog("test query")
    assert len(results) > 0

# Infrastructure requirements - use skipif, not markers
# tests/e2e/test_tabulator.py
@pytest.mark.skipif(
    not os.getenv("QUILT_TABULATOR_CATALOG"),
    reason="Tabulator catalog not configured"
)
def test_tabulator_workflow():
    # Test tabulator functionality
    ...
```

### CI Configuration

```yaml
# .github/workflows/test.yml
jobs:
  test-fast:
    runs-on: ubuntu-latest
    steps:
      # Use directories, not markers, for test types
      - run: uv run pytest tests/unit/ tests/func/ -m "not slow" --maxfail=3
        # Fast feedback: <30 seconds

  test-e2e:
    runs-on: ubuntu-latest
    needs: test-fast
    steps:
      # E2E tests by directory, exclude slow tests
      - run: uv run pytest tests/e2e/ -m "not slow"
        # E2E without slow tests: <2 minutes

  test-platform:
    runs-on: ubuntu-latest
    needs: test-fast
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      # Platform tests use marker (one of only 2 markers)
      - run: uv run pytest -m "platform"
        # Platform tests only on main branch

  test-slow:
    runs-on: ubuntu-latest
    needs: [test-fast, test-e2e]
    if: github.event_name == 'pull_request'
    steps:
      # Slow tests use marker (one of only 2 markers)
      - run: uv run pytest -m "slow"
        # Slow tests only for PRs, after fast tests pass
```

### Developer Workflow

```bash
# Rapid iteration (fastest) - use directories
uv run pytest tests/unit/

# Pre-commit check (fast + functional) - use directories
uv run pytest tests/unit/ tests/func/

# Include E2E but skip slow tests
uv run pytest tests/unit/ tests/func/ tests/e2e/ -m "not slow"

# Full local test (skip platform tests)
uv run pytest -m "not platform"

# Full CI test (all tests including platform and slow)
uv run pytest
```

---

## Part 3: Coverage-Driven Refactoring Strategy

### Addressing Issue #238 Goals

**Target: 75%+ combined coverage** (currently 55.7%)
**Gap: ~20% coverage improvement needed**

### Phase 1: Low-Hanging Fruit (+10-15% coverage)

#### 1.1 Visualization Module (1,296 lines, 0% coverage)

**Current State:**

```
src/quilt_mcp/visualization/
├── analyzers/       # Data analysis
├── generators/      # ECharts, Vega-Lite, etc.
├── layouts/         # Layout engines
└── engine.py        # Main engine
```

**Analysis:**

- **If actively used:** Critical coverage gap, needs tests
- **If experimental:** Mark as exempt from coverage requirements
- **If dead code:** Remove entirely

**Action Plan:**

1. **Audit usage** (1 hour):

```bash
# Check if visualization tools are called
grep -r "visualization" src/quilt_mcp/tools/
grep -r "create_visualization" src/quilt_mcp/
```

1. **If used, add smoke tests** (1-2 days):

```python
# tests/func/test_visualization_engine.py
@pytest.mark.func
def test_visualization_engine_creates_chart():
    data = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    chart = VisualizationEngine().create_chart(data, "line")
    assert chart is not None
    assert "option" in chart  # ECharts format
```

1. **If unused, exempt from coverage** (1 hour):

```yaml
# .coveragerc
[report]
exclude_lines =
    # Exclude experimental visualization module
    pragma: no cover
    visualization/
```

**Expected Coverage Gain:** +3-5%

---

#### 1.2 Dead Code Removal (95+ lines, 0% coverage)

**Candidates:**

- `tools/stack_buckets.py` (95 lines, 0% coverage)
- Any other 0% coverage modules

**Action Plan:**

1. **Identify dead code** (2 hours):

```bash
# Find all files with 0% coverage
uv run pytest --cov=src --cov-report=term-missing | grep "0%"
```

1. **Audit each file** (1-2 hours per file):
   - Is it imported anywhere?
   - Is it referenced in documentation?
   - Is it planned for future use?

2. **Remove or document** (1 hour):

```python
# Option 1: Remove dead code
git rm src/quilt_mcp/tools/stack_buckets.py

# Option 2: Mark as future/experimental
# src/quilt_mcp/tools/stack_buckets.py
"""
EXPERIMENTAL: Stack bucket operations (not yet implemented)
Coverage exemption: Planned for v0.15.0
"""
```

**Expected Coverage Gain:** +1-2%

---

#### 1.3 Add Skips for Configuration-Dependent Tests (0 coverage gain, but fixes CI)

**Problem:** Tests fail when required configuration is missing

**Example - Tabulator test:**

```python
# tests/e2e/test_athena.py
def test_tabulator_complete_workflow():
    # FAILS: "tabulator_data_catalog not configured"
    ...
```

**Fix:**

```python
@pytest.mark.skipif(
    not os.getenv("QUILT_TABULATOR_CATALOG"),
    reason="Tabulator catalog not configured"
)
def test_tabulator_complete_workflow():
    ...
```

**Action Plan:**

1. Audit all failing tests
2. Add appropriate skip conditions
3. Document required configuration in TESTING.md

---

### Phase 2: Reduce Over-Mocking (+5-10% coverage)

#### 2.1 Problem: Mocking Doesn't Test Real Code

**Current Pattern (Bad):**

```python
# tests/unit/backends/test_quilt3_backend_packages.py
@mock.patch("quilt_mcp.backends.quilt3_backend.quilt3")
def test_get_package(mock_quilt3):
    # Setup mocks
    mock_package = Mock()
    mock_package.entries = ["file1.txt", "file2.txt"]
    mock_quilt3.Package.browse.return_value = mock_package

    # Call
    backend = Quilt3_Backend()
    result = backend.get_package("user/pkg")

    # Assert mock was called (NOT testing real code!)
    mock_quilt3.Package.browse.assert_called_once()
    assert result == mock_package
```

**What's Wrong:**

- ✅ Tests that mock is called correctly
- ❌ Doesn't test actual parsing logic
- ❌ Doesn't test error handling
- ❌ Doesn't test data transformations
- ❌ False sense of security

**Better Pattern (Good):**

```python
# tests/func/backends/test_quilt3_backend_packages.py
@pytest.mark.func
def test_get_package_parsing():
    # Use a fake quilt3.Package, not a mock
    fake_package = FakeQuilt3Package(
        entries={
            "file1.txt": FakeEntry(size=100, hash="abc"),
            "dir/file2.txt": FakeEntry(size=200, hash="def")
        }
    )

    # Inject fake via dependency injection or monkey-patch
    backend = Quilt3_Backend()
    backend._package_factory = lambda *args: fake_package

    # Call REAL code
    result = backend.get_package("user/pkg")

    # Assert REAL behavior
    assert len(result.entries) == 2
    assert result.entries[0].path == "file1.txt"
    assert result.entries[0].size == 100
    assert result.total_size == 300  # Tests aggregation logic
```

**Benefits:**

- ✅ Tests real parsing logic
- ✅ Tests real error handling
- ✅ Tests real data transformations
- ✅ Tests edge cases (empty package, nested dirs, etc.)
- ✅ Refactoring-safe (code changes break tests appropriately)

---

#### 2.2 Strategy: Create Test Doubles

**Create reusable test doubles instead of mocks:**

```python
# tests/helpers/fake_quilt3.py
class FakeQuilt3Package:
    """Test double for quilt3.Package"""

    def __init__(self, entries: dict):
        self.entries = entries

    def __getitem__(self, key):
        return self.entries[key]

    def walk(self):
        for path, entry in self.entries.items():
            yield path, entry

class FakeQuilt3Backend:
    """Test double for quilt3 module"""

    def __init__(self):
        self.packages = {}

    def Package(self):
        return FakeQuilt3Package({})

    def browse(self, name, registry=None):
        return self.packages.get(name, FakeQuilt3Package({}))
```

**Usage:**

```python
# tests/func/test_package_operations.py
@pytest.fixture
def fake_quilt3():
    fake = FakeQuilt3Backend()
    # Seed with test data
    fake.packages["user/pkg"] = FakeQuilt3Package({
        "README.md": FakeEntry(size=100),
        "data.csv": FakeEntry(size=1000)
    })
    return fake

@pytest.mark.func
def test_package_operations(fake_quilt3):
    # Tests run against fake, not mocks
    backend = Quilt3_Backend(quilt3_module=fake_quilt3)
    result = backend.get_package("user/pkg")
    assert result.total_size == 1100  # Tests REAL aggregation logic
```

---

#### 2.3 Refactoring Priority Matrix

**High Priority (High mock count + High coverage gap):**

| File | Mock Count | Coverage Gap | Action |
|------|------------|--------------|--------|
| `test_quilt_service.py` | 109 | 17.4% gap | Refactor to func tests |
| `test_utils.py` | 48 | 46.4% gap | Refactor to func tests |
| `test_tabulator.py` | 31 | 62.3% gap | Refactor to func tests |

**Action Plan:**

1. **Week 1:** Refactor `test_quilt_service.py`
   - Create `FakeQuilt3Backend` test double
   - Move to `tests/func/backends/`
   - Keep unit tests for pure validation logic

2. **Week 2:** Refactor `test_utils.py`
   - Identify which utils are pure functions (keep unit tests)
   - Move IO-heavy tests to func tests

3. **Week 3:** Refactor `test_tabulator.py`
   - Create fake Athena client
   - Move to `tests/func/tools/`

**Expected Coverage Gain:** +5-8%

---

### Phase 3: Strategic Integration Tests (+5-10% coverage)

#### 3.1 Focus on Modules with High Unit-Only Coverage

**Target modules (from Issue #238):**

| Module | Unit Only | Integration | Gap |
|--------|-----------|-------------|-----|
| `error_recovery.py` | 59.9% | 0.0% | 127 lines |
| `workflow_service.py` | 66.5% | 18.1% | 91 lines |
| `governance_service.py` | 59.4% | 12.9% | 102 lines |
| `data_visualization.py` | 55.6% | 13.1% | 130 lines |

**Problem:** These modules have unit tests, but unit tests are mocked heavily, so real integration paths aren't tested.

---

#### 3.2 Error Recovery Integration Tests

**Current State:**

- Unit tests mock error scenarios
- No tests of real error recovery with AWS

**Add E2E Tests:**

```python
# tests/e2e/test_error_recovery.py
# Note: Location (tests/e2e/) defines test type - no @pytest.mark.e2e needed
@pytest.mark.slow  # One of our 2 markers
def test_s3_throttling_recovery():
    """Test that backend recovers from S3 throttling errors"""
    backend = Quilt3_Backend()

    # Use a high-throughput operation that might trigger throttling
    # (or use botocore stubber to inject throttling error)
    with botocore_stubber.stub_throttling_then_success():
        result = backend.list_objects("s3://bucket/prefix/", max_keys=10000)

    # Should succeed after retry
    assert len(result) > 0

def test_network_timeout_recovery():
    """Test recovery from network timeouts"""
    backend = Quilt3_Backend()

    with network_delay_simulator(delay_ms=5000):
        # Should timeout and retry
        result = backend.get_object("s3://bucket/key.txt")

    assert result is not None
```

**Expected Coverage Gain:** +2-3% (127 lines → 85-100 lines covered)

---

#### 3.3 Workflow Service Integration Tests

**Add Cross-Service Tests:**

```python
# tests/func/test_workflow_service.py
# Note: Location defines test type - no markers needed
def test_package_creation_workflow(fake_backend, fake_catalog):
    """Test full package creation workflow across services"""
    workflow_service = WorkflowService(backend=fake_backend, catalog=fake_catalog)

    # Test real workflow logic
    result = workflow_service.create_package_workflow(
        name="user/pkg",
        files=["file1.txt", "file2.txt"],
        metadata={"key": "value"}
    )

    # Verify workflow steps executed correctly
    assert result.package_created
    assert result.metadata_updated
    assert result.catalog_indexed
    assert fake_backend.packages["user/pkg"] is not None

# tests/e2e/test_workflow_service.py
# Note: Location (tests/e2e/) defines test type
def test_package_creation_workflow_real():
    """Test full package creation with real AWS"""
    workflow_service = WorkflowService()

    # Use test bucket
    result = workflow_service.create_package_workflow(
        name=f"test-user/test-pkg-{uuid.uuid4()}",
        files=["tests/fixtures/data/sample.txt"],
        metadata={"test": True}
    )

    # Verify in real S3
    assert result.package_created
    assert backend.package_exists(result.package_name)
```

**Expected Coverage Gain:** +2-3% (91 lines → 64-73 lines covered)

---

#### 3.4 Governance Service Integration Tests

**Focus on Policy Enforcement:**

```python
# tests/func/test_governance_service.py
# Note: Location defines test type
def test_policy_enforcement_workflow(fake_backend, fake_policy_store):
    """Test that policies are enforced across operations"""
    governance = GovernanceService(backend=fake_backend, policies=fake_policy_store)

    # Set up policy: users can't delete packages in prod
    fake_policy_store.add_policy({
        "action": "delete_package",
        "resource": "s3://prod-bucket/*",
        "effect": "deny"
    })

    # Test enforcement
    with pytest.raises(PermissionDenied):
        governance.delete_package("user/pkg", bucket="s3://prod-bucket")

    # Test allowed operation
    result = governance.delete_package("user/pkg", bucket="s3://dev-bucket")
    assert result.success

# tests/platform/test_governance_service.py
# Note: Platform tests go in tests/platform/ and use @pytest.mark.platform
@pytest.mark.platform  # One of our 2 markers
def test_governance_with_real_platform():
    """Test governance policies with real platform"""
    governance = GovernanceService()

    # Test real IAM-based policy enforcement
    # (requires specific IAM setup)
    result = governance.check_permissions(
        user="test-user",
        action="read_package",
        resource="s3://test-bucket/test-user/pkg"
    )

    assert result.allowed
```

**Expected Coverage Gain:** +2-3% (102 lines → 70-80 lines covered)

---

### Phase 3 Summary

**Total Expected Coverage Gain:** +6-9% across 450 lines

**Effort Breakdown:**

- Error recovery tests: 1-2 days
- Workflow service tests: 2-3 days
- Governance service tests: 2-3 days
- Data visualization tests: 1-2 days (or exempt if unused)

---

## Part 4: Fixture Refactoring

### Problem: Complex Fixtures Create Hidden Dependencies

**Current Issues (from 01-testing-issues.md):**

- 2 autouse session fixtures run for every test
- `pytest_configure` has 40 lines of global setup
- Complex fixture inheritance chains
- Session-scoped fixtures with state

### Proposed Fixture Strategy

#### 4.1 Remove Autouse Fixtures

**Current (Bad):**

```python
@pytest.fixture(scope="session", autouse=True)
def reset_runtime_auth_state():
    # Runs for EVERY test whether needed or not
    clear_runtime_auth()
    yield
    clear_runtime_auth()
```

**Proposed (Good):**

```python
@pytest.fixture(scope="function")
def clean_auth():
    """Opt-in fixture for tests that need clean auth state"""
    clear_runtime_auth()
    yield
    clear_runtime_auth()

# Usage: Only in tests that need it
def test_auth_flow(clean_auth):
    ...
```

---

#### 4.2 Simplify pytest_configure

**Current (Too Complex):**

```python
def pytest_configure(config):
    # 40 lines of global setup
    clear_runtime_auth()
    os.environ["QUILT_MULTIUSER_MODE"] = "false"
    os.environ.pop("MCP_JWT_SECRET", None)
    reset_mode_config()
    boto3.setup_default_session(...)
    os.environ["ATHENA_WORKGROUP"] = "primary"
```

**Proposed (Minimal):**

```python
def pytest_configure(config):
    """Minimal global configuration"""
    # Only truly global settings
    register_custom_markers(config)

    # Everything else becomes opt-in fixtures
```

**Move configuration to fixtures:**

```python
@pytest.fixture
def local_mode():
    """Configure local (non-multiuser) mode"""
    original = os.getenv("QUILT_MULTIUSER_MODE")
    os.environ["QUILT_MULTIUSER_MODE"] = "false"
    reset_mode_config()
    yield
    if original:
        os.environ["QUILT_MULTIUSER_MODE"] = original
    else:
        os.environ.pop("QUILT_MULTIUSER_MODE", None)
    reset_mode_config()

@pytest.fixture
def aws_session():
    """Configure AWS session with profile"""
    if profile := os.getenv("AWS_PROFILE"):
        session = boto3.Session(profile_name=profile)
        boto3.setup_default_session(profile_name=profile)
        yield session
        # Cleanup
    else:
        yield boto3.Session()
```

---

#### 4.3 Replace backend_mode Fixture

**Current Problem:**

- Runs tests twice (quilt3 + platform)
- 76 tests skipped when platform disabled
- Many tests don't need both modes

**Proposed Solution:**

```python
# Remove global parametrization
# Instead, use explicit markers

@pytest.fixture
def quilt3_backend():
    """Quilt3 backend for testing"""
    return Quilt3_Backend()

@pytest.fixture
def platform_backend():
    """Platform backend for testing"""
    pytest.importorskip("platform_module", reason="Platform tests disabled")
    return Platform_Backend()

# Tests that need both modes (rare)
@pytest.mark.parametrize("backend", ["quilt3", "platform"])
def test_backend_interface(backend, request):
    backend_instance = request.getfixturevalue(f"{backend}_backend")
    ...

# Most tests: Just use one backend
def test_quilt3_specific(quilt3_backend):
    ...

def test_platform_specific(platform_backend):
    ...
```

**Benefits:**

- Tests run once by default
- Explicit when both backends needed
- No more PLATFORM_TEST_ENABLED confusion
- Faster test suite

---

### Fixture Refactoring Plan

**Week 1: Audit and plan**

1. List all fixtures and their usage
2. Identify which can be opt-in
3. Document fixture dependencies

**Week 2: Remove autouse**

1. Remove `reset_runtime_auth_state` autouse
2. Update tests to use `clean_auth` fixture explicitly
3. Run tests, fix failures

**Week 3: Simplify pytest_configure**

1. Move config to opt-in fixtures
2. Update tests to use new fixtures
3. Document in TESTING.md

**Week 4: Replace backend_mode**

1. Create explicit backend fixtures
2. Update tests to use explicit fixtures
3. Remove parametrization

**Expected Impact:**

- 🚀 **20-30% faster test suite** (no double-running)
- 🧹 **Clearer test dependencies** (explicit fixtures)
- 🎯 **Easier debugging** (less hidden magic)

---

## Part 5: Anti-Patterns to Avoid

### 5.1 Don't Mock What You're Testing

❌ **Bad:**

```python
@mock.patch("module.function_a")
@mock.patch("module.function_b")
def test_module_workflow(mock_b, mock_a):
    # This doesn't test module.workflow(), just that mocks are called
    module.workflow()
    mock_a.assert_called()
    mock_b.assert_called()
```

✅ **Good:**

```python
def test_module_workflow(fake_external_service):
    # Test real workflow logic, mock only external dependencies
    result = module.workflow(external_service=fake_external_service)
    assert result.steps_completed == 3
    assert result.data_transformed
```

---

### 5.2 Don't Over-Parametrize

❌ **Bad:**

```python
@pytest.mark.parametrize("backend", ["quilt3", "platform"])
@pytest.mark.parametrize("mode", ["local", "multiuser"])
@pytest.mark.parametrize("region", ["us-east-1", "us-west-2"])
def test_everything(backend, mode, region):
    # Runs 2 × 2 × 2 = 8 times!
    # Most combinations not meaningful
    ...
```

✅ **Good:**

```python
def test_quilt3_local_us_east():
    # Most common case
    ...

def test_platform_multiuser_us_west():
    # Specific important case
    ...

# Only parametrize when all combinations are meaningful
@pytest.mark.parametrize("region", ["us-east-1", "us-west-2", "eu-west-1"])
def test_region_specific_logic(region):
    # Each region has different behavior
    ...
```

---

### 5.3 Don't Test Implementation Details

❌ **Bad:**

```python
def test_package_service():
    service = PackageService()
    service.get_package("user/pkg")
    # Testing internal implementation
    assert service._cache["user/pkg"] is not None
    assert service._request_count == 1
```

✅ **Good:**

```python
def test_package_service():
    service = PackageService()
    result = service.get_package("user/pkg")
    # Test observable behavior
    assert result.name == "user/pkg"
    assert len(result.entries) > 0
```

---

### 5.4 Don't Create Implicit Test Dependencies

❌ **Bad:**

```python
# test_a.py
def test_create_resource():
    create_resource("resource-1")
    # Doesn't clean up

# test_b.py
def test_use_resource():
    # Assumes resource-1 exists from test_a
    resource = get_resource("resource-1")
```

✅ **Good:**

```python
# test_a.py
def test_create_resource():
    resource_id = f"resource-{uuid.uuid4()}"
    create_resource(resource_id)
    # Cleanup
    delete_resource(resource_id)

# test_b.py
def test_use_resource():
    # Create own resource
    resource_id = f"resource-{uuid.uuid4()}"
    create_resource(resource_id)
    resource = get_resource(resource_id)
    # Cleanup
    delete_resource(resource_id)
```

---

### 5.5 Don't Write Mega-Fixtures

❌ **Bad:**

```python
@pytest.fixture
def everything():
    # 200 lines of setup
    backend = setup_backend()
    catalog = setup_catalog()
    auth = setup_auth()
    session = setup_session()
    database = setup_database()
    cache = setup_cache()
    # ... 50 more things

    yield {
        "backend": backend,
        "catalog": catalog,
        # ... 50 more keys
    }

    # 100 lines of teardown
```

✅ **Good:**

```python
@pytest.fixture
def backend():
    backend = setup_backend()
    yield backend
    cleanup_backend(backend)

@pytest.fixture
def catalog():
    catalog = setup_catalog()
    yield catalog
    cleanup_catalog(catalog)

# Compose as needed
def test_with_backend_and_catalog(backend, catalog):
    ...

def test_with_just_backend(backend):
    ...
```

---

## Part 6: Modern Testing Best Practices

### 6.1 Prefer Factory Fixtures Over Shared State

**Pattern: Factory fixtures create fresh instances**

```python
@pytest.fixture
def make_package():
    """Factory fixture for creating test packages"""
    packages = []

    def _make_package(name, entries=None):
        pkg = FakePackage(name, entries or {})
        packages.append(pkg)
        return pkg

    yield _make_package

    # Cleanup all created packages
    for pkg in packages:
        pkg.cleanup()

# Usage
def test_multiple_packages(make_package):
    pkg1 = make_package("user/pkg1")
    pkg2 = make_package("user/pkg2")
    assert pkg1 != pkg2
```

---

### 6.2 Use Hypothesis for Property-Based Testing

**For complex parsing/validation logic:**

```python
from hypothesis import given, strategies as st

@given(
    name=st.text(min_size=1, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))),
    version=st.integers(min_value=0, max_value=1000)
)
def test_package_name_parsing(name, version):
    """Test package name parsing with random inputs"""
    pkg_str = f"{name}@{version}"
    parsed = parse_package_name(pkg_str)
    assert parsed.name == name
    assert parsed.version == version
```

**Benefits:**

- Finds edge cases you didn't think of
- Tests properties, not specific examples
- Better coverage of input space

---

### 6.3 Use respx for HTTP Mocking

**Instead of mock.patch for HTTP:**

```python
import respx
import httpx

@respx.mock
def test_catalog_api():
    # Mock HTTP responses declaratively
    respx.get("https://catalog.example.com/api/packages").mock(
        return_value=httpx.Response(
            200,
            json={"packages": [{"name": "user/pkg"}]}
        )
    )

    # Test real HTTP client code
    client = CatalogClient("https://catalog.example.com")
    packages = client.list_packages()

    assert len(packages) == 1
    assert packages[0]["name"] == "user/pkg"
```

**Benefits:**

- Tests real HTTP client code
- Declarative mock setup
- Better error messages
- Works with async

---

### 6.4 Use freezegun for Time-Dependent Tests

**Instead of mocking time:**

```python
from freezegun import freeze_time

@freeze_time("2026-01-01 12:00:00")
def test_cache_expiration():
    cache = Cache(ttl_seconds=3600)
    cache.set("key", "value")

    # Fast-forward time
    with freeze_time("2026-01-01 13:01:00"):
        assert cache.get("key") is None  # Expired
```

---

### 6.5 Use pytest-timeout to Catch Infinite Loops

```python
@pytest.mark.timeout(5)  # Fail after 5 seconds
def test_recursive_operation():
    # If this hangs, test fails after 5s instead of hanging forever
    result = recursive_algorithm(input_data)
    assert result is not None
```

---

### 6.6 Use tmp_path for File Operations

**Built-in pytest fixture:**

```python
def test_file_operations(tmp_path):
    # tmp_path is a pathlib.Path to a temporary directory
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    result = process_file(test_file)

    assert result.success
    # No cleanup needed, tmp_path is automatically cleaned up
```

---

## Part 7: Coverage Validation Strategy

### 7.1 Coverage Thresholds

**Proposed thresholds (aligned with Issue #238):**

```yaml
# scripts/tests/coverage_required.yaml
thresholds:
  combined: 75  # Main goal (up from 55.7%)
  unit: 30      # Keep low (currently 37.2%)
  func: 30      # New category (replaces integration 29.0%)
  e2e: 28       # Keep current (32.0%)

exemptions:
  # Modules exempt from coverage requirements
  - "src/quilt_mcp/visualization/*"  # Experimental
  - "src/quilt_mcp/tools/stack_buckets.py"  # Dead code candidate
  - "src/quilt_mcp/cli.py"  # CLI entry point, hard to test

per_file_minimum: 50  # Each file should have at least 50% coverage
```

---

### 7.2 Coverage CI Gates

```yaml
# .github/workflows/coverage.yml
name: Coverage Check

on: [pull_request]

jobs:
  coverage:
    runs-on: ubuntu-latest
    steps:
      - name: Run tests with coverage
        run: |
          uv run pytest --cov=src --cov-report=term-missing --cov-report=xml

      - name: Check combined threshold
        run: |
          coverage report --fail-under=75

      - name: Check per-file minimum
        run: |
          python scripts/check_per_file_coverage.py --minimum=50

      - name: Upload to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

      - name: Comment on PR
        uses: py-cov-action/python-coverage-comment-action@v3
        with:
          GITHUB_TOKEN: ${{ github.token }}
```

---

### 7.3 Per-File Coverage Script

```python
# scripts/check_per_file_coverage.py
import sys
import xml.etree.ElementTree as ET

def check_per_file_coverage(coverage_xml, minimum=50):
    tree = ET.parse(coverage_xml)
    root = tree.getroot()

    violations = []

    for package in root.findall('.//package'):
        for class_elem in package.findall('class'):
            filename = class_elem.get('filename')

            # Skip exempted files
            if any(pattern in filename for pattern in EXEMPTIONS):
                continue

            lines = class_elem.find('lines')
            total = len(lines.findall('line'))
            covered = len([l for l in lines.findall('line') if int(l.get('hits', 0)) > 0])

            if total > 0:
                coverage_pct = (covered / total) * 100
                if coverage_pct < minimum:
                    violations.append({
                        'file': filename,
                        'coverage': coverage_pct,
                        'minimum': minimum
                    })

    if violations:
        print(f"❌ {len(violations)} files below {minimum}% coverage:")
        for v in violations:
            print(f"  {v['file']}: {v['coverage']:.1f}%")
        sys.exit(1)
    else:
        print(f"✅ All files meet {minimum}% coverage threshold")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--minimum', type=int, default=50)
    args = parser.parse_args()
    check_per_file_coverage('coverage.xml', args.minimum)
```

---

## Part 8: Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Goal:** Set up new structure without breaking existing tests

- [ ] Create new test directories (`func/`, `platform/`, `slow/`)
- [ ] Add pytest markers configuration
- [ ] Update CI to use new markers
- [ ] Document new structure in TESTING.md

**Deliverables:**

- New directory structure (empty)
- Updated pytest.ini with markers
- Updated CI configuration
- TESTING.md documentation

---

### Phase 2: Low-Hanging Fruit (Weeks 3-4)

**Goal:** +10-15% coverage gain

- [ ] Audit visualization module → add tests or exempt
- [ ] Audit stack_buckets.py → test or remove
- [ ] Fix failing tests with proper skip conditions
- [ ] Remove dead code

**Deliverables:**

- Visualization module tested or exempted
- Dead code removed or documented
- All tests passing or properly skipped
- Coverage: 65-70% (up from 55.7%)

---

### Phase 3: Reduce Over-Mocking (Weeks 5-7)

**Goal:** +5-10% coverage gain, better test quality

- [ ] Create test double helpers (`fake_quilt3`, `fake_boto3`)
- [ ] Refactor `test_quilt_service.py` (109 mocks)
- [ ] Refactor `test_utils.py` (48 mocks)
- [ ] Move tests from `unit/` to `func/` as appropriate

**Deliverables:**

- `tests/helpers/fake_*.py` modules
- Refactored high-mock tests
- Coverage: 70-75%

---

### Phase 4: Strategic Integration Tests (Weeks 8-10)

**Goal:** +5-10% coverage gain, test critical paths

- [ ] Add error recovery E2E tests
- [ ] Add workflow service func/e2e tests
- [ ] Add governance service func/e2e tests
- [ ] Add cross-service integration tests

**Deliverables:**

- New E2E tests for error recovery
- Workflow/governance integration tests
- Coverage: 75%+ ✅

---

### Phase 5: Fixture Refactoring (Weeks 11-12)

**Goal:** Improve maintainability and speed

- [ ] Remove autouse fixtures
- [ ] Simplify pytest_configure
- [ ] Replace backend_mode parametrization
- [ ] Document fixture usage patterns

**Deliverables:**

- Cleaner conftest.py files
- Opt-in fixtures
- 20-30% faster test suite
- Updated TESTING.md

---

### Phase 6: Documentation & Validation (Week 13)

**Goal:** Ensure sustainability

- [ ] Update TESTING.md with all patterns
- [ ] Add coverage checking scripts
- [ ] Update CI with per-file coverage checks
- [ ] Create test writing guide for contributors

**Deliverables:**

- Comprehensive TESTING.md
- Coverage enforcement in CI
- Contributor guide
- Team training session

---

## Part 9: Success Metrics

### Coverage Metrics

- ✅ **Combined coverage:** 75%+ (from 55.7%)
- ✅ **Per-file minimum:** 50%+ (except exemptions)
- ✅ **No 0% coverage modules** (except documented exemptions)
- ✅ **Unit test coverage:** 30%+ (maintain)
- ✅ **Func test coverage:** 30%+ (new category)
- ✅ **E2E test coverage:** 28%+ (maintain)

### Quality Metrics

- ✅ **Mock density:** <0.5 mocks per test (from 1.4)
- ✅ **All tests passing** or properly skipped
- ✅ **No xfailed tests** (fix or remove xfail markers)
- ✅ **Test execution time:** <120s for unit+func (from 171s integration)
- ✅ **Max file size:** <500 lines per test file (from 997)

### Developer Experience

- ✅ **Clear test categories:** All developers understand unit/func/e2e
- ✅ **Fast feedback:** `make test` completes in <30s
- ✅ **Easy debugging:** Can run single test without complex setup
- ✅ **Good documentation:** TESTING.md answers common questions

---

## Part 10: Risk Assessment

### Risks & Mitigations

**Risk 1: Breaking existing tests during refactoring**

- **Likelihood:** High
- **Impact:** Medium
- **Mitigation:**
  - Refactor incrementally
  - Run full suite after each change
  - Use git branches for each phase
  - Pair programming for complex refactors

**Risk 2: Slower test suite with more E2E tests**

- **Likelihood:** Medium
- **Impact:** Medium
- **Mitigation:**
  - Mark slow tests explicitly
  - Run slow tests only in CI, not locally
  - Parallelize E2E tests
  - Use fast setup/teardown

**Risk 3: Coverage doesn't improve despite effort**

- **Likelihood:** Low
- **Impact:** High
- **Mitigation:**
  - Track coverage after each phase
  - Adjust strategy if not hitting targets
  - Focus on highest-impact modules first

**Risk 4: Team resistance to new patterns**

- **Likelihood:** Medium
- **Impact:** Medium
- **Mitigation:**
  - Document patterns clearly
  - Provide examples
  - Code reviews enforce new patterns
  - Training sessions

---

## Conclusion

This refactoring proposal addresses three interconnected goals:

1. **Achieve 75%+ combined coverage** (Issue #238)
   - Test or remove 0% coverage modules (+10-15%)
   - Reduce over-mocking (+5-10%)
   - Add strategic integration tests (+5-10%)

2. **Improve test quality** (01-testing-issues.md)
   - Reduce mocking from 1,889 lines to <500 lines
   - Simplify fixtures (remove autouse, reduce session scope)
   - Fix failing tests and clean up skipped tests

3. **Enhance developer experience**
   - Clear test categories (unit/func/e2e)
   - Fast feedback loop (<30s for unit+func)
   - Better documentation (TESTING.md)
   - Sustainable test patterns

The 13-week phased approach ensures we can adapt based on learnings while delivering incremental value.

**Next Steps:**

1. Review and approve this proposal
2. Create GitHub project to track progress
3. Begin Phase 1 (foundation)
4. Weekly progress reviews

---

**Document Status:** Ready for review
**Estimated Effort:** 13 weeks (1 developer)
**Expected Outcome:** 75%+ coverage, better test quality, improved DX

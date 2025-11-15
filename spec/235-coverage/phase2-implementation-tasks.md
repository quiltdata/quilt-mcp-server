# Phase 2 Implementation Tasks: Reduce Over-Mocking

**Branch**: `235-integration-test-coverage-gap`
**Goal**: Increase coverage by +2.9-3.8% through proper integration testing
**Estimated Effort**: 41-62 hours

---

## Implementation Priority Order

**Execute in this order for maximum impact:**

1. **HIGH**: error_recovery.py (+35.4% module gain)
2. **HIGH**: quilt_service.py HTTP operations (+15-20% module gain)
3. **HIGH**: quilt_service.py package operations (+10-15% module gain)
4. **MEDIUM**: workflow_service.py (+31.9% module gain)
5. **LOW**: tabulator_service.py (+8.4% module gain)

---

## Phase 2A: Code Refactoring (MUST DO FIRST)

### Task 1: Refactor quilt_service.py - get_catalog_config()

**File**: `src/quilt_mcp/services/quilt_service.py`
**Lines**: 72-134

**Current code structure**:
```python
def get_catalog_config(self, catalog_url: str) -> dict[str, Any] | None:
    # Mixed: HTTP + business logic in one function
    session = self.get_session()
    response = session.get(config_url, timeout=10)
    full_config = response.json()
    # ... 30 lines of filtering logic ...
```

**Required changes**:

1. Split into 3 separate methods:

```python
def get_catalog_config(self, catalog_url: str) -> dict[str, Any] | None:
    """Get catalog configuration - main orchestrator."""
    if not self.has_session_support():
        raise Exception("quilt3 session not available")

    try:
        session = self.get_session()
        raw_config = self._fetch_catalog_config_http(session, catalog_url)
        return self._filter_and_derive_catalog_config(raw_config)
    except Exception:
        return None

def _fetch_catalog_config_http(self, session, catalog_url: str) -> dict[str, Any]:
    """Fetch raw config from catalog (HTTP I/O only).

    This method is the integration point - tests with respx will mock HTTP.
    """
    normalized_url = catalog_url.rstrip("/")
    config_url = f"{normalized_url}/config.json"
    response = session.get(config_url, timeout=10)
    response.raise_for_status()
    return response.json()

def _filter_and_derive_catalog_config(self, raw_config: dict) -> dict[str, Any]:
    """Filter config and derive computed fields (pure logic).

    This method is unit testable with no mocking.
    """
    filtered_config: dict[str, Any] = {}

    if "region" in raw_config:
        filtered_config["region"] = raw_config["region"]

    if "apiGatewayEndpoint" in raw_config:
        filtered_config["api_gateway_endpoint"] = raw_config["apiGatewayEndpoint"]

    if "analyticsBucket" in raw_config:
        analytics_bucket = raw_config["analyticsBucket"]
        filtered_config["analytics_bucket"] = analytics_bucket

        # Derive stack prefix
        if "-analyticsbucket" in analytics_bucket.lower():
            stack_prefix = analytics_bucket.split("-analyticsbucket")[0]
            filtered_config["stack_prefix"] = stack_prefix
            filtered_config["tabulator_data_catalog"] = f"quilt-{stack_prefix}-tabulator"

    return filtered_config if filtered_config else None
```

**Verification**: All existing tests in `tests/unit/test_quilt_service.py` must still pass.

---

### Task 2: Refactor quilt_service.py - create_package_revision()

**File**: `src/quilt_mcp/services/quilt_service.py`
**Lines**: ~350-450

**Current issue**: Directly instantiates `quilt3.Package()`, making it hard to test.

**Required changes**:

Add optional `_package_factory` parameter for dependency injection:

```python
def create_package_revision(
    self,
    package_name: str,
    s3_uris: List[str],
    metadata: Optional[Dict[str, Any]] = None,
    registry: Optional[str] = None,
    message: str = "Package created via QuiltService",
    auto_organize: bool = False,
    copy: str = "all",
    _package_factory: Optional[Callable] = None,  # NEW: For testing only
) -> Dict[str, Any]:
    """Create a new package revision.

    Args:
        _package_factory: Internal testing parameter. Do not use in production.
    """
    # Use injected factory for testing, otherwise use real Package
    if _package_factory is None:
        import quilt3
        _package_factory = quilt3.Package

    package = _package_factory()

    # ... rest of implementation unchanged ...
```

**Alternative approach** (if you prefer not to add parameter):

Extract package creation to a separate method:

```python
def _create_package_instance(self) -> Any:
    """Create a new Package instance (integration point for testing)."""
    import quilt3
    return quilt3.Package()

def create_package_revision(self, ...):
    package = self._create_package_instance()
    # ... rest of implementation ...
```

**Verification**: All tests must still pass.

---

### Task 3: Refactor tabulator_service.py - create_table()

**File**: `src/quilt_mcp/services/tabulator_service.py`
**Lines**: ~36-100

**Required changes**:

Split validation, normalization, and API calls:

```python
def create_table(
    self,
    bucket_name: str,
    table_name: str,
    schema: List[Dict],
    package_pattern: str,
    logical_key_pattern: str,
    parser_config: Dict,
    description: str = "",
) -> Dict:
    """Create table - orchestration."""
    # Step 1: Validation (unit testable)
    validation_errors = self._validate_table_config(
        bucket_name, table_name, schema, package_pattern, logical_key_pattern
    )
    if validation_errors:
        return {"success": False, "error_details": validation_errors}

    # Step 2: Normalization (unit testable)
    normalized_parser = self._normalize_parser_config(parser_config)

    # Step 3: YAML generation (unit testable)
    yaml_config = self._generate_table_yaml(
        schema, package_pattern, logical_key_pattern,
        normalized_parser, description
    )

    # Step 4: Admin API call (integration testable)
    return self._create_table_via_admin(bucket_name, table_name, yaml_config, normalized_parser)

def _validate_table_config(
    self, bucket_name: str, table_name: str, schema: List[Dict],
    package_pattern: str, logical_key_pattern: str
) -> List[str]:
    """Validate table configuration (pure logic)."""
    errors = []
    if not bucket_name:
        errors.append("Bucket name cannot be empty")
    if not table_name:
        errors.append("Table name cannot be empty")
    if not schema:
        errors.append("Schema cannot be empty")
    if not package_pattern:
        errors.append("Package pattern cannot be empty")
    if not logical_key_pattern:
        errors.append("Logical key pattern cannot be empty")
    return errors

def _normalize_parser_config(self, parser_config: Dict) -> Dict:
    """Normalize parser config (pure logic)."""
    config = parser_config.copy()
    config["format"] = config.get("format", "csv").lower()
    if config["format"] == "csv" and "delimiter" not in config:
        config["delimiter"] = ","
    return config

def _generate_table_yaml(
    self, schema: List[Dict], package_pattern: str,
    logical_key_pattern: str, parser_config: Dict, description: str
) -> str:
    """Generate YAML config (pure logic)."""
    # ... YAML generation logic ...
    return yaml_string

def _create_table_via_admin(
    self, bucket_name: str, table_name: str,
    yaml_config: str, normalized_parser: Dict
) -> Dict:
    """Create table via admin API (integration point)."""
    try:
        admin = self.get_tabulator_admin()
        admin.set_table(bucket=bucket_name, name=table_name, config=yaml_config)
        return {
            "success": True,
            "bucket": bucket_name,
            "table_name": table_name,
            "parser_config": normalized_parser,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**Verification**: Existing tabulator tests must pass.

---

## Phase 2B: Test Infrastructure Setup

### Task 4: Add Dependencies

**File**: `pyproject.toml`

Add to `[project.optional-dependencies]` under `dev`:

```toml
[project.optional-dependencies]
dev = [
    # ... existing dependencies ...
    "respx>=0.21.1",      # HTTP mocking for integration tests
    "freezegun>=1.5.1",   # Time travel for testing
]
```

Run:
```bash
uv sync
```

---

### Task 5: Create Test Fixtures Directory

Create directories:
```bash
mkdir -p tests/fixtures/catalog_configs
mkdir -p tests/fixtures/s3_objects
mkdir -p tests/fixtures/athena_responses
```

Create sample config files:

**File**: `tests/fixtures/catalog_configs/nightly_config.json`
```json
{
  "region": "us-east-1",
  "apiGatewayEndpoint": "https://0xrvxq2hb8.execute-api.us-east-1.amazonaws.com/prod",
  "analyticsBucket": "quilt-staging-analyticsbucket-10ort3e91tnoa",
  "alwaysRequiresAuth": true,
  "sentryDSN": "https://sentry.io/123",
  "mixpanelToken": "token123",
  "serviceBucket": "service-bucket",
  "registryUrl": "https://registry.example.com"
}
```

**File**: `tests/fixtures/catalog_configs/minimal_config.json`
```json
{
  "region": "us-west-2",
  "apiGatewayEndpoint": "https://api.example.com",
  "analyticsBucket": "test-analyticsbucket-xyz"
}
```

**File**: `tests/fixtures/catalog_configs/invalid_config.json`
```json
{
  "not": "valid",
  "missing": "required_fields"
}
```

---

### Task 6: Add Integration Test Fixtures

**File**: `tests/integration/conftest.py`

Add these fixtures:

```python
import pytest
import respx
import httpx
from pathlib import Path

@pytest.fixture
def catalog_config_fixtures():
    """Load catalog config fixtures."""
    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "catalog_configs"
    return {
        "nightly": fixtures_dir / "nightly_config.json",
        "minimal": fixtures_dir / "minimal_config.json",
        "invalid": fixtures_dir / "invalid_config.json",
    }

@pytest.fixture
def mock_catalog_http(catalog_config_fixtures):
    """Mock catalog HTTP endpoints using respx."""
    import json

    with respx.mock:
        # Mock successful response
        with open(catalog_config_fixtures["nightly"]) as f:
            nightly_data = json.load(f)

        respx.get("https://test-catalog.quiltdata.com/config.json").mock(
            return_value=httpx.Response(200, json=nightly_data)
        )

        # Mock 404 response
        respx.get("https://notfound-catalog.quiltdata.com/config.json").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        # Mock timeout
        respx.get("https://timeout-catalog.quiltdata.com/config.json").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        yield

@pytest.fixture
def quilt_service():
    """Create QuiltService instance for testing."""
    from quilt_mcp.services.quilt_service import QuiltService
    return QuiltService()
```

---

## Phase 2C: Write Integration Tests

### Task 7: Create test_quilt_service_http_integration.py

**File**: `tests/integration/test_quilt_service_http_integration.py`

```python
"""Integration tests for QuiltService HTTP operations."""

import pytest
import httpx
import respx
from quilt_mcp.services.quilt_service import QuiltService


@pytest.mark.integration
def test_get_catalog_config_success_integration(mock_catalog_http, quilt_service):
    """Test catalog config fetching with real HTTP client."""
    # Mock session support
    with unittest.mock.patch.object(quilt_service, 'has_session_support', return_value=True):
        with unittest.mock.patch.object(quilt_service, 'get_session') as mock_session:
            import requests
            mock_session.return_value = requests.Session()

            # This should use REAL httpx/requests but mocked endpoints
            result = quilt_service.get_catalog_config('https://test-catalog.quiltdata.com')

            assert result is not None
            assert result["region"] == "us-east-1"
            assert result["stack_prefix"] == "quilt-staging"
            assert result["tabulator_data_catalog"] == "quilt-quilt-staging-tabulator"
            # Verify filtered out sensitive data
            assert "sentryDSN" not in result
            assert "mixpanelToken" not in result


@pytest.mark.integration
def test_get_catalog_config_http_404(mock_catalog_http, quilt_service):
    """Test HTTP 404 handling."""
    with unittest.mock.patch.object(quilt_service, 'has_session_support', return_value=True):
        with unittest.mock.patch.object(quilt_service, 'get_session') as mock_session:
            import requests
            mock_session.return_value = requests.Session()

            result = quilt_service.get_catalog_config('https://notfound-catalog.quiltdata.com')
            assert result is None


@pytest.mark.integration
def test_get_catalog_config_timeout(mock_catalog_http, quilt_service):
    """Test HTTP timeout handling."""
    with unittest.mock.patch.object(quilt_service, 'has_session_support', return_value=True):
        with unittest.mock.patch.object(quilt_service, 'get_session') as mock_session:
            import requests
            mock_session.return_value = requests.Session()

            result = quilt_service.get_catalog_config('https://timeout-catalog.quiltdata.com')
            assert result is None


@pytest.mark.integration
def test_get_catalog_config_invalid_json(quilt_service):
    """Test invalid JSON response handling."""
    with respx.mock:
        respx.get("https://invalid-catalog.com/config.json").mock(
            return_value=httpx.Response(200, text="not json at all")
        )

        with unittest.mock.patch.object(quilt_service, 'has_session_support', return_value=True):
            with unittest.mock.patch.object(quilt_service, 'get_session') as mock_session:
                import requests
                mock_session.return_value = requests.Session()

                result = quilt_service.get_catalog_config('https://invalid-catalog.com')
                assert result is None
```

---

### Task 8: Create test_error_recovery_integration.py

**File**: `tests/integration/test_error_recovery_integration.py`

```python
"""Integration tests for error recovery module."""

import pytest
import time
from unittest.mock import Mock, patch
from quilt_mcp.tools import error_recovery


@pytest.mark.integration
def test_retry_with_real_failures():
    """Test retry logic with actual failures and recovery."""
    attempt_count = 0

    def failing_function():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise Exception(f"Attempt {attempt_count} failed")
        return "success"

    # Test that function retries and eventually succeeds
    result = error_recovery.with_retry(
        failing_function,
        max_retries=5,
        retry_delay=0.1
    )

    assert result == "success"
    assert attempt_count == 3


@pytest.mark.integration
def test_retry_exhaustion():
    """Test retry logic when max retries exceeded."""
    attempt_count = 0

    def always_failing():
        nonlocal attempt_count
        attempt_count += 1
        raise Exception("Always fails")

    with pytest.raises(Exception, match="Always fails"):
        error_recovery.with_retry(
            always_failing,
            max_retries=3,
            retry_delay=0.05
        )

    assert attempt_count == 4  # Initial + 3 retries


@pytest.mark.integration
def test_timeout_handling_integration():
    """Test timeout enforcement with real timing."""
    import time

    def slow_function():
        time.sleep(2)
        return "too slow"

    with pytest.raises(TimeoutError):
        error_recovery.with_timeout(
            slow_function,
            timeout_seconds=0.5
        )


# Add 5-10 more integration tests covering:
# - Exponential backoff
# - Circuit breaker pattern
# - Error categorization (retryable vs non-retryable)
# - Timeout with retry combination
# - Partial success scenarios
```

**Note**: Add similar comprehensive tests covering the 127 lines of error_recovery.py that currently have 0% integration coverage.

---

### Task 9: Create test_workflow_service_integration.py

**File**: `tests/integration/test_workflow_service_integration.py`

```python
"""Integration tests for workflow service."""

import pytest
from quilt_mcp.services.workflow_service import WorkflowService


@pytest.mark.integration
def test_workflow_execution_integration():
    """Test complete workflow execution with real state management."""
    service = WorkflowService()

    # Create workflow with actual validation
    workflow_id = service.create_workflow(
        name="test-workflow",
        steps=[
            {"action": "validate", "params": {}},
            {"action": "transform", "params": {}},
            {"action": "publish", "params": {}},
        ]
    )

    assert workflow_id is not None

    # Execute workflow with real state transitions
    result = service.execute_workflow(workflow_id)

    assert result["status"] == "completed"
    assert result["workflow_id"] == workflow_id


@pytest.mark.integration
def test_workflow_failure_recovery():
    """Test workflow recovery from failures."""
    service = WorkflowService()

    # Create workflow with failing step
    workflow_id = service.create_workflow(
        name="failing-workflow",
        steps=[
            {"action": "validate", "params": {}},
            {"action": "fail", "params": {}},  # This will fail
            {"action": "cleanup", "params": {}},
        ]
    )

    result = service.execute_workflow(workflow_id)

    assert result["status"] == "failed"
    assert "error" in result
    # Verify cleanup was attempted
    assert service.get_workflow_state(workflow_id)["cleanup_attempted"]


# Add 8-10 more integration tests covering workflow state management
```

---

## Phase 2D: Refactor Unit Tests

### Task 10: Create new unit tests for pure logic

**File**: `tests/unit/test_catalog_config_logic.py` (NEW FILE)

```python
"""Unit tests for catalog config filtering logic (pure logic, no I/O)."""

import pytest
from quilt_mcp.services.quilt_service import QuiltService


def test_filter_catalog_config_extracts_essential_keys():
    """Test that config filtering extracts only essential keys."""
    service = QuiltService()

    raw_config = {
        "region": "us-east-1",
        "apiGatewayEndpoint": "https://api.example.com",
        "analyticsBucket": "quilt-staging-analyticsbucket-abc",
        "sentryDSN": "https://sentry.io/123",  # Should be filtered
        "mixpanelToken": "secret",  # Should be filtered
        "serviceBucket": "service",  # Should be filtered
    }

    filtered = service._filter_and_derive_catalog_config(raw_config)

    assert filtered["region"] == "us-east-1"
    assert filtered["api_gateway_endpoint"] == "https://api.example.com"
    assert filtered["analytics_bucket"] == "quilt-staging-analyticsbucket-abc"
    assert filtered["stack_prefix"] == "quilt-staging"
    assert filtered["tabulator_data_catalog"] == "quilt-quilt-staging-tabulator"

    # Verify sensitive data filtered out
    assert "sentryDSN" not in filtered
    assert "mixpanelToken" not in filtered
    assert "serviceBucket" not in filtered


def test_stack_prefix_derivation_patterns():
    """Test stack prefix derivation from various bucket name patterns."""
    service = QuiltService()

    test_cases = [
        ("quilt-staging-analyticsbucket-xyz", "quilt-staging"),
        ("prod-analyticsbucket-abc", "prod"),
        ("dev-test-analyticsbucket-123", "dev-test"),
        ("my-stack-analyticsbucket-foo", "my-stack"),
    ]

    for bucket_name, expected_prefix in test_cases:
        config = {"analyticsBucket": bucket_name}
        result = service._filter_and_derive_catalog_config(config)
        assert result["stack_prefix"] == expected_prefix


def test_tabulator_catalog_name_derivation():
    """Test tabulator catalog name derivation."""
    service = QuiltService()

    test_cases = [
        ("quilt-staging", "quilt-quilt-staging-tabulator"),
        ("prod", "quilt-prod-tabulator"),
        ("dev-test", "quilt-dev-test-tabulator"),
    ]

    for stack_prefix, expected_catalog in test_cases:
        config = {"analyticsBucket": f"{stack_prefix}-analyticsbucket-xyz"}
        result = service._filter_and_derive_catalog_config(config)
        assert result["tabulator_data_catalog"] == expected_catalog


def test_filter_catalog_config_handles_missing_fields():
    """Test filtering handles missing optional fields gracefully."""
    service = QuiltService()

    minimal_config = {
        "region": "us-west-2",
    }

    result = service._filter_and_derive_catalog_config(minimal_config)

    assert result["region"] == "us-west-2"
    assert "api_gateway_endpoint" not in result
    assert "stack_prefix" not in result


def test_filter_catalog_config_empty_input():
    """Test filtering returns None for empty config."""
    service = QuiltService()

    result = service._filter_and_derive_catalog_config({})

    assert result is None
```

---

### Task 11: Update test_quilt_service.py - Remove Over-Mocked Tests

**File**: `tests/unit/test_quilt_service.py`

**Actions**:

1. **Keep these tests** (pure logic, already good):
   - `test_is_authenticated_when_not_logged_in`
   - `test_is_authenticated_when_logged_in`
   - `test_has_session_support_*`
   - All admin module availability tests

2. **Delete these tests** (only verify mock interactions):
   ```python
   # DELETE - Lines 238-254
   def test_browse_package_without_hash(self):
       # Only verifies Package.browse was called
       pass

   # DELETE - Lines 247-254
   def test_browse_package_with_hash(self):
       # Only verifies Package.browse was called
       pass

   # DELETE - Lines 256-263
   def test_create_bucket_returns_bucket_instance(self):
       # Only verifies Bucket() was called
       pass

   # DELETE - Lines 265-271
   def test_get_search_api_returns_search_module(self):
       # Only verifies import exists
       pass
   ```

3. **Simplify this test** (Lines 68-144):
   ```python
   # BEFORE: 77 lines with heavy mocking
   def test_get_catalog_config_filters_and_derives_stack_prefix(self):
       # ... 77 lines of mock setup ...

   # AFTER: Delete this test - replaced by:
   # - tests/unit/test_catalog_config_logic.py (pure logic)
   # - tests/integration/test_quilt_service_http_integration.py (HTTP)
   ```

4. **Simplify package tests** (Lines 338-602):
   ```python
   # BEFORE: 9 tests with heavy Package mocking

   # AFTER: Keep only 2-3 tests for parameter validation:
   def test_create_package_revision_validates_package_name(self):
       """Test package name validation (pure logic)."""
       service = QuiltService()

       with pytest.raises(ValueError, match="package_name"):
           service.create_package_revision(
               package_name="",  # Invalid
               s3_uris=["s3://bucket/file.txt"]
           )

   # Delete the rest - replace with integration tests
   ```

**Expected outcome**: Reduce test_quilt_service.py from 741 lines to ~400 lines.

---

### Task 12: Create unit tests for tabulator validation

**File**: `tests/unit/test_tabulator_validation.py` (NEW FILE)

```python
"""Unit tests for tabulator validation logic (pure logic)."""

import pytest
from quilt_mcp.services.tabulator_service import TabulatorService


def test_validate_table_config_catches_empty_bucket():
    """Test validation catches empty bucket name."""
    service = TabulatorService()

    errors = service._validate_table_config(
        bucket_name="",
        table_name="valid-table",
        schema=[{"name": "col1", "type": "STRING"}],
        package_pattern=r".*",
        logical_key_pattern=r".*"
    )

    assert len(errors) == 1
    assert "Bucket name cannot be empty" in errors[0]


def test_validate_table_config_multiple_errors():
    """Test validation catches multiple errors."""
    service = TabulatorService()

    errors = service._validate_table_config(
        bucket_name="",
        table_name="",
        schema=[],
        package_pattern="",
        logical_key_pattern=""
    )

    assert len(errors) == 5


def test_normalize_parser_config_csv():
    """Test parser config normalization for CSV."""
    service = TabulatorService()

    config = {"format": "CSV"}  # Uppercase
    normalized = service._normalize_parser_config(config)

    assert normalized["format"] == "csv"  # Lowercase
    assert normalized["delimiter"] == ","  # Default added


def test_normalize_parser_config_preserves_delimiter():
    """Test normalization preserves existing delimiter."""
    service = TabulatorService()

    config = {"format": "csv", "delimiter": "\t"}
    normalized = service._normalize_parser_config(config)

    assert normalized["delimiter"] == "\t"  # Not overwritten


def test_normalize_parser_config_json():
    """Test JSON format normalization."""
    service = TabulatorService()

    config = {"format": "JSON"}
    normalized = service._normalize_parser_config(config)

    assert normalized["format"] == "json"
    assert "delimiter" not in normalized  # No delimiter for JSON
```

---

## Phase 2E: Verification

### Task 13: Run Coverage Analysis

Run these commands:

```bash
# Run all tests with coverage
make test-all-coverage

# Check specific module coverage
pytest tests/unit/test_quilt_service.py --cov=quilt_mcp.services.quilt_service --cov-report=term-missing
pytest tests/integration/ --cov=quilt_mcp.services --cov-report=term-missing

# Generate updated coverage CSV
python scripts/coverage_analyzer.py
```

**Verification checklist**:
- [ ] Overall coverage increased by 2.9-3.8%
- [ ] quilt_service.py integration coverage increased from 21.5% to 40%+
- [ ] error_recovery.py integration coverage increased from 0% to 40%+
- [ ] No decrease in existing coverage
- [ ] All tests pass (unit + integration + e2e)

---

### Task 14: Clean Up and Documentation

1. **Update test README**:

   **File**: `tests/README.md`

   Add section:
   ```markdown
   ## Testing Philosophy

   ### Unit Tests
   - Test **pure logic** only
   - No I/O operations
   - No mocking of internal code
   - Fast (<1ms per test)
   - Located in `tests/unit/`

   ### Integration Tests
   - Test **component interaction**
   - Mock only external services (HTTP endpoints, AWS)
   - Use moto for AWS services
   - Use respx for HTTP mocking
   - Slower (<100ms per test)
   - Located in `tests/integration/`

   ### What to Mock vs Not Mock

   ✅ **DO Mock**:
   - HTTP endpoints (use respx)
   - AWS services (use moto)
   - External APIs

   ❌ **DON'T Mock**:
   - Internal application code
   - Business logic functions
   - Database/file operations within app
   - Session management
   ```

2. **Remove dead code**:
   - Delete unused mock classes
   - Remove commented-out test code
   - Clean up imports

3. **Commit changes**:
   ```bash
   git add -A
   git commit -m "feat: Refactor tests to reduce over-mocking (#238)

   - Split HTTP and logic layers in quilt_service.py
   - Add integration tests for HTTP operations (respx)
   - Add integration tests for error recovery
   - Add integration tests for workflow service
   - Convert over-mocked unit tests to pure logic tests
   - Remove tests that only verify mock interactions

   Coverage impact: +2.9-3.8% overall
   - quilt_service.py: 83.3% → 91.9% (+8.6%)
   - error_recovery.py: 59.9% → 95.3% (+35.4%)
   - workflow_service.py: 66.5% → 98.4% (+31.9%)

   Closes #238 Phase 2"
   ```

---

## Success Criteria Checklist

After completing all tasks, verify:

- [ ] **Code Changes**:
  - [ ] quilt_service.py refactored (HTTP separated from logic)
  - [ ] tabulator_service.py refactored (validation extracted)
  - [ ] All existing tests still pass after refactoring

- [ ] **Infrastructure**:
  - [ ] respx and freezegun installed
  - [ ] Fixture directories created
  - [ ] Sample config files added
  - [ ] Integration fixtures in conftest.py

- [ ] **New Tests**:
  - [ ] test_quilt_service_http_integration.py created (5+ tests)
  - [ ] test_error_recovery_integration.py created (10+ tests)
  - [ ] test_workflow_service_integration.py created (8+ tests)
  - [ ] test_catalog_config_logic.py created (8+ tests)
  - [ ] test_tabulator_validation.py created (6+ tests)

- [ ] **Test Cleanup**:
  - [ ] Deleted 5+ redundant mock-only tests
  - [ ] Simplified 9 package creation tests
  - [ ] Removed over-mocked HTTP tests

- [ ] **Coverage Goals**:
  - [ ] Overall coverage: 55.7% → 58.6%+ (+2.9-3.8%)
  - [ ] quilt_service.py: 83.3% → 91%+ (+8%+)
  - [ ] error_recovery.py: 59.9% → 85%+ (+25%+)
  - [ ] Test suite runs in <150 seconds

- [ ] **Documentation**:
  - [ ] tests/README.md updated with philosophy
  - [ ] Fixture directories documented
  - [ ] Code committed with detailed message

---

## Quick Reference: File Changes Summary

| File | Action | Priority |
|------|--------|----------|
| `src/quilt_mcp/services/quilt_service.py` | Refactor: Split get_catalog_config | HIGH |
| `src/quilt_mcp/services/quilt_service.py` | Refactor: Add DI to create_package_revision | HIGH |
| `src/quilt_mcp/services/tabulator_service.py` | Refactor: Extract validation | MEDIUM |
| `pyproject.toml` | Add respx, freezegun | HIGH |
| `tests/fixtures/catalog_configs/*.json` | Create 3 fixture files | HIGH |
| `tests/integration/conftest.py` | Add HTTP fixtures | HIGH |
| `tests/integration/test_quilt_service_http_integration.py` | Create new file | HIGH |
| `tests/integration/test_error_recovery_integration.py` | Create new file | HIGH |
| `tests/integration/test_workflow_service_integration.py` | Create new file | MEDIUM |
| `tests/unit/test_catalog_config_logic.py` | Create new file | HIGH |
| `tests/unit/test_tabulator_validation.py` | Create new file | MEDIUM |
| `tests/unit/test_quilt_service.py` | Delete 200+ lines | HIGH |
| `tests/README.md` | Document philosophy | MEDIUM |

**Total Files**: 4 refactored, 7 created, 1 modified, 1 updated

---

## Estimated Timeline

**Full-time (8 hours/day)**:
- Day 1: Tasks 1-3 (Refactoring)
- Day 2: Tasks 4-6 (Infrastructure)
- Day 3-4: Tasks 7-9 (Integration tests)
- Day 5: Tasks 10-12 (Unit test cleanup)
- Day 6: Tasks 13-14 (Verification)

**Part-time (4 hours/day)**:
- Weeks 1-2: Complete all tasks
- Week 2-3: Verification and cleanup

**Expected Outcome**: +2.9-3.8% overall coverage with meaningful integration tests that verify behavior rather than mock interactions.

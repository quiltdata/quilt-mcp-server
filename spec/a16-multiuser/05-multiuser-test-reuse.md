# Platform Backend Testing via Dependency Injection

## TL;DR

**YES - We can reuse ~90% of existing integration tests by setting `QUILT_MULTIUSER_MODE=true` or calling `set_test_mode_config(multiuser_mode=True)`.** The test suite is already backend-agnostic via the factory pattern.

## Architecture Enables Test Reuse

### How Backend Selection Works

Integration tests → Tool functions → **QuiltOpsFactory** → Backend (quilt3 or platform)

```python
# src/quilt_mcp/ops/factory.py:38-62
class QuiltOpsFactory:
    @staticmethod
    def create() -> QuiltOps:
        mode_config = get_mode_config()

        if mode_config.backend_type == "quilt3":
            return Quilt3_Backend()
        elif mode_config.backend_type == "graphql":
            return Platform_Backend()
```

**Key insight:** Backend selection is controlled by `ModeConfig.backend_type`, which reads `QUILT_MULTIUSER_MODE` env var.

### Test Configuration Hook

[src/quilt_mcp/config.py:175-182](../../src/quilt_mcp/config.py#L175-L182) provides test-specific override:

```python
def set_test_mode_config(multiuser_mode: bool) -> None:
    """Set a test ModeConfig instance as the singleton (used in tests)."""
    global _mode_config_instance
    _mode_config_instance = ModeConfig(multiuser_mode=multiuser_mode)
```

**This already exists!** We just need to use it.

## Test Reuse Analysis

### Backend-Agnostic Tests (Can Reuse Immediately)

**Package operations:** [tests/integration/test_packages_integration.py](../../tests/integration/test_packages_integration.py)
```python
# No quilt3 imports, only tool functions
from quilt_mcp.tools.packages import package_create, package_browse, package_delete

def test_package_create_update_delete_workflow(test_bucket, test_registry):
    create_result = package_create(
        package_name=pkg_name,
        s3_uris=[test_s3_uri],
        registry=test_registry,
    )
    assert isinstance(create_result, PackageCreateSuccess)
```

**Verdict:** ✅ **100% reusable** - just set multiuser mode

**Bucket operations:** [tests/integration/test_bucket_tools.py](../../tests/integration/test_bucket_tools.py)
```python
from quilt_mcp.tools.buckets import bucket_object_info, bucket_object_text

def test_bucket_object_info_known_file(test_registry):
    result = bucket_object_info(s3_uri=test_uri)
    assert hasattr(result, "object")
```

**Verdict:** ✅ **100% reusable**

**Auth/catalog:** [tests/integration/test_integration.py](../../tests/integration/test_integration.py)
```python
from quilt_mcp.tools.catalog import catalog_url
from quilt_mcp.services.auth_metadata import auth_status

def test_auth_status_returns_status():
    result = auth_status()
    assert result["status"] in ["authenticated", "not_authenticated"]
```

**Verdict:** ✅ **100% reusable**

### Backend-Specific Tests (Need Adaptation)

**Quilt3 session:** [tests/integration/test_quilt3_authentication.py](../../tests/integration/test_quilt3_authentication.py)
```python
from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

def test_quilt3_backend_can_get_auth_status():
    backend = Quilt3_Backend()
    status = backend.get_auth_status()
```

**Verdict:** ❌ Quilt3-specific, create platform equivalent

**Elasticsearch:** [tests/integration/test_elasticsearch_index_discovery.py](../../tests/integration/test_elasticsearch_index_discovery.py)
```python
backend = Quilt3ElasticsearchBackend(backend=quilt3_backend)
```

**Verdict:** ❌ Quilt3-specific wrapper, platform uses GraphQL search

**Summary:**
- **18/20 integration test files** (90%) are backend-agnostic
- **2/20 files** (10%) are quilt3-specific

## Implementation Strategy

### Phase 1: Parametrize Existing Tests (Week 1)

Add pytest parametrization to run same tests twice:

```python
# tests/conftest.py
@pytest.fixture(params=["quilt3", "platform"])
def backend_mode(request, monkeypatch):
    """Parametrize tests to run against both backends."""
    mode = request.param

    if mode == "platform":
        # Set environment for platform backend
        monkeypatch.setenv("QUILT_MULTIUSER_MODE", "true")
        monkeypatch.setenv("QUILT_CATALOG_URL", "https://example.quiltdata.com")
        monkeypatch.setenv("QUILT_REGISTRY_URL", "https://registry.example.com")
        # Inject test JWT token
        from quilt_mcp.runtime_context import push_runtime_context, RuntimeAuthState
        push_runtime_context(auth=RuntimeAuthState(
            scheme="Bearer",
            access_token=_generate_test_jwt(),
            claims={"id": "test-user", "exp": 9999999999}
        ))

    set_test_mode_config(multiuser_mode=(mode == "platform"))
    yield mode
    reset_mode_config()
```

Then mark backend-agnostic tests:

```python
@pytest.mark.integration
@pytest.mark.usefixtures("backend_mode")  # Runs twice: quilt3 + platform
def test_package_create_update_delete_workflow(test_bucket, test_registry):
    # Same test code, runs against both backends
    create_result = package_create(...)
```

**Result:** All 18 backend-agnostic test files run against platform backend automatically.

### Phase 2: Add Platform-Specific Integration Tests (Week 2)

Create new tests for platform-only features:

```python
# tests/integration/test_platform_graphql_integration.py
@pytest.mark.integration
@pytest.mark.platform  # New marker
def test_platform_graphql_package_search(platform_backend_mode):
    """Test GraphQL package search returns valid results."""
    from quilt_mcp.tools.packages import packages_search

    result = packages_search(query="test", registry=test_registry)
    assert isinstance(result, PackageSearchSuccess)
    assert len(result.packages) > 0
```

### Phase 3: Mock vs Live (Week 3)

Add fixture for controlled testing:

```python
@pytest.fixture
def platform_backend_mode(request):
    """Platform backend with optional HTTP mocking."""
    mock_responses = request.param if hasattr(request, 'param') else False

    if mock_responses:
        # Use responses library to mock GraphQL
        import responses
        responses.add(responses.POST,
                     "https://registry.example.com/graphql",
                     json={"data": {...}})
    else:
        # Use real catalog (requires credentials)
        if not os.getenv("PLATFORM_TEST_ENABLED"):
            pytest.skip("Platform integration tests disabled")

    set_test_mode_config(multiuser_mode=True)
    yield
```

## Minimal Changes Required

### Add to conftest.py

```python
# tests/conftest.py

def _generate_test_jwt():
    """Generate test JWT for platform backend tests."""
    import jwt
    return jwt.encode(
        {"id": "test-user", "uuid": "test-uuid", "exp": 9999999999},
        "test-secret",
        algorithm="HS256"
    )

@pytest.fixture(params=["quilt3", "platform"])
def backend_mode(request, monkeypatch):
    """Run tests against both backends."""
    mode = request.param

    if mode == "platform":
        # Platform configuration
        monkeypatch.setenv("QUILT_MULTIUSER_MODE", "true")
        monkeypatch.setenv("QUILT_CATALOG_URL", os.getenv("PLATFORM_CATALOG_URL", "https://test.quiltdata.com"))
        monkeypatch.setenv("QUILT_REGISTRY_URL", os.getenv("PLATFORM_REGISTRY_URL", "https://registry.test.com"))

        # Skip if platform testing not enabled
        if not os.getenv("PLATFORM_TEST_ENABLED"):
            pytest.skip("Platform integration tests disabled - set PLATFORM_TEST_ENABLED=true")

        # Inject JWT context
        from quilt_mcp.runtime_context import push_runtime_context, RuntimeAuthState, get_runtime_environment
        token = push_runtime_context(
            environment=get_runtime_environment(),
            auth=RuntimeAuthState(
                scheme="Bearer",
                access_token=_generate_test_jwt(),
                claims={"id": "test-user", "uuid": "test-uuid", "exp": 9999999999}
            )
        )
        request.addfinalizer(lambda: reset_runtime_context(token))

    set_test_mode_config(multiuser_mode=(mode == "platform"))
    yield mode
    reset_mode_config()
```

### Mark Backend-Agnostic Tests

Add one line to 18 test files:

```python
# tests/integration/test_packages_integration.py

@pytest.mark.integration
@pytest.mark.usefixtures("backend_mode")  # ← Add this line
def test_package_create_update_delete_workflow(...):
    # Existing test code unchanged
```

### Update make.dev

**CRITICAL FIX:** Enable platform tests in default integration target:

```makefile
# In test-integration target, add PLATFORM_TEST_ENABLED=true
$(RESULTS_DIR)/coverage-integration.xml: tests/integration/test_*.py | $(RESULTS_DIR)
    @echo "Running integration tests (AWS/external services)..."
    @uv sync --group test
    @if [ -d "tests/integration" ] && \
       [ "$$(find tests/integration -name "*.py" | wc -l)" -gt 0 ]; then \
        export PYTHONPATH="src" && \
        export PLATFORM_TEST_ENABLED=true && \
        uv run python -m pytest tests/integration/ -v \
            -m "not search and not admin" \
            --cov=quilt_mcp \
            --cov-report=xml:$(RESULTS_DIR)/coverage-integration.xml \
            --cov-report=term-missing; \
```

Without this, all `[platform]` parameterized tests skip. The `backend_mode` fixture
checks this env var at [conftest.py:248-250](../../tests/conftest.py#L248-L250).

**Keep separate platform-only target** for running just platform backend:

```makefile
# Add platform integration test target (platform only, no quilt3)
test-platform-integration:
    @echo "Running platform backend integration tests..."
    @export PLATFORM_TEST_ENABLED=true && \
     export PLATFORM_CATALOG_URL=https://test.quiltdata.com && \
     export QUILT_MULTIUSER_MODE=true && \
     uv run pytest tests/integration/ -v -k platform
```

## Comparison to Original Plan

| Approach | Effort | Coverage | Maintenance |
|----------|--------|----------|-------------|
| **Original (new tests)** | 3 weeks | Platform only | Duplicate code |
| **Dependency injection** | 1 week + marks | Both backends | Single codebase |

**Dependency injection wins:**
- ✅ Tests both backends with same code
- ✅ Catches backend parity issues
- ✅ No code duplication
- ✅ Existing tests become regression suite

## What About Unit Tests?

**Keep existing mocked unit tests.** They serve different purpose:

- **Unit tests (mocked):** Test backend implementation details, GraphQL query structure, error handling
- **Integration tests (parametrized):** Test backend behavior matches expectations

Example:
```python
# Unit test - platform-specific mocking
def test_platform_backend_graphql_query_structure(monkeypatch):
    """Verify GraphQL query has correct structure."""
    captured_query = None
    def mock_post(url, json, headers):
        nonlocal captured_query
        captured_query = json
    monkeypatch.setattr(requests, "post", mock_post)

    backend = Platform_Backend()
    backend.list_packages()

    assert "query" in captured_query
    assert "packages" in captured_query["query"]

# Integration test - backend-agnostic (via dependency injection)
@pytest.mark.usefixtures("backend_mode")
def test_list_packages_returns_results(test_registry):
    """Verify list_packages returns valid package list."""
    result = packages_list(registry=test_registry)
    assert result.success
    assert isinstance(result.packages, list)
```

## Next Steps

1. **Add `backend_mode` fixture to conftest.py** (30 min)
2. **Mark 18 backend-agnostic tests** with `@pytest.mark.usefixtures("backend_mode")` (1 hour)
3. **Set up test JWT generation** (30 min)
4. **Run integration tests with `PLATFORM_TEST_ENABLED=true`** (ongoing)
5. **Document platform test setup** in `docs/TESTING_PLATFORM.md` (1 hour)

**Total effort: ~1 day** to enable platform integration testing vs. **3 weeks** to write new tests.

## Success Metrics

After implementation:
```bash
# Run all tests against both backends
PLATFORM_TEST_ENABLED=true make test-integration

# Output shows:
# tests/integration/test_packages_integration.py::test_create[quilt3] PASSED
# tests/integration/test_packages_integration.py::test_create[platform] PASSED
# tests/integration/test_bucket_tools.py::test_info[quilt3] PASSED
# tests/integration/test_bucket_tools.py::test_info[platform] PASSED
# ...
# 271 tests × 2 backends = 542 test runs
```

Platform backend gets **live integration coverage** without writing new tests.

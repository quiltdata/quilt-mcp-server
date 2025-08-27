# Test Improvements: Enable Skipped Tests

## 🔍 Current Situation

**89 AWS tests** and **search tests** are being skipped in CI, reducing test coverage significantly.

### Skipped Test Categories:
1. **AWS Integration Tests** (89 tests) - `@pytest.mark.aws`
2. **Search Tests** - `@pytest.mark.search` 
3. **Async Tests** - Missing proper asyncio configuration

## 🚀 Proposed Solutions

### 1. **Fix Async Test Configuration**
```toml
# pyproject.toml - Add missing asyncio marker
[tool.pytest.ini_options]
markers = [
    "aws: marks tests that require AWS credentials and network access",
    "search: marks tests that require search functionality", 
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "performance: marks tests as performance benchmarks",
    "integration: marks tests as integration tests",
    "error_handling: marks tests as error handling tests",
    "asyncio: marks tests as async tests",  # ADD THIS
]
```

### 2. **Enable AWS Tests in CI with Mock Fallback**
```yaml
# .github/workflows/test.yml
- name: Run unit tests with AWS mocks
  run: make test-ci-with-aws-mocks
  env:
    # Provide mock AWS credentials for tests that check for their presence
    AWS_ACCESS_KEY_ID: "mock-access-key"
    AWS_SECRET_ACCESS_KEY: "mock-secret-key"
    AWS_DEFAULT_REGION: "us-east-1"
    # Flag to indicate this is CI with mocks
    CI_MOCK_MODE: "true"
```

### 3. **Create Smart Test Categories**
```makefile
# app/Makefile - Add new test targets
test-ci-with-aws-mocks:
	@echo "Running tests with AWS mocks enabled..."
	@uv sync --group test
	@export PYTHONPATH="$(PWD)" && CI_MOCK_MODE=1 uv run python -m pytest ../tests/ -v -m "not search and not slow" --timeout=15 --disable-warnings

test-unit-only:
	@echo "Running pure unit tests (no AWS, no search, no integration)..."
	@uv sync --group test  
	@export PYTHONPATH="$(PWD)" && uv run python -m pytest ../tests/ -v -m "not aws and not search and not integration and not slow" --timeout=10 --disable-warnings
```

### 4. **Improve AWS Test Mocking**
```python
# tests/conftest.py - Add smart mocking
import pytest
import os
from unittest.mock import Mock, patch

@pytest.fixture(autouse=True)
def mock_aws_in_ci():
    """Auto-mock AWS services when running in CI mock mode."""
    if os.getenv('CI_MOCK_MODE'):
        with patch('boto3.client') as mock_client:
            # Configure mock to return realistic responses
            mock_client.return_value = Mock()
            yield mock_client
    else:
        yield None
```

### 5. **Enable Search Tests with Mock Backend**
```python
# tests/test_search_mocked.py - Create mocked search tests
@pytest.mark.search
@pytest.mark.unit
def test_search_with_mock_backend():
    """Test search functionality with mocked backend."""
    with patch('search_backend.client') as mock_search:
        mock_search.search.return_value = {"results": []}
        # Test search functionality
```

## 📊 **Expected Impact**

### Before:
- **229 tests skipped** (72% of tests!)
- **89 tests collected** (28% coverage)
- Missing AWS integration coverage
- No async test validation

### After:
- **~50 tests skipped** (15% of tests)
- **~268 tests collected** (85% coverage)  
- AWS tests run with smart mocking
- Async tests properly configured
- Search tests with mock backends

## 🎯 **Implementation Priority**

1. **High Priority** - Fix asyncio configuration (easy win)
2. **High Priority** - Enable AWS tests with mocking
3. **Medium Priority** - Create search test mocks
4. **Low Priority** - Add integration test scheduling

## 🔧 **Quick Wins**

### Fix Asyncio Warnings (5 min fix):
```toml
# Add to pyproject.toml markers
"asyncio: marks tests as async tests",
```

### Enable AWS Tests (15 min fix):
```bash
# Update CI to provide mock credentials
AWS_ACCESS_KEY_ID: "mock-key"
AWS_SECRET_ACCESS_KEY: "mock-secret"  
CI_MOCK_MODE: "true"
```

This would immediately enable **89 additional tests** in CI! 🚀

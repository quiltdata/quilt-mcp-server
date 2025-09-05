# Testing Guide

This document outlines our comprehensive testing philosophy, practices, and real-world validation approach for the Quilt MCP Server.

## 🎯 Testing Philosophy

### Core Principles

1. **Real Data First**: We test with actual Benchling and Quilt data whenever possible
2. **Cross-System Integration**: Validate federated operations across multiple systems
3. **Performance Validation**: Ensure sub-second response times for critical operations
4. **Graceful Degradation**: Test error handling and fallback mechanisms
5. **Production Readiness**: Tests must reflect real-world usage patterns

### Testing Pyramid

```
                    🔺
                   /   \
                  /  E2E \
                 /  Tests \
                /_________\
               /           \
              / Integration \
             /    Tests     \
            /_______________\
           /                 \
          /    Unit Tests     \
         /   (85%+ Coverage)  \
        /____________________\
```

**Unit Tests (Base)**: Fast, isolated tests with comprehensive coverage
**Integration Tests (Middle)**: Cross-component validation and API testing  
**End-to-End Tests (Top)**: Real-world scenarios with actual data

## 🧪 Test Categories

### 1. Unit Tests (85%+ Coverage Required)

**Location**: `tests/`  
**Purpose**: Test individual functions and classes in isolation  
**Coverage Requirement**: 85% minimum

```bash
# Run unit tests with coverage
make coverage

# View coverage report
open htmlcov/index.html
```

**Example Unit Test**:
```python
# tests/test_package_operations.py

import pytest
from unittest.mock import AsyncMock, patch
from app.quilt_mcp.tools.package import package_browse

class TestPackageBrowse:
    @pytest.mark.asyncio
    async def test_successful_browse(self):
        \"\"\"Test successful package browsing\"\"\"
        with patch('app.quilt_mcp.tools.package.quilt3.Package') as mock_pkg:
            mock_pkg.browse.return_value = {
                'file1.csv': {'size': 1024, 'type': 'file'},
                'data/': {'type': 'directory'}
            }
            
            result = await package_browse(
                package_name=\"test/package\",
                registry=\"s3://test-bucket\"
            )
            
            assert result['success'] is True
            assert 'file_tree' in result
            assert len(result['file_tree']) == 2
    
    @pytest.mark.asyncio
    async def test_package_not_found(self):
        \"\"\"Test graceful handling of missing packages\"\"\"
        with patch('app.quilt_mcp.tools.package.quilt3.Package') as mock_pkg:
            mock_pkg.browse.side_effect = FileNotFoundError(\"Package not found\")
            
            result = await package_browse(
                package_name=\"nonexistent/package\",
                registry=\"s3://test-bucket\"
            )
            
            assert result['success'] is False
            assert 'Package not found' in result['error']
            assert 'package may not exist' in result['message'].lower()
```

### 2. Integration Tests

**Location**: `tests/test_integration.py`  
**Purpose**: Test component interactions and API endpoints  
**Focus**: Cross-system communication and data flow

```bash
# Run integration tests
make test

# Run specific integration test
pytest tests/test_integration.py::TestUnifiedSearch -v
```

**Example Integration Test**:
```python
# tests/test_integration.py

class TestUnifiedSearch:
    @pytest.mark.asyncio
    async def test_cross_backend_search(self):
        \"\"\"Test search across multiple backends\"\"\"
        # Test with real configuration
        result = await unified_search(
            query=\"RNA-seq data\",
            scope=\"global\",
            backends=[\"graphql\", \"elasticsearch\", \"s3\"],
            limit=10
        )
        
        assert result['success'] is True
        assert 'results' in result
        assert len(result['backends_used']) >= 2
        
        # Validate result structure
        for item in result['results']:
            assert 'source' in item
            assert 'score' in item
            assert item['score'] >= 0.0
```

### 3. Real-World Validation Tests

**Location**: `test_cases/`  
**Purpose**: Validate with actual production data and scenarios  
**Focus**: End-to-end workflows with real Benchling and Quilt data

#### SAIL Biomedicines User Stories

**File**: `test_cases/sail_user_stories_real_test.py`  
**Purpose**: Validate dual MCP architecture with real data

```bash
# Run SAIL real data tests
python test_cases/sail_user_stories_real_test.py
```

**Test Scenarios**:
- **SB001-REAL**: Federated discovery across Benchling and Quilt
- **SB002-REAL**: Cross-system notebook summarization  
- **SB003-REAL**: Package creation from Benchling sequences
- **SB004-REAL**: Multi-system data correlation

**Example Real-World Test**:
```python
# test_cases/sail_user_stories_real_test.py

async def test_sb001_real_federated_discovery(self):
    \"\"\"Test real federated discovery across Benchling and Quilt\"\"\"
    
    # Search Benchling for RNA-seq entries
    benchling_results = await self.benchling_client.call_tool(
        \"benchling_get_entries\",
        {\"name\": \"RNA-seq\", \"limit\": 10}
    )
    
    # Search Quilt for RNA datasets  
    quilt_results = await self.quilt_client.call_tool(
        \"unified_search\",
        {\"query\": \"RNA datasets\", \"limit\": 50}
    )
    
    # Validate cross-system correlation
    assert benchling_results['success'] is True
    assert quilt_results['success'] is True
    assert len(benchling_results['entries']) > 0
    assert len(quilt_results['results']) > 0
    
    # Test data correlation
    correlation = self.correlate_results(
        benchling_results['entries'],
        quilt_results['results']
    )
    
    assert correlation['matches'] > 0
    assert correlation['confidence'] > 0.7
```

#### CCLE Computational Biology Tests

**File**: `test_cases/ccle_computational_biology_test_runner.py`  
**Purpose**: Validate genomics workflows and data processing

```bash
# Run CCLE genomics tests
python test_cases/ccle_computational_biology_test_runner.py
```

**Test Scenarios**:
- **CB001**: Genomic data package creation
- **CB002**: Cross-reference with genomic databases
- **CB003**: Athena SQL queries on genomic data
- **CB004**: Metadata template validation for genomics
- **CB005**: Large-scale genomic data processing
- **CB006**: Multi-omics data integration

### 4. Performance and Load Tests

**Location**: `test_cases/mcp_comprehensive_test_simulation.py`  
**Purpose**: Validate performance under realistic load

```bash
# Run comprehensive performance tests
python test_cases/mcp_comprehensive_test_simulation.py
```

**Performance Metrics**:
- **Response Time**: < 1 second for 90% of operations
- **Throughput**: Handle 100+ concurrent requests
- **Memory Usage**: < 512MB under normal load
- **Error Rate**: < 1% for all operations

**Example Performance Test**:
```python
# test_cases/mcp_comprehensive_test_simulation.py

async def test_concurrent_search_performance(self):
    \"\"\"Test search performance under concurrent load\"\"\"
    
    # Create 50 concurrent search requests
    tasks = []
    for i in range(50):
        task = self.client.call_tool(
            \"unified_search\",
            {\"query\": f\"test query {i}\", \"limit\": 10}
        )
        tasks.append(task)
    
    # Execute concurrently and measure time
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    end_time = time.time()
    
    # Validate performance
    total_time = end_time - start_time
    assert total_time < 5.0  # All 50 requests in < 5 seconds
    
    # Validate success rate
    successful = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
    success_rate = successful / len(results)
    assert success_rate >= 0.95  # 95%+ success rate
```

## 🔧 Testing Infrastructure

### Test Configuration

**Pytest Configuration** (`tests/conftest.py`):
```python
import pytest
import asyncio
from unittest.mock import AsyncMock

@pytest.fixture(scope=\"session\")
def event_loop():
    \"\"\"Create event loop for async tests\"\"\"
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def mcp_client():
    \"\"\"Create MCP client for testing\"\"\"
    from app.quilt_mcp.utils import create_mcp_server
    server = create_mcp_server()
    # Return configured client
    return server

@pytest.fixture
def mock_aws_credentials():
    \"\"\"Mock AWS credentials for testing\"\"\"
    with patch.dict(os.environ, {
        'AWS_ACCESS_KEY_ID': 'test-key',
        'AWS_SECRET_ACCESS_KEY': 'test-secret',
        'AWS_DEFAULT_REGION': 'us-east-1'
    }):
        yield
```

### Test Data Management

**Test Data Sources**:
- **Real Data**: Actual Benchling and Quilt data (anonymized)
- **Synthetic Data**: Generated test datasets for edge cases
- **Mock Data**: Controlled responses for unit tests

**Test Data Organization**:
```
test_cases/
├── 📄 realistic_quilt_test_cases.json    # Real-world scenarios
├── 📄 sail_biomedicines_test_cases.json  # SAIL user stories
├── 📄 ccle_computational_biology_test_cases.json # Genomics workflows
└── 📁 fixtures/                          # Test data fixtures
    ├── 📄 sample_packages.json
    ├── 📄 mock_responses.json
    └── 📄 benchling_test_data.json
```

### Continuous Integration

**GitHub Actions Workflow** (`.github/workflows/test.yml`):
```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.11, 3.12]
    
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install uv
        uv sync --group test
    
    - name: Run unit tests
      run: make coverage
    
    - name: Run integration tests  
      run: make test
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## 📊 Test Execution and Reporting

### Running Tests

```bash
# Quick test suite (unit tests only)
make test

# Full test suite with coverage
make coverage

# Integration tests
pytest tests/test_integration.py -v

# Real-world validation
python test_cases/sail_user_stories_real_test.py
python test_cases/ccle_computational_biology_test_runner.py

# Performance benchmarks
python test_cases/mcp_comprehensive_test_simulation.py

# Specific test categories
pytest tests/ -k \"test_search\" -v        # Search-related tests
pytest tests/ -k \"test_package\" -v       # Package operation tests
pytest tests/ -k \"test_athena\" -v        # Athena/SQL tests
```

### Test Results and Reporting

**Coverage Reports**:
```bash
# Generate HTML coverage report
make coverage
open htmlcov/index.html

# Generate terminal coverage report
pytest --cov=app --cov-report=term-missing
```

**Real-World Test Results**:
Test results are stored in `test_results/` with detailed JSON reports:

```json
{
  \"test_suite\": \"SAIL Biomedicines Real Data\",
  \"execution_time\": \"2024-08-27T14:18:37\",
  \"total_tests\": 4,
  \"passed\": 4,
  \"failed\": 0,
  \"success_rate\": 100.0,
  \"execution_time_ms\": 480,
  \"results\": [
    {
      \"test_id\": \"SB001-REAL\",
      \"description\": \"Real Federated Discovery\",
      \"status\": \"PASSED\",
      \"execution_time_ms\": 120,
      \"benchling_entries\": 1,
      \"quilt_results\": 89,
      \"correlation_matches\": 4
    }
  ]
}
```

## 🎯 Testing Best Practices

### Writing Effective Tests

1. **Test Behavior, Not Implementation**:
   ```python
   # Good: Test the behavior
   async def test_package_creation_success(self):
       result = await create_package(\"test/pkg\", [\"s3://bucket/file.csv\"])
       assert result['success'] is True
       assert 'package_uri' in result
   
   # Avoid: Testing implementation details
   async def test_package_creation_calls_quilt_api(self):
       with patch('quilt3.Package') as mock:
           await create_package(\"test/pkg\", [\"s3://bucket/file.csv\"])
           mock.assert_called_once()  # Too implementation-specific
   ```

2. **Use Descriptive Test Names**:
   ```python
   # Good: Describes what is being tested
   async def test_unified_search_returns_ranked_results_from_multiple_backends(self):
   
   # Avoid: Vague test names
   async def test_search(self):
   ```

3. **Test Edge Cases and Error Conditions**:
   ```python
   async def test_package_browse_handles_empty_package(self):
   async def test_search_gracefully_handles_backend_timeout(self):
   async def test_athena_query_validates_sql_injection_attempts(self):
   ```

4. **Use Realistic Test Data**:
   ```python
   # Good: Realistic data
   test_package_name = \"genomics/ccle-rnaseq-2024\"
   test_s3_uri = \"s3://quilt-example/datasets/rna_seq/sample_001.fastq.gz\"
   
   # Avoid: Unrealistic data
   test_package_name = \"test/test\"
   test_s3_uri = \"s3://test/test.txt\"
   ```

### Test Organization

1. **Group Related Tests**:
   ```python
   class TestPackageOperations:
       class TestPackageCreation:
           async def test_create_with_valid_files(self):
           async def test_create_with_invalid_files(self):
       
       class TestPackageBrowsing:
           async def test_browse_existing_package(self):
           async def test_browse_nonexistent_package(self):
   ```

2. **Use Fixtures for Common Setup**:
   ```python
   @pytest.fixture
   async def sample_package():
       # Create test package
       pkg = await create_test_package()
       yield pkg
       # Cleanup
       await cleanup_test_package(pkg)
   ```

3. **Parameterize Tests for Multiple Scenarios**:
   ```python
   @pytest.mark.parametrize(\"query,expected_backends\", [
       (\"RNA-seq\", [\"graphql\", \"elasticsearch\"]),
       (\"*.csv\", [\"s3\", \"elasticsearch\"]),
       (\"genomics AND human\", [\"graphql\", \"elasticsearch\"])
   ])
   async def test_search_backend_selection(query, expected_backends):
       result = await unified_search(query)
       assert set(result['backends_used']) == set(expected_backends)
   ```

### Mock and Stub Guidelines

1. **Mock External Services**:
   ```python
   # Mock AWS services
   @patch('boto3.client')
   async def test_athena_query_execution(mock_boto):
       mock_athena = AsyncMock()
       mock_boto.return_value = mock_athena
       # Test implementation
   ```

2. **Use Real Data When Possible**:
   ```python
   # Prefer real data over mocks for integration tests
   async def test_real_quilt_package_browse(self):
       # Use actual Quilt package for testing
       result = await package_browse(
           package_name=\"quilt/example\",
           registry=\"s3://quilt-example\"
       )
   ```

3. **Mock Consistently**:
   ```python
   # Create reusable mock fixtures
   @pytest.fixture
   def mock_quilt_client():
       with patch('quilt3.Package') as mock:
           mock.browse.return_value = SAMPLE_PACKAGE_STRUCTURE
           yield mock
   ```

## 🚀 Performance Testing

### Performance Benchmarks

**Response Time Targets**:
- **Search Operations**: < 500ms for 90% of requests
- **Package Operations**: < 1s for 90% of requests  
- **SQL Queries**: < 2s for 90% of requests
- **File Operations**: < 100ms for small files (< 1MB)

**Load Testing**:
```python
# test_cases/performance_benchmarks.py

async def test_concurrent_package_operations(self):
    \"\"\"Test package operations under concurrent load\"\"\"
    
    # Create 20 concurrent package browse operations
    tasks = [
        package_browse(f\"test/package-{i}\", \"s3://test-bucket\")
        for i in range(20)
    ]
    
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    end_time = time.time()
    
    # Validate performance
    assert end_time - start_time < 3.0  # All operations in < 3s
    
    # Validate success rate
    successful = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
    assert successful / len(results) >= 0.95
```

### Memory and Resource Testing

```python
import psutil
import gc

async def test_memory_usage_under_load(self):
    \"\"\"Test memory usage doesn't grow excessively\"\"\"
    
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    
    # Perform 100 operations
    for i in range(100):
        await unified_search(f\"test query {i}\")
        
        # Force garbage collection every 10 operations
        if i % 10 == 0:
            gc.collect()
    
    final_memory = process.memory_info().rss
    memory_growth = final_memory - initial_memory
    
    # Memory growth should be < 100MB
    assert memory_growth < 100 * 1024 * 1024
```

## 🔍 Debugging and Troubleshooting Tests

### Common Test Issues

1. **Async Test Problems**:
   ```python
   # Ensure proper async test setup
   @pytest.mark.asyncio
   async def test_async_operation(self):
       result = await async_function()
       assert result is not None
   ```

2. **Mock Configuration Issues**:
   ```python
   # Ensure mocks are properly configured
   with patch('module.function') as mock_func:
       mock_func.return_value = expected_value
       result = await function_under_test()
       mock_func.assert_called_once()
   ```

3. **Environment Variable Issues**:
   ```python
   # Use proper environment setup
   @patch.dict(os.environ, {'TEST_VAR': 'test_value'})
   async def test_with_env_var(self):
       # Test implementation
   ```

### Test Debugging Tools

```bash
# Run tests with verbose output
pytest -v -s tests/

# Run specific test with debugging
pytest -v -s tests/test_search.py::TestUnifiedSearch::test_cross_backend_search

# Run tests with pdb debugging
pytest --pdb tests/test_search.py

# Run tests with coverage and missing lines
pytest --cov=app --cov-report=term-missing tests/
```

## 📈 Test Metrics and Quality Gates

### Quality Gates

Before merging code, ensure:

- [ ] **Unit Test Coverage**: ≥ 85%
- [ ] **Integration Tests**: All passing
- [ ] **Real-World Tests**: Key scenarios validated
- [ ] **Performance Tests**: No regression in response times
- [ ] **Error Handling**: All error paths tested

### Test Metrics Dashboard

We track these key metrics:

- **Coverage Percentage**: Current: 85%+
- **Test Execution Time**: Target: < 5 minutes for full suite
- **Real-World Test Success Rate**: Current: 100% (SAIL), 0% (CCLE - needs fixes)
- **Performance Regression**: Track response time trends

### Continuous Improvement

1. **Weekly Test Reviews**: Analyze test failures and flaky tests
2. **Monthly Performance Reviews**: Check for performance regressions
3. **Quarterly Test Strategy Reviews**: Evaluate testing approach effectiveness
4. **Real-World Scenario Updates**: Add new scenarios based on user feedback

This comprehensive testing approach ensures the Quilt MCP Server maintains high quality and reliability while supporting real-world bioinformatics workflows.

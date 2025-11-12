# Test Runners

This directory contains specialized integration and performance testing tools that are **NOT part of the**
**standard pytest test suite**. These runners are designed for manual execution and comprehensive validation
scenarios.

## Purpose

These test runners serve different purposes from regular unit/integration tests:

1. **Manual Integration Testing**: Standalone scripts for end-to-end functionality validation
2. **Performance Benchmarking**: Measure response times, throughput, and system behavior under load
3. **Real-world Validation**: Test against actual data scenarios and user workflows
4. **Interactive Testing**: Explore system behavior during development

## Available Runners

### Core MCP Testing

- **`mock_llm_mcp_test.py`** - Mock LLM interaction testing

### Domain-Specific Testing

- **`ccle_computational_biology_test_runner.py`** - Computational biology workflow validation using CCLE datasets
- **`ccle_direct_test_runner.py`** - Direct tool calls for CCLE genomics workflows
- **`sail_user_stories_test.py`** - SAIL user story validation (mock)
- **`sail_user_stories_real_test.py`** - SAIL user story validation (real data)

### Performance & Load Testing

- **`mcp_comprehensive_test_simulation.py`** - Load testing and performance benchmarks

## Usage

These runners are executed manually, not through pytest:

```bash
# Run computational biology tests
python tests/fixtures/runners/ccle_computational_biology_test_runner.py

# Run performance benchmarks
python tests/fixtures/runners/mcp_comprehensive_test_simulation.py
```

## Important Notes

- **Not included in `make test`**: These runners are separate from the standard test suite
- **Manual execution required**: They don't follow pytest naming conventions (`test_*.py`)
- **May require AWS credentials**: Some runners test against real AWS resources
- **Performance testing**: Some runners measure and report timing/throughput metrics
- **Real data dependencies**: Some runners require access to actual Quilt packages and datasets

## When to Use

- **Development validation**: Manual testing during feature development
- **Performance analysis**: Measuring system performance characteristics  
- **Release validation**: Comprehensive testing before releases
- **Debugging**: Interactive exploration of system behavior
- **User story validation**: Testing real-world usage scenarios

For standard unit and integration tests, use the pytest suite in the main `tests/` directory with
`make test` or `make coverage`.

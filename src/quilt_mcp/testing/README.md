# Quilt MCP Testing Framework

Comprehensive testing infrastructure for MCP servers with automatic test generation, intelligent validation, and tool loop orchestration.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Modules](#modules)
- [Public API](#public-api)
- [Usage Patterns](#usage-patterns)
- [Integration](#integration)
- [Design Principles](#design-principles)
- [Examples](#examples)

## Overview

The `quilt_mcp.testing` module provides a complete testing framework for MCP servers, extracted from the original monolithic test scripts (`mcp-test.py` and `mcp-test-setup.py`). It offers:

- **Automatic Test Generation**: Discovers tools, infers arguments, generates YAML configurations
- **Intelligent Classification**: Categorizes tools by effect (create/update/remove) and argument requirements
- **Comprehensive Validation**: Result validation, coverage analysis, failure pattern detection
- **Tool Loop Execution**: Multi-step workflows for testing write operations (create → modify → verify → cleanup)
- **Flexible Configuration**: YAML-based test definitions with environment variable substitution
- **Rich Output**: Detailed summaries with intelligent failure analysis

### Key Statistics

- **Module Size**: 4,644 lines across 9 modules
- **Test Coverage**: 266 unit tests (all passing)
- **Script Reduction**:
  - `mcp-test.py`: Reduced from ~2,400 to 1,599 lines (-33%)
  - `mcp-test-setup.py`: Reduced from ~1,954 to 302 lines (-85%)
- **Code Reuse**: Eliminates 40+ duplicated classes/functions

## Architecture

The testing framework is organized into five logical layers with clear dependency boundaries:

```
┌─────────────────────────────────────────────────────────────┐
│                    I/O Layer (Layer 5)                      │
│  yaml_generator.py │ config.py │ output.py                  │
│  - Test YAML gen   │ - Config  │ - Result formatting        │
│  - CSV/JSON export │   loading │ - Detailed summaries       │
└────────────────────┬────────────┬───────────────────────────┘
                     │            │
┌─────────────────────────────────────────────────────────────┐
│                 Orchestration Layer (Layer 4)               │
│  discovery.py              │  tool_loops.py                 │
│  - Tool discovery          │  - Loop execution              │
│  - Metadata extraction     │  - Template substitution       │
│  - Data registry           │  - Lifecycle testing           │
└────────────────────┬───────┴────────────────────────────────┘
                     │
┌─────────────────────────────────────────────────────────────┐
│                  Logic Layer (Layer 3)                      │
│  tool_classifier.py        │  validators.py                 │
│  - Tool classification     │  - Result validation           │
│  - Argument inference      │  - Coverage checking           │
│  - Mock context creation   │  - Failure analysis            │
└────────────────────┬───────┴────────────────────────────────┘
                     │
┌─────────────────────────────────────────────────────────────┐
│                Classification Layer (Layer 2)               │
│  tool_classifier.py                                         │
│  - classify_tool: Determine effect/category                 │
│  - infer_arguments: Generate test arguments                 │
└────────────────────┬───────────────────────────────────────┘
                     │
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer (Layer 1)                     │
│  models.py                                                  │
│  - TestResults: Test execution tracking                     │
│  - DiscoveryResult: Tool discovery results                  │
│  - DiscoveredDataRegistry: Data discovery tracking          │
└─────────────────────────────────────────────────────────────┘
```

### Dependency Graph

```
models.py (no dependencies)
    ↓
tool_classifier.py → models.py
    ↓
validators.py → models.py
    ↓
discovery.py → models.py, tool_classifier.py
tool_loops.py → models.py, validators.py
    ↓
config.py (no internal dependencies)
output.py → validators.py
    ↓
yaml_generator.py → all above modules
    ↓
scripts/mcp-test.py → all testing modules
scripts/mcp-test-setup.py → all testing modules
```

## Modules

### 1. `models.py` - Data Models (253 lines)

Pure data containers with no external dependencies.

**Classes**:
- `TestResults`: Tracks test execution results with pass/fail/skip counts
- `DiscoveryResult`: Captures tool discovery and execution results
- `DiscoveredDataRegistry`: Registry for discovered S3 keys, packages, and tables

**Example**:
```python
from quilt_mcp.testing import TestResults

results = TestResults()
results.add_pass("bucket_list", None, {"buckets": [...]})
results.add_fail("invalid_tool", None, "Tool not found")
results.add_skip("resource_test", "Resource unavailable")

summary = results.to_dict()
# {
#   "passed": 1,
#   "failed": 1,
#   "skipped": 1,
#   "tests": [...],
#   "passed_tests": [...],
#   "failed_tests": [...],
#   "skipped_tests": [...]
# }
```

### 2. `tool_classifier.py` - Tool Classification (436 lines)

Analyzes tool signatures and categorizes by effect and argument requirements.

**Key Functions**:
- `classify_tool(tool_name, handler)`: Returns (effect, category)
  - Effects: `none`, `create`, `update`, `remove`, `configure`, `none-context-required`
  - Categories: `zero-arg`, `required-arg`, `optional-arg`, `write-effect`, `context-required`
- `infer_arguments(tool_name, handler, env_vars, discovered_data)`: Generates test arguments
- `create_mock_context()`: Creates RequestContext for permission-required tools
- `get_user_athena_database(catalog_url)`: Extracts Athena database from CloudFormation

**Example**:
```python
from quilt_mcp.testing import classify_tool, infer_arguments

# Classify a tool
effect, category = classify_tool("package_create", handler)
# effect = "create", category = "write-effect"

# Infer test arguments
args = infer_arguments(
    "bucket_list",
    handler,
    env_vars={"TEST_QUILT_CATALOG_URL": "s3://my-bucket"},
    discovered_data={"s3_keys": ["file1.txt", "file2.csv"]}
)
# args = {"catalog_url": "s3://my-bucket"}
```

### 3. `validators.py` - Validation & Analysis (510 lines)

Validates test results and analyzes failure patterns.

**Classes**:
- `SearchValidator`: Validates search results (min/max, substring, regex, shape)
- `ResourceFailureType`: Enum for classifying resource failures

**Key Functions**:
- `validate_test_coverage(server_tools, config_tools)`: Ensures all tools have tests
- `validate_loop_coverage(server_tools, tool_loops, standalone)`: Validates write-effect coverage
- `classify_resource_failure(test_info)`: Categorizes resource test failures
- `analyze_failure_patterns(failed_tests)`: Groups failures and provides insights

**Example**:
```python
from quilt_mcp.testing import SearchValidator

# Create validator with constraints
validator = SearchValidator(
    min_results=5,
    max_results=100,
    must_contain={"field": "value"},
    result_shape=["name", "size", "modified"]
)

# Validate search results
result = validator.validate(response_data)
if result["valid"]:
    print("Search results valid")
else:
    print(f"Validation failed: {result['message']}")
```

### 4. `discovery.py` - Discovery Orchestration (509 lines)

Executes tools to discover available data and capture behavior.

**Classes**:
- `DiscoveryOrchestrator`: Coordinates tool execution and data discovery

**Key Functions**:
- `extract_tool_metadata(server)`: Extracts tool metadata (name, description, parameters)
- `extract_resource_metadata(server)`: Extracts resource metadata

**Example**:
```python
from quilt_mcp.testing import DiscoveryOrchestrator, DiscoveredDataRegistry

# Set up discovery
registry = DiscoveredDataRegistry()
orchestrator = DiscoveryOrchestrator(
    server=mcp_server,
    env_vars={"TEST_QUILT_CATALOG_URL": "s3://my-bucket"},
    discovered_data=registry,
    timeout=15.0
)

# Discover all tools
await orchestrator.discover_all_tools(tools)

# Access discovered data
print(f"S3 keys: {registry.s3_keys}")
print(f"Packages: {registry.packages}")
print(f"Athena tables: {registry.athena_tables}")
```

### 5. `tool_loops.py` - Tool Loop Framework (862 lines)

Executes multi-step loops for testing write operations.

**Classes**:
- `ToolLoopExecutor`: Executes create → modify → verify → cleanup cycles

**Key Functions**:
- `substitute_templates(value, env_vars, loop_uuid)`: Replaces `{uuid}`, `{env.VAR}` templates
- `generate_tool_loops(env_vars, base_role, secondary_role)`: Generates loop configurations
- `validate_tool_loops_coverage(server_tools, tool_loops, standalone)`: Coverage validation

**Example**:
```python
from quilt_mcp.testing import ToolLoopExecutor, substitute_templates

# Define a loop
loop_config = {
    "steps": [
        {
            "name": "create",
            "tool": "package_create",
            "args": {"bucket": "my-bucket", "name": "test-{uuid}"}
        },
        {
            "name": "verify",
            "tool": "package_list",
            "args": {"bucket": "my-bucket"}
        },
        {
            "name": "cleanup",
            "tool": "package_delete",
            "args": {"bucket": "my-bucket", "name": "test-{uuid}"}
        }
    ]
}

# Execute loop
executor = ToolLoopExecutor("package_lifecycle", loop_config, env_vars)
results = await executor.execute(mcp_tester)
```

### 6. `config.py` - Configuration Management (400 lines)

Loads, validates, and filters test configurations.

**Key Functions**:
- `load_test_config(config_path)`: Loads YAML configuration
- `filter_tests_by_idempotence(config, idempotent_only)`: Filters by effect
- `parse_selector(selector_str)`: Parses "all", "none", "tool1,tool2" selectors
- `validate_selector_names(selector_type, names, available, item_type)`: Validates selectors
- `filter_by_selector(items, selector_type, selector_names)`: Applies selector filters
- `truncate_response(response, max_size)`: Truncates large responses for YAML

**Example**:
```python
from quilt_mcp.testing import load_test_config, filter_tests_by_idempotence

# Load configuration
config = load_test_config(Path("mcp-test.yaml"))

# Filter to idempotent tests only
filtered_config, stats = filter_tests_by_idempotence(config, idempotent_only=True)
print(f"Filtered: {stats['removed']} write-effect tools")
print(f"Remaining: {stats['kept']} idempotent tools")
```

### 7. `output.py` - Output Formatting (589 lines)

Formats test results and generates detailed summaries.

**Key Functions**:
- `format_results_line(passed, failed, skipped)`: Formats concise results line
- `print_detailed_summary(tools_results, resources_results, loops_results, ...)`: Comprehensive output with failure analysis

**Example**:
```python
from quilt_mcp.testing import print_detailed_summary

# Print detailed summary
print_detailed_summary(
    tools_results={"passed": 50, "failed": 2, "tests": [...]},
    resources_results={"passed": 10, "failed": 0, "tests": [...]},
    loops_results={"passed": 5, "failed": 1, "loops": [...]},
    verbose=True,
    config=config
)
```

### 8. `yaml_generator.py` - YAML Generation (817 lines)

Generates test configuration YAML with discovery results.

**Key Functions**:
- `generate_csv_output(items, output_file)`: Exports tool metadata to CSV
- `generate_json_output(items, output_file)`: Exports structured JSON
- `generate_test_yaml(server, output_file, env_vars, skip_discovery, timeout)`: Main generation

**Example**:
```python
from quilt_mcp.testing import generate_test_yaml

# Generate test configuration
await generate_test_yaml(
    server=mcp_server,
    output_file="mcp-test.yaml",
    env_vars={
        "TEST_QUILT_CATALOG_URL": "s3://my-bucket",
        "TEST_ROLE_ARN": "arn:aws:iam::123:role/test"
    },
    skip_discovery=False,
    discovery_timeout=15.0
)
```

## Public API

All public API exports are defined in `__init__.py`:

```python
from quilt_mcp.testing import (
    # Data Models
    TestResults,
    DiscoveryResult,
    DiscoveredDataRegistry,

    # Classification
    classify_tool,
    infer_arguments,
    create_mock_context,
    get_user_athena_database,

    # Validation
    ResourceFailureType,
    SearchValidator,
    validate_test_coverage,
    classify_resource_failure,
    analyze_failure_patterns,
    validate_loop_coverage,

    # Discovery
    DiscoveryOrchestrator,
    extract_tool_metadata,
    extract_resource_metadata,

    # Tool Loops
    substitute_templates,
    ToolLoopExecutor,
    get_test_roles,
    generate_tool_loops,
    validate_tool_loops_coverage,

    # Configuration
    load_test_config,
    filter_tests_by_idempotence,
    parse_selector,
    validate_selector_names,
    filter_by_selector,
    truncate_response,

    # Output
    format_results_line,
    print_detailed_summary,

    # YAML Generation
    generate_csv_output,
    generate_json_output,
    generate_test_yaml,
)
```

## Usage Patterns

### Pattern 1: Test Generation Workflow

Complete workflow for generating test configurations:

```python
from quilt_mcp.testing import (
    extract_tool_metadata,
    extract_resource_metadata,
    DiscoveryOrchestrator,
    DiscoveredDataRegistry,
    classify_tool,
    infer_arguments,
    generate_tool_loops,
    validate_test_coverage,
    validate_loop_coverage,
    generate_test_yaml,
)

# 1. Extract metadata
tools = await extract_tool_metadata(server)
resources = await extract_resource_metadata(server)

# 2. Discover data
registry = DiscoveredDataRegistry()
orchestrator = DiscoveryOrchestrator(server, env_vars, registry)
await orchestrator.discover_all_tools(tools)

# 3. Classify and infer arguments
for tool in tools:
    effect, category = classify_tool(tool["name"], tool["handler"])
    args = infer_arguments(tool["name"], tool["handler"], env_vars, registry.to_dict())
    tool["effect"] = effect
    tool["category"] = category
    tool["args"] = args

# 4. Generate tool loops
tool_loops = generate_tool_loops(env_vars, base_role, secondary_role)

# 5. Validate coverage
validate_test_coverage(tools, config["tools"])
is_covered, missing = validate_loop_coverage(tools, tool_loops, config["tools"])

# 6. Generate YAML
await generate_test_yaml(server, "mcp-test.yaml", env_vars)
```

### Pattern 2: Test Execution Workflow

Complete workflow for executing tests:

```python
from quilt_mcp.testing import (
    load_test_config,
    parse_selector,
    filter_by_selector,
    filter_tests_by_idempotence,
    ToolLoopExecutor,
    SearchValidator,
    classify_resource_failure,
    analyze_failure_patterns,
    print_detailed_summary,
)

# 1. Load configuration
config = load_test_config(Path("mcp-test.yaml"))

# 2. Apply selectors
selector_type, selector_names = parse_selector("bucket_list,package_list")
config["tools"] = filter_by_selector(config["tools"], selector_type, selector_names)

# 3. Filter by idempotence
config, stats = filter_tests_by_idempotence(config, idempotent_only=True)

# 4. Execute tests
tools_results = await execute_tool_tests(config["tools"])
resources_results = await execute_resource_tests(config["resources"])

# 5. Execute loops
loop_results = TestResults()
for loop_name, loop_config in config.get("tool_loops", {}).items():
    executor = ToolLoopExecutor(loop_name, loop_config, env_vars)
    loop_result = await executor.execute(tester)
    loop_results.merge(loop_result)

# 6. Analyze and report
print_detailed_summary(
    tools_results=tools_results.to_dict(),
    resources_results=resources_results.to_dict(),
    loops_results=loop_results.to_dict(),
    verbose=True,
    config=config
)
```

### Pattern 3: Custom Validation

Create custom validators for specific requirements:

```python
from quilt_mcp.testing import SearchValidator

# Create validator with specific constraints
validator = SearchValidator(
    min_results=10,
    max_results=1000,
    must_contain={
        "metadata.owner": "data-team",
        "tags": ["production"]
    },
    result_shape=["name", "size", "last_modified", "metadata"]
)

# Validate search results
result = validator.validate(search_response)
if not result["valid"]:
    print(f"Validation failed: {result['message']}")
    if result["errors"]:
        for error in result["errors"]:
            print(f"  - {error}")
```

### Pattern 4: Custom Tool Loops

Define and execute custom multi-step workflows:

```python
from quilt_mcp.testing import ToolLoopExecutor, substitute_templates

# Define custom loop
custom_loop = {
    "description": "Test package workflow with metadata",
    "steps": [
        {
            "name": "create_package",
            "tool": "package_create",
            "args": {
                "bucket": "{env.TEST_BUCKET}",
                "name": "test-package-{uuid}",
                "metadata": {"created_by": "test"}
            }
        },
        {
            "name": "add_metadata",
            "tool": "package_metadata_update",
            "args": {
                "bucket": "{env.TEST_BUCKET}",
                "name": "test-package-{uuid}",
                "metadata": {"status": "ready"}
            }
        },
        {
            "name": "verify_metadata",
            "tool": "package_metadata_get",
            "args": {
                "bucket": "{env.TEST_BUCKET}",
                "name": "test-package-{uuid}"
            },
            "validate": {
                "must_contain": {"status": "ready"}
            }
        },
        {
            "name": "cleanup",
            "tool": "package_delete",
            "args": {
                "bucket": "{env.TEST_BUCKET}",
                "name": "test-package-{uuid}"
            }
        }
    ]
}

# Execute loop
executor = ToolLoopExecutor("custom_package_workflow", custom_loop, env_vars)
results = await executor.execute(mcp_tester)
```

## Integration

### Integration with `mcp-test.py`

The test execution script uses the testing module for all shared functionality:

```python
from quilt_mcp.testing import (
    TestResults,
    SearchValidator,
    ToolLoopExecutor,
    substitute_templates,
    validate_test_coverage,
    load_test_config,
    filter_tests_by_idempotence,
    parse_selector,
    validate_selector_names,
    filter_by_selector,
    format_results_line,
    print_detailed_summary,
)

# Script focuses on:
# - MCP transport (stdio, SSE)
# - Session management
# - Test orchestration
# - CLI parsing
```

**Before Refactoring**: 2,400 lines
**After Refactoring**: 1,599 lines (-33%)

### Integration with `mcp-test-setup.py`

The setup script uses the testing module for generation:

```python
from quilt_mcp.testing import (
    DiscoveryResult,
    DiscoveryOrchestrator,
    DiscoveredDataRegistry,
    classify_tool,
    infer_arguments,
    create_mock_context,
    get_user_athena_database,
    generate_tool_loops,
    get_test_roles,
    validate_test_coverage,
    validate_tool_loops_coverage,
    generate_csv_output,
    generate_json_output,
    generate_test_yaml,
    extract_tool_metadata,
    extract_resource_metadata,
)

# Script focuses on:
# - CLI parsing
# - Main generation flow
```

**Before Refactoring**: 1,954 lines
**After Refactoring**: 302 lines (-85%)

### Integration with Make Targets

Use the testing module through standard make commands:

```bash
# Generate test configuration
make test-mcp-setup

# Run all tests
make test-mcp

# Run specific test suites
uv run scripts/mcp-test.py --tools
uv run scripts/mcp-test.py --resources
uv run scripts/mcp-test.py --loops

# Run idempotent tests only
uv run scripts/mcp-test.py --idempotent-only

# Run with selectors
uv run scripts/mcp-test.py --tools-select "bucket_list,package_list"
uv run scripts/mcp-test.py --loops-select "package_lifecycle"
```

## Design Principles

### 1. DRY (Don't Repeat Yourself)

**Before**: Shared logic duplicated across scripts (~40+ classes/functions)
**After**: Single source of truth in testing module

### 2. Separation of Concerns

Each module has a single, well-defined responsibility:
- **models.py**: Data structures only
- **tool_classifier.py**: Classification logic only
- **validators.py**: Validation logic only
- **discovery.py**: Orchestration only
- **tool_loops.py**: Loop execution only
- **config.py**: Configuration only
- **output.py**: Formatting only
- **yaml_generator.py**: Generation only

### 3. Testability

Every module can be unit tested in isolation:
- 266 unit tests covering all modules
- 100% pass rate
- Clear test structure mirroring module organization

### 4. Reusability

Components are designed for reuse:
- Available as a library to other projects
- Clean public API with `__all__` exports
- Well-documented with examples

### 5. Extensibility

Easy to extend with new capabilities:
- Plugin system for custom validators (planned)
- Custom loop templates (planned)
- AI-powered test generation (planned)

### 6. Type Safety

Comprehensive type hints throughout:
- All public functions have type annotations
- Type checking with mypy/pyright
- Better IDE support and documentation

### 7. Clear Dependencies

Layered architecture with no circular dependencies:
```
models (no deps)
  ↓
tool_classifier, validators (models)
  ↓
discovery, tool_loops (models, classifier/validators)
  ↓
config, output (minimal deps)
  ↓
yaml_generator (all modules)
```

## Examples

### Example 1: Classify All Tools

```python
from quilt_mcp.testing import classify_tool, extract_tool_metadata

# Extract tool metadata
tools = await extract_tool_metadata(server)

# Classify each tool
for tool in tools:
    effect, category = classify_tool(tool["name"], tool["handler"])
    print(f"{tool['name']:30} effect={effect:10} category={category}")

# Output:
# bucket_list                    effect=none       category=required-arg
# package_create                 effect=create     category=write-effect
# package_update                 effect=update     category=write-effect
# package_delete                 effect=remove     category=write-effect
```

### Example 2: Discover Available Data

```python
from quilt_mcp.testing import (
    DiscoveryOrchestrator,
    DiscoveredDataRegistry,
    extract_tool_metadata,
)

# Set up discovery
registry = DiscoveredDataRegistry()
orchestrator = DiscoveryOrchestrator(
    server=server,
    env_vars={"TEST_QUILT_CATALOG_URL": "s3://my-bucket"},
    discovered_data=registry,
    timeout=15.0
)

# Discover all tools
tools = await extract_tool_metadata(server)
await orchestrator.discover_all_tools(tools)

# Access discovered data
print(f"Discovered S3 keys: {len(registry.s3_keys)}")
print(f"Discovered packages: {len(registry.packages)}")
print(f"Discovered Athena tables: {len(registry.athena_tables)}")

# Use discovered data
for key in registry.s3_keys[:5]:
    print(f"  - {key}")
```

### Example 3: Validate Test Coverage

```python
from quilt_mcp.testing import (
    extract_tool_metadata,
    load_test_config,
    validate_test_coverage,
    validate_loop_coverage,
)

# Extract server tools
server_tools = await extract_tool_metadata(server)

# Load test configuration
config = load_test_config(Path("mcp-test.yaml"))

# Validate tool coverage
try:
    validate_test_coverage(server_tools, config["tools"])
    print("✓ All tools have test coverage")
except ValueError as e:
    print(f"✗ Coverage validation failed: {e}")

# Validate loop coverage for write-effect tools
is_covered, missing = validate_loop_coverage(
    server_tools,
    config.get("tool_loops", {}),
    config["tools"]
)

if is_covered:
    print("✓ All write-effect tools have loop coverage")
else:
    print(f"✗ Missing loop coverage: {', '.join(missing)}")
```

### Example 4: Execute Complex Loop

```python
from quilt_mcp.testing import ToolLoopExecutor

# Define a complex multi-step loop
package_workflow = {
    "description": "Complete package lifecycle test",
    "steps": [
        # Create package
        {
            "name": "create",
            "tool": "package_create",
            "args": {
                "bucket": "{env.TEST_BUCKET}",
                "name": "test-{uuid}",
                "metadata": {"version": "1.0", "status": "draft"}
            }
        },
        # Update metadata
        {
            "name": "update_metadata",
            "tool": "package_metadata_update",
            "args": {
                "bucket": "{env.TEST_BUCKET}",
                "name": "test-{uuid}",
                "metadata": {"status": "published"}
            }
        },
        # Add files
        {
            "name": "add_file",
            "tool": "package_file_add",
            "args": {
                "bucket": "{env.TEST_BUCKET}",
                "name": "test-{uuid}",
                "logical_key": "data.csv",
                "physical_key": "s3://{env.TEST_BUCKET}/sample.csv"
            }
        },
        # Verify package
        {
            "name": "verify",
            "tool": "package_get",
            "args": {
                "bucket": "{env.TEST_BUCKET}",
                "name": "test-{uuid}"
            },
            "validate": {
                "must_contain": {
                    "metadata.status": "published",
                    "entries": ["data.csv"]
                }
            }
        },
        # Cleanup
        {
            "name": "cleanup",
            "tool": "package_delete",
            "args": {
                "bucket": "{env.TEST_BUCKET}",
                "name": "test-{uuid}"
            }
        }
    ]
}

# Execute loop
executor = ToolLoopExecutor("package_workflow", package_workflow, env_vars)
results = await executor.execute(mcp_tester)

# Check results
print(f"Loop execution: {results.passed} passed, {results.failed} failed")
for test in results.passed_tests:
    print(f"  ✓ {test['name']}")
for test in results.failed_tests:
    print(f"  ✗ {test['name']}: {test.get('error', 'Unknown error')}")
```

### Example 5: Custom Failure Analysis

```python
from quilt_mcp.testing import (
    TestResults,
    analyze_failure_patterns,
    classify_resource_failure,
)

# Collect test results
results = TestResults()
# ... run tests ...

# Analyze failures
if results.failed > 0:
    analysis = analyze_failure_patterns(results.failed_tests)

    print(f"\nFailure Analysis ({results.failed} failures):")
    print(f"  Error types: {len(analysis['error_types'])}")
    print(f"  Affected tools: {len(analysis['affected_tools'])}")
    print(f"  Common patterns: {len(analysis['common_patterns'])}")

    # Group by error type
    for error_type, count in analysis["error_types"].items():
        print(f"    - {error_type}: {count} occurrences")

    # Provide recommendations
    if analysis["recommendations"]:
        print("\n  Recommendations:")
        for rec in analysis["recommendations"]:
            print(f"    - {rec}")
```

## Future Enhancements

The following enhancements are planned for future versions:

1. **Plugin System**: Custom validators and loop templates
2. **AI-Powered Generation**: Intelligent test case generation using LLMs
3. **Coverage Visualization**: Interactive coverage reports and dashboards
4. **Performance Benchmarking**: Built-in benchmarking and regression detection
5. **CI Integration**: Automated test generation and execution in CI/CD
6. **Custom Templates**: Library of reusable loop patterns

## See Also

- **Specification**: `spec/a19-refactor/03-mcp-test-modularization.md`
- **Scripts**:
  - `scripts/mcp-test.py` - Test execution
  - `scripts/mcp-test-setup.py` - Test generation
- **Tests**:
  - `tests/unit/testing/` - Unit tests for testing module
  - `tests/func/test_mcp_server.py` - Functional tests
  - `tests/e2e/test_mcp_client.py` - End-to-end tests
- **Main README**: `/README.md`

---

**Module Version**: 0.1.0
**Author**: Quilt Data
**License**: Apache 2.0

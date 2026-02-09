"""MCP test infrastructure library.

This package provides a comprehensive testing framework for MCP servers,
including automatic test generation, tool classification, validation,
and intelligent result analysis.

Modules
-------
models
    Pure data models for test results and discovery tracking
tool_classifier
    Tool classification and automatic argument inference
validators
    Test result validation and failure pattern analysis
discovery
    Tool discovery orchestration and metadata extraction
tool_loops
    Multi-step loop execution for write operations
config
    Configuration loading, filtering, and management
output
    Test result formatting and detailed summaries
yaml_generator
    Automatic YAML test configuration generation

Quick Start
-----------
Generate test configuration:
    >>> from quilt_mcp.testing import generate_test_yaml
    >>> await generate_test_yaml(
    ...     server=my_server,
    ...     output_file="mcp-test.yaml",
    ...     env_vars={"TEST_QUILT_CATALOG_URL": "s3://bucket"}
    ... )

Load and run tests:
    >>> from quilt_mcp.testing import load_test_config, filter_tests_by_idempotence
    >>> config = load_test_config(Path("mcp-test.yaml"))
    >>> filtered, stats = filter_tests_by_idempotence(config, idempotent_only=True)

Classify tools:
    >>> from quilt_mcp.testing import classify_tool, infer_arguments
    >>> effect, category = classify_tool("bucket_list", handler)
    >>> args = infer_arguments("bucket_list", handler, env_vars)

Validate results:
    >>> from quilt_mcp.testing import SearchValidator, validate_test_coverage
    >>> validator = SearchValidator(min_results=5)
    >>> result = validator.validate(response)

Execute tool loops:
    >>> from quilt_mcp.testing import ToolLoopExecutor, substitute_templates
    >>> executor = ToolLoopExecutor("package_lifecycle", loop_config, env_vars)
    >>> results = await executor.execute(tester)

Format output:
    >>> from quilt_mcp.testing import print_detailed_summary, format_results_line
    >>> print_detailed_summary(tools_results, resources_results, verbose=True)

Architecture
------------
The testing framework is organized into layers:

1. Data Layer (models.py)
   - TestResults, DiscoveryResult, DiscoveredDataRegistry
   - No dependencies, pure data containers

2. Classification Layer (tool_classifier.py)
   - classify_tool, infer_arguments, create_mock_context
   - Depends on: models

3. Validation Layer (validators.py)
   - SearchValidator, validate_test_coverage, analyze_failure_patterns
   - Depends on: models

4. Orchestration Layer (discovery.py, tool_loops.py)
   - DiscoveryOrchestrator, ToolLoopExecutor
   - Depends on: models, tool_classifier, validators

5. I/O Layer (config.py, output.py, yaml_generator.py)
   - load_test_config, print_detailed_summary, generate_test_yaml
   - Depends on: All other layers

Dependency Graph:
    models.py (no deps)
        ↓
    tool_classifier.py → models
        ↓
    validators.py → models
        ↓
    discovery.py → models, tool_classifier
    tool_loops.py → models, validators
        ↓
    config.py (no internal deps)
    output.py → validators
        ↓
    yaml_generator.py → all modules

Design Principles
-----------------
- DRY: Single source of truth for shared logic
- Testable: Individual components unit testable
- Reusable: Available to other projects
- Extensible: Easy to add new capabilities
- Type-safe: Comprehensive type hints
- Well-documented: Extensive docstrings

Public API
----------
The __all__ list below defines the stable public API. All other exports
are considered internal implementation details and may change.

Usage Patterns
--------------
1. Test Generation Workflow:
   - extract_tool_metadata(server) → tools
   - extract_resource_metadata(server) → resources
   - DiscoveryOrchestrator.discover_all_tools() → discovered data
   - classify_tool, infer_arguments → test configs
   - generate_tool_loops → loop configs
   - validate_test_coverage, validate_loop_coverage → coverage checks
   - generate_test_yaml → output

2. Test Execution Workflow:
   - load_test_config → config
   - parse_selector, filter_by_selector → filtered tests
   - filter_tests_by_idempotence → idempotent tests
   - Execute tools, resources, loops → results
   - SearchValidator.validate → validated results
   - classify_resource_failure, analyze_failure_patterns → analysis
   - print_detailed_summary → output

3. Custom Validation:
   - SearchValidator → custom rules
   - classify_resource_failure → custom classification
   - analyze_failure_patterns → custom analysis

4. Custom Loop Execution:
   - substitute_templates → template processing
   - ToolLoopExecutor → custom loops
   - validate_loop_coverage → coverage validation

Future Enhancements
-------------------
Planned for future versions:
- Plugin system for custom validators
- AI-powered test generation
- Coverage visualization
- Performance benchmarking
- Integration with CI/CD systems
- Custom loop templates library

See Also
--------
- scripts/mcp-test.py: Test execution script
- scripts/mcp-test-setup.py: Test generation script
- spec/a19-refactor/03-mcp-test-modularization.md: Design specification
"""

# Phase 2: Export core models (IMPLEMENTED)
from .models import (
    TestResults,
    DiscoveryResult,
    DiscoveredDataRegistry,
)

# Phase 3: Export classification and validation (IMPLEMENTED: tool_classifier)
from .tool_classifier import (
    classify_tool,
    infer_arguments,
    create_mock_context,
    get_user_athena_database,
)

from .validators import (
    ResourceFailureType,
    SearchValidator,
    validate_test_coverage,
    classify_resource_failure,
    analyze_failure_patterns,
    validate_loop_coverage,
)

# Phase 4: Export discovery and loops (IMPLEMENTED)
from .discovery import (
    DiscoveryOrchestrator,
    extract_tool_metadata,
    extract_resource_metadata,
)

from .tool_loops import (
    substitute_templates,
    ToolLoopExecutor,
    get_test_roles,
    generate_tool_loops,
    validate_tool_loops_coverage,
)

from .client import (
    MCPTester,
)

# Phase 3: Export config utilities (IMPLEMENTED)
from .config import (
    load_test_config,
    filter_tests_by_idempotence,
    parse_selector,
    validate_selector_names,
    filter_by_selector,
    truncate_response,
)

# Phase 5: Export output and YAML generation (IMPLEMENTED)
from .output import (
    format_results_line,
    print_detailed_summary,
)

from .yaml_generator import (
    generate_csv_output,
    generate_json_output,
    generate_test_yaml,
)

# Public API exports - all components will be exposed when implemented
__all__ = [
    # Data Models (models.py)
    "TestResults",
    "DiscoveryResult",
    "DiscoveredDataRegistry",
    # Tool Classification (tool_classifier.py)
    "classify_tool",
    "infer_arguments",
    "create_mock_context",
    "get_user_athena_database",
    # Validation (validators.py)
    "ResourceFailureType",
    "SearchValidator",
    "validate_test_coverage",
    "classify_resource_failure",
    "analyze_failure_patterns",
    "validate_loop_coverage",
    # Discovery (discovery.py)
    "DiscoveryOrchestrator",
    "extract_tool_metadata",
    "extract_resource_metadata",
    # Tool Loops (tool_loops.py)
    "substitute_templates",
    "ToolLoopExecutor",
    "get_test_roles",
    "generate_tool_loops",
    "validate_tool_loops_coverage",
    # MCP Client (client.py)
    "MCPTester",
    # Configuration (config.py)
    "load_test_config",
    "filter_tests_by_idempotence",
    "parse_selector",
    "validate_selector_names",
    "filter_by_selector",
    "truncate_response",
    # Output (output.py)
    "format_results_line",
    "print_detailed_summary",
    # YAML Generation (yaml_generator.py)
    "generate_csv_output",
    "generate_json_output",
    "generate_test_yaml",
]

# Version information
__version__ = "0.1.0"
__author__ = "Quilt Data"
__description__ = "MCP test infrastructure library"

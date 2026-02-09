# A19-03: MCP Test Scripts Modularization

**Status**: ✅ Complete
**Author**: System
**Date**: 2024-02-08
**Completion Date**: 2024-02-08
**Completion Summary**: [04-mcp-test-modularization-complete.md](./04-mcp-test-modularization-complete.md)

## Context

The MCP test infrastructure consists of two large scripts:

- `scripts/mcp-test.py` (112KB, ~2,400 lines) - Test execution engine
- `scripts/mcp-test-setup.py` (80KB, ~1,954 lines) - Test configuration generator

These scripts contain significant **shared architectural components** (~40+ classes/functions) that violate DRY principles and make maintenance difficult. The duplication includes:

1. **Data models**: `TestResults`, `DiscoveryResult`, `DiscoveredDataRegistry`
2. **Tool classification**: `classify_tool()`, `infer_arguments()`, `create_mock_context()`
3. **Validation**: `SearchValidator`, `validate_test_coverage()`, failure analysis
4. **Tool loops**: `ToolLoopExecutor`, `substitute_templates()`, loop generation
5. **Configuration**: Config loading, filtering, environment handling
6. **Output formatting**: Result formatting, detailed summaries

## Problem Statement

### Current Issues

1. **Code Duplication**: Identical or near-identical implementations exist in both scripts
2. **Maintenance Burden**: Changes must be synchronized across two files
3. **Testing Difficulty**: Shared logic cannot be unit tested independently
4. **Reusability**: Valuable components (classification, validation) are locked in scripts
5. **Module Boundaries**: No clear separation between shared libraries and script-specific logic

### Impact

- Risk of divergence between implementations
- Difficulty adding new test capabilities
- Cannot leverage shared components in other tools
- Hard to validate individual components in isolation

## Proposed Solution

### Module Structure

Create a proper `src/quilt_mcp/testing/` module with clear separation of concerns:

```
src/quilt_mcp/testing/
├── __init__.py                # Public API exports
├── models.py                  # Data models (~100 lines)
├── tool_classifier.py         # Tool classification & inference (~200 lines)
├── validators.py              # Validation & analysis (~250 lines)
├── discovery.py               # Discovery orchestration (~250 lines)
├── tool_loops.py              # Loop execution & templates (~300 lines)
├── config.py                  # Config loading & filtering (~100 lines)
├── output.py                  # Formatting & reporting (~100 lines)
└── yaml_generator.py          # YAML generation (~150 lines)
```

**Scripts remain minimal**:

- `scripts/mcp-test.py` (~900 lines) - Transport, session management, CLI
- `scripts/mcp-test-setup.py` (~300 lines) - Generation flow, CLI

### Module Responsibilities

#### 1. `models.py` - Data Models

**Pure data containers, no dependencies**

```python
from dataclasses import dataclass, field
from typing import Dict, Any, List, Literal, Optional

class TestResults:
    """Tracks test results with consistent structure."""
    # Lines 282-356 from mcp-test.py

@dataclass
class DiscoveryResult:
    """Result of tool discovery/validation."""
    # Lines 108-130 from mcp-test-setup.py

class DiscoveredDataRegistry:
    """Registry for discovered data (S3 keys, packages, tables)."""
    # Lines 132-165 from mcp-test-setup.py
```

**Exports**:

- `TestResults` - Used by all test runners
- `DiscoveryResult` - Used by discovery and setup
- `DiscoveredDataRegistry` - Used by discovery and inference

#### 2. `tool_classifier.py` - Tool Classification & Inference

**Determines tool characteristics and generates test arguments**

```python
import inspect
from typing import Dict, Any, Tuple, Optional
from quilt_mcp.context.request_context import RequestContext

def classify_tool(tool_name: str, handler) -> Tuple[str, str]:
    """Classify tool by effect and category.

    Returns:
        (effect, category) where:
        - effect: none|create|update|remove|configure|none-context-required
        - category: zero-arg|required-arg|optional-arg|write-effect|context-required
    """
    # Lines 439-487 from mcp-test-setup.py

def infer_arguments(
    tool_name: str,
    handler,
    env_vars: Dict[str, str | None],
    discovered_data: Optional[Dict[str, Any]] = None,
    athena_database: Optional[str] = None
) -> Dict[str, Any]:
    """Infer test arguments from signature, environment, and discovered data."""
    # Lines 490-622 from mcp-test-setup.py

def create_mock_context() -> RequestContext:
    """Create mock RequestContext for permission-required tools."""
    # Lines 417-436 from mcp-test-setup.py

def get_user_athena_database(catalog_url: str) -> str:
    """Get UserAthenaDatabase from CloudFormation stack."""
    # Lines 71-101 from mcp-test-setup.py
```

**Exports**:

- `classify_tool()` - Used by setup, test filtering, coverage validation
- `infer_arguments()` - Used by setup for automatic test generation
- `create_mock_context()` - Used by discovery and testing
- `get_user_athena_database()` - Used by setup and potentially by tests

**Dependencies**: `models.py`, `RequestContext`

#### 3. `validators.py` - Validation & Analysis

**Validates test results and analyzes failure patterns**

```python
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter

class ResourceFailureType(Enum):
    """Classify resource test failures."""
    # Lines 157-163 from mcp-test.py

class SearchValidator:
    """Validates search results against expected outcomes."""
    # Lines 358-524 from mcp-test.py

def validate_test_coverage(
    server_tools: List[Dict[str, Any]],
    config_tools: Dict[str, Any]
) -> None:
    """Ensure all server tools are covered by test config."""
    # Lines 527-579 from mcp-test.py

def classify_resource_failure(test_info: dict) -> ResourceFailureType:
    """Classify resource failure for intelligent reporting."""
    # Lines 166-186 from mcp-test.py

def analyze_failure_patterns(failed_tests: List[Dict]) -> Dict[str, Any]:
    """Analyze failure patterns to provide actionable insights."""
    # Lines 189-247 from mcp-test.py

def validate_loop_coverage(
    server_tools: List[Dict[str, Any]],
    tool_loops: Dict[str, Any],
    standalone_tools: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """Validate that write-effect tools are covered by loops/tests."""
    # Lines 856-901 from mcp-test.py
```

**Exports**:

- `SearchValidator` - Used by test execution
- `validate_test_coverage()` - Used by setup and test runner
- `classify_resource_failure()` - Used by result reporting
- `analyze_failure_patterns()` - Used by detailed summary
- `validate_loop_coverage()` - Used by setup and test runner

**Dependencies**: `models.py`

#### 4. `discovery.py` - Discovery Orchestration

**Executes tools and captures behavior for test generation**

```python
import asyncio
import inspect
import time
from typing import Dict, Any, Optional

from .models import DiscoveryResult, DiscoveredDataRegistry
from .tool_classifier import create_mock_context

class DiscoveryOrchestrator:
    """Coordinates tool execution and data discovery."""
    # Lines 167-411 from mcp-test-setup.py

async def extract_tool_metadata(server) -> List[Dict[str, Any]]:
    """Extract comprehensive metadata from registered tools."""
    # Lines 1092-1132 from mcp-test-setup.py

async def extract_resource_metadata(server) -> List[Dict[str, Any]]:
    """Extract comprehensive metadata from registered resources."""
    # Lines 1134-1188 from mcp-test-setup.py
```

**Exports**:

- `DiscoveryOrchestrator` - Used by setup for tool validation
- `extract_tool_metadata()` - Used by setup for tool listing
- `extract_resource_metadata()` - Used by setup for resource listing

**Dependencies**: `models.py`, `tool_classifier.py`

#### 5. `tool_loops.py` - Tool Loop Framework

**Template-based loop execution for write-operation testing**

```python
import re
import uuid as uuid_module
from typing import Dict, Any

from .models import TestResults
from .validators import validate_loop_coverage

def substitute_templates(
    value: Any,
    env_vars: Dict[str, str],
    loop_uuid: str
) -> Any:
    """Recursively substitute template variables ({uuid}, {env.VAR})."""
    # Lines 586-627 from mcp-test.py

class ToolLoopExecutor:
    """Executes tool loops with create → modify → verify → cleanup cycles."""
    # Lines 630-852 from mcp-test.py

def get_test_roles() -> Tuple[str, str]:
    """Get standard test roles for user management tests."""
    # Lines 629-640 from mcp-test-setup.py

def generate_tool_loops(
    env_vars: Dict[str, str | None],
    base_role: str,
    secondary_role: str
) -> Dict[str, Any]:
    """Generate tool loops configuration for write-operation testing."""
    # Lines 643-1045 from mcp-test-setup.py

def validate_tool_loops_coverage(
    server_tools: Dict[str, Any],
    tool_loops: Dict[str, Any],
    standalone_tools: Dict[str, Any]
) -> None:
    """Validate write-effect tools are covered by loops/tests."""
    # Lines 1048-1085 from mcp-test-setup.py
```

**Exports**:

- `substitute_templates()` - Used by loop executor
- `ToolLoopExecutor` - Used by test runner
- `get_test_roles()` - Used by loop generation
- `generate_tool_loops()` - Used by setup
- `validate_tool_loops_coverage()` - Used by setup

**Dependencies**: `models.py`, `validators.py`

#### 6. `config.py` - Configuration Management

**Loads, validates, and filters test configurations**

```python
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple

import yaml

def load_test_config(config_path: Path) -> Dict[str, Any]:
    """Load test configuration from YAML file."""
    # Lines 1907-1933 from mcp-test.py

def filter_tests_by_idempotence(
    config: Dict[str, Any],
    idempotent_only: bool
) -> Tuple[Dict[str, Any], Dict]:
    """Filter test tools based on effect classification."""
    # Lines 1936-1981 from mcp-test.py

def parse_selector(selector_str: str) -> Tuple[str, Set[str]]:
    """Parse selector strings ('all', 'none', 'name1,name2')."""
    # Lines 2310-2346 from mcp-test.py

def validate_selector_names(
    selector_type: str,
    selector_names: Set[str],
    available_items: Dict[str, Any],
    item_type: str
) -> None:
    """Validate selector names exist in available items."""
    # Lines 2349-2376 from mcp-test.py

def filter_by_selector(
    items: Dict[str, Any],
    selector_type: str,
    selector_names: Set[str]
) -> Dict[str, Any]:
    """Filter dict items by selector type and names."""
    # Lines 2379-2401 from mcp-test.py

def truncate_response(response: Any, max_size: int = 1000) -> Any:
    """Truncate large responses for YAML serialization."""
    # Lines 1231-1263 from mcp-test-setup.py
```

**Exports**:

- `load_test_config()` - Used by test runner
- `filter_tests_by_idempotence()` - Used by test runner for --idempotent-only
- `parse_selector()` - Used by test runner CLI
- `validate_selector_names()` - Used by test runner CLI
- `filter_by_selector()` - Used by test runner CLI
- `truncate_response()` - Used by setup and potentially by reporting

**Dependencies**: None (pure utilities)

#### 7. `output.py` - Output Formatting

**Formats test results and generates detailed summaries**

```python
from typing import Dict, Any, Optional

from .validators import analyze_failure_patterns

def format_results_line(passed: int, failed: int, skipped: int = 0) -> str:
    """Format results line with conditional display of counts."""
    # Lines 250-279 from mcp-test.py

def print_detailed_summary(
    tools_results: Optional[Dict[str, Any]] = None,
    resources_results: Optional[Dict[str, Any]] = None,
    loops_results: Optional[Dict[str, Any]] = None,
    selection_stats: Optional[Dict[str, Any]] = None,
    server_info: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
    config: Optional[Dict[str, Any]] = None
) -> None:
    """Print intelligent test summary with context and pattern analysis."""
    # Lines 1984-2307 from mcp-test.py
```

**Exports**:

- `format_results_line()` - Used by test runner and setup
- `print_detailed_summary()` - Used by test runner

**Dependencies**: `validators.py`

#### 8. `yaml_generator.py` - YAML Generation

**Generates test configuration YAML with discovery results**

```python
import csv
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List

from .tool_classifier import classify_tool, infer_arguments
from .tool_loops import generate_tool_loops
from .validators import validate_test_coverage
from .discovery import DiscoveryOrchestrator

def generate_csv_output(items: List[Dict[str, Any]], output_file: str):
    """Generate CSV output for tools and resources."""
    # Lines 1190-1208 from mcp-test-setup.py

def generate_json_output(items: List[Dict[str, Any]], output_file: str):
    """Generate structured JSON output for tooling."""
    # Lines 1210-1228 from mcp-test-setup.py

async def generate_test_yaml(
    server,
    output_file: str,
    env_vars: Dict[str, str | None],
    skip_discovery: bool = False,
    discovery_timeout: float = 15.0
):
    """Generate mcp-test.yaml configuration with discovery and tool loops."""
    # Lines 1266-1743 from mcp-test-setup.py
```

**Exports**:

- `generate_csv_output()` - Used by setup
- `generate_json_output()` - Used by setup
- `generate_test_yaml()` - Used by setup

**Dependencies**: All other testing modules

### Dependency Graph

```
models.py (no dependencies)
    ↓
tool_classifier.py → models.py
    ↓
validators.py → models.py
    ↓
discovery.py → models.py, tool_classifier.py
    ↓
tool_loops.py → models.py, validators.py
    ↓
config.py (no internal dependencies)
    ↓
output.py → validators.py
    ↓
yaml_generator.py → all above modules
    ↓
scripts/mcp-test.py → all testing modules
scripts/mcp-test-setup.py → all testing modules
```

## Implementation Plan

### Phase 1: Create Module Structure

**Goal**: Establish clean module hierarchy

1. Create `src/quilt_mcp/testing/` directory
2. Create empty module files with docstrings
3. Create `__init__.py` with public API exports
4. Add to `pyproject.toml` if needed

### Phase 2: Extract Core Models

**Goal**: Move pure data structures first (no dependencies)

1. Extract `TestResults` from mcp-test.py → `models.py`
2. Extract `DiscoveryResult` from mcp-test-setup.py → `models.py`
3. Extract `DiscoveredDataRegistry` from mcp-test-setup.py → `models.py`
4. Add comprehensive docstrings and type hints
5. Write unit tests for each model

### Phase 3: Extract Classification & Validation

**Goal**: Move deterministic logic (high testability)

1. Extract `classify_tool()` → `tool_classifier.py`
2. Extract `infer_arguments()` → `tool_classifier.py`
3. Extract `create_mock_context()` → `tool_classifier.py`
4. Extract `get_user_athena_database()` → `tool_classifier.py`
5. Extract `SearchValidator` → `validators.py`
6. Extract validation functions → `validators.py`
7. Extract failure analysis → `validators.py`
8. Write unit tests for classification and validation logic

### Phase 4: Extract Discovery & Loops

**Goal**: Move orchestration components

1. Extract `DiscoveryOrchestrator` → `discovery.py`
2. Extract metadata extraction → `discovery.py`
3. Extract `substitute_templates()` → `tool_loops.py`
4. Extract `ToolLoopExecutor` → `tool_loops.py`
5. Extract loop generation → `tool_loops.py`
6. Write integration tests for discovery and loops

### Phase 5: Extract Config & Output

**Goal**: Move utilities and formatting

1. Extract config functions → `config.py`
2. Extract selector parsing → `config.py`
3. Extract output formatting → `output.py`
4. Extract YAML generation → `yaml_generator.py`
5. Write unit tests for utilities

### Phase 6: Update Scripts

**Goal**: Refactor scripts to use new modules

1. Update `mcp-test.py` imports:

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
       format_results_line,
       print_detailed_summary,
   )
   ```

2. Update `mcp-test-setup.py` imports:

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
       generate_csv_output,
       generate_json_output,
       generate_test_yaml,
   )
   ```

3. Remove duplicated code from scripts
4. Keep script-specific logic:
   - `mcp-test.py`: `LocalMCPServer`, `MCPTester`, `ToolsTester`, `ResourcesTester`, `main()`
   - `mcp-test-setup.py`: `main()` function, CLI parsing

### Phase 7: Testing & Validation

**Goal**: Ensure zero regression

1. Run full test suite: `make test-all`
2. Run MCP tests: `make test-mcp`
3. Run script validation: `make test-scripts`
4. Test setup regeneration: `uv run scripts/mcp-test-setup.py`
5. Test execution with various flags:
   - `uv run scripts/mcp-test.py --tools`
   - `uv run scripts/mcp-test.py --resources`
   - `uv run scripts/mcp-test.py --loops`
   - `uv run scripts/mcp-test.py --idempotent-only`
6. Verify coverage maintains 64%+

### Phase 8: Documentation

**Goal**: Document new module structure

1. Add module docstrings to each file
2. Update README with testing module documentation
3. Add architecture diagram showing module relationships
4. Document public API in `__init__.py`
5. Add examples of using testing utilities

## Testing Strategy

### Unit Tests

**Target**: Individual components in isolation

```python
# tests/unit/testing/test_models.py
def test_test_results_to_dict_contains_all_keys():
    """Ensure to_dict() always returns complete structure."""

# tests/unit/testing/test_tool_classifier.py
def test_classify_tool_detects_create_effect():
    """Verify create operations are detected."""

def test_infer_arguments_handles_bucket_params():
    """Verify bucket argument inference."""

# tests/unit/testing/test_validators.py
def test_search_validator_validates_min_results():
    """Verify minimum result count validation."""

def test_analyze_failure_patterns_groups_by_type():
    """Verify failure pattern analysis."""

# tests/unit/testing/test_tool_loops.py
def test_substitute_templates_replaces_uuid():
    """Verify {uuid} template substitution."""

def test_substitute_templates_replaces_env_vars():
    """Verify {env.VAR} template substitution."""

# tests/unit/testing/test_config.py
def test_filter_tests_by_idempotence():
    """Verify idempotent-only filtering."""

def test_parse_selector_handles_all():
    """Verify 'all' selector parsing."""
```

### Integration Tests

**Target**: Module interactions

```python
# tests/func/testing/test_discovery_integration.py
async def test_discovery_orchestrator_with_real_tool():
    """Test discovery with actual tool handler."""

# tests/func/testing/test_loop_executor_integration.py
def test_loop_executor_executes_multi_step_loop():
    """Test loop execution with mock MCPTester."""
```

### Regression Tests

**Target**: Ensure scripts work identically

```python
# tests/e2e/test_mcp_test_regression.py
def test_mcp_test_produces_identical_output():
    """Compare output before/after refactoring."""

def test_mcp_test_setup_produces_identical_yaml():
    """Compare YAML output before/after refactoring."""
```

## Migration Strategy

### Compatibility During Migration

1. **Incremental Migration**: Extract one module at a time
2. **Keep Both Versions**: Temporarily maintain old code during transition
3. **Feature Flags**: Use environment variables to toggle new vs old code
4. **Extensive Testing**: Run both versions in parallel during migration

### Rollback Plan

If issues arise:

1. Revert module extraction commits
2. Scripts still have inline implementations
3. No breaking changes to public APIs
4. Tests validate behavior parity

## Success Criteria

### Functional Requirements

- [x] All existing tests pass (100% pass rate)
- [x] `make test-all` succeeds
- [x] `make test-mcp` succeeds
- [x] Scripts produce identical output to current version
- [x] Setup generates identical YAML configuration
- [x] All CLI flags work correctly

### Code Quality Requirements

- [x] No code duplication between scripts and modules
- [x] All modules have comprehensive docstrings
- [x] All public functions have type hints
- [x] Unit test coverage ≥80% for new modules (achieved 100% for public API)
- [x] No circular dependencies between modules
- [x] Clean import hierarchy

### Performance Requirements

- [x] Test execution time unchanged (±5%)
- [x] Setup generation time unchanged (±5%)
- [x] No memory leaks or resource issues

## Benefits

### Immediate Benefits

1. **DRY Compliance**: Single source of truth for shared logic
2. **Testability**: Individual components can be unit tested
3. **Maintainability**: Changes made in one place
4. **Reusability**: Components available to other tools
5. **Clarity**: Clear module boundaries and responsibilities

### Long-term Benefits

1. **Extensibility**: Easy to add new test capabilities
2. **Integration**: Testing utilities available to other projects
3. **Documentation**: Clear API for using testing components
4. **Reliability**: More comprehensive test coverage
5. **Evolution**: Easier to refactor individual modules

## Risks & Mitigations

### Risk: Breaking Changes During Migration

**Mitigation**:

- Incremental extraction with extensive testing
- Maintain backward compatibility during transition
- Parallel testing of old and new implementations

### Risk: Circular Dependencies

**Mitigation**:

- Carefully designed dependency graph
- Models at bottom (no dependencies)
- Clear layering (data → logic → orchestration → I/O)

### Risk: Import Complexity

**Mitigation**:

- Clean `__init__.py` with explicit exports
- Document import patterns in README
- Use relative imports within module

### Risk: Performance Regression

**Mitigation**:

- Benchmark before/after migration
- Profile module import times
- Optimize hot paths if needed

## Timeline Estimate

- **Phase 1** (Module Structure): 2 hours
- **Phase 2** (Core Models): 4 hours
- **Phase 3** (Classification & Validation): 8 hours
- **Phase 4** (Discovery & Loops): 8 hours
- **Phase 5** (Config & Output): 6 hours
- **Phase 6** (Update Scripts): 6 hours
- **Phase 7** (Testing & Validation): 8 hours
- **Phase 8** (Documentation): 4 hours

**Total**: ~46 hours (~6 days of focused work)

## Future Enhancements

After successful modularization:

1. **Enhanced Discovery**: More intelligent argument inference
2. **Custom Validators**: Plugin system for custom validation rules
3. **Loop Templates**: Reusable loop patterns for common operations
4. **Test Generation**: AI-powered test case generation
5. **Coverage Reports**: Detailed coverage analysis and visualization
6. **CI Integration**: Automated test generation in CI/CD

## References

- Original Scripts:
  - `scripts/mcp-test.py` (~2,400 lines)
  - `scripts/mcp-test-setup.py` (~1,954 lines)

- Existing Test Infrastructure:
  - `tests/unit/test_mcp_test_coverage.py`
  - `tests/func/test_mcp_server.py`
  - `tests/e2e/test_mcp_client.py`

- Related Specifications:
  - `spec/a18-mcp-test/` - MCP test implementation history
  - `spec/a19-refactor/01-ops-dedupe.md` - Ops deduplication
  - `spec/a19-refactor/02-smarter-superclass.md` - Backend refactoring

## Approval

- [x] Architecture approved
- [x] Module structure approved
- [x] Migration plan approved
- [x] Testing strategy approved
- [x] Timeline approved

---

**Status**: ✅ **COMPLETE** - All phases implemented successfully.

See [04-mcp-test-modularization-complete.md](./04-mcp-test-modularization-complete.md) for completion summary.

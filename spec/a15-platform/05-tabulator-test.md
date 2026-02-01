# Tabulator Service Test Script Design

## Overview

This document describes the design and implementation of a demonstration script that showcases creating and destroying tabulator tables by directly calling the `TabulatorService` class.

**Key Finding**: Tabulator is NOT a backend mixin - it's a standalone service that can be instantiated and used independently without requiring the full backend stack.

## Purpose

- **What**: Create a standalone test script demonstrating tabulator lifecycle operations
- **Why**: Showcase direct service usage for development, testing, and documentation
- **How**: Executable script with mocking support, requiring no AWS/Quilt credentials by default

## Architecture Analysis

### Tabulator is a Service, Not a Mixin

The Quilt MCP server uses a modular backend architecture where `Quilt3_Backend` composes multiple mixins:

```
Quilt3_Backend (main class) inherits from:
├── Quilt3_Backend_Session      (auth & AWS)
├── Quilt3_Backend_Buckets      (bucket operations)
├── Quilt3_Backend_Content      (content operations)
├── Quilt3_Backend_Packages     (package operations)
├── Quilt3_Backend_Admin        (admin operations)
├── Quilt3_Backend_Base         (base utilities)
└── QuiltOps                    (migration abstraction)
```

**Tabulator is NOT part of this mixin architecture.** Instead, it's implemented as a dedicated service:

- **Location**: `src/quilt_mcp/services/tabulator_service.py` (586 lines)
- **Class**: `TabulatorService`
- **Pattern**: Standalone service, not a backend mixin

### Service Structure

**Initialization**:

```python
from quilt_mcp.services.tabulator_service import TabulatorService

# Without auth (for testing with mocks)
service = TabulatorService(use_quilt_auth=False)

# With auth (requires Quilt login)
service = TabulatorService(use_quilt_auth=True)
```

**Key Methods**:

| Method | Purpose | Parameters | Returns |
|--------|---------|------------|---------|
| `create_table()` | Create a tabulator table | bucket_name, table_name, schema, package_pattern, logical_key_pattern, parser_config, description | Dict with success/error |
| `delete_table()` | Delete a tabulator table | bucket_name, table_name | Dict with success/error |
| `list_tables()` | List tables in bucket | bucket | Dict with table list |
| `rename_table()` | Rename a table | bucket_name, table_name, new_table_name | Dict with success/error |

**Dependencies**:

- `quilt3.admin.tabulator` module (dynamically imported)
- Checks `ADMIN_AVAILABLE` flag (set by trying to import the module)
- All validation is self-contained within the service

**Validation Layers** (all internal):

- Schema validation: `_validate_schema()`
- Pattern validation: `_validate_patterns()`
- Parser config validation: `_validate_parser_config()`
- All return validation errors in response dicts

### Standalone Usage

**YES, the service CAN be used standalone** - it does NOT require the full `Quilt3_Backend` stack:

**Minimum requirements**:

1. `quilt3.admin.tabulator` module available (or mocked)
2. Quilt authentication (optional, can be disabled with `use_quilt_auth=False`)
3. No backend initialization needed

This makes it perfect for testing and demonstration scripts!

## Test Script Design

### Script Location

`scripts/tests/demo_tabulator_lifecycle.py`

### Key Features

1. **Mock Mode (Default)** - No credentials needed
   - Mocks `quilt3.admin.tabulator` module
   - Simulates successful and error responses
   - Demonstrates service behavior without AWS/Quilt setup

2. **Real Mode** (--no-mock flag) - Tests against actual Quilt
   - Requires `quilt3 catalog login`
   - Makes real API calls to Quilt catalog
   - Useful for integration testing

3. **Complete Lifecycle** - Demonstrates all operations
   - Create table with realistic schema
   - List tables in bucket
   - Delete table
   - Show validation errors
   - Handle admin unavailable scenario

4. **Verbose Mode** (--verbose flag) - Detailed output
   - Shows full service responses
   - Displays internal validation details
   - Useful for debugging

### Script Structure

```
demo_tabulator_lifecycle.py
│
├── Shebang & Docstring (1-15)
│   └── Usage examples with uv run
│
├── Imports & Path Setup (16-30)
│   ├── Standard library imports
│   ├── Mock utilities
│   └── sys.path manipulation for src/
│
├── Mock Setup Function (31-80)
│   ├── setup_mocking() → creates mock module
│   ├── Mock set_table() for success/error
│   └── Mock list_tables() for sample data
│
├── Helper Functions (81-120)
│   ├── print_section() → section headers
│   ├── print_result() → format dicts
│   └── format_schema() → pretty schema display
│
├── Demo Functions (121-400)
│   ├── demo_create_table() → create operation
│   ├── demo_list_tables() → list operation
│   ├── demo_delete_table() → delete operation
│   ├── demo_validation_errors() → error scenarios
│   └── demo_admin_unavailable() → graceful degradation
│
├── Main Function (401-500)
│   ├── Argument parsing (--no-mock, --verbose)
│   ├── Setup mocking if needed
│   ├── Run all demo steps
│   ├── Print summary
│   └── Error handling with traceback
│
└── Entry Point (501-503)
    └── if __name__ == "__main__"
```

### Example Data

**Schema** (Genomics Sample Tracking):

```python
EXAMPLE_SCHEMA = [
    {"name": "sample_id", "type": "STRING"},
    {"name": "collection_date", "type": "TIMESTAMP"},
    {"name": "concentration", "type": "FLOAT"},
    {"name": "quality_score", "type": "INT"},
    {"name": "passed_qc", "type": "BOOLEAN"}
]
```

**Rationale**: Genomics/scientific data is a common use case for Quilt, making this a realistic example that showcases all supported column types.

**Patterns**:

```python
PACKAGE_PATTERN = r"^experiments/(?P<year>\d{4})/(?P<experiment_id>[^/]+)$"
LOGICAL_KEY_PATTERN = r"samples/(?P<sample_type>[^/]+)\.csv$"
```

**Rationale**: These patterns demonstrate:

- Named capture groups (year, experiment_id, sample_type)
- Realistic directory structures
- Common file extensions (.csv)

**Parser Config**:

```python
PARSER_CONFIG = {
    "format": "csv",
    "delimiter": ",",
    "header": True
}
```

**Rationale**: CSV is the most common format, and this shows the standard configuration.

**Expected YAML Output** (generated by service):

```yaml
schema:
  - name: sample_id
    type: STRING
  - name: collection_date
    type: TIMESTAMP
  - name: concentration
    type: FLOAT
  - name: quality_score
    type: INT
  - name: passed_qc
    type: BOOLEAN
source:
  type: quilt-packages
  package_name: ^experiments/(?P<year>\d{4})/(?P<experiment_id>[^/]+)$
  logical_key: samples/(?P<sample_type>[^/]+)\.csv$
parser:
  format: csv
  delimiter: ","
  header: true
```

## Mock Strategy

### Why Mock?

1. **Accessibility**: No AWS/Quilt credentials required
2. **Speed**: Instant execution, no network calls
3. **Reliability**: No dependency on external services
4. **Demonstration**: Focus on service behavior, not infrastructure

### How to Mock

Mock the `quilt3.admin.tabulator` module using `unittest.mock`:

```python
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

def setup_mocking():
    """Setup comprehensive mocking for quilt3.admin.tabulator"""

    # Success response (no __typename attribute)
    success_response = SimpleNamespace()

    # Error response (has __typename = 'InvalidInput' or 'OperationError')
    error_response = SimpleNamespace()
    error_response.__typename = "InvalidInput"
    error_response.message = "Example error message"

    # Mock table object
    mock_table = SimpleNamespace(
        name="sample_tracking",
        config="schema:\n- name: sample_id\n  type: STRING\n..."
    )

    # Create mock module
    mock_module = MagicMock()
    mock_module.set_table.return_value = success_response
    mock_module.list_tables.return_value = [mock_table]

    # Patch the module
    patcher = patch('quilt3.admin.tabulator', mock_module)
    patcher.start()

    return patcher
```

**Key Points**:

- `SimpleNamespace()` with no `__typename` = success
- `SimpleNamespace()` with `__typename` = error (InvalidInput, OperationError)
- Mock both `set_table()` and `list_tables()`
- Return the patcher for cleanup in finally block

### Service Response Handling

The service checks for errors using `hasattr(response, '__typename')`:

```python
# In create_table():
response = admin_tabulator.set_table(...)

if hasattr(response, '__typename'):
    # Error case
    error_type = response.__typename
    error_msg = getattr(response, 'message', 'Unknown error')
    return {
        "success": False,
        "error": f"{error_type}: {error_msg}"
    }
else:
    # Success case
    return {
        "success": True,
        "table_name": table_name,
        "message": f"Tabulator table '{table_name}' created successfully"
    }
```

This pattern is consistent across all operations (create, delete, list).

## Output Format

### Design Principles

1. **Clear Section Headers**: Use `=` lines for major sections
2. **Step Numbering**: `[Step N]` for sequential operations
3. **Status Indicators**: `✅` for success, `❌` for errors, `ℹ️` for info
4. **Indentation**: 2 spaces for details, 4 spaces for nested content
5. **Consistent Spacing**: Blank lines between sections

### Example Output

```
================================================================================
TABULATOR SERVICE DEMONSTRATION
================================================================================

Running in: MOCK MODE (no Quilt credentials required)

[Step 1] Initializing TabulatorService
  ✅ Service initialized (use_quilt_auth=False)
  ℹ️  Admin available: True (mocked)

[Step 2] Creating Tabulator Table
  Bucket: demo-bucket
  Table: sample_tracking
  Schema: 5 columns (sample_id, collection_date, concentration, quality_score, passed_qc)
  Package Pattern: ^experiments/(?P<year>\d{4})/(?P<experiment_id>[^/]+)$
  Logical Key Pattern: samples/(?P<sample_type>[^/]+)\.csv$
  Parser: CSV (delimiter: ',', header: True)

  ✅ Table created successfully
  Response:
    {
      "success": true,
      "table_name": "sample_tracking",
      "message": "Tabulator table 'sample_tracking' created successfully"
    }

[Step 3] Listing Tables in Bucket
  Bucket: demo-bucket

  ✅ Found 1 table(s):
    - sample_tracking (5 columns)

[Step 4] Deleting Table
  Bucket: demo-bucket
  Table: sample_tracking

  ✅ Table deleted successfully

[Step 5] Validation Error Scenarios

  Test Case: Empty Schema
  ❌ Expected error: Schema cannot be empty

  Test Case: Invalid Column Type
  ❌ Expected error: Invalid type 'DATE' for column 'invalid'. Valid types: BOOLEAN, FLOAT, INT, STRING, TIMESTAMP

  Test Case: Invalid Regex Pattern
  ❌ Expected error: Invalid package pattern: unterminated character set at position 0

[Step 6] Admin Unavailable Scenario
  ℹ️  Simulating admin module unavailable
  ❌ Expected error: Admin functionality not available - quilt3.admin module not found

================================================================================
SUMMARY
================================================================================
✅ All demonstrations completed successfully!

Scenarios tested:
  ✅ Create table
  ✅ List tables
  ✅ Delete table
  ✅ Validation errors (3 cases)
  ✅ Admin unavailable

Total: 6/6 scenarios passed
```

## Usage Examples

### Basic Usage (Mock Mode)

```bash
# Run with mocking (default, no credentials needed)
uv run python scripts/tests/demo_tabulator_lifecycle.py
```

**Expected Result**: All 6 steps complete successfully with mock data.

### Verbose Mode

```bash
# Show detailed output
uv run python scripts/tests/demo_tabulator_lifecycle.py --verbose
```

**Expected Result**: Additional details like full response dicts, validation details, internal state.

### Real Mode (Requires Quilt Login)

```bash
# First, login to Quilt
quilt3 catalog login

# Run against real Quilt catalog
uv run python scripts/tests/demo_tabulator_lifecycle.py --no-mock
```

**Expected Result**: Real API calls to Quilt, actual tables created/deleted (use with caution!).

### Help

```bash
# Show usage information
uv run python scripts/tests/demo_tabulator_lifecycle.py --help
```

## Demonstration Scenarios

### Scenario 1: Create Table (Success)

**Purpose**: Show successful table creation with realistic schema and configuration.

**Steps**:

1. Define example schema (5 columns with different types)
2. Define package and logical key patterns
3. Define parser configuration
4. Call `service.create_table()`
5. Check response for `success: True`
6. Display table details

**Expected Output**:

```
✅ Table created successfully
{
  "success": true,
  "table_name": "sample_tracking",
  "message": "Tabulator table 'sample_tracking' created successfully"
}
```

### Scenario 2: List Tables (Success)

**Purpose**: Show how to retrieve list of tables in a bucket.

**Steps**:

1. Call `service.list_tables(bucket)`
2. Parse response
3. Display table count and details

**Expected Output**:

```
✅ Found 1 table(s):
  - sample_tracking (5 columns)
```

### Scenario 3: Delete Table (Success)

**Purpose**: Show successful table deletion.

**Steps**:

1. Call `service.delete_table(bucket, table_name)`
2. Check response for `success: True`
3. Display confirmation

**Expected Output**:

```
✅ Table deleted successfully
```

### Scenario 4: Validation Errors

**Purpose**: Demonstrate built-in validation catches errors before API calls.

**Test Cases**:

a. **Empty Schema**

```python
result = service.create_table(
    bucket_name="test",
    table_name="test",
    schema=[],  # Empty!
    package_pattern=r".+",
    logical_key_pattern=r".+",
    parser_config={"format": "csv"}
)
```

**Expected**: `"Schema cannot be empty"` in error_details

b. **Invalid Column Type**

```python
result = service.create_table(
    bucket_name="test",
    table_name="test",
    schema=[{"name": "col1", "type": "DATE"}],  # Invalid type!
    package_pattern=r".+",
    logical_key_pattern=r".+",
    parser_config={"format": "csv"}
)
```

**Expected**: `"Invalid type 'DATE'..."` in error_details

c. **Invalid Regex Pattern**

```python
result = service.create_table(
    bucket_name="test",
    table_name="test",
    schema=[{"name": "col1", "type": "STRING"}],
    package_pattern="[invalid",  # Bad regex!
    logical_key_pattern=r".+",
    parser_config={"format": "csv"}
)
```

**Expected**: `"Invalid package pattern: ..."` in error_details

### Scenario 5: Admin Unavailable

**Purpose**: Show graceful degradation when admin module is not available.

**Steps**:

1. Patch `ADMIN_AVAILABLE` to `False`
2. Create service with `use_quilt_auth=True`
3. Try to create table
4. Show error message

**Expected Output**:

```
❌ Expected error: Admin functionality not available - quilt3.admin module not found
```

## Integration with Existing Tests

### Unit Tests

**File**: `tests/unit/test_tabulator.py`

- Tests service initialization and validation methods
- Uses mocking extensively (same pattern as our script)
- Examples:
  - `test_create_table_normalizes_parser_format` - validates format normalization
  - `test_create_table_returns_validation_errors` - validates error handling

**Our Script Complements These By**:

- Providing executable demonstration
- Showing complete workflows
- Offering interactive testing
- Serving as living documentation

### E2E Tests

**File**: `tests/e2e/test_tabulator.py`

- Full workflow tests with async wrappers
- Uses `@patch` to mock `get_tabulator_service()`
- Tests all async functions (create, delete, rename, etc.)

**Our Script Complements These By**:

- Being runnable standalone (no pytest needed)
- Showing synchronous service usage
- Demonstrating realistic data examples
- Providing immediate feedback

## Technical Implementation Notes

### Path Setup

The script must add `src/` to Python path to import from `quilt_mcp`:

```python
import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))

from quilt_mcp.services.tabulator_service import TabulatorService
```

### Error Handling

Wrap each demo in try/except to allow script to continue on errors:

```python
def demo_create_table(service, bucket, table_name, verbose=False):
    try:
        result = service.create_table(...)
        if result["success"]:
            print(f"  ✅ Table created successfully")
        else:
            print(f"  ❌ Error: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
```

### Cleanup

Always stop mock patcher in finally block:

```python
def main():
    mock_patcher = None
    try:
        if not args.no_mock:
            mock_patcher = setup_mocking()

        # ... run demos ...

    finally:
        if mock_patcher:
            mock_patcher.stop()
```

### Valid Column Types

The service validates column types against this set:

```python
VALID_TYPES = {"STRING", "INT", "FLOAT", "BOOLEAN", "TIMESTAMP"}
```

These map to Athena/Glue data types used by Quilt tabulator.

## Future Enhancements

### Possible Additions

1. **Rename Operation**: Add demo for `rename_table()`
2. **Multiple Tables**: Create multiple tables, list all, delete all
3. **Configuration Variations**: Test different parser formats (TSV, JSON, Parquet)
4. **Performance Timing**: Add timing for each operation
5. **Comparison Mode**: Run mock vs real side-by-side with timing comparison
6. **Interactive Mode**: Prompt user for bucket/table names
7. **Export Results**: Save results to JSON file for analysis

### Not Included (By Design)

1. **Async Operations**: Script uses synchronous service methods (async wrappers are for MCP)
2. **MCP Integration**: Script calls service directly, not through MCP protocol
3. **Authentication Flow**: Assumes `quilt3 catalog login` already done for real mode
4. **Resource Cleanup**: In real mode, tables are deleted; in mock mode, nothing persists

## References

### Source Files

- [src/quilt_mcp/services/tabulator_service.py:1-586](../../../src/quilt_mcp/services/tabulator_service.py) - Main service implementation
- [tests/unit/test_tabulator.py:1-206](../../../tests/unit/test_tabulator.py) - Unit tests with mock patterns
- [tests/e2e/test_tabulator.py:1-523](../../../tests/e2e/test_tabulator.py) - E2E tests with async wrappers
- [scripts/tests/test_jwt_search.py:1-154](../../../scripts/tests/test_jwt_search.py) - Example script structure

### Related Specifications

- [04-tabulator-mixin.md](./04-tabulator-mixin.md) - Original spec (note: actually a service, not mixin!)
- [03-quiltops-abstraction.md](./03-quiltops-abstraction.md) - QuiltOps backend architecture

### External Documentation

- [Quilt3 Admin Documentation](https://docs.quiltdata.com/) - Official Quilt documentation
- [AWS Athena Documentation](https://docs.aws.amazon.com/athena/) - Athena/Glue data types

## Conclusion

This test script demonstrates that:

1. **Tabulator is accessible**: Can be used directly without full MCP/backend stack
2. **Service is well-designed**: Clean API with built-in validation
3. **Testing is straightforward**: Mock strategy is simple and effective
4. **Documentation by example**: Script serves as living documentation

The script will be useful for:

- **Development**: Quick testing during implementation
- **Documentation**: Show developers how to use the service
- **Debugging**: Isolate service behavior from MCP/backend concerns
- **Onboarding**: Help new developers understand tabulator functionality

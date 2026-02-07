# A18: MCP Test Setup - Comprehensive Test Coverage

## Problem Statement

Current state:

- `scripts/mcp-test-setup.py` generates `scripts/tests/mcp-test.yaml` test configuration
- **31 tools on the server are NOT covered by test config**
- Script regenerates YAML on every run (no incremental updates)
- Make target doesn't track dependencies on `./tools/` changes

## Goals

1. **100% tool coverage**: Every tool on the server must have a test configuration
2. **Smart regeneration**: Only update YAML when `./tools/` source changes
3. **Maintainable defaults**: Auto-generate sensible test configs without manual maintenance
4. **Clear failure modes**: Missing test configs should be explicit, not silent

## Design

### 1. Tool Discovery & Classification

**Current behavior:**

- Extracts all tools from server
- Some tools get custom configs from `custom_configs` dict
- Others get empty `arguments: {}`
- Tools with write effects (create/update/remove) are skipped during discovery

**New behavior:**

```yaml
Tool Classification System:
  Category 1: Zero-arg read-only tools
    - No arguments required
    - Safe to run during discovery
    - Example: auth_status, catalog_info, packages_list

  Category 2: Required-arg read-only tools
    - Need arguments but safe to test
    - Use environment variables for defaults
    - Example: bucket_object_info (needs s3_uri)

  Category 3: Optional-arg read-only tools
    - Work with no args, better with args
    - Test both modes
    - Example: search_catalog (no bucket = global search)

  Category 4: Write-effect tools
    - Create/update/remove/configure effects
    - SKIPPED during discovery (safety)
    - Still need test schema defined

  Category 5: Context-required tools
    - Need RequestContext parameter
    - Currently failing with "missing argument: 'context'"
    - Example: check_bucket_access, discover_permissions
```

### 2. Argument Inference System

**Replace hardcoded `custom_configs` with intelligent inference:**

**Stage 1: Signature analysis**

- Inspect function signature with `inspect.signature(handler.fn)`
- Extract parameter names, types, defaults
- Identify required vs optional parameters

**Stage 2: Environment-based defaults**

```python
Default Argument Sources:
  1. Environment variables (.env)
     - QUILT_TEST_BUCKET → bucket_name, bucket, s3_uri
     - QUILT_TEST_PACKAGE → package_name, package
     - QUILT_TEST_ENTRY → path, logical_key, s3_uri
     - QUILT_CATALOG_URL → catalog_url, registry

  2. Parameter name patterns
     - bucket* → extract from QUILT_TEST_BUCKET
     - package* → use QUILT_TEST_PACKAGE
     - path, key, entry → use QUILT_TEST_ENTRY
     - database → "default"
     - table → "test_table"
     - limit, max_* → 10
     - query → "SELECT 1 as test_value"

  3. Type-based defaults
     - bool → True/False (based on param name)
     - int → 10 (for limits), 200 (for max_bytes)
     - str → look up by name pattern
     - Optional[X] → None or default value

  4. Discovered data (from prior tool runs)
     - If bucket_objects_list ran: use first discovered s3_uri
     - If search_catalog ran: use first package_name
     - If athena_tables_list ran: use first table name
```

**Stage 3: Validation**

- Check if all required params have values
- Warn about missing defaults (don't fail silently)
- Allow override via `custom_configs` for special cases

### 3. Context Parameter Handling

**Problem:** Tools like `check_bucket_access` and `discover_permissions` require `context: RequestContext`

**Solution:**

```python
Context Injection Strategy:
  1. Detect context parameter in signature
     - Look for param named 'context'
     - Type annotation = RequestContext or similar

  2. Create mock context for discovery
     - Use current auth credentials
     - Set user_id = "test_user"
     - Set headers from environment

  3. Special category in test config
     effect: "none-context-required"

  4. Pass context automatically during discovery
     - Don't include in YAML arguments
     - Injected by test runner
```

### 4. Test Configuration Schema Enhancement

**Current YAML structure:**

```yaml
test_tools:
  tool_name:
    description: "..."
    effect: none|create|update|remove|configure
    arguments: {...}
    response_schema: {...}
    discovery:
      status: PASSED|FAILED|SKIPPED
      error: "..."
```

**Enhanced structure:**

```yaml
test_tools:
  tool_name:
    description: "..."
    effect: none|create|update|remove|configure|none-context-required

    # NEW: Argument metadata
    argument_source:
      bucket: "env:QUILT_TEST_BUCKET"
      package_name: "env:QUILT_TEST_PACKAGE"
      limit: "default:10"
      context: "injected:RequestContext"

    # NEW: Test categories
    test_category: "zero-arg" | "required-arg" | "optional-arg" | "write-effect" | "context-required"

    # NEW: Coverage tracking
    coverage:
      has_unit_test: true
      has_func_test: false
      has_e2e_test: true
      test_files:
        - "tests/unit/test_bucket_tools.py::test_bucket_object_info"
        - "tests/e2e/test_bucket_workflows.py::test_full_workflow"

    arguments: {...}
    response_schema: {...}
    discovery:
      status: PASSED|FAILED|SKIPPED
      error: "..."

    # NEW: Validation tracking
    validation:
      required_args_satisfied: true
      missing_args: []
      has_test_data: true
      can_run_discovery: true
```

### 5. Make Target Dependencies

**Current:**

```makefile
test-scripts: scripts/tests/mcp-test.yaml
 @echo "Testing scripts..."
 uv run python scripts/mcp-test.py

scripts/tests/mcp-test.yaml:
 uv run python scripts/mcp-test-setup.py
```

**New (dependency tracking):**

```makefile
# Track all tool source files
TOOL_SOURCES := $(shell find src/quilt_mcp/tools -name '*.py')
BACKEND_SOURCES := $(shell find src/quilt_mcp/backends -name '*.py')
SERVER_SOURCES := src/quilt_mcp/main.py src/quilt_mcp/server.py

# Only regenerate when sources change
scripts/tests/mcp-test.yaml: $(TOOL_SOURCES) $(BACKEND_SOURCES) $(SERVER_SOURCES) scripts/mcp-test-setup.py
 @echo "Regenerating test config (sources changed)..."
 uv run python scripts/mcp-test-setup.py
 @touch scripts/tests/mcp-test.yaml

# Force regeneration
.PHONY: test-config-force
test-config-force:
 uv run python scripts/mcp-test-setup.py

# Validate coverage without regenerating
.PHONY: test-config-validate
test-config-validate:
 uv run python scripts/mcp-test-setup.py --validate-only

test-scripts: scripts/tests/mcp-test.yaml
 @echo "Running MCP tests..."
 uv run python scripts/mcp-test.py
```

### 6. Coverage Validation

**New CLI modes for mcp-test-setup.py:**

```python
CLI Options:
  --skip-discovery        # Don't run tools, just generate schema
  --validate-only         # Check coverage, don't write YAML
  --show-missing          # List tools without test configs
  --show-categories       # Show tool categorization
  --fix-missing           # Auto-generate configs for missing tools
  --verbose              # Detailed output
  --quick                # Fast mode (existing)
```

**Coverage validation logic:**

```python
def validate_coverage():
    """Ensure every server tool has a test config."""
    server_tools = get_server_tools()
    config_tools = load_yaml_config()

    missing = server_tools - config_tools

    if missing:
        print(f"❌ ERROR: {len(missing)} tool(s) NOT covered!")
        for tool in sorted(missing):
            category = classify_tool(tool)
            print(f"  - {tool} ({category})")
        return False

    print(f"✅ All {len(server_tools)} tools covered")
    return True
```

### 7. Missing Tool Analysis

**The 31 missing tools are likely:**

1. **Context-required tools** (failing with "missing argument: 'context'")
   - `check_bucket_access`
   - `discover_permissions`

2. **Visualization tools** (missing required args)
   - `create_data_visualization`
   - `generate_package_visualizations`
   - `generate_quilt_summarize_json`

3. **Tabulator tools** (need complex args or config)
   - `tabulator_query_execute` (missing 'query')
   - `tabulator_table_create`
   - `tabulator_open_query_toggle`

4. **Admin tools** (many write-effect, skipped)
   - All `admin_*` tools are likely SKIPPED
   - But still need test schema defined

5. **Workflow tools** (write-effect)
   - `workflow_create`, `workflow_add_step`, etc.

## Implementation Tasks

### Task 1: Tool Classifier

**File:** `scripts/mcp-test-setup.py`

- [ ] Add `classify_tool(tool_name, handler)` function
- [ ] Implement 5-category classification system
- [ ] Return category + reasoning for each tool
- [ ] Add `--show-categories` CLI flag to display classification

### Task 2: Argument Inference Engine

**File:** `scripts/mcp-test-setup.py`

- [ ] Add `infer_arguments(tool_name, handler, env_vars)` function
- [ ] Implement signature inspection
- [ ] Implement environment-based defaults
- [ ] Implement parameter name pattern matching
- [ ] Implement type-based defaults
- [ ] Add validation for required params
- [ ] Replace hardcoded `custom_configs` with inference + overrides

### Task 3: Context Parameter Handler

**File:** `scripts/mcp-test-setup.py`

- [ ] Add `create_mock_context()` function
- [ ] Detect context parameters in signatures
- [ ] Inject context during discovery
- [ ] Add "none-context-required" effect type
- [ ] Document context-required tools in YAML

### Task 4: Enhanced YAML Schema

**File:** `scripts/mcp-test-setup.py`

- [ ] Add `argument_source` metadata to output
- [ ] Add `test_category` field
- [ ] Add `coverage` tracking (link to test files)
- [ ] Add `validation` section
- [ ] Update `generate_test_yaml()` to include new fields

### Task 5: Coverage Validator

**File:** `scripts/mcp-test-setup.py`

- [ ] Add `validate_coverage()` function
- [ ] Implement `--validate-only` mode
- [ ] Implement `--show-missing` mode
- [ ] Implement `--fix-missing` mode
- [ ] Return non-zero exit code if coverage incomplete

### Task 6: Make Target Updates

**File:** `Makefile`

- [ ] Add tool source file tracking
- [ ] Add conditional regeneration
- [ ] Add `test-config-force` target
- [ ] Add `test-config-validate` target
- [ ] Update `test-scripts` dependency chain

### Task 7: Missing Tool Resolution

**Manual investigation + fixes:**

- [ ] Run `--show-missing` to identify all 31 tools
- [ ] For each tool, determine why it's missing:
  - Missing required args? → Add to inference patterns
  - Context required? → Use context injection
  - Complex args? → Add to custom_configs override
  - Truly missing? → Add tool definition
- [ ] Verify all tools have test configs
- [ ] Run `--validate-only` to confirm 100% coverage

### Task 8: Integration & Testing

**Files:** `Makefile`, test scripts

- [ ] Test incremental make behavior (no rebuild when unchanged)
- [ ] Test forced regeneration
- [ ] Test coverage validation
- [ ] Verify all 31 tools now have configs
- [ ] Run full test suite
- [ ] Update documentation

## Success Criteria

1. **✅ 100% coverage**: `make test-config-validate` shows 0 missing tools
2. **✅ Smart regeneration**: YAML only updates when `./tools/` changes
3. **✅ Clear errors**: Missing configs fail fast with helpful messages
4. **✅ Maintainable**: New tools auto-generate sensible configs
5. **✅ No silent failures**: Every tool classified, every gap reported

## Testing Strategy

**Unit tests:**

- Test tool classification logic
- Test argument inference for each pattern
- Test context injection
- Test coverage validation

**Integration tests:**

- Run full discovery with all tools
- Verify YAML schema matches spec
- Test make dependency tracking

**Validation:**

```bash
# Before changes
make test-scripts  # Should show "31 tools NOT covered"

# After changes
make test-config-force         # Force regeneration
make test-config-validate      # Should pass with 0 missing
make test-scripts              # Should test all tools
```

## Migration Notes

**Backward compatibility:**

- Keep existing `custom_configs` as override mechanism
- Existing YAML format still works
- New fields are additive (optional)

**Rollout:**

1. Implement classifier + inference (Tasks 1-2)
2. Test on subset of missing tools
3. Add context handling (Task 3)
4. Resolve all 31 missing tools (Task 7)
5. Update make targets (Task 6)
6. Validate 100% coverage

## Future Enhancements

**Phase 2:**

- Link test configs to actual test files (coverage tracking)
- Auto-generate test stubs for uncovered tools
- Validate test configs match tool signatures
- CI job to prevent regressions (coverage must stay 100%)

**Phase 3:**

- Generate test reports (which tools pass/fail)
- Performance benchmarking for all tools
- Auto-update test configs when signatures change

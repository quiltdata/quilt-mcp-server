# Design Spec: Intelligent MCP Test Setup with Discovery & Validation

**Status:** Draft
**Created:** 2026-02-05
**Purpose:** Transform `mcp-test-setup.py` from a static config generator into an intelligent test discovery system that validates tools and captures real data.

---

## Problem Statement

### Current Limitations

The existing `mcp-test-setup.py` script (616 lines) generates test configurations but:

1. **No Validation**: Generates configs for all tools without verifying they actually work
2. **Static Test Data**: Uses hardcoded/env-based values that may not exist
3. **Silent Failures**: Tools that fail in production aren't detected until test execution
4. **Shallow Coverage**: Test expectations are generic (e.g., "return an array") rather than validating actual response structure
5. **Manual Discovery**: Requires manual inspection to find real S3 objects, packages, or catalog data

### Real-World Impact

- Tests pass with trivial checks but miss actual bugs
- Invalid tool configurations go undetected until runtime
- Test maintainers must manually discover valid test data
- CI failures from hardcoded assumptions about data availability

---

## Goals

### Primary Objectives

1. **Discovery Phase**: Execute tools with test parameters to discover what actually works
2. **Failure Detection**: Record PASSED/FAILED/SKIPPED status for each tool (failures don't crash setup)
3. **Data Capture**: Record actual response values for use in test expectations
4. **Smart Fallbacks**: Use discovered data to inform later tool tests (e.g., use real S3 keys found by `bucket_objects_list`)
5. **Enhanced YAML**: Generate test configs with rich expectations based on real responses

### Non-Goals

- **Not a test runner**: This script generates configs; `mcp-test.py` remains the execution engine
- **Not run in CI**: This is a local development tool; CI uses the committed YAML config
- **Not environment-specific**: Discovery adapts to available resources

### Workflow

```text
┌─────────────────────────────────────────────────────┐
│ LOCAL DEVELOPMENT                                   │
│                                                     │
│ 1. Developer runs: mcp-test-setup.py               │
│    • Discovers which tools work                    │
│    • Records PASSED/FAILED/SKIPPED status          │
│    • Captures real response examples               │
│    • Generates: scripts/tests/mcp-test.yaml        │
│                                                     │
│ 2. Developer reviews failures, fixes environment   │
│    • Add IAM permissions                           │
│    • Fix service URLs                              │
│    • Re-run setup                                  │
│                                                     │
│ 3. Developer commits updated mcp-test.yaml         │
│    git add scripts/tests/mcp-test.yaml             │
│    git commit -m "Update test config"              │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ CI/CD PIPELINE                                      │
│                                                     │
│ 1. Checkout code (includes mcp-test.yaml)          │
│                                                     │
│ 2. Run test runner: mcp-test.py                    │
│    • Uses committed config                         │
│    • Reports tools with FAILED status as failures  │
│    • Validates PASSED tools against examples       │
│                                                     │
│ 3. Report results                                  │
│    ✓ 35 PASSED, ✗ 7 FAILED, ⊘ 5 SKIPPED          │
│    Exit 1 if any FAILED                            │
└─────────────────────────────────────────────────────┘
```

---

## Design Overview

### Three-Phase Architecture

```
Phase 1: INTROSPECTION (Current)
├── Extract tool metadata
├── Extract resource metadata
└── Classify effects (read/write/configure)

Phase 2: DISCOVERY (New)
├── Execute safe tools with test params
├── Capture responses & errors
├── Extract reusable data (keys, IDs, schemas)
└── Warn about failures (don't block)

Phase 3: GENERATION (Enhanced)
├── Generate CSV/JSON (current)
├── Generate enhanced YAML with:
│   ├── Actual response examples
│   ├── Discovered test values
│   ├── Field-level expectations
│   └── Validation warnings
```

### Key Principles

- **Safety First**: Only execute read-only tools (effect='none')
- **Fail Gracefully**: Tool failures don't crash setup, but ARE recorded as FAILURES
- **Data Propagation**: Use early discoveries to inform later tests
- **Backward Compatible**: Enhanced YAML remains compatible with current `mcp-test.py`
- **Proper Categorization**: Each tool gets PASSED/FAILED/SKIPPED status, not just "warnings"

---

## Detailed Design

### Phase 2: Discovery Engine

#### 2.1 Discovery Orchestrator

**Responsibilities:**

- Coordinate tool execution in dependency order
- Manage discovered data registry
- Handle timeouts and errors gracefully (don't crash setup)
- **Record test results**: PASSED/FAILED/SKIPPED status for each tool

**Execution Order:**

```text
1. Discovery Tools (high priority)
   - bucket_objects_list → discover real S3 keys
   - tabulator_tables_list → discover real tables
   - package_browse → discover package structure

2. Dependent Tools (use discovered data)
   - bucket_object_info (use keys from step 1)
   - bucket_object_text (use keys from step 1)
   - tabulator_table_schema (use tables from step 1)

3. Search & Query Tools (lowest priority)
   - search_catalog (use packages from step 1)
   - athena_query_execute (use tables from step 1)
```

#### 2.2 Tool Invocation Strategy

**Per-Tool Execution:**

```python
async def discover_tool(tool_name, handler, arguments):
    """
    Execute a tool and capture its behavior.

    Returns:
        DiscoveryResult with:
        - status: 'PASSED' | 'FAILED' | 'SKIPPED'
        - response: dict | None (captured output)
        - error: str | None (error message if FAILED)
        - error_category: str | None (categorization for reporting)
        - duration_ms: float
        - discovered_data: dict (extracted values)
    """
```

**Safety Guards:**

- Only invoke tools with `effect='none'` (read-only)
- Skip tools with `effect='create'/'update'/'remove'` → status='SKIPPED'
- Apply 5-second timeout per tool
- Catch all exceptions → status='FAILED' (don't crash setup)

**Data Extraction:**

From successful responses, extract:

- **S3 Keys**: From `bucket_objects_list` → use in `bucket_object_*` tests
- **Package Names**: From search results → use in `package_browse` tests
- **Table Names**: From `tabulator_tables_list` → use in schema tests
- **Schema Fields**: From `athena_table_schema` → validate in query results
- **Resource URIs**: From catalog operations → use in resource tests

#### 2.3 Discovered Data Registry

**Structure:**

```yaml
discovered_data:
  s3_keys:
    - "s3://bucket/path/file1.csv"
    - "s3://bucket/path/file2.json"

  package_names:
    - "examples/wellplates"
    - "data/genomics/sample-001"

  tables:
    - database: "default"
      table: "my_table"
      columns: ["id", "name", "value"]

  catalog_resources:
    - uri: "quilt+s3://bucket#package=examples/wellplates"
      type: "package"
```

**Usage:**

- Discovery tools populate registry
- Subsequent tools read from registry to construct arguments
- Test YAML embeds registry for reference

#### 2.4 Critical Distinction: Test Failures vs Setup Warnings

**Test Failures (FAILED status):**

When a tool execution fails during discovery, this is a **TEST FAILURE**, not a warning:

- Tool returned an error response
- Tool timed out
- Tool threw an exception
- Response didn't match expected schema

**Recording:**

```yaml
test_tools:
  athena_query_execute:
    discovery:
      status: "FAILED"  # This is a test failure!
      error: "AccessDeniedException: User not authorized for Athena"
      error_category: "access_denied"
    # Test runner should mark this as FAILED in test report
```

**Setup Warnings (informational):**

These are NOT test failures, just informational messages:

- "No S3 objects found for testing, using fallback values"
- "Elasticsearch may be disabled, search tests will check for graceful degradation"
- "Skipped 7 write-effect tools (create/update/remove)"

**Reporting:**

Setup script should:

1. Complete successfully (exit code 0) even if tools fail
2. Print summary: "✓ 35 PASSED, ✗ 7 FAILED, ⊘ 5 SKIPPED"
3. Embed PASSED/FAILED/SKIPPED status in YAML
4. Test runner (`mcp-test.py`) reports these as actual test results

**Why This Matters:**

- CI sees real failure count (not hidden in "warnings")
- Developers know which tools are broken
- Test reports accurately reflect tool health
- FAILED tools can be re-tested after fixes

**How Test Runner Uses Discovery Status:**

The test runner (`mcp-test.py`) should handle discovery status as follows:

```python
# In mcp-test.py
def run_tool_test(tool_config):
    discovery_status = tool_config.get('discovery', {}).get('status')

    if discovery_status == 'FAILED':
        # Already failed during setup - report as FAILED immediately
        return TestResult(
            status='FAILED',
            message=f"Tool failed during discovery: {tool_config['discovery']['error']}"
        )

    elif discovery_status == 'SKIPPED':
        # Skipped during setup (write operation) - skip in test run too
        return TestResult(status='SKIPPED', message="Write-effect tool skipped")

    elif discovery_status == 'PASSED':
        # Passed discovery - now execute actual test
        # Can use response_example for validation
        return execute_tool_test(tool_config)

    else:
        # No discovery data (backward compat) - run test normally
        return execute_tool_test(tool_config)
```

**Reporting:**

```text
mcp-test.py results:
  ✓ 35 PASSED (tools work as expected)
  ✗ 7 FAILED (failed during discovery phase)
  ⊘ 5 SKIPPED (write operations not tested)
```

---

### Phase 3: Enhanced Config Generation

#### 3.1 Rich Test Expectations

**Before (Current):**

```yaml
test_tools:
  bucket_object_info:
    arguments:
      s3_uri: "s3://quilt-example/examples/wellplates/.timestamp"
    response_schema:
      type: object
      properties:
        content:
          type: array
```

**After (Enhanced):**

```yaml
test_tools:
  bucket_object_info:
    arguments:
      s3_uri: "s3://quilt-example/examples/wellplates/.timestamp"

    # Discovery results
    discovery:
      status: "success"
      duration_ms: 234
      discovered_at: "2026-02-05T10:30:00Z"

    # Actual response sample
    response_example:
      content:
        - type: "application/json"
          size: 42
          last_modified: "2026-01-15T08:00:00Z"
          etag: "abc123"

    # Enhanced validation
    validation:
      type: "object_metadata"
      required_fields: ["type", "size", "last_modified", "etag"]
      field_types:
        size: "integer"
        type: "string"
      constraints:
        size: {min: 1, max: 1000000}
```

**For Failed Discovery:**

```yaml
test_tools:
  athena_table_schema:
    arguments:
      database: "default"
      table: "test_table"

    discovery:
      status: "failed"
      error: "AccessDeniedException: User not authorized for Athena"
      duration_ms: 120

    # Fallback to basic validation
    validation:
      type: "error_expected"
      acceptable_errors: ["AccessDeniedException", "TableNotFoundException"]
```

#### 3.2 Dependency Chain Tracking

**Link Tests via Discovered Data:**

```yaml
test_tools:
  bucket_objects_list:
    # ... config ...
    discovered_data:
      s3_keys: ["s3://bucket/file1.csv", "s3://bucket/file2.json"]

  bucket_object_text:
    arguments:
      s3_uri: "{{discovered.s3_keys[0]}}"  # Reference to discovered data
    depends_on: ["bucket_objects_list"]
```

#### 3.3 Setup Warnings (Informational Only)

**Top-Level Setup Warnings Section:**

**IMPORTANT**: These are informational messages about setup process, NOT test failures.
Test failures are recorded in the `discovery.status` field of each tool.

```yaml
_setup_warnings:
  - category: "no_data_discovered"
    message: "No S3 objects found via bucket_objects_list, using fallback test values"
    recommendation: "Verify QUILT_TEST_BUCKET contains data"

  - category: "service_unavailable"
    message: "Elasticsearch not responding during setup - search tests may fail"
    recommendation: "Check catalog URL or skip search tests with SKIP_SEARCH=true"

  - category: "template_validation_skipped"
    message: "Resource templates cannot be tested without actual values"
    recommendation: "Manual validation required for templated resources"
```

**Test Failures are Separate:**

```yaml
test_tools:
  athena_query_execute:
    discovery:
      status: "FAILED"  # ← This is the test failure
      error: "AccessDeniedException"
      error_category: "access_denied"
    # Test runner will report this as FAILED
```

---

## Implementation Details

### 4.1 Discovery Result Model

```python
@dataclass
class DiscoveryResult:
    """Result of attempting to discover/validate a tool."""
    tool_name: str
    status: Literal['PASSED', 'FAILED', 'SKIPPED']
    duration_ms: float

    # Successful execution (status='PASSED')
    response: dict | None = None
    discovered_data: dict = field(default_factory=dict)

    # Failed execution (status='FAILED')
    error: str | None = None
    error_category: str | None = None  # access_denied, timeout, validation_error, etc.

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def success(self) -> bool:
        """Backward compatibility: success = (status == 'PASSED')"""
        return self.status == 'PASSED'
```

### 4.2 Discovery Strategy Per Tool Category

**Catalog Tools:**

```python
# Priority 1: Configure catalog
discover("catalog_configure")  # Set base URL

# Priority 2: Search for packages
result = discover("search_catalog", scope="package", limit=5)
package_names = extract_package_names(result)

# Priority 3: Use discovered packages
for pkg in package_names[:2]:
    discover("package_browse", package_name=pkg)
```

**Bucket Tools:**

```python
# Priority 1: List objects
result = discover("bucket_objects_list", max_keys=10)
s3_keys = extract_s3_keys(result)

# Priority 2: Inspect discovered objects
for key in s3_keys[:3]:
    discover("bucket_object_info", s3_uri=key)
    if is_text_file(key):
        discover("bucket_object_text", s3_uri=key, max_bytes=500)
```

**Query Tools:**

```python
# Priority 1: List tables
result = discover("tabulator_tables_list")
tables = extract_tables(result)

# Priority 2: Get schemas for discovered tables
for table in tables[:2]:
    discover("tabulator_table_schema", table=table.name, database=table.database)

# Priority 3: Try simple query
discover("tabulator_bucket_query", query="SELECT 1 as test")
```

### 4.3 Error Categorization

**Error Categories for Warnings:**

- `access_denied`: Permissions issue (recommend IAM policy)
- `service_unavailable`: External service down (recommend skip flag)
- `resource_not_found`: Test data missing (recommend setup script)
- `timeout`: Operation too slow (recommend longer timeout)
- `invalid_arguments`: Config error (recommend parameter fix)
- `validation_error`: Response structure unexpected (recommend schema update)

### 4.4 Progress Reporting

**Console Output During Discovery:**

```text
🔍 Phase 2: Discovering & Validating Tools...

📦 Bucket Operations:
  ✓ PASSED bucket_objects_list → Found 23 objects (125ms)
  ✓ PASSED bucket_object_info → Validated metadata (89ms)
  ✗ FAILED bucket_object_fetch → Timeout after 5s

🔎 Search Operations:
  ✓ PASSED search_catalog.package → Found 5 packages (234ms)
  ✗ FAILED search_catalog.file → AccessDeniedException: Elasticsearch unavailable

📊 Test Results Summary:
  ✓ 18 PASSED
  ✗ 2 FAILED  ← These are test failures, not warnings!
  ⊘ 5 SKIPPED (write-effect tools)

💾 Discovered Data:
  - 23 S3 keys from bucket_objects_list
  - 5 package names from search_catalog

📝 Generated: scripts/tests/mcp-test.yaml
   • 18 tools with PASSED status and real response examples
   • 2 tools with FAILED status (need investigation)
   • 5 tools SKIPPED (write operations)
```

---

## Backward Compatibility

### 4.5 Compatibility Strategy

**YAML Structure:**

- Existing fields (`arguments`, `response_schema`, `effect`) unchanged
- New fields (`discovery`, `response_example`, `validation`) are additions
- Current `mcp-test.py` ignores unknown fields (graceful degradation)

**Migration Path:**

1. Enhanced YAML works with old `mcp-test.py` (ignores new fields)
2. New `mcp-test.py` can leverage enhanced data for better validation
3. Users can regenerate configs to get discovery benefits

---

## Performance Considerations

### 4.6 Optimization Strategies

**Parallel Discovery:**

- Execute independent tools concurrently (e.g., all bucket reads in parallel)
- Respect dependency chains (package discovery → package browse)

**Timeout Management:**

- Default 5s per tool
- Configurable via `--discovery-timeout` flag
- Log slow tools for optimization

**Caching:**

- Cache discovered data across runs (optional `--use-cache` flag)
- Invalidate cache after 24 hours or on explicit `--refresh`

**Selective Discovery:**

- `--quick` mode: Only validate priority tools (skip slow operations)
- `--skip-discovery`: Generate config without validation (current behavior)
- `--retry-failed`: Re-discover only tools with FAILED status in existing config

---

## Security & Safety

### 4.7 Safety Constraints

**Read-Only Guarantee:**

- NEVER execute tools with `effect != 'none'`
- Double-check effect classification before execution
- Hard-coded blocklist: `create`, `update`, `delete`, `put`, `remove`, `reset`

**Credential Handling:**

- Use existing AWS profile (no new credentials)
- Respect IAM permissions (errors are warnings, not failures)
- No credential modification or storage

**Resource Limits:**

- Max 10 objects per bucket listing
- Max 500 bytes for text fetches
- Max 5s per tool invocation
- Total discovery timeout: 2 minutes

---

## Future Enhancements

### 4.8 Potential Extensions

**Statistical Analysis:**

- Track tool latency distribution across runs
- Detect performance regressions
- Recommend timeout adjustments

**Test Data Seeding:**

- If no data found, optionally create minimal test fixtures
- Requires explicit `--seed-data` flag
- Only creates read-only test objects

**Interactive Mode:**

- Prompt user to resolve failures
- Ask "Which package should I use for testing?"
- Guided setup for new environments

**CI Integration:**

- `--ci` mode: Fail if critical tools can't be validated
- Generate GitHub Actions annotations
- Upload discovery report as artifact

---

## Success Metrics

### 4.9 Measuring Success

**Quantitative:**

- **Discovery Rate**: % of tools successfully validated (target: >80%)
- **False Negatives**: Tests pass but tools broken (target: <5%)
- **Setup Time**: Acceptable discovery overhead (target: <2min)

**Qualitative:**

- **Developer Experience**: Warnings guide troubleshooting
- **Test Quality**: Caught bugs in production tools
- **Maintenance**: Fewer manual config updates needed

---

## Appendix: Example Workflows

### A.1 Fresh Environment Setup

**Scenario:** New developer setting up for first time

```bash
# Run enhanced setup
python scripts/mcp-test-setup.py

# Console output:
# 🔍 Phase 1: Introspecting MCP server...
# 📊 Found 42 tools, 8 resources
#
# 🔍 Phase 2: Discovering & validating tools...
#
# 📊 Test Results Summary:
#   ✓ 35 PASSED (83%)
#   ✗ 7 FAILED (17%)
#   ⊘ 5 SKIPPED (write operations)
#
# ❌ Failed Tools (these are test failures, not warnings):
#   • athena_query_execute: AccessDenied - add AthenaFullAccess to IAM
#   • search_catalog: ServiceUnavailable - Elasticsearch may be disabled
#   • tabulator_bucket_query: AccessDenied - missing Athena permissions
#   [... 4 more]
#
# 📝 Generated enhanced test configuration:
#    - scripts/tests/mcp-test.yaml (with discovery results)
#    - 35 tools: PASSED status with real response examples
#    - 7 tools: FAILED status (need investigation before tests will pass)
#    - 5 tools: SKIPPED status (write operations)
#
# Exit code: 0 (setup completed, but 7 tools failed validation)
```

### A.2 CI/CD Pipeline Usage

**IMPORTANT**: `mcp-test-setup.py` is NOT run in CI. It's a local development tool.

**CI Workflow:**

```bash
# CI runs the test runner with committed config
python scripts/mcp-test.py

# Exit codes:
# 0 = All tests passed (from committed mcp-test.yaml)
# 1 = Some tests failed (including FAILED status from discovery)
# 2 = Test runner error
```

**The committed `mcp-test.yaml` includes discovery results:**

- Tools with `FAILED` status are reported as test failures
- Tools with `PASSED` status are tested against their response examples
- Tools with `SKIPPED` status are skipped

**Local → CI Flow:**

```text
Developer (local):
  1. Run: python scripts/mcp-test-setup.py
  2. Review failures, fix environment issues
  3. Re-run setup until satisfied
  4. Commit: scripts/tests/mcp-test.yaml (with discovery results)
  5. Push to GitHub

CI (automated):
  1. Checkout code (includes committed mcp-test.yaml)
  2. Run: python scripts/mcp-test.py
  3. Report: ✓ 35 PASSED, ✗ 7 FAILED (from discovery status)
  4. Fail build if any test failed
```

### A.3 Quick Validation Mode

**Scenario:** Rapid check before commit

```bash
# Skip slow tools, validate essentials only
python scripts/mcp-test-setup.py --quick

# Validates only core tools:
# - bucket_objects_list
# - package_browse
# - search_catalog (basic)
# - Skips: Athena queries, large file fetches, slow operations
```

### A.4 Retry Failed Tools

**Scenario:** Environment fixed, re-test only failed tools

```bash
# Only re-discover tools that previously failed
python scripts/mcp-test-setup.py --retry-failed

# Reads existing mcp-test.yaml
# Re-executes only tools with discovery.status='FAILED'
# Updates their status if now passing
```

---

## Implementation Phases

### Phase 1: Core Discovery (Week 1)

- [ ] Implement `DiscoveryResult` model
- [ ] Build discovery orchestrator with dependency resolution
- [ ] Add safety guards (read-only enforcement)
- [ ] Test with 5 representative tools

### Phase 2: Data Propagation (Week 1-2)

- [ ] Implement discovered data registry
- [ ] Build data extraction logic (S3 keys, packages, tables)
- [ ] Wire up dependency chains
- [ ] Validate with bucket → object workflow

### Phase 3: Enhanced YAML (Week 2)

- [ ] Extend YAML generation with discovery results
- [ ] Add response examples
- [ ] Add warning annotations
- [ ] Maintain backward compatibility

### Phase 4: Polish & Documentation (Week 2-3)

- [ ] Add progress reporting
- [ ] Implement error categorization
- [ ] Write user documentation
- [ ] Add CLI flags (--quick, --skip-discovery, --retry-failed)

---

## Open Questions

1. **Setup Exit Code**: Should setup exit non-zero if tools fail discovery?
   - **Key Insight**: Setup is a LOCAL tool for generating configs, NOT run in CI
   - CI runs `mcp-test.py` (the test runner), not `mcp-test-setup.py`
   - **Option A**: Always exit 0 (setup completed, failures recorded in YAML)
   - **Option B**: Exit 1 if any tool failed (alerts developer immediately)
   - **Recommendation**: Option A - setup's job is to generate config, not enforce passing tests
   - Developer sees failure summary and can investigate; committed YAML includes FAILED status

2. **Failure Threshold**: What % of failures is acceptable?
   - If 90% of tools fail, setup probably indicates env misconfiguration
   - **Recommendation**: Warn if >50% fail, suggest checking AWS credentials/permissions
   - But still exit 0 and generate config (failures recorded in YAML)

3. **Discovered Data Expiry**: Should cached discovery data expire?
   - **Recommendation**: 24-hour TTL, invalidate on `.env` change

4. **Resource Template Testing**: Can we safely test templated resources?
   - **Recommendation**: No - require manual test case authoring

5. **Test Data Seeding**: Should setup create test fixtures if none exist?
   - **Recommendation**: Phase 2 feature, requires explicit opt-in

6. **Re-run Failed Tools**: Should setup allow re-testing only failed tools?
   - **Recommendation**: Add `--retry-failed` flag to re-discover only FAILED tools

---

## Conclusion

This design transforms `mcp-test-setup.py` from a static generator into an intelligent discovery system that:

1. **Validates tools actually work** in the target environment
2. **Captures real data** for robust test expectations
3. **Provides actionable warnings** when tools can't be validated
4. **Reduces manual maintenance** through automated discovery

The three-phase architecture (Introspection → Discovery → Generation) maintains backward compatibility while enabling significantly richer test coverage.

**Next Steps:**

1. Review and approve design
2. Implement Phase 1 (Core Discovery)
3. Validate with production tools
4. Iterate based on real-world usage

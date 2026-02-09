# Spec: Intelligent MCP Test Setup

## Overview

Design specifications for transforming `scripts/mcp-test-setup.py` from a static configuration generator into an intelligent test discovery system.

## Documents

### [01-intelligent-test-setup.md](./01-intelligent-test-setup.md)

**Main Design Specification** - Status: ✅ Complete

Complete design for adding discovery, validation, and data capture to the test setup script.

### [02-implementation-report.md](./02-implementation-report.md)

**Implementation Report** - Status: ✅ Phase 1 Complete

Detailed report documenting the implementation of the discovery system, including:

- Architecture and code changes
- Test results (22 PASSED, 8 FAILED, 25 SKIPPED)
- Performance metrics and optimization opportunities
- Error analysis with recommendations
- Future enhancement roadmap

**Key Features:**

- **Discovery Phase**: Actually execute read-only tools to validate they work
- **Test Failures (not warnings!)**: Detect broken tools and record as FAILED status
- **Data Capture**: Record real responses to enhance test expectations
- **Smart Dependencies**: Use discovered data (e.g., real S3 keys) in subsequent tests

**Critical Design Principle:**
Tool failures during discovery are **TEST FAILURES**, not just "warnings":

- Each tool gets `PASSED`, `FAILED`, or `SKIPPED` status
- Test runner reports these as actual test results
- CI/CD sees real failure counts (not hidden as warnings)

**Benefits:**

- Catches tool failures early (during setup, not CI)
- Proper test failure reporting (not buried in warnings)
- Generates better test expectations from real data
- Reduces manual test maintenance

## Quick Start

**Read the spec:**

```bash
# View the full design
cat spec/a18-mcp-test/01-intelligent-test-setup.md

# Key sections:
# - Problem Statement (why current approach is insufficient)
# - Three-Phase Architecture (introspection → discovery → generation)
# - Enhanced YAML Format (with discovery results)
# - Implementation Phases (4-week timeline)
```

**Implementation order:**

1. Phase 1: Core Discovery (Week 1)
   - Build discovery orchestrator
   - Add safety guards (read-only enforcement)
   - Test with 5 representative tools

2. Phase 2: Data Propagation (Week 1-2)
   - Implement discovered data registry
   - Build dependency chains
   - Validate with real workflows

3. Phase 3: Enhanced YAML (Week 2)
   - Extend generation with discovery results
   - Add response examples and warnings

4. Phase 4: Polish (Week 2-3)
   - Progress reporting
   - CLI flags
   - Documentation

## Design Principles

1. **Safety First**: Only execute read-only tools (effect='none')
2. **Fail Gracefully**: Capture errors as warnings, don't block setup
3. **Data Propagation**: Use early discoveries to inform later tests
4. **Backward Compatible**: Enhanced YAML works with current mcp-test.py

## Example Output

**Before (current):**

```yaml
test_tools:
  bucket_object_info:
    arguments:
      s3_uri: "s3://bucket/file.csv"  # Hardcoded, may not exist
    response_schema:
      type: object  # Generic validation
```

**After (enhanced):**

```yaml
test_tools:
  bucket_object_info:
    arguments:
      s3_uri: "s3://bucket/file.csv"  # Discovered from bucket_objects_list

    discovery:
      status: "success"
      duration_ms: 234

    response_example:  # Actual captured response
      content:
        - type: "text/csv"
          size: 1024
          last_modified: "2026-01-15T08:00:00Z"

    validation:  # Field-level expectations
      required_fields: ["type", "size", "last_modified"]
      field_types:
        size: "integer"
```

**With warnings:**

```yaml
_warnings:
  - tool: "athena_query_execute"
    category: "access_denied"
    message: "Athena access failed - user needs AthenaFullAccess policy"
    recommendation: "Add IAM permissions or set SKIP_ATHENA=true"
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: INTROSPECTION (Current)                            │
│ • Extract tool metadata from MCP server                     │
│ • Classify effects (read/write/configure)                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: DISCOVERY (New)                                    │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Priority 1: Discovery Tools                             │ │
│ │ • bucket_objects_list → discover S3 keys               │ │
│ │ • search_catalog → discover packages                   │ │
│ │ • tabulator_tables_list → discover tables              │ │
│ └─────────────────────────────────────────────────────────┘ │
│                            ↓                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Priority 2: Dependent Tools (use discovered data)       │ │
│ │ • bucket_object_info(discovered_keys[0])                │ │
│ │ • package_browse(discovered_packages[0])                │ │
│ │ • tabulator_table_schema(discovered_tables[0])          │ │
│ └─────────────────────────────────────────────────────────┘ │
│                            ↓                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Discovered Data Registry                                │ │
│ │ • s3_keys: [...]                                        │ │
│ │ • package_names: [...]                                  │ │
│ │ • tables: [...]                                         │ │
│ │ • errors: [...]                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: GENERATION (Enhanced)                              │
│ • CSV/JSON metadata (current)                               │
│ • Enhanced YAML with:                                       │
│   - Discovery results                                       │
│   - Response examples                                       │
│   - Rich validation rules                                   │
│   - Warning annotations                                     │
└─────────────────────────────────────────────────────────────┘
```

## Success Criteria

**Quantitative:**

- Discovery Rate: >80% of tools successfully validated
- False Negatives: <5% (tests pass but tools broken)
- Setup Time: <2 minutes

**Qualitative:**

- Warnings guide developers to fix environment issues
- Test expectations catch real bugs
- Reduced manual config maintenance

## Related Files

- **Current Implementation**: [scripts/mcp-test-setup.py](../../scripts/mcp-test-setup.py)
- **Test Runner**: [scripts/mcp-test.py](../../scripts/mcp-test.py)
- **Generated Config**: [scripts/tests/mcp-test.yaml](../../scripts/tests/mcp-test.yaml)

## Status

**Current**: ✅ Phase 1 Implementation Complete (2026-02-05)

**Completed:**

1. ✅ Core Discovery Engine implemented
2. ✅ Safety guards (read-only enforcement)
3. ✅ Data extraction (S3 keys, packages, tables)
4. ✅ Enhanced YAML generation with discovery results
5. ✅ CLI flags (--skip-discovery, --discovery-timeout)
6. ✅ Validated with 55 tool configurations

**Results:**

- 22 tools PASSED with real response capture
- 8 tools FAILED with actionable errors
- 25 tools SKIPPED (write operations)
- 5 S3 keys discovered from bucket_objects_list

**Next Steps:**

1. Fix Athena permissions (Glue IAM policies)
2. Add context object mocking for permission tools
3. Implement dependency resolution (use discovered data)
4. Add parallel execution for 2x speedup
5. Create quick mode for rapid validation

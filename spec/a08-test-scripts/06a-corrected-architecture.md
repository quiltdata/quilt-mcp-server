# Corrected Architecture Understanding

**Date:** 2025-11-12
**Status:** ✅ CORRECTED
**Related:** [06-resource-testing-extension.md](./06-resource-testing-extension.md)

## Critical Correction

The initial specification draft incorrectly described the relationship between `test_mcp.py` and `mcp-test.py`. This document clarifies the actual architecture.

## What Was Wrong

**Incorrect Understanding:**
- Believed `test_mcp.py` calls `mcp-test.py` to run tests
- Thought they were part of a single orchestrated workflow

**Evidence of Error:**
- `test_mcp.py` docstring says "Runs mcp-test.py" (line 8)
- `MCP_TEST_SCRIPT` variable defined (line 35) but never used
- Only 1 occurrence of `MCP_TEST_SCRIPT` in entire file (grep confirms)

## Actual Architecture

### Two Independent Test Systems

```
┌──────────────────────────────────────────────────────────────┐
│                    PRIMARY: test_mcp.py                       │
│                 (stdio, Docker, CI/CD integrated)             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  • Manages Docker container lifecycle                        │
│  • Uses stdio transport (stdin/stdout pipes)                 │
│  • Implements own test logic (run_tests_stdio)               │
│  • Called by: make test-scripts                              │
│  • Used in: CI/CD pipeline                                   │
│  • Config: scripts/tests/mcp-test.yaml                       │
│                                                               │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                  SECONDARY: mcp-test.py                       │
│                    (HTTP, manual, standalone)                 │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  • Standalone HTTP endpoint tester                           │
│  • Requires external running server                          │
│  • No Docker management                                      │
│  • Called by: manual invocation only                         │
│  • Used in: manual testing, debugging                        │
│  • Config: scripts/tests/mcp-test.yaml (same file!)          │
│                                                               │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                  SHARED: mcp-list.py                          │
│             (Config generator, used by both)                  │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  • Introspects MCP server code                               │
│  • Extracts tool and resource metadata                       │
│  • Generates mcp-test.yaml configuration                     │
│  • Generates CSV/JSON metadata files                         │
│  • Called by: make mcp-list (or manually)                    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Relationship

```
                    ┌──────────────┐
                    │ mcp-list.py  │
                    │   (Config    │
                    │  Generator)  │
                    └──────┬───────┘
                           │
                           │ Generates
                           │
                           ▼
                ┌──────────────────────┐
                │  mcp-test.yaml       │
                │  (Shared Config)     │
                └──────┬───────┬───────┘
                       │       │
         Uses          │       │         Uses
         (primary)     │       │         (manual)
                       │       │
                 ┌─────▼──┐  ┌─▼──────┐
                 │ test_  │  │ mcp-   │
                 │ mcp.py │  │ test.py│
                 │(stdio) │  │ (HTTP) │
                 └────────┘  └────────┘
                     │
                     │ Manages
                     ▼
              ┌────────────┐
              │   Docker   │
              │ Container  │
              └────────────┘

Independent execution paths - NOT connected!
```

## Key Facts

### test_mcp.py (Primary)

**Purpose:** Automated integration testing for CI/CD

**Transport:** stdio (stdin/stdout pipes)

**Server Management:**
- Starts Docker container: `docker run -i quiltdata/quilt-mcp-server`
- Pipes stdin/stdout directly
- Cleans up container on exit

**Test Implementation:**
- `run_tests_stdio()` function (lines 212-346)
- Direct JSON-RPC over stdio
- Line-by-line request/response

**Usage:**
```bash
make test-scripts                    # Primary usage
python scripts/tests/test_mcp.py     # Direct usage
python scripts/tests/test_mcp.py --all  # All tests including writes
```

**When Run:**
- Every CI/CD build
- Pre-release validation
- Developer testing via make

### mcp-test.py (Secondary)

**Purpose:** Manual testing of running HTTP MCP servers

**Transport:** HTTP (JSON-RPC over HTTP)

**Server Management:**
- None - requires external server
- User must start server separately
- User provides endpoint URL

**Test Implementation:**
- `MCPTester` class (lines 21-136)
- `run_tools_test()` function (lines 152-189)
- HTTP requests via `requests` library

**Usage:**
```bash
# Start server externally first
python scripts/mcp-test.py http://localhost:8765/mcp --list-tools
python scripts/mcp-test.py http://localhost:8765/mcp --tools-test
python scripts/mcp-test.py http://localhost:8765/mcp --test-tool catalog_configure
```

**When Run:**
- Manual debugging
- Testing external deployments
- HTTP transport validation
- NOT in CI/CD pipeline

### mcp-list.py (Shared)

**Purpose:** Generate test configuration from code introspection

**Key Functions:**
- `extract_tool_metadata()` - introspect tools
- `extract_resource_metadata()` - introspect resources
- `generate_test_yaml()` - create mcp-test.yaml

**Output Files:**
1. `scripts/tests/mcp-test.yaml` - Test configuration (used by both)
2. `tests/fixtures/mcp-list.csv` - CSV metadata
3. `build/tools_metadata.json` - JSON metadata

**Usage:**
```bash
make mcp-list                        # Via make
python scripts/mcp-list.py           # Direct
```

**When Run:**
- When tools/resources change
- Before running tests
- Part of `make test-scripts` flow

## Why the Confusion?

1. **Outdated Docstring**
   - Line 8 of `test_mcp.py` says "Runs mcp-test.py"
   - This was likely true in an earlier design
   - Implementation changed but docstring didn't

2. **Unused Variable**
   - `MCP_TEST_SCRIPT` defined but never used
   - Suggests refactoring happened
   - Variable left behind as remnant

3. **Similar Names**
   - `test_mcp.py` vs `mcp-test.py`
   - Easy to confuse their roles
   - Both do "MCP testing" but differently

4. **Shared Config**
   - Both use `mcp-test.yaml`
   - Looks like they're connected
   - Actually just share data format

## Implications for Resource Testing

### Primary Focus: test_mcp.py (stdio)

**Must Have:**
- Add `run_resource_tests_stdio()` function
- Test resources in same Docker container
- Integrate into CI/CD pipeline
- Use stdio transport matching tool tests

**Why Primary:**
- Already integrated into `make test-scripts`
- Runs in CI/CD automatically
- Docker management built-in
- Primary validation method

### Secondary: mcp-test.py (HTTP)

**Nice to Have:**
- Add `list_resources()` method
- Add `read_resource()` method
- Add `run_resources_test()` function
- Test resources over HTTP

**Why Secondary:**
- Manual use only
- Not in CI/CD
- Requires external server
- Debugging/dev tool

### Shared: mcp-list.py

**Required:**
- Extend `generate_test_yaml()` to include `test_resources` section
- Resource metadata extraction already exists
- Just need to add to YAML output

## Implementation Priority

### Phase 1: Essential (Primary System)

1. **mcp-list.py:** Add `test_resources` to YAML generation
2. **test_mcp.py:** Add `run_resource_tests_stdio()`
3. **test_mcp.py:** Integrate resource tests into main flow

**Deliverable:** Resources tested in CI/CD pipeline

### Phase 2: Optional (Secondary System)

4. **mcp-test.py:** Add resource testing methods
5. **mcp-test.py:** Add CLI arguments for resources

**Deliverable:** Manual HTTP resource testing capability

### Phase 3: Documentation

6. Update README with resource testing usage
7. Document differences between test systems
8. Create troubleshooting guide

## Updated Spec Changes

The main specification ([06-resource-testing-extension.md](./06-resource-testing-extension.md)) has been updated to reflect this corrected understanding:

1. **Executive Summary:** Clarified two independent systems
2. **Current State:** Marked HTTP testing as "secondary, nice-to-have"
3. **Architecture:** Separated primary (stdio) and secondary (HTTP) diagrams
4. **Implementation Plan:** Prioritized stdio implementation
5. **Docstring Fix:** Updated `test_mcp.py` docstring to be accurate

## Conclusion

**Corrected Understanding:**
- `test_mcp.py` and `mcp-test.py` are independent tools
- They share configuration format but not execution
- Resource testing should focus on `test_mcp.py` first (stdio)
- HTTP testing in `mcp-test.py` is a secondary nice-to-have

**Next Steps:**
1. Focus implementation on `test_mcp.py` (stdio) resource testing
2. Treat `mcp-test.py` (HTTP) as optional enhancement
3. Ensure CI/CD pipeline gets resource coverage

---

**Status:** ✅ ARCHITECTURE CORRECTED
**Impact:** Implementation priorities clarified
**Author:** Claude Code
**Date:** 2025-11-12

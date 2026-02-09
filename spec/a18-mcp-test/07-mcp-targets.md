# Problem: MCP Test Target Rationalization

**Status**: Problem Definition
**Sprint**: A18
**Date**: 2026-02-07
**Context**: [A18 Sprint Design](../a18-design.md)

---

## Problem Statement

The `make.dev` file contains 10 different MCP testing targets with overlapping functionality, unclear naming, and redundant execution paths. This creates confusion about which test to run, duplicates maintenance effort, and makes the testing infrastructure harder to understand and evolve.

---

## Current State

### Test Targets in `make.dev` (lines 150-234)

```makefile
test-mcp                # Standard MCP tests (local, stdio)
test-mcp-local          # Explicit local mode with verbose
test-mcp-docker         # Docker mode with verbose
test-orchestrator       # Compare stdio vs HTTP+JWT
test-stateless          # Pytest on tests/stateless/
test-mcp-stateless      # Docker + HTTP+JWT stateless
test-multiuser          # Pytest on tests/func/test_multiuser.py
test-multiuser-fake     # Docker + HTTP+JWT multiuser dev
```

### Supporting Infrastructure

**Test Scripts**:
- `scripts/tests/test_mcp.py` (737 lines) - Server orchestration
- `scripts/mcp-test.py` (1,988 lines) - Core test logic (stdio + HTTP)
- `scripts/mcp-test-setup.py` (1,459 lines) - Config generation
- `scripts/test-multiuser.py` (511 lines) - Multiuser HTTP testing
- `scripts/docker_manager.py` (~300 lines) - Docker management

**Test Configurations**:
- `scripts/tests/mcp-test.yaml` (auto-generated, ~72KB)
- `scripts/tests/mcp-test-multiuser.yaml` (manual)

---

## Problems Identified

### 1. **Target Redundancy**

**Issue**: Multiple targets execute essentially the same tests in slightly different ways.

**Examples**:
- `test-mcp` vs `test-mcp-local` - Both run local stdio tests, difference is only verbosity flag
- `test-mcp-docker` - Same tests as above but in Docker container
- All three use identical test logic from `mcp-test.py`

**Impact**: Users unsure which to run during development vs CI vs release validation.

---

### 2. **Naming Inconsistency**

**Issue**: Target names don't follow clear patterns, making it hard to infer functionality.

**Examples**:
- `test-mcp` (local stdio)
- `test-mcp-local` (local stdio, verbose)
- `test-mcp-docker` (docker stdio, verbose)
- `test-mcp-stateless` (docker HTTP+JWT)
- `test-multiuser-fake` (docker HTTP+JWT)

**Confusion**:
- Why is `test-mcp` not explicit about being "local"?
- Why does `-local` suffix mean "verbose" not just "local execution"?
- Why `-stateless` vs `-multiuser-fake` when both use HTTP+JWT?
- What's the difference between `test-multiuser` (pytest) and `test-multiuser-fake` (HTTP)?

---

### 3. **Transport Mode Ambiguity**

**Issue**: Not clear which targets use stdio vs HTTP, making it hard to understand what's being tested.

**Transport Breakdown**:
```
stdio:     test-mcp, test-mcp-local, test-mcp-docker
HTTP+JWT:  test-mcp-stateless, test-multiuser-fake, test-orchestrator (both)
pytest:    test-stateless, test-multiuser, test-scripts
```

**Impact**:
- Users don't know if they're testing local stdio integration vs HTTP deployment
- No clear way to run "all HTTP tests" or "all stdio tests"

---

### 4. **Docker Management Duplication**

**Issue**: Two separate Docker orchestration systems with different interfaces.

**System 1**: `test_mcp.py` contains `DockerMCPServer` class
- Purpose: Manage Docker containers for stdio testing
- Interface: Python class with start/stop methods
- Usage: `test-mcp-docker` target

**System 2**: `scripts/docker_manager.py` standalone script
- Purpose: Manage Docker containers for HTTP testing
- Interface: CLI tool with start/stop commands
- Usage: `test-mcp-stateless`, `test-multiuser-fake` targets

**Impact**:
- Duplicate container lifecycle management code
- Inconsistent behavior between stdio and HTTP Docker modes
- Maintenance burden of keeping two systems in sync

---

### 5. **Test Execution Duplication**

**Issue**: Multiple scripts contain overlapping test logic.

**Duplication**:
- `mcp-test.py` - Core test logic, supports both stdio and HTTP transports
- `test-multiuser.py` - HTTP-only test logic, duplicates tool/resource testing from `mcp-test.py`
- `test_mcp.py` - Server orchestration, contains stdio-specific logic

**Impact**:
- Tool testing logic exists in both `mcp-test.py` (ToolsTester) and `test-multiuser.py` (HTTP requests)
- Changes to test validation must be made in multiple places
- Inconsistent error handling and reporting across modes

---

### 6. **Configuration Fragmentation**

**Issue**: Two separate YAML configurations for similar purposes.

**Files**:
- `scripts/tests/mcp-test.yaml` (auto-generated)
  - 100+ tools with arguments and validation
  - 40+ resources
  - Discovered data and classification
  - Used by: `test-mcp*` targets

- `scripts/tests/mcp-test-multiuser.yaml` (manual)
  - User definitions with JWT tokens
  - Tool configurations (subset of above?)
  - Used by: `test-multiuser-fake` target

**Impact**:
- Changes to tool configurations need updates in both files
- No single source of truth for what tools/resources to test
- Manual sync required for multiuser config

---

### 7. **Pytest Integration Confusion**

**Issue**: Some targets use `pytest` directly, others use custom test runners.

**Pytest Targets**:
- `test-stateless` - pytest on `tests/stateless/`
- `test-multiuser` - pytest on `tests/func/test_multiuser.py`
- `test-scripts` - pytest on `scripts/tests/test_*.py`

**Custom Runners**:
- `test-mcp*` targets use `scripts/tests/test_mcp.py`
- `test-multiuser-fake` uses `scripts/test-multiuser.py`

**Impact**:
- Coverage metrics split across pytest and custom runners
- Inconsistent output formats
- No unified test result tracking

---

### 8. **Unclear Test Selection**

**Issue**: No clear guidance on which test to run for different scenarios.

**Common Questions**:
- "I changed a tool implementation, which test should I run?"
- "How do I test before pushing to CI?"
- "Which test validates HTTP+JWT integration?"
- "What's the minimum test for quick iteration?"
- "Which test should CI run?"

**Current State**: Users must read Make target comments or trial-and-error to discover the right test.

---

### 9. **Verbose Flag Inconsistency**

**Issue**: Some targets have explicit verbose variants, others don't.

**Explicit Verbose**:
- `test-mcp` (no verbose) vs `test-mcp-local` (with `-v`)
- `test-mcp-docker` (with `-v`)

**Implicit Verbose**:
- `test-multiuser-fake` uses `--verbose` flag
- `test-orchestrator` (verbosity unclear)

**Impact**:
- Inconsistent debugging experience
- Users unsure how to get detailed output for failing tests

---

### 10. **Test Orchestrator Unclear Purpose**

**Issue**: `test-orchestrator` target's purpose is not clear from name or comments.

**Comment**: "Test orchestrator - compare stdio vs HTTP+JWT modes"

**Questions**:
- What does "compare" mean? Side-by-side diff? Validation that both work?
- When should this be run vs regular tests?
- Is this for CI or manual validation?
- How does it relate to other test targets?

**Impact**: Target is likely underused because purpose is unclear.

---

## Scope

### In Scope

Problems related to Make test targets:
- Target naming and organization
- Redundant target definitions
- Unclear purpose and usage
- Transport mode confusion
- Docker orchestration duplication

### Out of Scope

The following are NOT problems to solve:
- Test script internals (`mcp-test.py`, `test_mcp.py` implementation)
- Test configuration generation (`mcp-test-setup.py`)
- Test coverage validation logic
- Pytest test files themselves
- CI/CD pipeline configuration
- Test execution performance optimization

---

## Impact Assessment

### User Impact (Developers)

**Daily Development**:
- Confusion about which test to run → slower iteration
- Running wrong test → missing bugs or over-testing
- Verbose flag inconsistency → harder debugging

**Onboarding**:
- New contributors overwhelmed by 10 test targets
- Unclear documentation → trial-and-error learning
- Redundant targets suggest technical debt

### Maintainer Impact

**Code Maintenance**:
- Duplicate Docker management → double the bug surface
- Split test logic → changes require multiple file edits
- Configuration fragmentation → inconsistent behavior

**Evolution**:
- Adding new test modes unclear where to integrate
- Refactoring difficult due to coupling
- Technical debt accumulation

---

## Success Criteria

A successful rationalization would achieve:

1. **Clear naming** - Target names clearly indicate what they test
2. **No redundancy** - Each target serves distinct purpose
3. **Obvious selection** - Users can quickly choose right test for their scenario
4. **Unified orchestration** - Single Docker management system
5. **Consolidated config** - Single source of truth for test configuration
6. **Consistent verbosity** - Predictable way to get detailed output
7. **Better documentation** - Self-documenting target names and comments

---

## Related Work

- **Phase 3 Discovery**: [spec/a18-mcp-test/05-discovery-orchestrator.md](05-discovery-orchestrator.md) - Recent improvements to test generation
- **Test Infrastructure**: [spec/a11-client-testing/](../a11-client-testing/) - Original MCP testing design
- **Coverage Validation**: Implemented in `mcp-test.py` (100% tool coverage enforcement)

---

## Notes

- This document defines problems only, not solutions
- Solution design will be documented separately
- Focus is on Make target organization, not test script implementation
- Docker management duplication may warrant separate refactoring task

<!-- markdownlint-disable MD013 -->
# Story 1: Fix DXT Reliability Issues

## Story Summary

**As a** DXT maintainer  
**I want** to fix the core DXT functionality issues discovered during comprehensive testing  
**So that** customers receive working DXT packages that properly integrate with Claude Desktop

## Problem Context

### QA Testing Results

The comprehensive testing framework implemented in **story-1-comprehensive-dxt-testing.md** has revealed what appear to be actual DXT bugs, not just test issues. These could be the real DXT functionality problems we were concerned about originally.

**Critical Issues Discovered:**

- MCP integration import errors suggest DXT packaging/structure problems
- NPX dependency issues may reveal environment compatibility bugs
- Test failures are exposing real DXT runtime issues that would affect customers
- The underlying DXT functionality has problems beyond "fixing tests"

### Root Cause Analysis Required

The testing has exposed potential issues in:

1. **DXT Package Structure**: Import errors in `dxt_main.py` suggest bundling problems
2. **Bootstrap Environment Setup**: NPX dependency resolution failures
3. **MCP Protocol Integration**: Communication issues with stdio transport
4. **Python Module Resolution**: Path configuration problems in bundled environment

## Acceptance Criteria

### AC1: Fix DXT Import and Module Resolution Issues

- [ ] Analyze and fix `from quilt_mcp.utils import run_server` import failures in `dxt_main.py`
- [ ] Ensure proper Python path configuration for bundled dependencies in `lib/` directory
- [ ] Verify all required modules are properly bundled in the `.dxt` package structure
- [ ] Fix any missing `__init__.py` files or module structure issues
- [ ] Test import resolution in clean environments without source dependencies

### AC2: Resolve NPX and Environment Dependencies

- [ ] Fix NPX `@anthropic-ai/dxt` CLI dependency resolution issues
- [ ] Ensure DXT package can be executed via `npx @anthropic-ai/dxt run package.dxt`
- [ ] Resolve any Node.js version compatibility issues
- [ ] Fix environment variable propagation to bundled Python processes
- [ ] Test DXT execution across different system configurations

### AC3: Fix MCP Protocol Communication Issues

- [ ] Resolve stdio transport setup issues in DXT environment
- [ ] Fix MCP handshake failures and timeout issues
- [ ] Ensure proper JSON-RPC protocol communication via stdin/stdout
- [ ] Fix any stdout contamination that breaks MCP protocol
- [ ] Verify tool discovery and execution work through MCP interface

### AC4: Fix Bootstrap Environment Creation

- [ ] Resolve virtual environment creation issues in `bootstrap.py`
- [ ] Fix dependency installation failures (quilt3, fastmcp, mcp, boto3, httpx)
- [ ] Ensure proper Python executable permissions and execution
- [ ] Fix any issues with dependency version conflicts
- [ ] Test bootstrap process in restricted permission environments

### AC5: Fix Package Integrity and Build Issues

- [ ] Verify DXT package structure matches expected format
- [ ] Fix any issues with `manifest.json` configuration
- [ ] Ensure all required files are properly included in the package
- [ ] Fix any file permission issues after extraction
- [ ] Validate package checksums and integrity

## Technical Investigation Plan

### Phase 1: Import and Module Resolution Analysis

**Files to Examine:**

- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/assets/dxt_main.py`
- `/Users/ernest/GitHub/quilt-mcp-server/app/quilt_mcp/utils.py`
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/Makefile` (dependency bundling process)
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/build/` (built package structure)

**Investigation Steps:**

1. Examine the path setup in `dxt_main.py` lines 7-10
2. Verify the `$(APP_MARKER)` target in Makefile properly copies quilt_mcp module
3. Check if `__init__.py` files are present in bundled module structure
4. Test import resolution in the build directory before packaging

### Phase 2: Environment and NPX Integration Analysis

**Files to Examine:**

- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/assets/bootstrap.py`
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/assets/manifest.json`
- Test failure logs from MCP integration tests

**Investigation Steps:**

1. Analyze NPX execution command in test files
2. Verify `@anthropic-ai/dxt` CLI compatibility with current package format
3. Check environment variable handling in bootstrap process
4. Test package execution in isolated environments

### Phase 3: MCP Protocol Integration Analysis

**Test Files to Review:**

- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/tests/mcp_integration/test_mcp_handshake.py`
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/tests/mcp_integration/test_tool_discovery.py`
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/tests/mcp_integration/test_tool_execution.py`

**Investigation Steps:**

1. Run the MCP tests to capture actual error messages
2. Test stdio transport setup manually with DXT package
3. Verify tool registration and discovery process
4. Check for stdout contamination breaking JSON-RPC protocol

### Phase 4: Bootstrap and Dependency Analysis

**Files to Examine:**

- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/tests/package/test_bootstrap_execution.py`
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/tests/package/test_dxt_loading.py`

**Investigation Steps:**

1. Test bootstrap.py execution in clean temporary environments
2. Verify dependency installation process (pip install commands)
3. Check virtual environment creation and Python executable setup
4. Test with different Python versions and system configurations

## Context Files for Dev Agent

### Primary Story Context

- `/Users/ernest/GitHub/quilt-mcp-server/docs/epics/dxt-reliability/story-1-comprehensive-dxt-testing.md` - Original comprehensive testing framework implementation

### QA Results (if available)

- Look for `story-1-qa.md` in the docs/epics/dxt-reliability/ directory for detailed QA findings

### Core DXT Implementation Files

- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/assets/dxt_main.py` - Main DXT entry point (import issues)
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/assets/bootstrap.py` - Environment setup (NPX issues)
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/assets/manifest.json` - DXT configuration
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/Makefile` - Build process (bundling issues)

### Source Dependencies

- `/Users/ernest/GitHub/quilt-mcp-server/app/quilt_mcp/utils.py` - Module being imported by dxt_main.py
- `/Users/ernest/GitHub/quilt-mcp-server/app/quilt_mcp/tools/__init__.py` - Tool modules structure

### Test Files Revealing Issues

- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/tests/mcp_integration/test_mcp_handshake.py`
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/tests/mcp_integration/test_tool_discovery.py`
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/tests/package/test_dxt_main_startup.py`
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/tests/package/test_bootstrap_execution.py`
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/tests/package/test_dxt_loading.py`

### Build Artifacts to Examine

- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/build/` - Built package contents before DXT packaging
- `/Users/ernest/GitHub/quilt-mcp-server/tools/dxt/dist/` - Final DXT packages to test

## Priority and Dependencies

### Priority: P0 Critical

These are blocking issues that prevent DXT from functioning in customer environments.

### Dependencies

- Must have failing tests to reproduce issues
- Requires access to build environment and NPX CLI
- Needs ability to create and test DXT packages

### Execution Order

1. **Start with Import Issues** - Fix the foundational module resolution problems
2. **Environment Setup** - Fix bootstrap and NPX integration
3. **MCP Protocol** - Fix communication issues once basic execution works
4. **Package Integrity** - Ensure proper bundling and structure
5. **Comprehensive Testing** - Validate all fixes with existing test suite

## Technical Requirements

### Development Environment Setup

```bash
# Ensure required tools are available
cd /Users/ernest/GitHub/quilt-mcp-server/tools/dxt
make check-tools

# Build current DXT package to examine issues
make build

# Run specific test categories to reproduce issues
make test-dxt-package
make test-mcp-integration
```

### Investigation Commands

```bash
# Test package integrity
npx @anthropic-ai/dxt info dist/quilt-mcp-*.dxt

# Test manual execution
npx @anthropic-ai/dxt run dist/quilt-mcp-*.dxt

# Examine build contents
ls -la build/
python -c "import sys; sys.path.insert(0, 'build'); import dxt_main"
```

## Expected Outcomes

### Functional DXT Package

- DXT package successfully loads via NPX CLI
- All imports resolve correctly in bundled environment
- MCP handshake and tool discovery work properly
- Bootstrap creates functional Python environment

### Reliable Customer Experience

- DXT works in clean customer environments
- Error messages are clear and actionable
- Performance meets established benchmarks
- Package integrity validates correctly

### Test Suite Validation

- All P0 critical tests pass consistently
- MCP integration tests demonstrate end-to-end functionality
- Environment simulation tests validate customer compatibility

## Risks and Mitigations

### Risk 1: Deep architectural issues requiring significant refactoring

**Mitigation**: Start with minimal fixes, escalate to architecture review if needed
**Fallback**: Document limitations and provide workaround instructions

### Risk 2: NPX/Node.js compatibility issues across environments

**Mitigation**: Test across multiple Node.js versions, document requirements
**Fallback**: Provide alternative installation methods

### Risk 3: MCP protocol changes breaking compatibility

**Mitigation**: Verify MCP protocol version compatibility, update if needed
**Fallback**: Support multiple MCP protocol versions

## Definition of Done

- [ ] All import errors in DXT package resolved
- [ ] NPX execution works across test environments
- [ ] MCP handshake and tool discovery functional
- [ ] Bootstrap process creates working Python environment
- [ ] Package structure and integrity validated
- [ ] P0 critical tests pass consistently
- [ ] Customer environment simulation tests pass
- [ ] Documentation updated with any new requirements or limitations

## Success Metrics

- **Import Resolution**: 100% success rate for module imports in DXT environment
- **NPX Execution**: DXT packages execute successfully via `npx @anthropic-ai/dxt run`
- **MCP Integration**: Complete MCP handshake and tool discovery within 10 seconds
- **Bootstrap Success**: Python environment creation succeeds in >95% of test scenarios
- **Test Pass Rate**: All P0 tests pass, >90% of P1 tests pass
- **Customer Readiness**: DXT packages work in simulated customer environments

---

**Story Type**: Bug Fix  
**Epic**: DXT Reliability Enhancement  
**Estimate**: 13 story points (complex cross-system debugging)  
**Priority**: P0 Critical  
**Blocking**: Customer DXT deployments  
**Created**: 2025-01-03  
**Status**: Ready for Implementation

---

## For Dev Agent Implementation

**Start Here**: Begin by running the existing test suite to reproduce the issues:

```bash
cd /Users/ernest/GitHub/quilt-mcp-server/tools/dxt
make test-dxt-package
make test-mcp-integration
```

**Focus Areas**: The most likely issues are in:

1. Python path setup in `dxt_main.py`
2. Module bundling process in `Makefile`
3. NPX CLI compatibility with current package format
4. MCP stdio transport configuration

**Expected Failures**: Look for ImportError, ModuleNotFoundError, NPX execution failures, and MCP timeout issues in the test output.

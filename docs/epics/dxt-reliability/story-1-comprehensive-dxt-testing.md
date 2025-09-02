<!-- markdownlint-disable MD013 -->
# Story 1: Comprehensive DXT Testing Framework

## Story Summary

**As a** DXT maintainer  
**I want** comprehensive testing of the actual bundled DXT package in Claude Desktop  
**So that** we can catch DXT configuration and integration issues before customers receive broken packages

## Story Details

### Current State Analysis

**Existing DXT Testing:**

- `tools/dxt/Makefile` has basic `make test` target that only tests bootstrap import
- No testing of the actual packaged `.dxt` file that customers receive
- No validation that the DXT works correctly when loaded by Claude Desktop
- Build failures often discovered after customer deployment when DXT fails to load

**Critical Gap - The Real Issue:**

- We build `.dxt` packages but never test them as bundled DXT configurations
- No validation that `manifest.json`, `bootstrap.py`, and `dxt_main.py` work together correctly
- No testing of the DXT package in the actual Claude Desktop MCP client environment
- Missing validation that the bundled configuration properly communicates via stdio transport

### Acceptance Criteria

#### AC1: Actual DXT Package Testing

- [ ] Add `make test-dxt-package` target that tests the built `.dxt` file directly
- [ ] Load the actual DXT package using `@anthropic-ai/dxt` CLI and validate it starts
- [ ] Test that the bundled `manifest.json` is valid and properly configured
- [ ] Verify that `bootstrap.py` creates the environment and loads dependencies correctly
- [ ] Validate that `dxt_main.py` properly initializes the MCP server with stdio transport

#### AC2: Claude Desktop MCP Integration Testing

- [ ] Simulate Claude Desktop MCP client communication with the bundled DXT
- [ ] Test the complete MCP handshake, tool discovery, and tool execution flow
- [ ] Validate that all 84+ tools are properly registered and callable through the DXT
- [ ] Test error handling when DXT encounters issues during operation
- [ ] Verify proper cleanup when DXT is terminated

#### AC3: DXT Configuration Validation

- [ ] Test that different DXT configurations (with/without authentication) work correctly
- [ ] Validate that environment variables are properly passed to the bundled server
- [ ] Test DXT behavior with different Claude Desktop versions (if applicable)
- [ ] Verify that DXT logging doesn't interfere with MCP protocol communication

#### AC4: Customer Environment Simulation

- [ ] Test DXT package in clean environments (no existing Python/dependencies)
- [ ] Validate DXT works with different Python versions available on system
- [ ] Test common customer failure scenarios (permission issues, network restrictions)
- [ ] Verify DXT package integrity and checksums before testing

### Technical Approach

#### DXT Package Testing Architecture

```text
tools/dxt/tests/
├── package/                     # Test the actual built .dxt package
│   ├── test_dxt_loading.py     # Test DXT package loads correctly
│   ├── test_manifest_validity.py # Validate manifest.json configuration
│   ├── test_bootstrap_execution.py # Test bootstrap.py in clean environment
│   └── test_dxt_main_startup.py   # Test dxt_main.py MCP server startup
├── mcp_integration/            # Test DXT as MCP server
│   ├── test_mcp_client_communication.py # Simulate Claude Desktop communication
│   ├── test_tool_discovery.py  # Test all tools are discoverable via DXT
│   ├── test_tool_execution.py  # Test tools work through DXT package
│   └── fixtures/               # MCP protocol test fixtures
├── environments/               # Test DXT in different environments
│   ├── test_clean_environment.py # Test in environment with no dependencies
│   ├── test_python_versions.py   # Test with different Python versions
│   └── test_restricted_permissions.py # Test with limited permissions
└── validation/                 # DXT package validation
    ├── test_package_integrity.py # Test DXT package checksums and structure
    └── test_configuration_variants.py # Test different DXT configurations
```

#### New Makefile Targets

```makefile
# Add to tools/dxt/Makefile
test-dxt-package: build
 @echo "Testing the actual built DXT package..."
 cd tests && python -m pytest package/ -v

test-mcp-integration: build
 @echo "Testing DXT as MCP server with simulated Claude Desktop..."
 cd tests && python -m pytest mcp_integration/ -v

test-environments: build
 @echo "Testing DXT in different customer environments..."
 cd tests && python -m pytest environments/ -v

test-dxt-comprehensive: test test-dxt-package test-mcp-integration test-environments
 @echo "All DXT package tests completed successfully"
```

### Implementation Details

#### Phase 1: DXT Package Loading and Validation

1. **Test actual DXT package loading**:
   ```python
   # Test that built .dxt package can be loaded by @anthropic-ai/dxt CLI
   def test_dxt_package_loads():
       dxt_path = "build/quilt-mcp-server.dxt"
       result = subprocess.run(["npx", "@anthropic-ai/dxt", "validate", dxt_path])
       assert result.returncode == 0
   ```

2. **Validate DXT configuration components**:
   - Test `manifest.json` has correct MCP server configuration
   - Verify `bootstrap.py` executes successfully in clean environment
   - Test `dxt_main.py` starts MCP server with proper stdio transport

#### Phase 2: Claude Desktop MCP Integration Testing

1. **Simulate Claude Desktop MCP client**:
   ```python
   # Test DXT communicates correctly with MCP client via stdio
   def test_mcp_client_communication():
       dxt_process = start_dxt_package()  # Start the actual .dxt package
       mcp_client = MCPTestClient(dxt_process.stdin, dxt_process.stdout)
       
       # Test MCP handshake
       response = mcp_client.initialize()
       assert response["capabilities"]["tools"] is not None
       
       # Test tool discovery
       tools = mcp_client.list_tools()
       assert len(tools) >= 84  # Verify all tools are registered
   ```

2. **End-to-end tool execution testing**:
   - Test that tools can be invoked through the DXT package
   - Verify tool responses are properly formatted for MCP protocol
   - Test error handling when tools fail or encounter issues

#### Phase 3: Customer Environment Testing

1. **Clean environment testing**:
   ```python
   # Test DXT package works in environment with no pre-existing dependencies
   def test_clean_environment_installation():
       with TemporaryDirectory() as temp_dir:
           # Copy DXT package to clean directory
           # Test that bootstrap.py creates venv and installs dependencies
           # Verify DXT starts correctly without any pre-existing setup
   ```

2. **Different Python version testing**:
   - Test DXT package with Python 3.11, 3.12, etc.
   - Verify graceful failure with unsupported Python versions
   - Test that DXT finds and uses correct Python executable

### Dependencies

**External Dependencies:**

- `@anthropic-ai/dxt` CLI for DXT package validation and testing
- pytest framework (already in use)
- MCP client testing library or custom MCP test harness
- Docker (for clean environment testing)

**Internal Dependencies:**

- Built `.dxt` package from existing `tools/dxt/Makefile` system
- Current `bootstrap.py`, `dxt_main.py`, and `manifest.json` assets
- Actual MCP server code in `app/quilt_mcp/` (as bundled in DXT)

### Risks and Mitigations

**Risk 1: DXT package testing requires complex setup and dependencies**

- **Mitigation**: Use existing `@anthropic-ai/dxt` CLI, create reusable test fixtures
- **Fallback**: Start with basic DXT loading tests, expand gradually

**Risk 2: MCP protocol testing is complex and may be flaky**

- **Mitigation**: Create robust MCP test client, use timeouts and retries
- **Fallback**: Focus on DXT package validation first, add MCP testing incrementally

**Risk 3: Testing actual DXT packages significantly increases build time**

- **Mitigation**: Make DXT package testing optional separate target, run in parallel
- **Fallback**: Implement fast smoke tests vs. comprehensive validation modes

### Definition of Done

- [ ] DXT package loading and validation tests implemented
- [ ] MCP client simulation tests verify actual DXT functionality
- [ ] Customer environment tests validate DXT works in clean environments
- [ ] New test targets integrated into `tools/dxt/Makefile`
- [ ] All tests validate the actual built `.dxt` package, not just source code
- [ ] Existing DXT build workflow continues to function unchanged

### Success Metrics

- **DXT Package Validation**: 100% of built DXT packages pass loading and startup tests
- **MCP Integration**: All 84+ tools discoverable and executable through DXT package
- **Environment Compatibility**: DXT package works in >95% of tested customer environments
- **Build Reliability**: 0% DXT packages released that fail basic functionality tests

---

**Story Type**: Enhancement  
**Epic**: DXT Reliability Enhancement  
**Estimate**: 5 story points  
**Priority**: High  
**Created**: 2025-01-02

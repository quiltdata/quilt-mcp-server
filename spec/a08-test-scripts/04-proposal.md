# Systematic MCP Testing Infrastructure Fix

## Date
2025-11-12

## Status
🟢 **PROPOSED** - Comprehensive plan to fix and validate MCP test infrastructure

## Problem Summary

The MCP integration test suite (`scripts/tests/test_mcp.py`) is completely failing with "Invalid request parameters" errors on all tool calls. While the stdio transport successfully initializes, all `tools/call` requests fail with JSON-RPC error code -32602.

**Current State:**
- ✅ Docker container starts successfully
- ✅ Stdio transport connects and initializes
- ❌ All 22 tool calls fail with identical error
- ❌ No detailed error information from server

## Root Cause Analysis

### Known Facts

1. **Initialize works**: The MCP server accepts and responds to `initialize` requests correctly
2. **Consistent failure**: All tools fail with the same error, suggesting protocol/format issue
3. **No error details**: Server returns `"data": ""` with no additional context
4. **Format matches fixtures**: Our request format matches `tests/fixtures/runners/llm_mcp_test.py`

### Hypothesis: Parameter Structure Mismatch

The JSON-RPC error code `-32602` ("Invalid params") suggests:
- Wrong parameter nesting structure
- Missing required fields
- Incorrect field names for MCP protocol version

## Systematic Approach

### Phase 1: Protocol Discovery (Investigation)

**Goal:** Understand the correct MCP protocol format for `tools/call`

**Tasks:**
1. **Check MCP specification**
   - Read official MCP protocol docs for `tools/call` format
   - Verify parameter structure for protocol version 2024-11-05
   - Find official examples of tool call requests

2. **Inspect FastMCP source code**
   - Clone/examine FastMCP library
   - Find `tools/call` handler implementation
   - Identify expected parameter schema
   - Check for any version-specific differences

3. **Test with MCP SDK**
   - Install official `@modelcontextprotocol/sdk` (TypeScript)
   - Create minimal client that calls a tool
   - Capture exact JSON-RPC messages it sends
   - Compare with our current format

4. **Verify tool registration**
   - Call `tools/list` before attempting `tools/call`
   - Confirm tools are registered with expected schemas
   - Check if tool schemas reveal parameter structure

**Deliverables:**
- Document with correct `tools/call` format
- Comparison table: our format vs. correct format
- Test cases showing working vs. broken requests

### Phase 2: Test Infrastructure Hardening

**Goal:** Create robust test infrastructure with clear diagnostics

**Tasks:**
1. **Enhanced logging and diagnostics**
   ```python
   # Add to test_mcp.py:
   - Log full request/response for each test
   - Capture and display container stderr in real-time
   - Add --debug flag for verbose protocol tracing
   - Save test artifacts (requests/responses) to files
   ```

2. **Protocol validation layer**
   ```python
   # New module: scripts/mcp_protocol.py
   - JSON schema validation for requests
   - Helper functions for building MCP messages
   - Protocol version compatibility checks
   - Error message decoder
   ```

3. **Incremental test progression**
   ```python
   # Test phases:
   Phase 1: Initialize only
   Phase 2: tools/list
   Phase 3: Single simple tool (no args)
   Phase 4: Single tool with args
   Phase 5: All tools
   ```

4. **Better error reporting**
   ```python
   # When tests fail, show:
   - Full request that was sent
   - Full response received
   - Expected vs. actual format comparison
   - Suggested fixes based on error code
   - Link to relevant protocol docs
   ```

**Deliverables:**
- Enhanced `test_mcp.py` with detailed diagnostics
- New `mcp_protocol.py` validation module
- Test output that clearly shows what's wrong
- Debug mode that saves all protocol messages

### Phase 3: Baseline Validation

**Goal:** Establish a working baseline with known-good implementation

**Tasks:**
1. **Manual protocol testing**
   ```bash
   # Create standalone script: scripts/test-protocol.sh
   # Tests each protocol message independently:
   echo '{"jsonrpc":"2.0","id":1,"method":"initialize",...}' | docker run -i ...
   echo '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | docker run -i ...
   echo '{"jsonrpc":"2.0","id":3,"method":"tools/call",...}' | docker run -i ...
   ```

2. **Reference implementation comparison**
   - Test against known-working MCP server (if available)
   - Compare request/response formats
   - Document any differences in our server's behavior

3. **Unit tests for protocol helpers**
   ```python
   # tests/unit/test_mcp_protocol.py
   def test_build_initialize_request():
       request = build_initialize_request(...)
       assert validate_mcp_request(request)

   def test_build_tool_call_request():
       request = build_tool_call_request("tool_name", {"arg": "value"})
       assert validate_mcp_request(request)
   ```

**Deliverables:**
- Manual test script that confirms protocol messages
- Unit tests for protocol message builders
- Documentation of working message formats
- Comparison with reference implementations

### Phase 4: Fix Implementation

**Goal:** Correct the protocol format and fix all tests

**Tasks:**
1. **Update request format**
   ```python
   # Based on Phase 1 findings, update:
   def build_tool_call_request(tool_name: str, arguments: dict):
       # Use correct format discovered in Phase 1
       return {
           "jsonrpc": "2.0",
           "id": request_id,
           "method": "tools/call",
           "params": {
               # CORRECT STRUCTURE HERE
           }
       }
   ```

2. **Update test suite**
   - Modify `run_tests_stdio()` to use correct format
   - Update test configuration if needed
   - Add validation before sending requests

3. **Verify all tools**
   - Run full test suite with corrected format
   - Verify both idempotent and non-idempotent tools
   - Test with various argument types (strings, numbers, objects)

**Deliverables:**
- Fixed `test_mcp.py` with correct protocol
- All 22 tools passing in test suite
- Documentation of corrections made
- Before/after comparison

### Phase 5: Documentation and CI Integration

**Goal:** Ensure tests are maintainable and run automatically

**Tasks:**
1. **Update documentation**
   - Document correct MCP protocol usage
   - Update test suite README
   - Add troubleshooting guide
   - Document common failure modes

2. **CI/CD integration**
   ```yaml
   # .github/workflows/test-mcp.yml
   - name: Run MCP integration tests
     run: make test-scripts
   - name: Upload test artifacts
     if: failure()
     uses: actions/upload-artifact@v3
     with:
       name: mcp-test-logs
       path: scripts/tests/logs/
   ```

3. **Monitoring and alerts**
   - Add test result reporting
   - Track test execution time
   - Alert on regression

**Deliverables:**
- Updated documentation in `spec/` and `scripts/tests/README.md`
- CI workflow for automated testing
- Test result reporting
- Troubleshooting guide

## Success Criteria

### Must Have (P0)
- [ ] All 22 idempotent tools pass in test suite
- [ ] Clear documentation of correct MCP protocol format
- [ ] Tests run successfully in CI/CD
- [ ] Comprehensive error messages when tests fail

### Should Have (P1)
- [ ] Protocol validation layer prevents invalid requests
- [ ] Debug mode provides detailed diagnostics
- [ ] Manual test scripts for protocol verification
- [ ] Unit tests for protocol helpers

### Nice to Have (P2)
- [ ] Test execution time < 2 minutes
- [ ] Parallel tool testing for speed
- [ ] Performance metrics tracking
- [ ] Comparison with other MCP implementations

## Timeline Estimate

| Phase | Estimated Time | Dependencies |
|-------|---------------|--------------|
| 1. Protocol Discovery | 2-3 hours | MCP docs, FastMCP source |
| 2. Test Infrastructure | 2-3 hours | Phase 1 findings |
| 3. Baseline Validation | 1-2 hours | Phases 1, 2 |
| 4. Fix Implementation | 1-2 hours | Phase 3 baseline |
| 5. Documentation/CI | 1-2 hours | Phase 4 working tests |
| **Total** | **7-12 hours** | Sequential execution |

## Resource Requirements

### Tools Needed
- Docker with `quilt-mcp:test` image built
- Python 3.11+ with dependencies
- Node.js (for official MCP SDK testing)
- Git access to FastMCP repository

### Access Required
- AWS credentials for testing (read-only sufficient)
- Quilt catalog access (demo or staging)
- GitHub for CI/CD workflow updates

### Documentation
- MCP protocol specification: https://spec.modelcontextprotocol.io
- FastMCP repository: https://github.com/jlowin/fastmcp
- Quilt MCP server docs: `docs/`

## Risk Assessment

### High Risk
- **Protocol mismatch more complex than expected**
  - Mitigation: Phase 1 focuses on discovery before implementation
  - Fallback: Test against reference implementation first

### Medium Risk
- **FastMCP has bugs/limitations**
  - Mitigation: Consider alternative MCP server library
  - Fallback: HTTP transport if stdio is fundamentally broken

### Low Risk
- **Tests take too long to run**
  - Mitigation: Parallel execution, selective testing
  - Fallback: Acceptable if comprehensive

## Alternatives Considered

### Alternative 1: Switch to HTTP Transport
**Pros:**
- More documentation available
- Web-based tools can test it
- Might have better error messages

**Cons:**
- Session management issues (documented in 02-mcp-http-session-issue.md)
- More complex infrastructure
- Not how Claude Desktop uses MCP

**Decision:** Stick with stdio, it's the correct long-term approach

### Alternative 2: Use Different MCP Server Library
**Pros:**
- Might have clearer error messages
- Could have better documentation
- May be more actively maintained

**Cons:**
- Major refactor of server code
- Unknown if it would solve the issue
- FastMCP is specifically designed for Python

**Decision:** Fix current implementation first, consider alternative if systematic debugging fails

### Alternative 3: Skip Integration Tests
**Pros:**
- Unblocks development
- Unit tests still provide coverage

**Cons:**
- No end-to-end validation
- Can't catch integration issues
- Reduces confidence in releases

**Decision:** Not acceptable, integration tests are critical

## Execution Plan

### Orchestration Strategy

Use **workflow-orchestrator** agent to:
1. Execute phases sequentially with dependencies
2. Track progress through workflow steps
3. Collect artifacts from each phase
4. Make go/no-go decisions between phases
5. Report comprehensive results

### Workflow Structure

```yaml
workflow_id: mcp-test-fix-2025-11-12
name: Systematic MCP Test Infrastructure Fix

steps:
  - id: phase1-protocol-discovery
    description: Discover correct MCP protocol format
    type: research
    dependencies: []

  - id: phase2-test-infrastructure
    description: Build robust test infrastructure
    type: development
    dependencies: [phase1-protocol-discovery]

  - id: phase3-baseline-validation
    description: Establish working baseline
    type: validation
    dependencies: [phase1-protocol-discovery, phase2-test-infrastructure]

  - id: phase4-fix-implementation
    description: Implement protocol fixes
    type: development
    dependencies: [phase3-baseline-validation]

  - id: phase5-documentation
    description: Document and integrate with CI
    type: documentation
    dependencies: [phase4-fix-implementation]
```

## Expected Outcomes

### Immediate (End of Day 1)
- Understand correct MCP protocol format
- Have working test infrastructure with good diagnostics
- At least 1 tool working correctly

### Short Term (End of Week)
- All 22 idempotent tools passing
- Tests running in CI/CD
- Documentation updated

### Long Term (Ongoing)
- Stable test suite with <1% flake rate
- Fast feedback loop (<2 min test execution)
- Clear diagnostics when issues occur

## References

- [MCP Protocol Specification](https://spec.modelcontextprotocol.io)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Previous Investigation: HTTP Session Issues](./02-mcp-http-session-issue.md)
- [Current Investigation: Stdio Approach](./03-stdio-transport-approach.md)
- [Original Test Design](./01-test-mcp.md)

---

**Author:** Systematic analysis of MCP test infrastructure issues
**Status:** Ready for execution via workflow orchestrator
**Priority:** P0 - Blocking releases and development confidence
**Last Updated:** 2025-11-12

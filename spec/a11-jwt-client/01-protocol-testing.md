# MCP Protocol Compliance Testing Integration

**Status**: Draft
**Created**: 2026-01-29
**PR Reference**: [#218 - Add MCP JSON-RPC 2.0 protocol compliance validation](https://github.com/quiltdata/quilt-mcp-server/pull/218)
**Objective**: Integrate comprehensive MCP protocol validation into CI/CD pipeline to catch protocol violations early

## Problem Statement

PR #218 introduces comprehensive protocol compliance testing that validates the MCP server's implementation of:

- JSON-RPC 2.0 specification compliance
- Server-Sent Events (SSE) transport
- Session management via `mcp-session-id` headers
- Protocol method flows (initialize, tools/list)

**Current State**: The test exists in `tests/integration/test_docker_container.py` but is marked with
`@pytest.mark.skip` with reason "Requires MCP server with known protocol bug".

**IMPORTANT UPDATE (2026-01-29)**: The underlying bug **has been FIXED** in commit `d32e488`
(Jan 28, 2026)! The test is still marked as skipped, but the session management issue has been
resolved. See "Bug Status Update" section below.

**The Decision**: Should we pull in PR #218's work or re-implement it?

## Analysis: Pull vs Re-implement

### Current Codebase Status

The test from PR #218 **already exists** in the codebase at [tests/integration/test_docker_container.py:362-537](../../tests/integration/test_docker_container.py#L362-L537), including:

- Full test implementation (177 lines)
- SSE response parsing
- Session management validation
- JSON-RPC 2.0 format checking
- Clear documentation of the bug it exposes

**Conclusion**: ✅ **No need to pull from PR #218** - the code is already in `main` branch, just marked as skipped.

### What PR #218 Provides

1. **Protocol Validation Test** (`test_mcp_protocol_compliance`)
   - Already in codebase, line 362+
   - Validates HTTP transport with proper headers
   - Tests SSE (Server-Sent Events) format
   - Confirms JSON-RPC 2.0 structure
   - Tests initialize → tools/list flow

2. **Bug Discovery**
   - Identified real issue: tools/list fails with "MCP error -32602: Invalid request parameters"
   - Same error seen in MCP Inspector
   - Occurs even after successful initialize

3. **Documentation**
   - Comprehensive PR description
   - Clear test behavior explanation
   - Notes on what was validated

### Recommendation

**Do NOT pull/merge PR #218.** Instead:

1. **Use existing test** - It's already in the codebase
2. **Fix the underlying bug** - Address why tools/list fails
3. **Unskip the test** - Remove `@pytest.mark.skip` once bug is fixed
4. **Close PR #218** - Thank contributors, explain test is already incorporated

## Bug Status Update: FIXED! ✅

### The Bug Has Been Resolved (Commit d32e488, Jan 28, 2026)

**Root Cause Identified**: This was NOT a FastMCP bug, but **incorrect usage of FastMCP** in our code.

The test was failing because:

1. **Session ID passed as query parameter** (`?sessionId=...`) instead of `mcp-session-id` header
   - MCP HTTP protocol requires header format
2. **FastMCP not configured for stateless mode** - requires `stateless_http=True`
3. **SSE responses instead of JSON** - stateless mode should use `json_response=True`

**The Fix** (already merged in [src/quilt_mcp/utils.py:406](../../src/quilt_mcp/utils.py#L406)):

```python
# Check if we're running in stateless mode (for containerized deployments)
stateless_mode = os.environ.get("QUILT_MCP_STATELESS_MODE", "false").lower() == "true"

# Use JSON responses in stateless mode for simpler HTTP client integration
app = mcp.http_app(transport=transport, stateless_http=stateless_mode, json_response=stateless_mode)
```

**Status**: Bug is FIXED, but test remains skipped. Primary task now is to **verify the fix and unskip the test**.

### Original Bug Symptoms (Historical)

From the test code (line 492-514):

```python
# tools/list request with empty params
tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

# Expected: result with tools array
# Actual: error -32602 "Invalid request parameters"
```

This was caused by incorrect session management configuration, now resolved.

## Task List: Protocol Testing Integration

### Phase 1: Verify Fix and Unskip Test (UPDATED - Bug Already Fixed!)

**Note**: Original Phase 1 tasks (bug investigation/fix) are no longer needed since the bug was
fixed in commit `d32e488`. New Phase 1 focuses on verification and activation.

#### Task 1.1: Verify the Fix Works

**Goal**: Confirm the session management fix resolves the protocol test failure

**Steps**:

- [ ] Set `QUILT_MCP_STATELESS_MODE=true` in test environment
- [ ] Temporarily remove `@pytest.mark.skip` from test
- [ ] Run the protocol compliance test locally
- [ ] Check if initialize → tools/list flow works
- [ ] Verify all assertions pass
- [ ] Run test multiple times to check for flakiness

**Success Criteria**:

- ✅ Test passes without modifications
- ✅ No "Invalid request parameters" error
- ✅ tools/list returns tool array correctly
- ✅ Test runs consistently (not flaky)

**If test still fails**: Document the new failure mode and investigate why stateless mode config
isn't being applied to the test.

#### Task 1.2: Unskip the Test Permanently

**Goal**: Remove skip marker and integrate test into CI

**Steps**:

- [ ] Remove `@pytest.mark.skip(reason="Requires MCP server with known protocol bug")` line
- [ ] Update test docstring to reflect that bug is fixed
- [ ] Add comment referencing commit `d32e488` that fixed the issue
- [ ] Ensure test runs in CI with correct environment variables
- [ ] Verify test doesn't break existing CI pipeline

**Success Criteria**:

- ✅ Skip marker removed
- ✅ Test runs in CI on every commit
- ✅ No CI pipeline breakage
- ✅ Test is documented and maintainable

**Location**: [tests/integration/test_docker_container.py:363](../../tests/integration/test_docker_container.py#L363)

#### Task 1.3: Verify All MCP Methods Work in Stateless Mode

**Goal**: Ensure the fix applies to all protocol methods, not just tools/list

**Test coverage**:

- [ ] initialize (should already work)
- [ ] tools/list (primary fix target)
- [ ] tools/call (test with various tools)
- [ ] resources/list (if applicable)
- [ ] resources/read (if applicable)
- [ ] prompts/list (if implemented)

**Steps**:

- [ ] Review test coverage in existing protocol test
- [ ] Add additional test cases for methods not currently covered
- [ ] Ensure stateless mode works for all protocol flows
- [ ] Document any methods that require special handling

**Success Criteria**:

- ✅ All implemented MCP methods work in stateless mode
- ✅ No regression in existing functionality
- ✅ Session state properly maintained throughout lifecycle
- ✅ Test coverage is comprehensive

### Phase 2: Enhanced Protocol Testing

**Note**: Task 2.1 moved to Phase 1 since it's now the primary action item.

#### Task 2.2: Enhance Test Coverage

**Goal**: Add more protocol validation cases

**Additional test cases to add**:

- [ ] **Test missing Accept header** (should return 406)
- [ ] **Test invalid JSON-RPC format** (missing jsonrpc field)
- [ ] **Test mismatched request/response IDs**
- [ ] **Test method calls before initialize** (should fail)
- [ ] **Test session expiration** (if applicable)
- [ ] **Test concurrent sessions** (different session IDs)
- [ ] **Test tools/call with various parameters**
- [ ] **Test error response format** (error field structure)

**Success Criteria**:

- ✅ Edge cases covered
- ✅ Error conditions tested
- ✅ Follows MCP specification exactly
- ✅ Clear test documentation

#### Task 2.3: Add SSE Transport Validation

**Goal**: Validate Server-Sent Events format compliance

**What to test**:

- [ ] SSE `data:` line format
- [ ] SSE event stream structure
- [ ] Proper line endings (`\n\n`)
- [ ] Handling of multi-line responses
- [ ] Event IDs (if used)
- [ ] Retry intervals (if applicable)
- [ ] Connection keep-alive

**Success Criteria**:

- ✅ SSE format strictly follows spec
- ✅ Compatible with standard SSE clients
- ✅ Handles edge cases (empty events, etc.)

#### Task 2.4: Create Protocol Regression Tests

**Goal**: Prevent future protocol violations

**Test suite to create**: `tests/integration/test_protocol_regression.py`

**Tests to include**:

- [ ] JSON-RPC field presence (jsonrpc, id, method, params)
- [ ] JSON-RPC version exactly "2.0"
- [ ] Response ID matches request ID
- [ ] Error responses have error field
- [ ] Success responses have result field
- [ ] No mixing of result and error in same response
- [ ] Standard error codes (-32700, -32600, -32601, etc.)
- [ ] Session header consistency

**Success Criteria**:

- ✅ Tests catch protocol violations immediately
- ✅ Fast execution (< 30 seconds)
- ✅ Clear failure messages
- ✅ Runs on every commit

### Phase 3: Documentation and Monitoring

#### Task 3.1: Document Protocol Implementation

**Goal**: Clear documentation of MCP protocol compliance

**Documents to create**:

- [ ] `docs/MCP_PROTOCOL.md`
  - JSON-RPC 2.0 implementation details
  - SSE transport specifics
  - Session management approach
  - Supported methods and parameters
  - Error codes and meanings
  - Known limitations or extensions

- [ ] `docs/TESTING_PROTOCOL.md`
  - How to run protocol tests
  - How to add new protocol tests
  - Common protocol issues and solutions
  - Debugging protocol failures

**Success Criteria**:

- ✅ Developers understand protocol requirements
- ✅ Easy to verify compliance
- ✅ Clear troubleshooting guide

#### Task 3.2: Add Protocol Validation Metrics

**Goal**: Monitor protocol compliance in production

**Metrics to track**:

- [ ] Count of JSON-RPC 2.0 format violations
- [ ] Session management errors
- [ ] Invalid method calls
- [ ] Parameter validation failures
- [ ] SSE transport errors
- [ ] Session ID mismatches

**Implementation**:

- [ ] Add metrics to FastMCP middleware
- [ ] Log protocol violations
- [ ] Create CloudWatch dashboard
- [ ] Set up alerts for error rate spikes

**Success Criteria**:

- ✅ Protocol issues visible in metrics
- ✅ Can detect violations in production
- ✅ Historical trend data available

#### Task 3.3: Create Protocol Testing Guide for Developers

**Goal**: Make it easy to test protocol compliance during development

**Guide contents**:

- [ ] How to run protocol tests locally
- [ ] How to test with curl
- [ ] Example requests/responses for each method
- [ ] Common mistakes and how to avoid them
- [ ] Using MCP Inspector for testing
- [ ] Debugging session issues

**Location**: `docs/development/PROTOCOL_TESTING.md`

**Success Criteria**:

- ✅ Developers can validate protocol compliance before PR
- ✅ Clear examples for all scenarios
- ✅ Troubleshooting guide for common issues

### Phase 4: PR Cleanup

#### Task 4.1: Close PR #218

**Goal**: Clean up stale PR gracefully

**Steps**:

- [ ] Comment on PR thanking contributor
- [ ] Explain test is already in codebase
- [ ] Reference this spec document
- [ ] Explain bug was discovered and will be fixed
- [ ] Close PR with explanation

**Comment template**:

```markdown
Thank you for this comprehensive protocol validation test!

Great news - we've resolved the issue this test exposed:

### Test Status

Your test already exists in our main branch at `tests/integration/test_docker_container.py:362`
and was marked as skipped due to the bug it discovered.

### Bug Fixed

The underlying issue has been resolved in commit d32e488 (Jan 28, 2026). The problem was
incorrect FastMCP configuration - we weren't properly enabling stateless mode with the required
`stateless_http=True` and `json_response=True` parameters.

### What was wrong

1. Session IDs passed as query params instead of mcp-session-id headers
2. FastMCP not configured for stateless mode
3. SSE responses instead of JSON in stateless mode

### Next steps

1. Verify the fix resolves the test failures
2. Unskip the test and integrate into CI
3. Add additional protocol validation coverage

See spec/a11-jwt-client/01-protocol-testing.md for the full plan.

### Closing this PR

- The test code is already in our codebase
- The bug it discovered has been fixed
- We're now working on verification and activation

Thank you for helping us identify and fix this important protocol compliance issue!
```

**Success Criteria**:

- ✅ PR closed with clear explanation
- ✅ Contributor acknowledged
- ✅ Path forward documented

## Implementation Timeline (REVISED - Bug Already Fixed!)

**Previous estimate**: 4 weeks (assuming bug investigation and fix)
**Revised estimate**: 1-2 weeks (verification and enhancement only)

### Week 1: Verify Fix and Activate Test (PRIORITY)

**Days 1-2: Verify and unskip**
- Task 1.1: Verify the fix works (4 hours)
- Task 1.2: Unskip the test (2 hours)
- Task 1.3: Verify all methods (4 hours)

**Days 3-4: Enhanced testing**
- Task 2.2: Enhance coverage (1 day)
- Task 2.3: SSE validation (1 day)

**Day 5: PR cleanup**
- Task 4.1: Close PR #218 (2 hours)

### Week 2: Documentation and Monitoring (Optional)

**Days 1-2: Documentation**
- Task 3.1: Protocol documentation (1 day)
- Task 3.3: Developer guide (1 day)

**Day 3: Monitoring**
- Task 3.2: Add metrics (4 hours)
- Task 2.4: Regression tests (4 hours)

**Total: 1-2 weeks** depending on whether documentation/monitoring are prioritized

## Dependencies and Blockers

### Dependencies

- **FastMCP Library**: ✅ No issues - was usage error, not library bug
- **MCP Specification**: Need to reference official spec for validation
- **JWT Authentication**: Session management relates to [04-finish-jwt.md](../a10-multitenant/04-finish-jwt.md)
- **Stateless Mode Config**: Test requires `QUILT_MCP_STATELESS_MODE=true`

### Potential Blockers (UPDATED)

- ~~FastMCP library bug requiring upstream fix~~ ✅ RESOLVED - was usage error
- Test may fail if `QUILT_MCP_STATELESS_MODE` not set in test environment
- Other integration tests may not be compatible with stateless mode
- CI environment may need configuration updates

### Mitigation Strategies

- ~~Keep test skipped until fix is proven stable~~ - Fix already stable, just needs verification
- Ensure test environment properly configures stateless mode
- Run comprehensive integration suite to check for regressions
- Document stateless mode requirements clearly

## Success Criteria Summary

### Technical Success

- ✅ Protocol compliance test passes consistently
- ✅ All MCP methods work with proper session management
- ✅ SSE transport validated
- ✅ JSON-RPC 2.0 compliance verified
- ✅ No protocol regressions in CI

### Process Success

- ✅ Tests integrated into CI pipeline
- ✅ Documentation complete
- ✅ Developers can easily test protocol compliance
- ✅ PR #218 closed gracefully
- ✅ Protocol monitoring in production

### Business Success

- ✅ Catch protocol violations before production
- ✅ Confidence in MCP specification compliance
- ✅ Better compatibility with MCP clients
- ✅ Reduced debugging time for integration issues

## Related Work

- **JWT Authentication**: [04-finish-jwt.md](../a10-multitenant/04-finish-jwt.md) - Session management overlaps with auth
- **Stateless Architecture**: [01-stateless.md](../a10-multitenant/01-stateless.md) - Session state must be stateless
- **Stateless Testing**: [02-test-stateless.md](../a10-multitenant/02-test-stateless.md) - Protocol tests should work in stateless mode

## Open Questions

1. **Is this a FastMCP bug or our implementation bug?**
   - Need to test with minimal FastMCP example
   - Check if other FastMCP apps have same issue

2. **What's the correct session lifetime?**
   - Should sessions expire?
   - How long should session state persist?

3. **Do we need session persistence across server restarts?**
   - Probably not for stateless architecture
   - But need to handle gracefully

4. **Should we add protocol version negotiation?**
   - MCP spec may evolve
   - Need strategy for supporting multiple versions

## References

- PR #218: <https://github.com/quiltdata/quilt-mcp-server/pull/218>
- MCP Specification: <https://modelcontextprotocol.io/specification>
- JSON-RPC 2.0 Spec: <https://www.jsonrpc.org/specification>
- SSE Spec: <https://html.spec.whatwg.org/multipage/server-sent-events.html>
- Current test: [tests/integration/test_docker_container.py:362](../../tests/integration/test_docker_container.py#L362)
- Runtime context: [src/quilt_mcp/runtime_context.py](../../src/quilt_mcp/runtime_context.py)
- HTTP app builder: [src/quilt_mcp/utils.py](../../src/quilt_mcp/utils.py)

## Appendix: Test Output Analysis

### Current Failing Test Output (Expected)

```python
# When test is unskipped, expect this failure:
AssertionError: tools/list should return result, but got error:
{
  'code': -32602,
  'message': 'Invalid request parameters'
}
This is the same error MCP Inspector sees!
```

### Expected Passing Test Output

```python
# After fix, expect:
✓ Initialize returns valid response
✓ Session ID captured and used
✓ tools/list returns tool array
✓ All JSON-RPC fields present and correct
✓ SSE format valid
✓ Session maintained throughout test
```

### Debugging Steps

If test still fails after fix:

1. Check session store logs
2. Verify session ID matches between requests
3. Confirm initialize marked session as ready
4. Check parameter validation rules
5. Review FastMCP session lifecycle
6. Compare with working stdio transport (if available)

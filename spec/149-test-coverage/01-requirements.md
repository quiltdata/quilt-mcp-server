<!-- markdownlint-disable MD013 -->
# Test Coverage Improvement Requirements

**GitHub Issue**: [#149 - Improve test coverage in highest-leverage areas - Target: 85%+ overall coverage](https://github.com/quiltdata/quilt-mcp-server/issues/149)

**Issue Branch**: `149-test-coverage`

**Created**: 2025-09-12

## Problem Statement

The quilt-mcp-server currently has 52.78% overall test coverage (4,200/7,958 lines covered), which falls significantly short of the project's established 85%+ coverage requirement. However, the real challenge isn't just reaching an arbitrary coverage number - it's ensuring we have the right types of tests:

1. **Golden path integration tests** that verify core functionality works end-to-end
2. **Comprehensive unit tests** that catch edge cases and error scenarios that are difficult to trigger in integration tests  
3. **Separate tracking** of unit vs integration coverage to ensure both dimensions are adequately addressed
4. **Strategic prioritization** acknowledging this is a significant undertaking requiring focus on highest-impact areas first

## User Stories

### US-1: Development Team Confidence

**As a** developer working on the quilt-mcp-server  
**I want** comprehensive test coverage (85%+) across all critical modules  
**So that** I can refactor, extend, and maintain code with confidence that regressions will be caught immediately

### US-2: Production Risk Mitigation  

**As a** platform operator deploying quilt-mcp-server to production  
**I want** all critical integration points and error handling paths to be tested  
**So that** production incidents are minimized and system reliability is maximized

### US-3: Golden Path Integration Coverage

**As a** platform operator deploying quilt-mcp-server  
**I want** integration tests that validate core user workflows work end-to-end  
**So that** I can be confident the system's primary value propositions function correctly in production

### US-4: Comprehensive Unit Coverage  

**As a** developer working on error handling and edge cases  
**I want** 100% unit test coverage of error scenarios and boundary conditions  
**So that** hypothetical failure modes are caught before they can impact users

### US-5: Separate Coverage Tracking

**As a** development team member  
**I want** clear visibility into both unit and integration test coverage separately  
**So that** we can ensure balance between broad functional validation and deep error scenario testing

### US-6: Development Velocity

**As a** developer adding new features or fixing bugs  
**I want** fast, reliable test feedback loops  
**So that** I can iterate quickly without fear of breaking existing functionality

## Acceptance Criteria

### AC-1: Separate Coverage Tracking

1. **Unit test coverage tracking must be separated from integration test coverage**
2. Coverage measurement must use distinct commands:
   - `make test-unit --cov` for unit-only coverage
   - `make test-integration --cov` for integration-only coverage  
   - `make coverage` for combined reporting with breakdown
3. Coverage reporting must show both metrics clearly and separately
4. Target: 100% unit test coverage, 85%+ integration coverage

### AC-2: Golden Path Integration Tests

1. **Core MCP server functionality must have end-to-end validation**
   - Package browsing and search workflows
   - AWS authentication and permission discovery
   - GraphQL query execution for common use cases
   - Athena query processing for standard scenarios
2. **Integration tests must validate actual business value delivery**
   - User can successfully browse a package from start to finish
   - User can search and discover data using typical patterns
   - System correctly handles AWS credential flows
3. **Integration tests must use real external services where practical**
   - Actual AWS services with test accounts/resources
   - Real GraphQL endpoints with controlled test data
   - Genuine MCP protocol interactions

### AC-3: 100% Unit Test Coverage for Error Scenarios

1. **All error conditions must have unit tests that force the scenarios**
   - Network failures and timeouts
   - Invalid input validation and edge cases
   - AWS permission denied scenarios
   - GraphQL query failures and malformed responses
2. **Unit tests must focus on code paths difficult to trigger in integration tests**
   - Hypothetical error conditions that rarely occur naturally
   - Boundary value testing (empty inputs, oversized inputs, etc.)
   - Race conditions and concurrent access scenarios
3. **Error handling must be comprehensively validated**
   - Proper error message formatting and user-facing content
   - Correct exception types and error codes
   - Graceful degradation behavior

### AC-4: Prioritized Implementation Strategy

1. **Phase 1 (Highest Impact): Critical zero-coverage modules**
   - integration.py (0% coverage, 193 lines) → 100% unit coverage
   - Focus on error scenarios that can't be easily integration tested
2. **Phase 2 (High Value): Golden path integration coverage**
   - End-to-end workflows for core user value propositions
   - Real AWS service integration scenarios
3. **Phase 3 (Coverage Completion): Remaining unit coverage gaps**
   - GraphQL backend: Focus on error handling (19% → 100% unit)
   - AWS permission discovery: Edge cases (31% → 100% unit)  
   - Athena service: Error scenarios (60% → 100% unit)

### AC-5: Implementation Reality Acknowledgment

1. **This is a substantial undertaking requiring strategic focus**
2. **Biggest wins must be prioritized over completionist approaches**
3. **Integration tests may require significant infrastructure setup**
4. **Unit tests for hypothetical errors may require extensive mocking**
5. **Timeline expectations must account for complexity and discovery phases**

## Success Criteria

### Quantitative Metrics (Revised for Realistic Prioritization)

**Milestone 1 (Critical Wins)**:

- **optimization/integration.py**: 0% → 100% unit coverage (193 lines, highest impact - this is a production module, not integration tests)
- **Golden path integration tests**: 3-5 end-to-end workflows validated
- **Separate coverage tracking**: Infrastructure in place for unit vs integration reporting

**Milestone 2 (High Value)**:

- **Core user workflows**: Package browsing, search, AWS auth working end-to-end
- **GraphQL backend**: Critical error scenarios covered via unit tests
- **AWS permission discovery**: Edge cases and error handling unit tested

**Milestone 3 (Coverage Completion)**:

- **Overall unit coverage**: 100% on all modules (ambitious target)
- **Overall integration coverage**: 85%+ on golden path scenarios
- **Combined coverage**: Likely 90%+ when both dimensions addressed

### Qualitative Improvements (Strategic Focus)

- **Risk Reduction**: Biggest failure points (zero-coverage modules) are now tested
- **Development Confidence**: Core workflows validated, edge cases covered
- **Practical Testing Strategy**: Balance of integration confidence and unit thoroughness
- **Incremental Progress**: Deliverable wins at each phase, not all-or-nothing approach

### Business Impact (Acknowledging Reality)

- **Immediate Value**: Critical modules no longer untested liability
- **Long-term Reliability**: Golden path workflows validated against regressions  
- **Sustainable Testing**: Separate tracking enables ongoing maintenance of both test types
- **Strategic Investment**: Foundation established for continued coverage improvement

## Implementation Approach (Revised Strategy)

### Phase 1: Foundation & Critical Wins (Priority 1)

**Setup separate coverage tracking infrastructure**:

- Modify Makefile to support `make test-unit --cov` and `make test-integration --cov`
- Configure coverage reporting to show unit vs integration breakdown
- Establish testing patterns for both unit and integration scenarios

**Address optimization/integration.py module (0% coverage)**:

- 100% unit test coverage focusing on error scenarios and edge cases  
- Mock MCP server interactions to force error conditions
- Test environment-based configuration and optimization behaviors
- Note: This is a production module that integrates optimization with MCP server, not integration test code

### Phase 2: Golden Path Integration (Priority 2)  

**Core user workflow validation**:

- Package browsing: End-to-end workflow from authentication to data access
- Search functionality: GraphQL queries returning expected results
- AWS integration: Real credential flows and permission discovery
- Athena queries: Standard SQL execution scenarios with real AWS resources

**Infrastructure requirements**:

- AWS test account setup with controlled permissions and data
- Integration test environment configuration
- Real external service testing (not just mocks)

### Phase 3: Unit Coverage Completion (Priority 3)

**Error scenario focus for remaining modules**:

- GraphQL backend: Force network failures, malformed responses, timeout scenarios
- AWS permission discovery: Test permission denied, API limit exceeded, service unavailable
- Athena service: Query failures, workgroup misconfigurations, result processing errors

**Comprehensive edge case testing**:

- Boundary value testing (empty inputs, oversized payloads, etc.)
- Race conditions and concurrent access patterns
- Input validation and security scenarios

### Phase 4: Quality & Maintenance (Priority 4)

**Sustainable testing infrastructure**:

- CI/CD integration with separate coverage gates for unit vs integration
- Test performance optimization and reliability improvement
- Documentation of testing patterns and maintenance procedures
- Developer guidance for maintaining coverage standards

## Open Questions (Revised for Strategic Implementation)

1. **Coverage Infrastructure**: How should we implement separate unit vs integration coverage tracking? Modify existing Makefile targets or create new infrastructure?

2. **Integration Test Environment**: Should golden path integration tests use real AWS services, localstack, or a hybrid approach? What are the cost and reliability implications?

3. **Phase Completion Criteria**: What defines "done" for each phase? Should we require formal review gates or use coverage metrics as completion indicators?

4. **Error Scenario Prioritization**: Which error conditions should be unit tested first? Network failures, permission errors, or input validation scenarios?

5. **Test Reliability Strategy**: How should we handle integration test flakiness when using real external services? Retry policies, test environment isolation, or fallback mocking?

6. **Resource Allocation**: Is this effort expected to take weeks, months, or quarters? Should it block other development or proceed in parallel?

7. **Success Measurement**: How will we track progress across the three dimensions (unit coverage, integration coverage, golden path validation)?

8. **Technical Debt Balance**: Should we refactor existing code to make it more testable, or focus purely on adding tests to existing implementations?

## Dependencies and Constraints

### Technical Dependencies

- Existing test infrastructure and patterns in `tests/` directory
- AWS service availability for integration testing
- MCP protocol compliance requirements
- Current CI/CD pipeline configuration

### Resource Constraints  

- Development time allocation for comprehensive test writing
- AWS testing resource costs and access permissions
- CI/CD pipeline execution time limits
- Test maintenance overhead for ongoing development

### Quality Constraints

- Must maintain 100% backward compatibility
- Cannot break existing functionality during coverage improvements  
- Must follow established BDD testing patterns
- All tests must be deterministic and reliable

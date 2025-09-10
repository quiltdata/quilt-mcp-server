<!-- markdownlint-disable MD013 -->
# Phase 1 Implementation Checklist: Enhanced Athena Workgroups Listing

**Issue #133**  
**Branch:** `133-athena-workgroups-impl`  
**Checklist Date:** 2025-09-10  
**Phase:** 1 of 1

## Overview

This checklist provides detailed instructions for orchestrator agents to implement the enhanced Athena workgroups listing functionality following the I RASP DECO methodology. Each episode represents an atomic change unit that maintains working state throughout implementation.

## Episode 1: Add ENABLED State Filter

### [ ] Episode 1 Red Phase: Write Failing Test

- [ ] Create test `test_athena_workgroups_list_filters_enabled_only()` in appropriate test file
- [ ] Mock `ListWorkGroups` to return both ENABLED and DISABLED workgroups
- [ ] Assert that only ENABLED workgroups appear in final result
- [ ] Verify test fails without implementation
- [ ] Commit failing test: `"test: Add BDD test for ENABLED workgroup filtering"`

### [ ] Episode 1 Green Phase: Minimal Implementation

- [ ] Locate workgroup list processing logic in `athena_workgroups_list` function
- [ ] Add filter condition `State == "ENABLED"` to ListWorkGroups response processing
- [ ] Modify workgroup iteration to skip DISABLED workgroups before GetWorkGroup calls
- [ ] Ensure filter is applied early to reduce unnecessary API calls
- [ ] Verify test passes with minimal implementation
- [ ] Commit implementation: `"feat: Filter workgroups to ENABLED state only"`

### [ ] Episode 1 Refactor Phase: Structure Assessment

- [ ] Assess if filter logic is clear and maintainable
- [ ] Consider extracting filter to helper function if beneficial
- [ ] Ensure code readability and intent expression
- [ ] Run all existing tests to ensure no regressions
- [ ] Commit refactoring (if performed): `"refactor: Clean up workgroup filtering logic"`

### [ ] Episode 1 Success Criteria Validation

- [ ] Only ENABLED workgroups appear in results
- [ ] DISABLED workgroups are filtered out before GetWorkGroup calls
- [ ] All existing tests pass
- [ ] No change to public API response structure
- [ ] IDE diagnostics clean

---

## Episode 2: Remove Synthetic `accessible` Field

### [ ] Episode 2 Red Phase: Write Failing Test

- [ ] Create test `test_athena_workgroups_list_no_synthetic_accessible_field()`
- [ ] Assert 'accessible' field is not present in any workgroup result
- [ ] Verify test fails with current implementation
- [ ] Commit failing test: `"test: Add BDD test ensuring no synthetic accessible field"`

### [ ] Episode 2 Green Phase: Minimal Implementation

- [ ] Locate `accessible` field creation logic in workgroup response building
- [ ] Remove `accessible` field creation/assignment code
- [ ] Remove sorting by `accessible` field if present
- [ ] Ensure response contains only AWS API fields
- [ ] Update existing test assertions to remove checks for `accessible` field
- [ ] Verify test passes and existing tests still work
- [ ] Commit implementation: `"feat: Remove synthetic accessible field from workgroups"`

### [ ] Episode 2 Refactor Phase: Structure Assessment

- [ ] Assess if response structure is clean and consistent
- [ ] Consider if field removal improves code clarity
- [ ] Ensure consistent field handling across response building
- [ ] Run all tests to verify clean response structure
- [ ] Commit refactoring (if performed): `"refactor: Simplify workgroup response structure"`

### [ ] Episode 2 Success Criteria Validation

- [ ] No `accessible` field in response
- [ ] No sorting by `accessible` field
- [ ] Response structure matches AWS API fields
- [ ] All tests pass with updated assertions
- [ ] IDE diagnostics clean

---

## Episode 3: Remove `state` Field from Output

### [ ] Episode 3 Red Phase: Write Failing Test

- [ ] Create test `test_athena_workgroups_list_no_state_field_in_output()`
- [ ] Assert 'state' field is not present in workgroup results
- [ ] Rationale: Since all results are ENABLED (Episode 1), state field is redundant
- [ ] Verify test fails with current implementation
- [ ] Commit failing test: `"test: Add BDD test ensuring no state field in output"`

### [ ] Episode 3 Green Phase: Minimal Implementation

- [ ] Locate `state` field inclusion in response structure
- [ ] Remove `state` field from response building logic
- [ ] Update response construction to exclude state information
- [ ] Update existing test assertions to remove checks for `state` field
- [ ] Verify test passes and response is simplified
- [ ] Commit implementation: `"feat: Remove redundant state field from workgroups response"`

### [ ] Episode 3 Refactor Phase: Structure Assessment

- [ ] Assess if response is cleaner without redundant state field
- [ ] Consider if documentation needs updating for field removal
- [ ] Ensure response structure consistency
- [ ] Run all tests to verify simplified structure works correctly
- [ ] Commit refactoring (if performed): `"refactor: Clean up response field structure"`

### [ ] Episode 3 Success Criteria Validation

- [ ] No `state` field in response (all workgroups are ENABLED by Episode 1)
- [ ] Response structure simplified
- [ ] All tests pass with updated assertions
- [ ] IDE diagnostics clean

---

## Episode 4: Remove Error Messages from Description Field

### [ ] Episode 4 Red Phase: Write Failing Test

- [ ] Create test `test_athena_workgroups_list_clean_description_field()`
- [ ] Mock GetWorkGroup failure scenarios (access denied, not found, etc.)
- [ ] Assert description field contains only AWS data or remains unchanged
- [ ] Assert no error messages pollute the description field
- [ ] Verify test fails with current error handling
- [ ] Commit failing test: `"test: Add BDD test for clean description field handling"`

### [ ] Episode 4 Green Phase: Minimal Implementation

- [ ] Locate error message injection into `description` field
- [ ] Remove error message assignment to description field
- [ ] Preserve original AWS `Description` field value from ListWorkGroups
- [ ] Handle GetWorkGroup failures without polluting description
- [ ] Add appropriate logging for GetWorkGroup failures (debug/info level)
- [ ] Update existing test assertions to verify clean description field handling
- [ ] Verify test passes and descriptions remain clean
- [ ] Commit implementation: `"feat: Remove error messages from workgroup description field"`

### [ ] Episode 4 Refactor Phase: Structure Assessment

- [ ] Assess if error handling is clean and maintainable
- [ ] Consider if logging level is appropriate for troubleshooting
- [ ] Ensure separation of concerns between error handling and data presentation
- [ ] Run all tests to verify clean error handling
- [ ] Commit refactoring (if performed): `"refactor: Clean up description field handling"`

### [ ] Episode 4 Success Criteria Validation

- [ ] Description field never contains error messages
- [ ] Original AWS Description field preserved
- [ ] GetWorkGroup failures logged but not exposed to users
- [ ] All tests pass with clean description assertions
- [ ] IDE diagnostics clean

---

## Episode 5: Implement Layered API Access Pattern

### [ ] Episode 5 Red Phase: Write Failing Test

- [ ] Create test `test_athena_workgroups_list_layered_api_access()`
- [ ] Test minimal permissions scenario (ListWorkGroups only)
- [ ] Test enhanced permissions scenario (both ListWorkGroups and GetWorkGroup)
- [ ] Assert core functionality works in both cases
- [ ] Assert graceful degradation when GetWorkGroup fails
- [ ] Verify tests fail with current implementation
- [ ] Commit failing test: `"test: Add BDD tests for layered API access pattern"`

### [ ] Episode 5 Green Phase: Minimal Implementation

- [ ] Implement core functionality using ListWorkGroups only
- [ ] Add optional enhancement using GetWorkGroup when available
- [ ] Handle GetWorkGroup failures gracefully without affecting core results
- [ ] Ensure essential workgroup information available from ListWorkGroups alone
- [ ] Add diagnostic logging for permission scenarios
- [ ] Add new test scenarios for both minimal and enhanced permissions
- [ ] Verify tests pass and layered access works correctly
- [ ] Commit implementation: `"feat: Implement layered API access for workgroups listing"`

### [ ] Episode 5 Refactor Phase: Structure Assessment

- [ ] Assess if layered access pattern is clear and maintainable
- [ ] Consider if error handling separation is effective
- [ ] Ensure code clearly expresses the layered approach
- [ ] Run all tests to verify robust permission handling
- [ ] Commit refactoring (if performed): `"refactor: Clean up layered API access implementation"`

### [ ] Episode 5 Success Criteria Validation

- [ ] Core functionality works with minimal permissions (ListWorkGroups only)
- [ ] Enhancement works when both permissions available
- [ ] GetWorkGroup failures don't break core functionality
- [ ] Logging provides diagnostic information for troubleshooting
- [ ] All tests pass for both permission scenarios
- [ ] IDE diagnostics clean

---

## Episode 6: Final Integration Validation

### [ ] Episode 6 Red Phase: Write Failing Test

- [ ] Create test `test_athena_workgroups_list_end_to_end_integration()`
- [ ] Test complete workflow with all changes applied:
  - ENABLED filtering
  - No synthetic fields (`accessible`, `state`)
  - Clean descriptions
  - Layered API access
- [ ] Assert comprehensive integration works end-to-end
- [ ] Verify test should pass after all previous episodes are complete
- [ ] Commit integration test: `"test: Add end-to-end integration test for workgroups enhancement"`

### [ ] Episode 6 Green Phase: Final Validation

- [ ] Run complete test suite to ensure all episodes work together
- [ ] Verify no regressions in existing functionality
- [ ] Confirm all design goals are met end-to-end
- [ ] Test with various permission combinations
- [ ] Verify error scenarios are handled gracefully
- [ ] Commit final validation: `"feat: Complete athena workgroups enhancement integration"`

### [ ] Episode 6 Refactor Phase: Documentation Update

- [ ] Update any inline documentation affected by changes
- [ ] Ensure code comments reflect new behavior
- [ ] Update function docstrings if needed
- [ ] Verify code clearly expresses intent and design decisions
- [ ] Commit documentation updates: `"docs: Update workgroups function documentation"`

### [ ] Episode 6 Success Criteria Validation

- [ ] All existing tests pass
- [ ] New integration test passes
- [ ] No synthetic fields in any response (`accessible`, `state`)
- [ ] Only ENABLED workgroups returned
- [ ] Clean AWS field structure preserved
- [ ] Layered API access working correctly
- [ ] Error handling doesn't pollute data fields
- [ ] IDE diagnostics clean

---

## Episode 7: AthenaQueryService Integration

### [ ] Episode 7 Red Phase: Write Failing Test

- [ ] Create test `test_athena_workgroups_list_uses_athena_query_service()`
- [ ] Test that workgroups listing uses same auth patterns as other Athena tools
- [ ] Assert consistent credential handling and error patterns
- [ ] Mock AthenaQueryService integration scenarios
- [ ] Verify test fails without service integration
- [ ] Commit test: `"test: Add BDD test for AthenaQueryService integration"`

### [ ] Episode 7 Green Phase: Minimal Implementation

- [ ] Locate existing AthenaQueryService class and methods
- [ ] Add workgroup listing methods to AthenaQueryService
- [ ] Update `athena_workgroups_list` function to use consolidated service
- [ ] Ensure authentication patterns remain consistent with other Athena tools
- [ ] Maintain all filtering and response logic from previous episodes
- [ ] Update tests to reflect service integration changes
- [ ] Verify integration maintains all previous functionality
- [ ] Commit implementation: `"refactor: Integrate workgroups listing with AthenaQueryService"`

### [ ] Episode 7 Refactor Phase: Structure Assessment

- [ ] Assess if service consolidation improves maintainability
- [ ] Consider if further Athena service methods could be unified
- [ ] Ensure consistent error handling patterns across service
- [ ] Verify authentication code duplication is reduced
- [ ] Run all tests to ensure service integration works correctly
- [ ] Commit refactoring (if performed): `"refactor: Clean up service integration patterns"`

### [ ] Episode 7 Success Criteria Validation

- [ ] Consolidated authentication patterns across Athena tools
- [ ] No breaking changes to public API
- [ ] All tests pass with refactored implementation
- [ ] Reduced code duplication in auth handling
- [ ] Service integration maintains all Episode 1-6 improvements
- [ ] IDE diagnostics clean

---

## Final Validation Checklist

### [ ] Complete Episode Sequence Validation

- [ ] Episode 1: ENABLED filtering implemented and tested
- [ ] Episode 2: Synthetic `accessible` field removed
- [ ] Episode 3: Redundant `state` field removed
- [ ] Episode 4: Clean description field handling
- [ ] Episode 5: Layered API access pattern working
- [ ] Episode 6: End-to-end integration validated
- [ ] Episode 7: AthenaQueryService integration complete

### [ ] Quality Gates

- [ ] All BDD tests pass (existing + new)
- [ ] 100% test coverage maintained
- [ ] All IDE diagnostics clean
- [ ] `make test` passes completely
- [ ] `make lint` passes without issues
- [ ] No breaking changes to public API

### [ ] Documentation and Cleanup

- [ ] All commit messages follow conventional commits format
- [ ] Code comments accurately reflect new behavior
- [ ] Function docstrings updated where needed
- [ ] Working state maintained throughout all episodes

### [ ] Integration Requirements Met

- [ ] No synthetic fields in response
- [ ] Only ENABLED workgroups returned
- [ ] Clean AWS field structure preserved
- [ ] Layered API access working correctly
- [ ] Enhanced diagnostic logging in place
- [ ] AthenaQueryService integration complete
- [ ] Consolidated authentication patterns
- [ ] Error handling doesn't pollute data fields

## Orchestrator Agent Instructions

### TDD Discipline Requirements

- **CRITICAL**: Each episode MUST follow strict Red → Green → Refactor cycle
- Write failing test first, commit with "test: ..." message
- Implement minimal code to pass test, commit with "feat: ..." or "fix: ..." message
- Assess refactoring opportunities, commit improvements with "refactor: ..." message
- **NEVER** write production code without a failing test demanding it

### Working State Maintenance

- Each episode must maintain working state after completion
- All tests must pass after each episode
- Update test assertions during Green phase of same episode (not deferred)
- No broken intermediate states allowed
- Independent testability for each atomic change

### Error Handling Patterns

- Use appropriate logging levels (debug/info for diagnostics, warn/error for genuine issues)
- Never pollute data fields with error messages
- Implement graceful degradation for permission scenarios
- Maintain clean separation between error handling and data presentation

### Commit Strategy

- Separate commits for Red, Green, and Refactor phases
- Clear commit messages following conventional commits format
- Each episode results in 1-3 commits maximum
- Push after each complete episode for validation

### Quality Validation After Each Episode

- [ ] Run `make test` - all tests must pass
- [ ] Run `make lint` - no linting issues
- [ ] Check IDE diagnostics - must be clean
- [ ] Verify working state maintained
- [ ] Update this checklist with episode completion

## Success Metrics

### Functional Requirements

- Only ENABLED workgroups in results
- No synthetic fields (`accessible`, `state`)
- Clean AWS API field structure
- Graceful permission handling (ListWorkGroups + optional GetWorkGroup)
- Error-free data presentation

### Technical Requirements

- 100% BDD test coverage
- Consolidated authentication patterns
- Reduced code duplication
- Enhanced diagnostic logging
- Maintainable layered architecture

### Quality Requirements

- All existing functionality preserved
- No breaking API changes
- Clean, self-documenting code
- Robust error handling
- Performance optimization (fewer unnecessary API calls)

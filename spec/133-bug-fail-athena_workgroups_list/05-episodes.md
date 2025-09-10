<!-- markdownlint-disable MD013 -->
# Phase 1 Episodes: Enhanced Athena Workgroups Listing Implementation

**Issue #133**  
**Branch:** `133-bug-fail-athena_workgroups_list`  
**Episodes Date:** 2025-09-10  
**Phase:** 1 of 1

## Episode Breakdown Using I RASP DECO Methodology

### Episode 1: Add ENABLED State Filter

**Category:** Infrastructure  
**Type:** Atomic Change Unit  
**Dependencies:** None

#### Episode 1 Red Phase: Write Failing Test

```python
def test_athena_workgroups_list_filters_enabled_only():
    """Should only return workgroups with State == 'ENABLED'"""
    # Mock ListWorkGroups returning both ENABLED and DISABLED
    # Assert only ENABLED workgroups in final result
```

#### Episode 1 Green Phase: Minimal Implementation

- Add filter `State == "ENABLED"` to ListWorkGroups response processing
- Modify workgroup list iteration to skip DISABLED workgroups

#### Episode 1 Refactor Phase: Structure Assessment

- Assess if filter logic is clear and maintainable
- Consider extracting filter to helper function if beneficial

#### Episode 1 Success Criteria

- [ ] Only ENABLED workgroups appear in results
- [ ] DISABLED workgroups are filtered out before GetWorkGroup calls
- [ ] All existing tests pass
- [ ] No change to public API response structure

#### Episode 1 Commit Messages

- Red: `test: Add BDD test for ENABLED workgroup filtering`
- Green: `feat: Filter workgroups to ENABLED state only`
- Refactor: `refactor: Clean up workgroup filtering logic` (if needed)

---

### Episode 2: Remove Synthetic `accessible` Field

**Category:** API Simplification  
**Type:** Atomic Change Unit  
**Dependencies:** Episode 1

#### Episode 2 Red Phase: Write Failing Test

```python
def test_athena_workgroups_list_no_synthetic_accessible_field():
    """Should not include synthetic 'accessible' field in response"""
    # Assert 'accessible' field is not present in any workgroup result
```

#### Episode 2 Green Phase: Minimal Implementation

- Remove `accessible` field creation logic
- Remove sorting by `accessible` field
- Ensure response contains only AWS API fields
- Update existing test assertions to remove checks for `accessible` field

#### Episode 2 Refactor Phase: Structure Assessment

- Assess if response structure is clean and consistent
- Consider if field removal improves code clarity

#### Episode 2 Success Criteria

- [ ] No `accessible` field in response
- [ ] No sorting by `accessible` field
- [ ] Response structure matches AWS API fields
- [ ] All tests pass with updated assertions

#### Episode 2 Commit Messages

- Red: `test: Add BDD test ensuring no synthetic accessible field`
- Green: `feat: Remove synthetic accessible field from workgroups`
- Refactor: `refactor: Simplify workgroup response structure` (if needed)

---

### Episode 3: Remove `state` Field from Output

**Category:** API Simplification  
**Type:** Atomic Change Unit  
**Dependencies:** Episode 1, Episode 2

#### Episode 3 Red Phase: Write Failing Test

```python
def test_athena_workgroups_list_no_state_field_in_output():
    """Should not include 'state' field since all results are ENABLED"""
    # Assert 'state' field is not present in workgroup results
```

#### Episode 3 Green Phase: Minimal Implementation

- Remove `state` field from response structure
- Update response building to exclude state information
- Update existing test assertions to remove checks for `state` field

#### Episode 3 Refactor Phase: Structure Assessment

- Assess if response is cleaner without redundant state field
- Consider if documentation needs updating for field removal

#### Episode 3 Success Criteria

- [ ] No `state` field in response (all workgroups are ENABLED by Episode 1)
- [ ] Response structure simplified
- [ ] All tests pass with updated assertions

#### Episode 3 Commit Messages

- Red: `test: Add BDD test ensuring no state field in output`
- Green: `feat: Remove redundant state field from workgroups response`
- Refactor: `refactor: Clean up response field structure` (if needed)

---

### Episode 4: Remove Error Messages from Description Field

**Category:** Data Integrity  
**Type:** Atomic Change Unit  
**Dependencies:** Episode 1, Episode 2, Episode 3

#### Episode 4 Red Phase: Write Failing Test

```python
def test_athena_workgroups_list_clean_description_field():
    """Description field should contain only AWS data, no error messages"""
    # Mock GetWorkGroup failure scenarios
    # Assert description field contains AWS data or remains unchanged
```

#### Episode 4 Green Phase: Minimal Implementation

- Remove error message injection into `description` field
- Preserve original AWS `Description` field value
- Handle GetWorkGroup failures without polluting description
- Update existing test assertions to verify clean description field handling

#### Episode 4 Refactor Phase: Structure Assessment

- Assess if error handling is clean and maintainable
- Consider if logging level is appropriate for troubleshooting

#### Episode 4 Success Criteria

- [ ] Description field never contains error messages
- [ ] Original AWS Description field preserved
- [ ] GetWorkGroup failures logged but not exposed to users
- [ ] All tests pass with clean description assertions

#### Episode 4 Commit Messages

- Red: `test: Add BDD test for clean description field handling`
- Green: `feat: Remove error messages from workgroup description field`
- Refactor: `refactor: Clean up description field handling` (if needed)

---

### Episode 5: Implement Layered API Access Pattern

**Category:** Service Architecture  
**Type:** Atomic Change Unit  
**Dependencies:** Episode 1, Episode 2, Episode 3, Episode 4

#### Episode 5 Red Phase: Write Failing Test

```python
def test_athena_workgroups_list_layered_api_access():
    """Should work with ListWorkGroups only, enhance with GetWorkGroup when available"""
    # Test minimal permissions scenario (ListWorkGroups only)
    # Test enhanced permissions scenario (both APIs)
    # Assert core functionality in both cases
```

#### Episode 5 Green Phase: Minimal Implementation

- Implement core functionality using ListWorkGroups only
- Add optional enhancement using GetWorkGroup when available
- Handle GetWorkGroup failures gracefully without affecting core results
- Add new test scenarios for both minimal and enhanced permissions

#### Episode 5 Refactor Phase: Structure Assessment

- Assess if layered access pattern is clear and maintainable
- Consider if error handling separation is effective

#### Episode 5 Success Criteria

- [ ] Core functionality works with minimal permissions
- [ ] Enhancement works when permissions available
- [ ] GetWorkGroup failures don't break core functionality
- [ ] Logging provides diagnostic information

#### Episode 5 Commit Messages

- Red: `test: Add BDD tests for layered API access pattern`
- Green: `feat: Implement layered API access for workgroups listing`
- Refactor: `refactor: Clean up layered API access implementation` (if needed)

---

### Episode 6: Final Integration Validation

**Category:** Integration Testing  
**Type:** Atomic Change Unit  
**Dependencies:** Episode 1, Episode 2, Episode 3, Episode 4, Episode 5

#### Episode 6 Red Phase: Write Failing Test

```python
def test_athena_workgroups_list_end_to_end_integration():
    """Complete integration test with all changes applied"""
    # Test complete workflow with ENABLED filtering, no synthetic fields,
    # clean descriptions, and layered API access
    # This test should pass after all previous episodes are complete
```

#### Episode 6 Green Phase: Final Validation

- Run complete test suite to ensure all episodes work together
- Verify no regressions in existing functionality
- Confirm all design goals are met end-to-end

#### Episode 6 Refactor Phase: Documentation Update

- Update any inline documentation affected by changes
- Ensure code comments reflect new behavior
- Update function docstrings if needed

#### Episode 6 Success Criteria

- [ ] All existing tests pass
- [ ] New integration test passes
- [ ] No synthetic fields in any response
- [ ] Only ENABLED workgroups returned
- [ ] Clean AWS field structure preserved
- [ ] Layered API access working correctly

#### Episode 6 Commit Messages

- Red: `test: Add end-to-end integration test for workgroups enhancement`
- Green: `feat: Complete athena workgroups enhancement integration`
- Refactor: `docs: Update workgroups function documentation` (if needed)

---

## Optional Refactoring Episodes

### Episode R1: AthenaQueryService Integration (Optional)

**Category:** Service Consolidation  
**Type:** Refactoring Episode  
**Dependencies:** All core episodes complete

#### Assessment Phase: Evaluate Integration Benefits

- Evaluate if AthenaQueryService integration would improve maintainability
- Consider impact on authentication patterns
- Assess effort vs. benefit ratio

#### Implementation Phase: Service Consolidation

- Add workgroup methods to AthenaQueryService
- Update athena_workgroups_list to use consolidated service
- Ensure authentication patterns remain consistent

#### Episode R1 Success Criteria

- [ ] Consolidated authentication patterns across Athena tools
- [ ] No breaking changes to public API
- [ ] All tests pass with refactored implementation

---

### Episode R2: Service-Level Error Handling Improvements (Optional)

**Category:** Error Handling Enhancement  
**Type:** Refactoring Episode  
**Dependencies:** All core episodes complete

#### Assessment Phase: Evaluate Error Handling

- Evaluate current error handling patterns across Athena tools
- Consider standardizing error logging and reporting
- Assess opportunities for improved diagnostics

#### Implementation Phase: Error Handling Enhancement

- Standardize error handling patterns
- Improve diagnostic logging consistency
- Enhance error context for troubleshooting

#### Episode R2 Success Criteria

- [ ] Consistent error handling across Athena tools
- [ ] Enhanced diagnostic capabilities
- [ ] No impact on user-facing functionality

---

## Episode Sequencing and Dependencies

```mermaid
graph TD
    E1[Episode 1: ENABLED Filter] --> E2[Episode 2: Remove accessible]
    E1 --> E3[Episode 3: Remove state]
    E2 --> E4[Episode 4: Clean description]
    E3 --> E4
    E4 --> E5[Episode 5: Layered API]
    E5 --> E6[Episode 6: Update tests]
    E6 --> R1[Episode R1: Service Integration]
    E6 --> R2[Episode R2: Error Handling]
```

## TDD Cycle Management

### Red → Green → Refactor Discipline

Each episode follows strict TDD:

1. **Red Phase:** Write failing test first, commit as "test: ..."
2. **Green Phase:** Minimal implementation to pass, commit as "feat: ..." or "fix: ..."
3. **Refactor Phase:** Assess and improve if beneficial, commit as "refactor: ..."

### Working State Maintenance

- Each episode maintains working state
- All tests pass after each episode completion
- No broken intermediate states
- Independent testability for each atomic change
- **CRITICAL**: Each episode updates its own test assertions during Green phase
- Test updates are NOT deferred to a later episode
- Every commit leaves the codebase in a working, testable state

### Commit Strategy

- Separate commits for Red, Green, and Refactor phases
- Clear commit messages following conventional commits
- Each episode results in 1-3 commits maximum
- Push after each complete episode for CI validation

## Success Validation

### After Each Episode

- [ ] All existing tests pass
- [ ] New BDD tests pass
- [ ] IDE diagnostics clean
- [ ] Working state maintained

### After All Episodes

- [ ] No synthetic fields in response
- [ ] Only ENABLED workgroups returned
- [ ] Clean AWS field structure preserved
- [ ] Layered API access working
- [ ] Enhanced diagnostic logging in place
- [ ] 100% test coverage maintained

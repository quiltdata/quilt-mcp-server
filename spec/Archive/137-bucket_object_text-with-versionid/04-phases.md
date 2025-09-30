<!-- markdownlint-disable MD013 -->
# Phases Document: bucket_object_text with versionId Support

**Issue**: #137 - Add versionId support to bucket_object_text function

## Overview

This phases document breaks down the implementation into incremental, reviewable PRs that sequentially build toward the desired end state defined in `03-specifications.md`. Each phase delivers working, testable functionality while maintaining backward compatibility.

## Phase 1: Test Infrastructure Foundation

**Objective**: Fix existing test failures and establish baseline test coverage for safe refactoring.

**Why First**: Based on analysis in `02-analysis.md`, systematic mocking inconsistencies prevent reliable testing. Must establish solid test foundation before making any changes.

### Phase 1 Deliverables

1. **Fix Mock Inconsistencies** - Address systematic `boto3.client()` vs `get_s3_client()` mocking issues:
   - Fix `test_bucket_object_link_error()` in `test_bucket_tools.py`
   - Fix all failing mock tests in `test_utils.py`:
     - `test_generate_signed_url_complex_key`
     - `test_generate_signed_url_exception_mocked`
     - `test_generate_signed_url_expiration_limits_mocked`
     - `test_generate_signed_url_mocked`

2. **Measure Current Coverage** - Establish baseline coverage metrics using `make coverage`

3. **Add Missing Integration Tests** - Complete test coverage for existing functionality:
   - Add `test_bucket_object_link_integration()` with real AWS testing
   - Add missing error scenario tests for all four functions

### Phase 1 Success Criteria

- All existing tests pass: `make test` returns green
- Coverage baseline documented for bucket_object_* functions
- Clear understanding of current test patterns and fixtures

### Phase 1 Dependencies

- None (foundation phase)

### Phase 1 Estimated PR Size

- Small to Medium (primarily test fixes)
- Focus on reliability over new functionality

---

## Phase 2: URI Parsing Infrastructure (Pre-factoring)

**Objective**: Extract and standardize URI parsing logic into reusable utilities without changing function behavior.

**Why Second**: Implements "make the change easy" principle by consolidating duplicated parsing logic before adding versionId support.

### Phase 2 Deliverables

1. **Create Shared URI Parser** - Add `parse_s3_uri()` function to `/src/quilt_mcp/utils.py`:

   ```python
   def parse_s3_uri(s3_uri: str) -> tuple[str, str, str | None]:
       """Parse S3 URI into bucket, key, and optional version_id"""
       # Initial implementation: version_id always returns None
       # Maintains exact compatibility with current parsing logic
   ```

2. **Refactor All Four Functions** - Replace duplicated parsing logic:
   - `bucket_object_info()` (lines 89-92)
   - `bucket_object_text()` (lines 124-127)  
   - `bucket_object_fetch()` (lines 233-236)
   - `bucket_object_link()` (lines 298-301)

3. **Add URI Parser Tests** - Comprehensive test coverage for new utility:
   - Valid S3 URI formats
   - Edge cases (empty keys, special characters)
   - Error scenarios (malformed URIs)
   - Backward compatibility validation

### Phase 2 Success Criteria

- All existing tests continue to pass (no behavior changes)
- URI parsing logic consolidated into single, well-tested function
- Zero functional changes to bucket_object_* functions
- 100% test coverage for new `parse_s3_uri()` function

### Phase 2 Dependencies

- Phase 1 completion (reliable test foundation)

### Phase 2 Estimated PR Size

- Medium (refactoring without behavior changes)
- Clear "before/after" with identical functionality

---

## Phase 3: versionId Query Parameter Support

**Objective**: Implement versionId extraction from query parameters in URI parser.

**Why Third**: "Make the easy change" - now that URI parsing is centralized, adding versionId support is a single-point change.

### Phase 3 Deliverables

1. **Enhance URI Parser** - Add versionId query parameter support using `urllib.parse`:

   ```python
   def parse_s3_uri(s3_uri: str) -> tuple[str, str, str | None]:
       """Parse S3 URI into bucket, key, and optional version_id"""
       # s3://bucket/key?versionId=abc123 -> ("bucket", "key", "abc123")
       # s3://bucket/key -> ("bucket", "key", None)
   ```

2. **Strict Query Parameter Validation** - Following Quilt3 reference implementation:
   - Only `versionId` query parameter allowed
   - Reject URIs with unexpected query parameters
   - Proper URL decoding with `unquote()`

3. **Comprehensive versionId Tests** - New test scenarios:
   - URI parsing with versionId query parameters
   - Multiple query parameter rejection
   - URL encoding/decoding scenarios
   - Malformed query parameter handling

### Phase 3 Success Criteria

- URI parser correctly extracts versionId from query parameters
- Strict validation rejects unexpected query parameters
- All existing functionality unaffected (version_id unused by functions yet)
- 100% test coverage for versionId parsing scenarios

### Phase 3 Dependencies

- Phase 2 completion (shared URI parser infrastructure)

### Phase 3 Estimated PR Size

- Small to Medium (focused change to single function)
- Clear test-driven development approach

---

## Phase 4: S3 API versionId Parameter Support

**Objective**: Pass extracted versionId to S3 API calls in all four reader functions.

**Why Fourth**: With versionId parsing complete, enable actual version retrieval functionality.

### Phase 4 Deliverables

1. **Update All Four Functions** - Add conditional versionId parameter to S3 calls:
   - `bucket_object_info()`: `head_object(Bucket=bucket, Key=key, VersionId=version_id)` when version_id present
   - `bucket_object_text()`: `get_object(Bucket=bucket, Key=key, VersionId=version_id)` when version_id present
   - `bucket_object_fetch()`: `get_object(Bucket=bucket, Key=key, VersionId=version_id)` when version_id present
   - `bucket_object_link()`: `generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key, "VersionId": version_id})` when version_id present

2. **Enhanced Error Handling** - Distinguish version-specific errors:
   - `NoSuchVersion` - version ID does not exist
   - `AccessDenied` - insufficient permissions for specific version
   - Include version context in error responses

3. **Integration Tests with Real AWS** - Test actual version retrieval:
   - Use versioned objects in test bucket
   - Verify correct version content retrieval
   - Test version-specific error scenarios

### Phase 4 Success Criteria

- All four functions support versionId parameter from URIs
- Version-specific S3 API calls work correctly
- Backward compatibility maintained (URIs without versionId unchanged)
- Version-specific errors properly handled and reported

### Phase 4 Dependencies

- Phase 3 completion (versionId query parameter support)
- Test infrastructure must support versioned test objects

### Phase 4 Estimated PR Size

- Medium to Large (touches all four functions)
- Significant integration testing requirements

---

## Phase 5: Test Coverage Completion and Documentation

**Objective**: Achieve comprehensive test coverage and complete documentation for versionId functionality.

**Why Last**: Ensures complete validation and usability once core functionality is implemented.

### Phase 5 Deliverables

1. **Comprehensive Test Coverage** - Extend existing test functions:
   - Add versionId scenarios to `test_bucket_object_info_success()`
   - Add versionId scenarios to `test_bucket_object_fetch_base64()`
   - Add versionId scenarios to `test_bucket_object_link_success()`
   - Add versionId scenarios to `test_bucket_object_text_csv_file()`

2. **Cross-Function Consistency Tests** - Validate consistent behavior:
   - Same versionId returns same object across all functions
   - Error handling consistency across all functions
   - Performance impact assessment

3. **Documentation Updates** - Update function docstrings and examples:
   - Document versionId query parameter support
   - Provide usage examples with versioned URIs
   - Document version-specific error responses

### Phase 5 Success Criteria

- 100% test coverage achieved for all bucket_object_* functions
- Consistent versionId behavior across all four functions
- Complete documentation with usage examples
- Performance impact measured and documented

### Phase 5 Dependencies

- Phase 4 completion (core versionId functionality)

### Phase 5 Estimated PR Size

- Small to Medium (primarily tests and documentation)
- Focused on completeness and polish

---

## Integration Testing Strategy

### Test Environment Requirements

1. **Versioned S3 Bucket** - Test bucket must have versioning enabled
2. **Multi-Version Test Objects** - Objects with known version IDs for testing
3. **Error Scenario Objects** - Objects with restricted version access for error testing

### Cross-Phase Testing

- **Phase 1**: Focus on existing functionality reliability
- **Phase 2**: Ensure no regressions during refactoring
- **Phase 3**: Validate URI parsing without S3 interaction
- **Phase 4**: Full integration testing with real S3 versioned objects
- **Phase 5**: Comprehensive end-to-end validation

### Continuous Integration

- All phases must pass existing test suite
- Each phase adds incremental test coverage
- No phase should reduce overall test coverage
- Performance regression testing in Phase 4-5

## Risk Mitigation

### Backward Compatibility Protection

- URI parsing changes isolated to utility function
- Function signatures remain unchanged
- Existing URI formats continue to work identically
- Comprehensive regression testing at each phase

### Error Handling Evolution

- Phase 1: Fix existing error handling
- Phase 2: Maintain current error patterns
- Phase 3: No error handling changes (version_id unused)
- Phase 4: Add version-specific error detection
- Phase 5: Validate error handling consistency

### Performance Considerations

- Phase 2-3: Minimal performance impact (parsing overhead)
- Phase 4: Potential S3 API performance differences with versionId
- Phase 5: Performance impact measurement and optimization

## Dependency Management

### Sequential Dependencies

1. **Phase 1 → Phase 2**: Reliable tests required for safe refactoring
2. **Phase 2 → Phase 3**: Shared URI parser required for versionId support
3. **Phase 3 → Phase 4**: versionId extraction required for S3 API calls
4. **Phase 4 → Phase 5**: Core functionality required for comprehensive testing

### Parallel Opportunities

- Phase 2-3: Documentation planning can begin
- Phase 4-5: Integration test design can overlap with implementation

### External Dependencies

- AWS test environment must support versioned objects
- boto3 version compatibility (already supported)
- urllib.parse availability (Python standard library)

## Success Metrics

### Phase Completion Criteria

- **Phase 1**: All tests pass, coverage baseline established
- **Phase 2**: Zero behavior changes, URI parsing consolidated
- **Phase 3**: versionId parsing functional, no S3 impact yet
- **Phase 4**: Full versionId functionality across all four functions
- **Phase 5**: 100% coverage, complete documentation

### Overall Success Validation

1. **Functional**: Can read versioned objects using URIs like `s3://bucket/path/file.txt?versionId=xyz`
2. **Compatible**: No breaking changes to existing URI formats
3. **Consistent**: All four functions support versionId identically
4. **Reliable**: 100% test coverage with robust error handling
5. **Documented**: Clear usage examples and error reference

## Implementation Notes

### Pre-factoring Opportunities Identified

- **Phase 2**: Extract duplicated URI parsing (identified in analysis)
- **Phase 4**: Standardize error response formats across functions
- **Phase 5**: Consolidate integration test patterns

### Test-Driven Development Approach

- Each phase follows Red-Green-Refactor cycle
- Tests written before implementation changes
- Continuous validation of backward compatibility
- Progressive enhancement of test coverage

### Code Review Considerations

- Phase 1: Focus on test reliability and mocking fixes
- Phase 2: Verify no functional changes during refactoring
- Phase 3: Validate URI parsing logic and edge cases
- Phase 4: Review S3 API integration and error handling
- Phase 5: Ensure comprehensive coverage and documentation quality

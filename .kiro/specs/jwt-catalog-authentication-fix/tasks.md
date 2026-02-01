# Implementation Plan: JWT Catalog Authentication Fix

## Overview

This implementation plan converts the JWT authentication system from AWS-only to complete authentication by extracting real catalog bearer tokens from quilt3 sessions and embedding them in JWT tokens. The approach maintains backward compatibility while enabling full stateless operation.

## Tasks

- [ ] 1. Create catalog authentication data models
  - Create `CatalogAuth`, `SessionValidation`, and `AuthValidation` dataclasses
  - Implement validation methods and JWT claim conversion
  - Add expiration checking and error message generation
  - _Requirements: 1.1, 1.3, 1.4, 2.1, 2.5_

- [ ] 1.1 Write property test for data model validation
  - **Property 1: Complete JWT Generation**
  - **Validates: Requirements 1.1, 1.3, 1.4**

- [ ] 2. Implement catalog authentication extraction
  - [ ] 2.1 Add `extract_catalog_authentication()` function to jwt_helper.py
    - Extract bearer token from active quilt3 session headers
    - Extract catalog URL and registry URL from quilt3 configuration
    - Handle various session states and configurations
    - _Requirements: 1.1, 1.3_

  - [ ] 2.2 Add `validate_quilt3_session()` function to jwt_helper.py
    - Check session authentication status
    - Validate configuration completeness
    - Generate appropriate error messages and login commands
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [ ] 2.3 Write property test for session validation
    - **Property 2: Session Validation and Error Guidance**
    - **Validates: Requirements 1.2, 1.5, 2.1, 2.2, 2.3**

  - [ ] 2.4 Write property test for registry selection
    - **Property 3: Registry Selection Consistency**
    - **Validates: Requirements 2.4, 2.5**

- [ ] 3. Enhance JWT generation with catalog authentication
  - [ ] 3.1 Update `generate_test_jwt()` function signature
    - Add catalog_auth parameter and auto_extract option
    - Maintain backward compatibility with existing parameters
    - _Requirements: 1.4_

  - [ ] 3.2 Implement complete JWT claim generation
    - Embed catalog bearer token, catalog URL, and registry URL in JWT claims
    - Preserve existing AWS role claims and session tags
    - Handle missing catalog authentication with clear errors
    - _Requirements: 1.4, 1.5_

  - [ ] 3.3 Add comprehensive error handling
    - Implement specific error messages for each failure type
    - Provide step-by-step resolution instructions
    - Include exact quilt3 login commands in error messages
    - _Requirements: 1.2, 1.5, 2.2_

  - [ ] 3.4 Write unit tests for JWT generation edge cases
    - Test missing session scenarios
    - Test expired session detection
    - Test configuration validation errors
    - _Requirements: 1.2, 1.5, 2.3_

- [ ] 4. Checkpoint - Validate JWT generation enhancements
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Enhance MCP server authentication service
  - [ ] 5.1 Add catalog authentication setup to JWTAuthService
    - Implement `setup_catalog_authentication()` method
    - Extract catalog claims from JWT tokens
    - Configure quilt3 session with catalog bearer token
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ] 5.2 Implement authentication routing logic
    - Route AWS operations to boto3 session credentials
    - Route catalog operations to authenticated requests session
    - Handle mixed authentication scenarios appropriately
    - _Requirements: 3.5, 4.2, 4.3, 4.4_

  - [ ] 5.3 Add comprehensive authentication validation
    - Implement `validate_complete_authentication()` method
    - Check availability of both AWS and catalog authentication
    - Generate specific error messages for missing authentication types
    - _Requirements: 3.4, 4.5_

  - [ ] 5.4 Write property test for authentication processing
    - **Property 4: Complete Authentication Processing**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.5, 4.2, 4.3, 4.4**

  - [ ] 5.5 Write property test for authentication error handling
    - **Property 5: Authentication Error Handling**
    - **Validates: Requirements 3.4, 4.5, 7.2, 7.5**

- [ ] 6. Implement backward compatibility preservation
  - [ ] 6.1 Add legacy JWT token support
    - Detect JWT tokens with AWS-only authentication
    - Continue supporting S3/IAM operations for legacy tokens
    - Provide informative errors for catalog operations with legacy tokens
    - _Requirements: 4.1, 8.1, 8.2_

  - [ ] 6.2 Implement graceful degradation
    - Handle partial authentication scenarios appropriately
    - Maintain existing AWS authentication workflows
    - Preserve current test coverage for AWS operations
    - _Requirements: 8.3, 8.4, 8.5_

  - [ ] 6.3 Write property test for backward compatibility
    - **Property 6: Backward Compatibility Preservation**
    - **Validates: Requirements 4.1, 8.1, 8.2, 8.3**

- [ ] 7. Update test infrastructure
  - [ ] 7.1 Enhance Makefile test targets
    - Add quilt3 session validation to `test-stateless-mcp` target
    - Extract catalog token automatically during test setup
    - Provide clear error messages when prerequisites are missing
    - _Requirements: 5.1, 5.2_

  - [ ] 7.2 Update JWT integration tests
    - Validate both AWS and catalog authentication in generated JWTs
    - Test both S3 operations and catalog operations in stateless mode
    - Verify complete authentication workflow end-to-end
    - _Requirements: 5.3, 5.4, 6.1, 6.2, 6.3_

  - [ ] 7.3 Add comprehensive error reporting
    - Capture specific authentication failure details
    - Provide remediation steps for different failure types
    - Distinguish between AWS and catalog authentication failures
    - _Requirements: 5.5, 6.4_

  - [ ]* 7.4 Write property test for test validation
    - **Property 7: Complete Test Validation**
    - **Validates: Requirements 5.1, 5.3, 5.4, 6.1, 6.2, 6.3, 6.5**

  - [ ]* 7.5 Write property test for test error reporting
    - **Property 8: Test Error Reporting**
    - **Validates: Requirements 5.2, 5.5, 6.4**

- [ ] 8. Implement comprehensive error messaging
  - [ ] 8.1 Standardize error message formats
    - Create consistent error message templates
    - Include specific resolution steps for each error type
    - Provide exact commands needed for remediation
    - _Requirements: 7.1, 7.3, 7.4_

  - [ ] 8.2 Add educational error messages
    - Explain differences between AWS and catalog authentication
    - Provide context for authentication requirements
    - Guide users through authentication setup process
    - _Requirements: 7.2_

  - [ ]* 8.3 Write property test for error messaging consistency
    - **Property 9: Consistent Error Messaging**
    - **Validates: Requirements 7.1, 7.3, 7.4**

- [ ] 9. Final integration and validation
  - [ ] 9.1 Wire all components together
    - Integrate enhanced JWT generation with MCP server authentication
    - Connect catalog authentication setup with quilt service operations
    - Ensure seamless operation across all authentication scenarios
    - _Requirements: 3.5, 4.4_

  - [ ] 9.2 Validate deployment compatibility
    - Test existing AWS-only JWT workflows continue working
    - Verify new catalog authentication features work correctly
    - Confirm backward compatibility preservation
    - _Requirements: 8.4, 8.5_

  - [ ]* 9.3 Write property test for deployment compatibility
    - **Property 10: Deployment Compatibility**
    - **Validates: Requirements 8.4, 8.5**

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties with minimum 100 iterations
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end authentication workflows
- Backward compatibility is preserved throughout the implementation
# Implementation Plan: Quilt Ops Admin Refactoring

## Overview

This implementation plan refactors the governance_service.py to use the QuiltOps abstraction pattern with an admin submodule instead of directly calling quilt3.admin modules. The approach follows the established domain-driven architecture while maintaining full backward compatibility.

## Tasks

- [ ] 1. Create admin domain objects
  - [ ] 1.1 Create User domain object in src/quilt_mcp/domain/user.py
    - Define User dataclass with all required fields (name, email, active status, admin status, SSO status, service status, join date, login date, role, extra roles)
    - Add proper type annotations and validation
    - _Requirements: 1.1_

  - [ ] 1.2 Create Role domain object in src/quilt_mcp/domain/role.py
    - Define Role dataclass with id, name, ARN, and type properties
    - Add proper type annotations
    - _Requirements: 1.2_

  - [ ] 1.3 Create SSOConfig domain object in src/quilt_mcp/domain/sso_config.py
    - Define SSOConfig dataclass with text, timestamp, and uploader properties
    - Add proper type annotations
    - _Requirements: 1.3_

  - [ ] 1.4 Update domain __init__.py to export new admin domain objects
    - Add imports for User, Role, SSOConfig
    - Update __all__ list
    - _Requirements: 1.1, 1.2, 1.3_

- [ ]* 1.5 Write property tests for domain objects
  - **Property 1: Domain Object Structure Completeness**
  - **Validates: Requirements 1.1, 1.2, 1.3**

- [ ] 2. Create AdminOps interface and extend QuiltOps
  - [ ] 2.1 Create AdminOps abstract interface in src/quilt_mcp/ops/admin_ops.py
    - Define abstract methods for user management (list, get, create, delete, set email, set admin, set active, reset password, manage roles)
    - Define abstract methods for role management (list roles)
    - Define abstract methods for SSO configuration (get, set, remove config)
    - Add proper type hints and documentation
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 2.2 Extend QuiltOps interface to include admin property
    - Add abstract admin property that returns AdminOps
    - Update imports and type hints
    - _Requirements: 2.1_

- [ ] 3. Implement Quilt3_Backend_Admin class
  - [ ] 3.1 Create Quilt3_Backend_Admin implementation in src/quilt_mcp/backends/quilt3_backend_admin.py
    - Implement AdminOps interface methods
    - Add transformation methods for quilt3.admin objects to domain objects
    - Add error handling with domain exception mapping
    - _Requirements: 3.1, 3.3, 3.4, 3.6_

  - [ ]* 3.2 Write property tests for admin backend implementation
    - **Property 2: Data Transformation Bidirectional Consistency**
    - **Property 3: Error Handling Preservation**
    - **Property 4: Exception Mapping Consistency**
    - **Validates: Requirements 3.3, 3.4, 3.6**

- [ ] 4. Integrate admin functionality into Quilt3_Backend
  - [ ] 4.1 Update Quilt3_Backend to include admin property
    - Initialize Quilt3_Backend_Admin instance
    - Implement admin property to return admin instance
    - Maintain admin availability checking
    - _Requirements: 4.1, 4.3, 4.5_

  - [ ]* 4.2 Write property tests for backend integration
    - **Property 5: Interface Implementation Completeness**
    - **Property 6: Admin Availability Graceful Degradation**
    - **Validates: Requirements 4.3, 4.4, 4.5**

- [ ] 5. Checkpoint - Ensure backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Refactor GovernanceService to use QuiltOps.admin
  - [ ] 6.1 Update GovernanceService constructor to accept QuiltOps instance
    - Modify __init__ method to take QuiltOps parameter
    - Update admin availability checking to use QuiltOps.admin
    - _Requirements: 5.1_

  - [ ] 6.2 Refactor user management functions to use QuiltOps.admin
    - Update admin_users_list, admin_user_get, admin_user_create, admin_user_delete functions
    - Replace direct quilt3.admin calls with QuiltOps.admin calls
    - Add domain object to response format transformation
    - _Requirements: 5.1, 5.3_

  - [ ] 6.3 Refactor user modification functions to use QuiltOps.admin
    - Update admin_user_set_email, admin_user_set_admin, admin_user_set_active, admin_user_reset_password functions
    - Update admin_user_set_role, admin_user_add_roles, admin_user_remove_roles functions
    - Replace direct quilt3.admin calls with QuiltOps.admin calls
    - _Requirements: 5.1, 5.3_

  - [ ] 6.4 Refactor role and SSO functions to use QuiltOps.admin
    - Update admin_roles_list, admin_sso_config_get, admin_sso_config_set, admin_sso_config_remove functions
    - Replace direct quilt3.admin calls with QuiltOps.admin calls
    - Add domain object to response format transformation
    - _Requirements: 5.1, 5.3_

  - [ ] 6.5 Update error handling to work with domain exceptions
    - Modify _handle_admin_error to catch and transform domain exceptions
    - Preserve existing error response formats and messages
    - _Requirements: 5.4, 5.6_

- [ ]* 6.6 Write property tests for governance service refactoring
  - **Property 7: API Backward Compatibility**
  - **Property 8: Input Validation Consistency**
  - **Validates: Requirements 5.2, 5.4, 5.5, 5.6**

- [ ] 7. Update governance service instantiation
  - [ ] 7.1 Update governance service factory/instantiation code
    - Modify code that creates GovernanceService instances to pass QuiltOps
    - Ensure proper dependency injection
    - _Requirements: 5.1_

  - [ ] 7.2 Preserve module-level admin objects for backward compatibility
    - Keep existing module-level admin_users, admin_roles, admin_sso_config variables
    - Ensure tests that depend on these objects continue to work
    - _Requirements: 8.5_

- [ ] 8. Migrate governance tests to mock QuiltOps.admin
  - [ ] 8.1 Update test imports and mocking strategy
    - Change from mocking quilt3.admin modules to mocking QuiltOps.admin methods
    - Update test setup and teardown
    - _Requirements: 6.1_

  - [ ] 8.2 Update user management test cases
    - Migrate tests for admin_users_list, admin_user_get, admin_user_create, admin_user_delete
    - Migrate tests for admin_user_set_email, admin_user_set_admin, admin_user_set_active, admin_user_reset_password
    - Migrate tests for admin_user_set_role, admin_user_add_roles, admin_user_remove_roles
    - _Requirements: 6.2_

  - [ ] 8.3 Update role and SSO test cases
    - Migrate tests for admin_roles_list
    - Migrate tests for admin_sso_config_get, admin_sso_config_set, admin_sso_config_remove
    - _Requirements: 6.2_

  - [ ] 8.4 Update error handling test cases
    - Migrate tests for UserNotFoundError, BucketNotFoundError, Quilt3AdminError handling
    - Ensure error response format tests still pass
    - _Requirements: 6.2_

- [ ]* 8.5 Write property tests for test compatibility
  - **Property 9: Test Compatibility Preservation**
  - **Validates: Requirements 6.5**

- [ ] 9. Final integration and compatibility verification
  - [ ] 9.1 Run comprehensive test suite
    - Execute all existing governance tests
    - Verify no test failures or regressions
    - _Requirements: 8.4_

  - [ ] 9.2 Verify backward compatibility
    - Test that existing function signatures are preserved
    - Test that response formats are identical
    - Test that error handling behavior is unchanged
    - _Requirements: 8.1, 8.2, 8.3_

- [ ]* 9.3 Write comprehensive property tests for backward compatibility
  - **Property 10: Authentication Behavior Preservation**
  - **Property 11: Module Structure Backward Compatibility**
  - **Property 12: Error Pattern Consistency**
  - **Property 13: Domain Object Validation**
  - **Validates: Requirements 8.1, 8.2, 8.3, 8.5, 8.6, 9.4, 10.5**

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The refactoring maintains 100% backward compatibility
- Admin operations are now accessed via QuiltOps.admin submodule
- Tabulator functionality has been removed from scope
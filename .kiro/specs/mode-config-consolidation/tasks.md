# Implementation Plan: Mode Configuration Consolidation

## Overview

This implementation plan consolidates scattered mode detection logic into a single `ModeConfig` abstraction, eliminating three redundant environment variables and providing centralized configuration management. The approach follows a hard switch pattern with no backward compatibility requirements, allowing complete simplification while maintaining local development and multitenant production capabilities.

## Tasks

- [x] 1. Create ModeConfig abstraction and Platform Backend stub
  - [x] 1.1 Create ModeConfig singleton with mode properties
    - Create `src/quilt_mcp/config/mode_config.py` with ModeConfig class
    - Implement singleton pattern with `get_mode_config()` function
    - Add properties: `is_multitenant`, `is_local_dev`, `backend_type`, `requires_jwt`, `allows_filesystem_state`, `allows_quilt3_library`, `tenant_mode`, `requires_graphql`, `default_transport`
    - Implement `validate()` and `get_validation_errors()` methods
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 1.2 Write property tests for ModeConfig
    - **Property 1: Mode Configuration Parsing**
    - **Property 2: Singleton Pattern Consistency**
    - **Property 3: Mode Property Completeness**
    - **Validates: Requirements 1.1, 1.2, 1.4, 1.5**

  - [x] 1.3 Create Platform Backend stub
    - Create `src/quilt_mcp/backends/platform_backend.py` with Platform_Backend class
    - Extend QuiltOps abstract interface
    - All methods raise NotImplementedError with clear message directing to local development
    - _Requirements: 2.4_

  - [ ]* 1.4 Write property test for Platform Backend error handling
    - **Property 5: Platform Backend Error Handling**
    - **Validates: Requirements 2.4**

- [-] 2. Update backend and authentication factories
  - [ ] 2.1 Update QuiltOps factory to use ModeConfig
    - Modify `src/quilt_mcp/ops/factory.py` to import and use `get_mode_config()`
    - Replace credential detection with `mode_config.backend_type` query
    - Create Quilt3_Backend for "quilt3" backend type
    - Create Platform_Backend for "graphql" backend type
    - Remove `_detect_quilt3_session()` method entirely
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 2.2 Write property test for backend selection
    - **Property 4: Backend Selection Consistency**
    - **Validates: Requirements 2.1, 2.2**

  - [ ] 2.3 Update context factory authentication logic
    - Modify `src/quilt_mcp/context/factory.py` to use ModeConfig
    - Replace `get_jwt_mode_enabled()` calls with `mode_config.requires_jwt`
    - Update tenant mode determination to use `mode_config.tenant_mode`
    - Enforce JWT-only authentication in multitenant mode
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 2.4 Write property test for authentication service selection
    - **Property 6: Authentication Service Selection**
    - **Validates: Requirements 3.1, 3.2**

- [ ] 3. Remove redundant environment variables and update services
  - [ ] 3.1 Update IAM auth service to use ModeConfig
    - Modify `src/quilt_mcp/services/iam_auth_service.py` line 29
    - Delete line reading `os.getenv("QUILT_DISABLE_QUILT3_SESSION")`
    - Replace with `mode_config.allows_quilt3_library` check
    - _Requirements: 4.2, 7.1, 7.2_

  - [ ] 3.2 Delete global JWT mode detection from auth service
    - Modify `src/quilt_mcp/services/auth_service.py` lines 51-71
    - Delete `_JWT_MODE_ENABLED` global variable
    - Delete `get_jwt_mode_enabled()` function
    - Delete `reset_auth_service()` function
    - Update all callers to use `get_mode_config().requires_jwt`
    - _Requirements: 4.3, 3.3_

  - [ ] 3.3 Update HTTP utilities to use ModeConfig
    - Modify `src/quilt_mcp/utils.py` lines 420-425
    - Delete line reading `os.environ.get("QUILT_MCP_STATELESS_MODE")`
    - Replace with `mode_config.is_multitenant` for stateless HTTP configuration
    - Set `json_response=mode_config.is_multitenant`
    - _Requirements: 4.1, 6.1, 6.2, 6.3_

  - [ ]* 3.4 Write property test for HTTP configuration
    - **Property 10: HTTP Configuration Mode Alignment**
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [ ] 3.5 Update permission discovery service
    - Modify `src/quilt_mcp/services/permission_discovery.py` line 81
    - Delete line reading `os.getenv("QUILT_DISABLE_QUILT3_SESSION")`
    - Replace with `mode_config.allows_quilt3_library` check
    - _Requirements: 4.2, 7.4_

- [ ] 4. Update runtime context and main server
  - [ ] 4.1 Update runtime context default environment
    - Modify `src/quilt_mcp/runtime_context.py` lines 35, 74-81
    - Initialize `_default_state` based on ModeConfig
    - Set environment="web" for multitenant mode
    - Set environment="desktop" for local mode
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 4.2 Write property test for runtime context defaults
    - **Property 13: Runtime Context Environment Defaults**
    - **Validates: Requirements 8.1, 8.2, 8.4**

  - [ ] 4.3 Add startup validation to main server
    - Modify `src/quilt_mcp/main.py` to import and use ModeConfig
    - Call `mode_config.validate()` early in startup before accepting requests
    - Log validation errors from `get_validation_errors()` and exit on failure
    - Log current mode and key configuration on successful validation
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 4.4 Write property tests for startup validation
    - **Property 7: Multitenant JWT Validation**
    - **Property 8: Startup Validation Execution**
    - **Property 9: Validation Logging**
    - **Validates: Requirements 3.4, 5.1, 5.2, 5.3, 5.4, 5.5**

- [ ] 5. Update JWT middleware and transport configuration
  - [ ] 5.1 Update JWT middleware enforcement
    - Modify JWT middleware instantiation to pass `require_jwt=mode_config.requires_jwt`
    - Ensure JWT enforced in multitenant mode, optional in local mode
    - _Requirements: 3.1, 3.2_

  - [ ] 5.2 Add transport protocol selection
    - Update server configuration to use `mode_config.default_transport`
    - Set HTTP transport for multitenant mode
    - Set stdio transport for local mode
    - _Requirements: 8.4_

  - [ ]* 5.3 Write property test for transport selection
    - **Property 11: Transport Protocol Selection**
    - **Validates: Requirements 8.4**

- [ ] 6. Checkpoint - Ensure core functionality works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Update test configurations
  - [ ] 7.1 Update unit test configuration
    - Modify `tests/conftest.py` line 138
    - Remove line: `os.environ["QUILT_DISABLE_QUILT3_SESSION"] = "1"`
    - Unit tests should run in default local mode
    - _Requirements: 9.1, 9.3_

  - [ ] 7.2 Update stateless test configuration
    - Modify `tests/stateless/conftest.py`
    - Set `QUILT_MULTITENANT_MODE=true` explicitly
    - Configure JWT test secrets: `MCP_JWT_SECRET=test-secret`, issuer, audience
    - Delete redundant environment variables: `QUILT_MCP_STATELESS_MODE`, `MCP_REQUIRE_JWT`, `QUILT_DISABLE_QUILT3_SESSION`
    - _Requirements: 9.2, 9.3, 9.4_

  - [ ] 7.3 Fix malformed test in test_s3_package.py
    - Update test `test_create_enhanced_package_uses_create_package_revision` in
      `tests/unit/test_s3_package.py` lines 365-411
    - Change `@patch("quilt_mcp.tools.packages.QuiltService")` to
      `@patch("quilt_mcp.tools.packages.QuiltOpsFactory")`
    - Update mock to return mock QuiltOps backend instead of QuiltService instance
    - Update return value to `Package_Creation_Result` domain object (not dict)
    - Update assertions to verify `mock_backend.create_package_revision()` called (not QuiltService)
    - _Fixes: Test patching wrong abstraction after QuiltOps migration_
    - _See: .kiro/specs/a12-quilt-ops/08-malformed-auth-tests.md_

  - [ ]* 7.4 Write property tests for test suite coverage
    - **Property 14: Test Suite Mode Coverage**
    - **Validates: Requirements 9.5**

- [ ] 8. Verify complete removal of redundant variables
  - [ ] 8.1 Search codebase for deleted environment variables
    - Run `grep -r "QUILT_MCP_STATELESS_MODE" src/quilt_mcp/` (should return zero results)
    - Run `grep -r "QUILT_DISABLE_QUILT3_SESSION" src/quilt_mcp/` (should return zero results)
    - Run `grep -r "MCP_REQUIRE_JWT" src/quilt_mcp/ | grep -v mode_config` (should return zero results except mode_config.py)
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

  - [ ]* 8.2 Write property tests for session management and local mode
    - **Property 12: Session Management Mode Alignment**
    - **Property 15: Local Mode Functionality**
    - **Validates: Requirements 7.1, 7.2, 7.4, 10.2, 10.3, 10.4**

- [ ] 9. Final validation and testing
  - [ ] 9.1 Run comprehensive test suite
    - Execute `uv run pytest tests/unit/` (unit tests in local mode)
    - Execute `uv run pytest tests/stateless/` (multitenant mode tests)
    - Execute `uv run pytest tests/integration/` (integration tests)
    - Verify all tests pass in both deployment modes
    - _Requirements: 9.5_

  - [ ] 9.2 Manual testing verification
    - Test local mode: Start server without configuration, verify local development works
    - Test multitenant mode: Start server with `QUILT_MULTITENANT_MODE=true` and JWT config
    - Test invalid configuration: Start server with multitenant mode but missing JWT config, verify clear error
    - _Requirements: 10.1, 5.2_

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- This is a hard switch implementation with no backward compatibility requirements
- All mode decisions must go through ModeConfig singleton after implementation
- Zero references to deleted environment variables should remain in source code
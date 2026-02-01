# Requirements Document

## Introduction

The Quilt MCP Server currently uses multiple scattered environment variables for mode detection, creating confusion and maintenance overhead. This feature consolidates all mode-related configuration into a single boolean environment variable `QUILT_MULTITENANT_MODE`, eliminating redundant variables and providing a single source of truth for all mode-related decisions.

## Glossary

- **ModeConfig**: Central configuration abstraction that manages deployment mode decisions
- **Local_Mode**: Development mode using local AWS credentials and filesystem state
- **Multitenant_Mode**: Production mode requiring JWT authentication and stateless operation
- **Backend_Type**: The type of backend service (quilt3 library or GraphQL platform)
- **Quilt3_Backend**: Backend implementation using the quilt3 Python library
- **Platform_Backend**: Backend implementation using GraphQL API calls to Quilt Platform
- **JWT_Authentication**: Token-based authentication required in multitenant mode
- **IAM_Authentication**: AWS credential-based authentication used in local mode
- **Stateless_Operation**: Mode where NO persistent state (local, temporary, or in-memory) is retained between invocations
- **Session_Management**: Handling of authentication sessions and credentials

## Requirements

### Requirement 1: Single Boolean Mode Configuration

**User Story:** As a system administrator, I want to configure deployment mode with a single environment variable, so that I can eliminate configuration complexity and reduce deployment errors.

#### Acceptance Criteria

1. WHEN `QUILT_MULTITENANT_MODE=true` is set, THE ModeConfig SHALL enable multitenant mode
2. WHEN `QUILT_MULTITENANT_MODE=false` is set, THE ModeConfig SHALL enable local development mode
3. WHEN `QUILT_MULTITENANT_MODE` is unset, THE ModeConfig SHALL default to local development mode
4. THE ModeConfig SHALL provide a singleton instance accessible via `get_mode_config()` function
5. THE ModeConfig SHALL expose boolean properties for all mode-related decisions

### Requirement 2: Mode-Based Backend Selection

**User Story:** As a developer, I want the system to automatically select the appropriate backend based on deployment mode, so that I don't need to manually configure backend selection.

#### Acceptance Criteria

1. WHEN in multitenant mode, THE Backend_Factory SHALL create Platform_Backend instances
2. WHEN in local mode, THE Backend_Factory SHALL create Quilt3_Backend instances
3. THE Backend_Factory SHALL query ModeConfig instead of detecting credentials directly
4. WHEN Platform_Backend is not implemented, THE Backend_Factory SHALL create a stub with clear error messages

### Requirement 3: Mode-Based Authentication Service Selection

**User Story:** As a security administrator, I want authentication services to be selected based on deployment mode, so that security requirements are enforced consistently.

#### Acceptance Criteria

1. WHEN in multitenant mode, THE Auth_Factory SHALL only create JWT authentication services
2. WHEN in local mode, THE Auth_Factory SHALL check runtime authentication and fallback to IAM services
3. THE Auth_Factory SHALL query ModeConfig for JWT requirements instead of separate environment variables
4. WHEN multitenant mode is enabled but JWT configuration is missing, THE Auth_Factory SHALL fail with clear error messages

### Requirement 4: Elimination of Redundant Environment Variables

**User Story:** As a system administrator, I want to eliminate redundant environment variables, so that configuration is simplified and maintenance overhead is reduced.

#### Acceptance Criteria

1. THE System SHALL delete all code reading `QUILT_MCP_STATELESS_MODE` environment variable
2. THE System SHALL delete all code reading `QUILT_DISABLE_QUILT3_SESSION` environment variable  
3. THE System SHALL delete all code reading `MCP_REQUIRE_JWT` as a mode detection flag
4. THE System SHALL replace all deleted environment variable checks with ModeConfig property queries
5. WHEN searching the codebase for deleted variables, THE System SHALL return zero results in source code

### Requirement 5: Startup Configuration Validation

**User Story:** As a system administrator, I want the system to validate configuration at startup, so that invalid configurations are detected before accepting requests.

#### Acceptance Criteria

1. WHEN the server starts, THE ModeConfig SHALL validate all required configuration for the current mode
2. WHEN multitenant mode is enabled but JWT secrets are missing, THE System SHALL exit with clear error messages
3. WHEN validation fails, THE System SHALL log specific missing configuration items
4. WHEN validation succeeds, THE System SHALL log the current deployment mode and key settings
5. THE Validation SHALL occur before the server begins accepting requests

### Requirement 6: Mode-Aware HTTP Configuration

**User Story:** As a developer, I want HTTP client behavior to be configured based on deployment mode, so that stateless and stateful modes operate correctly.

#### Acceptance Criteria

1. WHEN in multitenant mode, THE HTTP_Utils SHALL enable stateless HTTP operation
2. WHEN in multitenant mode, THE HTTP_Utils SHALL enable JSON response format
3. WHEN in local mode, THE HTTP_Utils SHALL disable stateless HTTP operation
4. THE HTTP_Utils SHALL query ModeConfig instead of reading `QUILT_MCP_STATELESS_MODE` directly

### Requirement 7: Mode-Aware Session Management

**User Story:** As a developer, I want session management to respect deployment mode constraints, so that security boundaries are maintained.

#### Acceptance Criteria

1. WHEN in multitenant mode, THE Session_Services SHALL disable quilt3 library session usage
2. WHEN in local mode, THE Session_Services SHALL allow quilt3 library session usage
3. THE Session_Services SHALL query ModeConfig for session permissions instead of reading `QUILT_DISABLE_QUILT3_SESSION`
4. THE Permission_Discovery SHALL respect session management constraints from ModeConfig

### Requirement 8: Mode-Aware Runtime Context

**User Story:** As a developer, I want runtime context to be initialized based on deployment mode, so that default behaviors match the deployment environment.

#### Acceptance Criteria

1. WHEN in multitenant mode, THE Runtime_Context SHALL default to "web" environment
2. WHEN in local mode, THE Runtime_Context SHALL default to "desktop" environment  
3. THE Runtime_Context SHALL query ModeConfig for environment defaults
4. THE Runtime_Context SHALL initialize state management based on mode requirements

### Requirement 9: Test Configuration Updates

**User Story:** As a developer, I want test configurations to use the new mode system, so that tests validate both deployment modes correctly.

#### Acceptance Criteria

1. THE Unit_Tests SHALL run in default local mode without explicit configuration
2. THE Stateless_Tests SHALL explicitly set `QUILT_MULTITENANT_MODE=true`
3. THE Test_Configuration SHALL remove all references to deleted environment variables
4. THE Test_Configuration SHALL configure JWT test secrets for multitenant mode tests
5. WHEN tests run, THE Test_Suite SHALL validate both local and multitenant modes

### Requirement 10: Local Development Mode Capability

**User Story:** As a developer, I want the ability to run the system in local development mode, so that I can develop and test features locally.

#### Acceptance Criteria

1. WHEN no mode configuration is provided, THE System SHALL operate in local development mode
2. WHEN in local mode, THE System SHALL support local authentication methods (AWS profiles, IAM roles)
3. THE Local_Mode SHALL maintain filesystem state management capabilities
4. THE Local_Mode SHALL allow quilt3 library usage for development convenience
5. THE System SHALL be free to change implementation details as long as local development remains functional

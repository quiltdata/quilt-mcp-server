# Requirements Document

## Introduction

The Quilt MCP server currently has a critical authentication flaw in stateless environments. While JWT tokens successfully carry AWS role information for S3/IAM operations, they lack catalog bearer tokens required for search and package operations. This causes catalog operations to fail in Docker containers and other stateless environments where quilt3 session state is not available.

The solution requires extracting real authentication from active quilt3 sessions and embedding it in JWT tokens, rather than constructing synthetic authentication.

## Glossary

- **JWT_Helper**: Script that generates JWT tokens for testing
- **Catalog_Bearer_Token**: Authentication token required for Quilt catalog API operations
- **Quilt3_Session**: Active authentication session created by `quilt3 login`
- **MCP_Server**: Model Context Protocol server that handles Quilt operations
- **Stateless_Environment**: Execution context (like Docker) without persistent quilt3 session
- **AWS_Role_Info**: IAM role credentials for S3 and AWS operations
- **Catalog_URL**: Base URL for Quilt catalog API endpoints
- **Registry_URL**: S3 URL for the Quilt package registry

## Requirements

### Requirement 1: Extract Catalog Authentication

**User Story:** As a developer, I want JWT tokens to contain real catalog authentication, so that catalog operations work in stateless environments.

#### Acceptance Criteria

1. WHEN generating a JWT token, THE JWT_Helper SHALL extract the catalog bearer token from the active quilt3 session
2. WHEN no quilt3 session exists, THE JWT_Helper SHALL return a descriptive error message directing users to run `quilt3 login`
3. WHEN extracting session data, THE JWT_Helper SHALL retrieve the catalog URL and registry URL from quilt3 configuration
4. WHEN embedding catalog authentication, THE JWT_Helper SHALL include bearer token, catalog URL, and registry URL in JWT claims
5. WHEN catalog extraction fails, THE JWT_Helper SHALL provide specific error messages indicating the failure reason

### Requirement 2: Validate Session Prerequisites

**User Story:** As a developer, I want clear validation of quilt3 session requirements, so that I understand what setup is needed before JWT generation.

#### Acceptance Criteria

1. WHEN validating prerequisites, THE JWT_Helper SHALL check that a quilt3 session is active and authenticated
2. WHEN session validation fails, THE JWT_Helper SHALL display the exact `quilt3 login` command needed
3. WHEN session exists but is expired, THE JWT_Helper SHALL detect expiration and request re-authentication
4. WHEN multiple registries are configured, THE JWT_Helper SHALL use the default registry or allow registry selection
5. WHEN session validation succeeds, THE JWT_Helper SHALL confirm which catalog and registry will be used

### Requirement 3: Update MCP Authentication Service

**User Story:** As an MCP server, I want to use catalog authentication from JWT tokens, so that catalog operations succeed in stateless environments.

#### Acceptance Criteria

1. WHEN processing a JWT token, THE MCP_Server SHALL extract catalog bearer token from JWT claims
2. WHEN making catalog API requests, THE MCP_Server SHALL use the bearer token from JWT claims for authentication
3. WHEN catalog URL is provided in JWT, THE MCP_Server SHALL use that URL for catalog operations
4. WHEN JWT lacks catalog authentication, THE MCP_Server SHALL return a clear error message about missing catalog credentials
5. WHEN both AWS and catalog authentication are available, THE MCP_Server SHALL use appropriate credentials for each operation type

### Requirement 4: Preserve AWS Authentication

**User Story:** As an MCP server, I want to maintain existing AWS role authentication, so that S3 and IAM operations continue working.

#### Acceptance Criteria

1. WHEN processing JWT tokens, THE MCP_Server SHALL continue extracting AWS role information as before
2. WHEN making S3 operations, THE MCP_Server SHALL use AWS credentials from JWT claims
3. WHEN making IAM operations, THE MCP_Server SHALL use AWS role information from JWT claims
4. WHEN both authentication types are present, THE MCP_Server SHALL route operations to appropriate credential sets
5. WHEN AWS authentication is missing, THE MCP_Server SHALL return specific errors for AWS operations

### Requirement 5: Update Test Infrastructure

**User Story:** As a developer running tests, I want test workflows to validate authentication prerequisites, so that tests fail fast with clear guidance.

#### Acceptance Criteria

1. WHEN running stateless MCP tests, THE Test_Infrastructure SHALL verify quilt3 session exists before JWT generation
2. WHEN quilt3 session is missing, THE Test_Infrastructure SHALL display setup instructions and exit with clear error
3. WHEN generating test JWTs, THE Test_Infrastructure SHALL validate that both AWS and catalog authentication are embedded
4. WHEN running integration tests, THE Test_Infrastructure SHALL test both S3 operations and catalog operations
5. WHEN tests fail due to authentication, THE Test_Infrastructure SHALL provide specific remediation steps

### Requirement 6: Implement Catalog Operations Testing

**User Story:** As a developer, I want comprehensive testing of catalog operations, so that I can verify the authentication fix works correctly.

#### Acceptance Criteria

1. WHEN testing catalog operations, THE Test_Suite SHALL verify `search_catalog` returns results using JWT authentication
2. WHEN testing package operations, THE Test_Suite SHALL verify package listing and metadata retrieval work
3. WHEN testing in stateless mode, THE Test_Suite SHALL confirm no local quilt3 session is required
4. WHEN authentication fails, THE Test_Suite SHALL capture and report specific error details
5. WHEN all operations succeed, THE Test_Suite SHALL confirm both AWS and catalog functionality is working

### Requirement 7: Error Handling and User Guidance

**User Story:** As a developer encountering authentication issues, I want clear error messages and guidance, so that I can quickly resolve problems.

#### Acceptance Criteria

1. WHEN JWT generation fails, THE System SHALL provide step-by-step instructions for resolution
2. WHEN catalog authentication is missing, THE System SHALL explain the difference between AWS and catalog authentication
3. WHEN session is expired, THE System SHALL provide the exact commands needed to re-authenticate
4. WHEN configuration is invalid, THE System SHALL identify specific configuration problems
5. WHEN operations fail in stateless mode, THE System SHALL distinguish between AWS and catalog authentication failures

### Requirement 8: Backward Compatibility

**User Story:** As a developer with existing JWT workflows, I want the authentication fix to be backward compatible, so that existing functionality continues working.

#### Acceptance Criteria

1. WHEN processing legacy JWT tokens, THE MCP_Server SHALL continue supporting AWS-only authentication for S3 operations
2. WHEN catalog authentication is unavailable, THE MCP_Server SHALL gracefully degrade catalog operations with informative errors
3. WHEN updating JWT generation, THE System SHALL maintain existing AWS role extraction functionality
4. WHEN running existing tests, THE System SHALL preserve current AWS authentication test coverage
5. WHEN deploying updates, THE System SHALL not break existing AWS-only JWT workflows
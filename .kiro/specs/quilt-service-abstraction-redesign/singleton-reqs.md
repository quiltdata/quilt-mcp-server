# Requirements: Request-Scoped Service Management

## Introduction

The Quilt MCP server currently uses module-level singleton patterns for critical services (authentication, permissions, workflows). This design assumes a single-user-per-process model, which is appropriate for CLI tools but fundamentally incompatible with multitenant server deployments where multiple users' requests are handled by the same long-lived process.

These singletons create shared mutable state across all requests, leading to critical security vulnerabilities including credential leakage, permission cache poisoning, and data isolation violations. This redesign will eliminate module-level singletons and introduce request-scoped service management to enable safe multitenant deployments.

## Problem Statement

The MCP server contains three module-level singletons that maintain user-specific state:

1. **`auth_service.py:_AUTH_SERVICE`**: Cached authentication service that provides boto3 sessions with AWS credentials
   - Initialized once based on environment variables (JWT vs IAM mode)
   - Reused across all requests in the process
   - Contains user-specific AWS credentials that bleed across request boundaries

2. **`permissions_service.py:_permission_discovery`**: Cached AWS permission discovery service
   - Initializes AWS clients (S3, IAM, STS) once with first request's credentials
   - Maintains TTL caches of permission checks and bucket access
   - Shares permission cache across all users, enabling privilege escalation

3. **`workflow_service.py:_workflows`**: In-memory workflow storage dictionary
   - Shared mutable dictionary storing all users' workflow definitions
   - No tenant isolation - users can overwrite each other's workflows
   - No persistence - workflows lost on process restart

### Security Impact

In a multitenant deployment where the MCP server handles concurrent requests from multiple users:

- **Credential Leakage**: User A's AWS credentials cached in `_AUTH_SERVICE` are reused for User B's requests
- **Permission Escalation**: User A's permission check results cached in `_permission_discovery` returned to User B
- **Data Isolation Violation**: User A can see and modify User B's workflows in shared `_workflows` dictionary
- **Compliance Violations**: Audit logs show incorrect user identities for AWS operations

### Current Behavior

```
Process Start
    │
    ├─> Request 1 (User A, JWT for Account X)
    │   └─> Initializes _AUTH_SERVICE with User A's credentials
    │   └─> Initializes _permission_discovery with User A's AWS clients
    │   └─> Creates workflow in shared _workflows dict
    │
    ├─> Request 2 (User B, JWT for Account Y)
    │   └─> Reuses _AUTH_SERVICE with User A's credentials ❌
    │   └─> Reuses _permission_discovery with User A's AWS clients ❌
    │   └─> Sees User A's workflow in _workflows dict ❌
    │
    └─> Request 3 (User C, different credentials)
        └─> Same problems - shared state across all users ❌
```

## Glossary

- **Module-Level Singleton**: Global variable initialized once at module import time, shared across all code using that module
- **Request-Scoped Instance**: Service instance created per request, containing only that request's user context
- **Request Context**: Container holding all user-specific services and state for a single request/tool invocation
- **Auth Service**: Service providing boto3.Session with AWS credentials (IAM or JWT-derived)
- **Permission Discovery**: Service caching AWS permission checks and bucket access results
- **Workflow Service**: Service managing user-defined workflow definitions
- **Tenant Isolation**: Guarantee that one user cannot access another user's data or credentials
- **Credential Leakage**: Security vulnerability where User A's credentials are exposed to User B
- **Permission Cache Poisoning**: Vulnerability where User A's cached permissions are returned to User B

## Requirements

### Requirement 1: Eliminate Module-Level Singletons

**User Story**: As a security engineer, I need to ensure that no user-specific state is shared between different users' requests, so that credential leakage and permission escalation vulnerabilities are eliminated.

#### Acceptance Criteria

1. WHEN the MCP server processes multiple requests from different users, EACH request SHALL have its own isolated auth service instance
2. WHEN the MCP server processes multiple requests from different users, EACH request SHALL have its own isolated permission discovery instance
3. WHEN the MCP server processes multiple requests from different users, EACH request SHALL have its own isolated workflow service instance
4. THE system SHALL NOT use module-level global variables (`_AUTH_SERVICE`, `_permission_discovery`, `_workflows`) for storing user-specific state
5. WHEN a request completes, ITS service instances SHALL be eligible for garbage collection (no persistent references)

### Requirement 2: Request-Scoped Service Lifecycle

**User Story**: As an MCP tool developer, I want service instances to be automatically scoped to the current request, so that I don't accidentally use another user's credentials or permissions.

#### Acceptance Criteria

1. WHEN an MCP tool is invoked, THE system SHALL create a new request context containing fresh service instances
2. WHEN an MCP tool accesses the auth service, THE system SHALL provide the auth service instance for the current request only
3. WHEN an MCP tool accesses the permission discovery service, THE system SHALL provide the permission discovery instance for the current request only
4. WHEN an MCP tool accesses the workflow service, THE system SHALL provide the workflow service instance for the current request only
5. WHEN the MCP tool completes, THE request context and its service instances SHALL be destroyed

### Requirement 3: Authentication Context Isolation

**User Story**: As a user, I need my AWS credentials to be isolated from other users' credentials, so that other users cannot access my AWS resources using my identity.

#### Acceptance Criteria

1. WHEN User A makes a request with JWT token for AWS Account X, THE auth service SHALL use ONLY User A's credentials
2. WHEN User B makes a concurrent request with JWT token for AWS Account Y, THE auth service SHALL use ONLY User B's credentials
3. User A's auth service instance SHALL NOT be accessible to User B's request
4. User B's auth service instance SHALL NOT be accessible to User A's request
5. WHEN a request completes, THE auth service instance SHALL NOT be cached for reuse by other requests

### Requirement 4: Permission Cache Isolation

**User Story**: As a compliance officer, I need to ensure that permission checks are performed with the correct user's credentials, so that audit logs accurately reflect who accessed which resources.

#### Acceptance Criteria

1. WHEN User A checks permissions for bucket X, THE permission discovery service SHALL use User A's AWS credentials
2. WHEN User B checks permissions for bucket X, THE permission discovery service SHALL use User B's AWS credentials (NOT cached results from User A)
3. WHEN User A's cached permissions expire, THE cache invalidation SHALL NOT affect User B's permission cache
4. THE permission discovery service SHALL NOT share its permission cache across different users' requests
5. WHEN a permission check is logged, THE log SHALL contain the correct requesting user's identity (not another user's identity)

### Requirement 5: Workflow Data Isolation

**User Story**: As a user, I need my workflow definitions to be private and persistent, so that other users cannot see, modify, or delete my workflows, and so that my workflows survive server restarts.

#### Acceptance Criteria

1. WHEN User A creates a workflow named "analysis", THE workflow SHALL be associated with User A's tenant/user ID
2. WHEN User B creates a workflow named "analysis", THE workflow SHALL be associated with User B's tenant/user ID (not overwrite User A's workflow)
3. WHEN User A lists workflows, THE result SHALL contain ONLY User A's workflows (not User B's workflows)
4. WHEN User A deletes a workflow, THE operation SHALL affect ONLY User A's workflows (not User B's workflows)
5. WHEN the MCP server restarts, THE workflows SHALL persist and remain associated with the correct users

### Requirement 6: Single-User Mode Support

**User Story**: As a CLI tool user, I want the MCP server to work in single-user mode without
requiring tenant configuration, so that simple deployments remain simple.

#### Acceptance Criteria

1. WHEN the MCP server runs in single-user mode (environment flag or configuration), THE system SHALL use simplified service lifecycle management
2. WHEN running in single-user mode, THE system SHALL NOT require tenant IDs
3. WHEN running in single-user mode, THE system SHALL use "default" as the tenant ID automatically
4. THE system SHALL auto-detect single-user vs multitenant mode based on configuration
5. THE system SHALL support both single-user and multitenant modes with the same codebase

### Requirement 7: Request Context Propagation

**User Story**: As a developer working on MCP tools, I need a clear mechanism to access request-scoped services, so that I don't need to manually thread context through every function call.

#### Acceptance Criteria

1. WHEN an MCP tool is invoked, THE system SHALL establish a request context containing all required services
2. WHEN an MCP tool needs to access a service, THE tool SHALL be able to retrieve it from the request context without manual threading
3. THE request context propagation mechanism SHALL work correctly with nested tool calls
4. THE request context propagation mechanism SHALL work correctly with async/await patterns
5. WHEN a request context is not available (e.g., called outside request scope), THE system SHALL provide a clear error message

### Requirement 8: Concurrent Request Safety

**User Story**: As a platform engineer, I need the MCP server to safely handle concurrent requests from multiple users, so that race conditions and data corruption do not occur.

#### Acceptance Criteria

1. WHEN two users make concurrent requests, EACH request SHALL have completely isolated service instances
2. WHEN User A modifies their workflow during User B's concurrent request, THE operations SHALL NOT interfere with each other
3. THE system SHALL NOT use shared mutable state that could cause race conditions between concurrent requests
4. WHEN testing with concurrent load, THE system SHALL NOT exhibit credential leakage or data corruption
5. THE system SHALL NOT require global locks or mutexes to prevent race conditions (design shall be thread-safe by isolation)

### Requirement 9: Testing and Validation

**User Story**: As a quality assurance engineer, I need comprehensive tests that validate tenant isolation, so that I can verify that security vulnerabilities have been eliminated.

#### Acceptance Criteria

1. THE test suite SHALL include tests that simulate concurrent requests from multiple users with different credentials
2. THE test suite SHALL verify that User A cannot access User B's credentials, permissions, or workflows
3. THE test suite SHALL verify that permission caches are not shared between users
4. THE test suite SHALL verify that workflow storage is isolated per tenant/user
5. THE test suite SHALL include load tests that verify correct behavior under concurrent request load

### Requirement 10: Migration Strategy

**User Story**: As a system administrator, I need a clear migration path from the current singleton architecture to request-scoped services, so that I can deploy the changes without breaking existing deployments.

#### Acceptance Criteria

1. THE migration SHALL support incremental rollout (one service at a time)
2. THE migration SHALL include feature flags to enable/disable new behavior
3. WHEN a service is migrated, THE old singleton pattern SHALL be removed (not deprecated alongside new pattern)
4. THE migration SHALL NOT require changes to MCP tool implementations (transparent to tool developers)
5. THE migration documentation SHALL include rollback procedures in case of issues

## Non-Functional Requirements

### Performance

1. Request-scoped service creation SHALL add less than 10ms overhead per request
2. Service instance creation SHALL be optimized to avoid unnecessary initialization work
3. Permission cache SHALL remain effective within a single request context (no performance regression)

### Observability

1. Log entries SHALL include request context identifiers to trace service instances
2. Metrics SHALL track service instance creation and destruction rates
3. Alerts SHALL trigger if service instances are not being garbage collected (memory leak detection)

### Security

1. Service instances SHALL NOT be serializable or transferable between requests
2. Service instance memory SHALL be cleared when instances are destroyed
3. Credentials stored in service instances SHALL NOT be logged or persisted

## Out of Scope

The following are explicitly **not** part of this requirements document:

1. **Multi-region deployment**: This focuses on single-process isolation, not distributed systems
2. **Distributed caching**: Permission caches remain in-process, not shared across servers
3. **External workflow storage**: Workflow persistence mechanism is implementation detail
4. **Authentication protocol changes**: This addresses service lifecycle, not authentication mechanisms
5. **QuiltOps backend selection**: Backend selection logic is independent of service scoping

## Success Criteria

This requirements initiative is considered successful when:

- [ ] No module-level singletons exist for user-specific services (auth, permissions, workflows)
- [ ] Concurrent requests from different users have completely isolated service instances
- [ ] Security tests demonstrate no credential leakage or permission cache poisoning
- [ ] Existing single-user deployments continue to work without configuration changes
- [ ] MCP tools require no code changes to adopt new service lifecycle
- [ ] Performance overhead for request-scoped services is less than 10ms per request
- [ ] All existing tests pass with new request-scoped architecture
- [ ] Documentation clearly explains migration path and new architecture

# Implementation Tasks: Request-Scoped Service Management

## Elimination of Module-Level Singletons

This task list follows Test-Driven Development (TDD) principles and implements the migration
incrementally across four phases. Each phase can be deployed independently.

**Migration Phases:**

- **Phase 1**: Eliminate authentication service singleton (`_AUTH_SERVICE`)
- **Phase 2**: Eliminate permission discovery singleton (`_permission_discovery`)
- **Phase 3**: Eliminate workflow service singleton (`_workflows`)
- **Phase 4**: Add multitenant deployment support

---

## Phase 1: Auth Service Migration

### Task 1: Create Request Context Foundation (TDD)

Create the core request context infrastructure using TDD approach.

#### 1.1 TDD: RequestContext dataclass

- [x] Write tests for RequestContext in `tests/unit/context/test_request_context.py`
- [x] Write tests for required field validation (request_id, tenant_id, auth_service)
- [x] Write tests for is_authenticated property
- [x] Write tests for get_boto_session() method
- [x] Write tests that RequestContext rejects missing services
- [x] Create `src/quilt_mcp/context/request_context.py` to make tests pass
- [x] Implement RequestContext with fields: request_id, tenant_id, user_id, auth_service,
  permission_service, workflow_service
- [x] Add `__post_init__` validation for required services
- [x] Implement `is_authenticated` property
- [x] Implement get_boto_session() convenience method

#### 1.2 TDD: Request context exceptions

- [x] Write tests for context exceptions in `tests/unit/context/test_exceptions.py`
- [x] Write tests for ContextNotAvailableError with clear error message
- [x] Write tests for ServiceInitializationError with service name and reason
- [x] Write tests for TenantValidationError for single-user vs multitenant modes
- [x] Create `src/quilt_mcp/context/exceptions.py` to make tests pass
- [x] Implement ContextNotAvailableError with actionable error message
- [x] Implement ServiceInitializationError with service context
- [x] Implement TenantValidationError with mode-specific messages

#### 1.3 Verification Checkpoint: Request Context Foundation

- [x] Run linting: `ruff check src/quilt_mcp/context/`
- [x] Run tests: `pytest tests/unit/context/ -v`
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: implement RequestContext foundation"`

---

### Task 2: Refactor Auth Service to Remove Singleton (TDD)

Update auth service to be instantiable per-request instead of module-level singleton.

#### 2.1 TDD: Auth service base class

- [x] Write tests for AuthService ABC in `tests/unit/services/test_auth_service.py`
- [x] Write tests for abstract method requirements (get_session, is_valid, get_user_identity)
- [x] Write tests that instantiation is possible (not a singleton)
- [x] Write tests for session caching within a single instance
- [x] Update `src/quilt_mcp/services/auth_service.py` to remove singleton pattern
- [x] Remove module-level `_AUTH_SERVICE` variable
- [x] Define AuthService as abstract base class with required methods
- [x] Ensure AuthService can be instantiated multiple times

#### 2.2 TDD: JWTAuthService implementation

- [x] Write tests for JWTAuthService in `tests/unit/services/test_jwt_auth_service.py`
- [x] Write tests for JWT token validation
- [x] Write tests for AWS credential exchange
- [x] Write tests for boto3 session creation
- [x] Write tests for is_valid() checking JWT expiration
- [x] Write tests for get_user_identity() extracting user info from JWT
- [x] Create or update `src/quilt_mcp/services/jwt_auth_service.py` to make tests pass
- [x] Implement JWT validation logic
- [x] Implement AWS credential exchange from JWT
- [x] Implement boto3 session creation with JWT-derived credentials
- [x] Implement is_valid() and get_user_identity() methods

#### 2.3 TDD: IAMAuthService implementation

- [x] Write tests for IAMAuthService in `tests/unit/services/test_iam_auth_service.py`
- [x] Write tests for quilt3 session config validation
- [x] Write tests for boto3 session creation from quilt3 config
- [x] Write tests for is_valid() checking session validity
- [x] Write tests for get_user_identity() from session
- [x] Create or update `src/quilt_mcp/services/iam_auth_service.py` to make tests pass
- [x] Implement quilt3 session validation
- [x] Implement boto3 session creation from session config
- [x] Implement is_valid() and get_user_identity() methods

#### 2.4 TDD: Remove singleton usage in existing code

- [x] Write tests that verify singleton accessor is removed
- [x] Write tests that verify code must use passed-in auth_service instances
- [x] Remove `get_auth_service()` singleton accessor function
- [x] Remove module-level `_AUTH_SERVICE` variable
- [x] Update all code that used singleton to accept auth_service parameter

#### 2.5 Verification Checkpoint: Auth Service Refactor

- [x] Run linting: `ruff check src/quilt_mcp/services/`
- [x] Run tests: `pytest tests/unit/services/test_*auth*.py -v`
- [x] Verify no module-level `_AUTH_SERVICE` variable exists
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: refactor auth service to remove singleton pattern"`

---

### Task 3: Implement RequestContextFactory (TDD)

Create factory for creating request-scoped service instances.

#### 3.1 TDD: Factory initialization and mode detection

- [x] Write tests for RequestContextFactory in `tests/unit/context/test_factory.py`
- [x] Write tests for mode detection (single-user, multitenant, auto)
- [x] Write tests for auto mode reading QUILT_MULTITENANT_MODE env var
- [x] Write tests for explicit mode override
- [x] Create `src/quilt_mcp/context/factory.py` to make tests pass
- [x] Implement __init__ with mode parameter
- [x] Implement _determine_mode() for auto-detection
- [x] Add environment variable reading for mode detection

#### 3.2 TDD: Context creation with auth service

- [x] Write tests for create_context() method
- [x] Write tests for JWT token authentication path
- [x] Write tests for quilt3 session authentication path
- [x] Write tests for tenant_id validation in multitenant mode
- [x] Write tests for default tenant in single-user mode
- [x] Write tests for request_id generation (unique per request)
- [x] Write tests for error when no authentication provided
- [x] Implement create_context() method
- [x] Implement _create_auth_service() with JWT vs IAM routing
- [x] Add tenant_id validation logic
- [x] Add request_id generation using uuid
- [x] Add clear error messages for authentication failures

#### 3.3 TDD: Service instance creation

- [x] Write tests that verify each context gets new auth service instance
- [x] Write tests that verify auth service instances are not shared
- [x] Write tests for error handling in service creation
- [x] Write tests that service instances are eligible for GC after context deletion
- [x] Implement service instance creation without caching
- [x] Ensure each create_context() call creates fresh service instances
- [x] Add error handling and wrapping for service creation failures

#### 3.4 Verification Checkpoint: RequestContextFactory

- [ ] Run linting: `ruff check src/quilt_mcp/context/`
- [ ] Run tests: `pytest tests/unit/context/test_factory.py -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: implement RequestContextFactory for auth service"`

---

### Task 4: Integrate Request Context into MCP Server (TDD)

Update MCP server to create request contexts for each tool invocation.

#### 4.1 TDD: Context propagation mechanism

- [ ] Write tests for context propagation in `tests/unit/server/test_context_propagation.py`
- [ ] Write tests for set_current_context() and get_current_context()
- [ ] Write tests that context is thread-safe (or async-safe)
- [ ] Write tests for ContextNotAvailableError when accessed outside request
- [ ] Write tests that context is cleared after request completes
- [ ] Create `src/quilt_mcp/context/propagation.py` to make tests pass
- [ ] Implement thread-local or context variable storage
- [ ] Implement set_current_context() and get_current_context()
- [ ] Add proper cleanup in finally blocks

#### 4.2 TDD: MCP tool handler integration

- [ ] Write tests for MCP handler with context creation in `tests/unit/server/test_mcp_handler.py`
- [ ] Write tests that context is created before tool execution
- [ ] Write tests that context is cleared after tool execution
- [ ] Write tests that tool execution errors still clean up context
- [ ] Write tests for auth info extraction from MCP request
- [ ] Update MCP server tool handler in `src/quilt_mcp/server.py`
- [ ] Add context factory initialization
- [ ] Add context creation at start of each tool invocation
- [ ] Add context cleanup in finally block
- [ ] Implement auth info extraction from request

#### 4.3 TDD: Update tools to use request context

- [ ] Write tests that tools can access current context via get_current_context()
- [ ] Write tests that tools get auth service from context
- [ ] Write tests that tools no longer use singleton accessor
- [ ] Update all tools to use get_current_context()
- [ ] Document migration pattern for reference

#### 4.4 Verification Checkpoint: MCP Server Integration

- [ ] Run linting: `ruff check src/quilt_mcp/server.py src/quilt_mcp/context/`
- [ ] Run tests: `pytest tests/unit/server/ -v`
- [ ] Test MCP server startup with new context creation
- [ ] Verify context is created and cleaned up correctly
- [ ] Commit changes: `git add . && git commit -m "feat: integrate request context into MCP server"`

---

### Task 5: Migration Testing and Validation (Phase 1)

Comprehensive testing to verify singleton elimination for auth service.

#### 5.1 TDD: Concurrent request isolation tests

- [ ] Write integration tests for concurrent requests in `tests/integration/test_auth_isolation.py`
- [ ] Write tests that simulate 10+ concurrent requests with different users
- [ ] Write tests that verify each request has isolated auth service instance
- [ ] Write tests that User A's credentials are not accessible to User B
- [ ] Write tests that boto3 sessions are isolated per request
- [ ] Implement async test infrastructure for concurrent requests
- [ ] Verify all isolation tests pass

#### 5.2 TDD: Memory leak detection tests

- [ ] Write tests for service instance cleanup in `tests/integration/test_memory_cleanup.py`
- [ ] Write tests using weakref to verify GC eligibility
- [ ] Write tests that service instances are destroyed after request
- [ ] Write tests that no references are retained after context deletion
- [ ] Write tests for multiple request cycles to detect leaks
- [ ] Verify all memory tests pass

#### 5.3 TDD: Performance regression tests

- [ ] Write performance tests in `tests/performance/test_context_overhead.py`
- [ ] Write tests measuring context creation time (must be < 10ms)
- [ ] Write tests comparing performance before and after migration
- [ ] Write tests for 100+ request creations to measure average overhead
- [ ] Verify performance requirements are met

#### 5.4 TDD: Security validation tests

- [ ] Write security tests in `tests/security/test_credential_isolation.py`
- [ ] Write tests that attempt to access another user's credentials
- [ ] Write tests that verify credentials are destroyed after request
- [ ] Write tests that credentials are not logged or persisted
- [ ] Write tests for audit logging with correct user identity
- [ ] Verify all security tests pass

#### 5.5 Verification Checkpoint: Phase 1 Complete

- [ ] Run linting: `ruff check src/quilt_mcp/`
- [ ] Run full test suite: `pytest -v`
- [ ] Run integration tests: `pytest tests/integration/test_auth_isolation.py -v`
- [ ] Run security tests: `pytest tests/security/test_credential_isolation.py -v`
- [ ] Verify no `_AUTH_SERVICE` module-level variable exists in codebase
- [ ] Verify MCP server works with request-scoped auth
- [ ] Commit changes: `git add . && git commit -m "feat: Phase 1 complete - auth service singleton eliminated"`
- [ ] Create tag: `git tag phase1-auth-singleton-eliminated`

---

## Phase 2: Permission Service Migration

### Task 6: Refactor Permission Discovery Service (TDD)

Update permission service to be instantiable per-request.

#### 6.1 TDD: Permission service initialization

- [ ] Write tests for PermissionDiscoveryService in `tests/unit/services/test_permission_service.py`
- [ ] Write tests that service accepts AuthService in constructor
- [ ] Write tests that service initializes AWS clients from auth service session
- [ ] Write tests that service has request-scoped cache (not shared)
- [ ] Write tests that multiple instances have isolated caches
- [ ] Update `src/quilt_mcp/services/permissions_service.py` to remove singleton
- [ ] Remove module-level `_permission_discovery` variable
- [ ] Update constructor to accept AuthService parameter
- [ ] Initialize AWS clients from auth service's boto3 session
- [ ] Ensure cache is instance variable (not module-level)

#### 6.2 TDD: Permission cache isolation

- [ ] Write tests that cache is not shared between instances
- [ ] Write tests that cache TTL is per-instance
- [ ] Write tests that cache invalidation doesn't affect other instances
- [ ] Write tests for cache key generation
- [ ] Verify cache implementation uses instance variables
- [ ] Add tests for cache eviction and expiration

#### 6.3 TDD: Remove singleton usage

- [ ] Write tests that old singleton accessor no longer works
- [ ] Write tests that code must use passed-in permission_service instances
- [ ] Remove `get_permission_discovery()` singleton accessor
- [ ] Update code that used singleton to accept permission_service parameter
- [ ] Add deprecation warnings if needed

#### 6.4 Verification Checkpoint: Permission Service Refactor

- [ ] Run linting: `ruff check src/quilt_mcp/services/permissions_service.py`
- [ ] Run tests: `pytest tests/unit/services/test_permission_service.py -v`
- [ ] Verify no `_permission_discovery` module-level variable exists
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: refactor permission service to remove singleton"`

---

### Task 7: Integrate Permission Service into Request Context (TDD)

Add permission service to request context creation.

#### 7.1 TDD: Update RequestContext with permission service

- [ ] Write tests for RequestContext with permission_service field
- [ ] Write tests that permission_service is required
- [ ] Write tests for convenience methods accessing permission service
- [ ] Update `src/quilt_mcp/context/request_context.py`
- [ ] Add permission_service field to RequestContext
- [ ] Add validation that permission_service is not None
- [ ] Add convenience methods for permission checks

#### 7.2 TDD: Update factory to create permission service

- [ ] Write tests for factory creating permission service
- [ ] Write tests that permission service gets auth service from context
- [ ] Write tests that each context gets fresh permission service instance
- [ ] Write tests for error handling in permission service creation
- [ ] Update `src/quilt_mcp/context/factory.py`
- [ ] Implement _create_permission_service() method
- [ ] Pass auth_service to PermissionDiscoveryService constructor
- [ ] Add error handling and wrapping

#### 7.3 TDD: Update tools to use context permission service

- [ ] Write tests that tools access permission service via context
- [ ] Write tests that tools no longer use singleton accessor
- [ ] Update all tools to use `get_current_context().permission_service`
- [ ] Remove singleton accessor calls from tools

#### 7.4 Verification Checkpoint: Permission Service Integration

- [ ] Run linting: `ruff check src/quilt_mcp/context/ src/quilt_mcp/services/`
- [ ] Run tests: `pytest tests/unit/context/ tests/unit/services/ -v`
- [ ] Verify permission service is created per-request
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: integrate permission service into request context"`

---

### Task 8: Permission Cache Isolation Testing (TDD)

Validate that permission caches are isolated per request.

#### 8.1 TDD: Permission cache isolation tests

- [ ] Write tests in `tests/integration/test_permission_isolation.py`
- [ ] Write tests that User A's cached permissions not visible to User B
- [ ] Write tests that concurrent permission checks are isolated
- [ ] Write tests that cache TTL is per-instance
- [ ] Write tests that User A's cache invalidation doesn't affect User B
- [ ] Verify all isolation tests pass

#### 8.2 TDD: Permission check correctness tests

- [ ] Write tests that permission checks use correct user's credentials
- [ ] Write tests that AWS API calls use correct boto3 session
- [ ] Write tests for audit logging with correct user identity
- [ ] Verify permission checks are correct per user

#### 8.3 Verification Checkpoint: Phase 2 Complete

- [ ] Run linting: `ruff check src/quilt_mcp/`
- [ ] Run full test suite: `pytest -v`
- [ ] Run integration tests: `pytest tests/integration/test_permission_isolation.py -v`
- [ ] Verify no `_permission_discovery` module-level variable exists
- [ ] Verify MCP server works with request-scoped permissions
- [ ] Commit changes: `git add . && git commit -m "feat: Phase 2 complete - permission service singleton eliminated"`
- [ ] Create tag: `git tag phase2-permission-singleton-eliminated`

---

## Phase 3: Workflow Service Migration

### Task 9: Implement Tenant-Isolated Workflow Storage (TDD)

Create workflow storage with tenant partitioning.

#### 9.1 TDD: Workflow storage interface

- [ ] Write tests for WorkflowStorage ABC in `tests/unit/storage/test_workflow_storage.py`
- [ ] Write tests for abstract methods: save, load, list_all, delete
- [ ] Write tests that storage is tenant-aware
- [ ] Create `src/quilt_mcp/storage/workflow_storage.py`
- [ ] Define WorkflowStorage abstract base class
- [ ] Define methods for CRUD operations on workflows
- [ ] Add tenant_id to all method signatures

#### 9.2 TDD: File-based workflow storage

- [ ] Write tests for FileBasedWorkflowStorage in `tests/unit/storage/test_file_storage.py`
- [ ] Write tests for tenant directory isolation (~/.quilt/workflows/{tenant_id}/)
- [ ] Write tests that Tenant A cannot access Tenant B's workflows
- [ ] Write tests for workflow JSON serialization
- [ ] Write tests for workflow CRUD operations
- [ ] Create `src/quilt_mcp/storage/file_storage.py`
- [ ] Implement FileBasedWorkflowStorage with tenant directories
- [ ] Implement save, load, list_all, delete methods
- [ ] Add file system isolation per tenant
- [ ] Add error handling for file operations

#### 9.3 TDD: Workflow persistence

- [ ] Write tests that workflows survive process restart
- [ ] Write tests for workflow data consistency
- [ ] Write tests for concurrent workflow access safety
- [ ] Verify file-based storage persists correctly
- [ ] Add file locking if needed for concurrent safety

#### 9.4 Verification Checkpoint: Workflow Storage

- [ ] Run linting: `ruff check src/quilt_mcp/storage/`
- [ ] Run tests: `pytest tests/unit/storage/ -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: implement tenant-isolated workflow storage"`

---

### Task 10: Refactor Workflow Service (TDD)

Update workflow service to use tenant-isolated storage.

#### 10.1 TDD: Workflow service with tenant isolation

- [ ] Write tests for WorkflowService in `tests/unit/services/test_workflow_service.py`
- [ ] Write tests that service accepts tenant_id in constructor
- [ ] Write tests that service uses tenant-partitioned storage
- [ ] Write tests that workflow operations only affect tenant's workflows
- [ ] Update `src/quilt_mcp/services/workflow_service.py` to remove singleton
- [ ] Remove module-level `_workflows` dictionary
- [ ] Update constructor to accept tenant_id parameter
- [ ] Initialize workflow storage with tenant isolation
- [ ] Update all workflow methods to use storage backend

#### 10.2 TDD: Workflow CRUD operations

- [ ] Write tests for create_workflow() with tenant isolation
- [ ] Write tests for get_workflow() with tenant isolation
- [ ] Write tests for list_workflows() showing only tenant's workflows
- [ ] Write tests for delete_workflow() with tenant isolation
- [ ] Write tests that Tenant A cannot see/modify Tenant B's workflows
- [ ] Implement workflow CRUD methods using storage backend
- [ ] Ensure all operations are tenant-scoped

#### 10.3 TDD: Remove singleton usage

- [ ] Write tests that old singleton accessor no longer works
- [ ] Write tests that code must use passed-in workflow_service instances
- [ ] Remove `get_workflow_service()` singleton accessor
- [ ] Update code that used singleton to accept workflow_service parameter

#### 10.4 Verification Checkpoint: Workflow Service Refactor

- [ ] Run linting: `ruff check src/quilt_mcp/services/workflow_service.py`
- [ ] Run tests: `pytest tests/unit/services/test_workflow_service.py -v`
- [ ] Verify no `_workflows` module-level variable exists
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: refactor workflow service with tenant isolation"`

---

### Task 11: Integrate Workflow Service into Request Context (TDD)

Add workflow service to request context creation.

#### 11.1 TDD: Update RequestContext with workflow service

- [ ] Write tests for RequestContext with workflow_service field
- [ ] Write tests that workflow_service is required
- [ ] Write tests for convenience methods accessing workflow service
- [ ] Update `src/quilt_mcp/context/request_context.py`
- [ ] Add workflow_service field to RequestContext
- [ ] Add validation that workflow_service is not None
- [ ] Add convenience methods for workflow operations

#### 11.2 TDD: Update factory to create workflow service

- [ ] Write tests for factory creating workflow service
- [ ] Write tests that workflow service gets tenant_id from context
- [ ] Write tests that each context gets fresh workflow service instance
- [ ] Write tests for error handling in workflow service creation
- [ ] Update `src/quilt_mcp/context/factory.py`
- [ ] Implement _create_workflow_service() method
- [ ] Pass tenant_id to WorkflowService constructor
- [ ] Add error handling and wrapping

#### 11.3 TDD: Update tools to use context workflow service

- [ ] Write tests that tools access workflow service via context
- [ ] Write tests that tools no longer use singleton accessor
- [ ] Update workflow tools to use `get_current_context().workflow_service`
- [ ] Remove singleton accessor calls from tools
- [ ] Verify tenant isolation in tool operations

#### 11.4 Verification Checkpoint: Workflow Service Integration

- [ ] Run linting: `ruff check src/quilt_mcp/context/ src/quilt_mcp/services/`
- [ ] Run tests: `pytest tests/unit/context/ tests/unit/services/ -v`
- [ ] Verify workflow service is created per-request
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: integrate workflow service into request context"`

---

### Task 12: Workflow Isolation Testing (TDD)

Validate that workflows are isolated per tenant.

#### 12.1 TDD: Workflow tenant isolation tests

- [ ] Write tests in `tests/integration/test_workflow_isolation.py`
- [ ] Write tests that Tenant A cannot see Tenant B's workflows
- [ ] Write tests that workflow names don't collide across tenants
- [ ] Write tests that workflow operations are tenant-scoped
- [ ] Write tests that workflow deletion only affects tenant's workflows
- [ ] Verify all isolation tests pass

#### 12.2 TDD: Workflow persistence tests

- [ ] Write tests for workflow persistence across process restarts
- [ ] Write tests for workflow data integrity
- [ ] Write tests that tenant isolation survives restarts
- [ ] Verify persistence works correctly

#### 12.3 TDD: Concurrent workflow access tests

- [ ] Write tests for concurrent workflow operations
- [ ] Write tests that User A and User B can modify workflows concurrently
- [ ] Write tests for race condition safety
- [ ] Verify concurrent access is safe

#### 12.4 Verification Checkpoint: Phase 3 Complete

- [ ] Run linting: `ruff check src/quilt_mcp/`
- [ ] Run full test suite: `pytest -v`
- [ ] Run integration tests: `pytest tests/integration/test_workflow_isolation.py -v`
- [ ] Verify no `_workflows` module-level variable exists
- [ ] Verify MCP server works with tenant-isolated workflows
- [ ] Commit changes: `git add . && git commit -m "feat: Phase 3 complete - workflow service singleton eliminated"`
- [ ] Create tag: `git tag phase3-workflow-singleton-eliminated`

---

## Phase 4: Multitenant Deployment Support

### Task 13: Add Multitenant Mode Support (TDD)

Enable multitenant mode with tenant extraction and validation.

#### 13.1 TDD: Tenant extraction from authentication

- [ ] Write tests for tenant extraction in `tests/unit/context/test_tenant_extraction.py`
- [ ] Write tests for extracting tenant_id from JWT token
- [ ] Write tests for extracting tenant_id from session metadata
- [ ] Write tests for fallback to environment variable
- [ ] Write tests for error when tenant_id missing in multitenant mode
- [ ] Create `src/quilt_mcp/context/tenant_extraction.py`
- [ ] Implement JWT token decoding for tenant_id
- [ ] Implement session metadata parsing for tenant_id
- [ ] Add environment variable fallback
- [ ] Add validation and error messages

#### 13.2 TDD: Update factory for tenant extraction

- [ ] Write tests for factory extracting tenant from auth_info
- [ ] Write tests for multitenant mode requiring tenant_id
- [ ] Write tests for single-user mode using "default" tenant
- [ ] Write tests for mode-specific validation
- [ ] Update `src/quilt_mcp/context/factory.py`
- [ ] Add tenant extraction logic in create_context()
- [ ] Add mode-specific validation
- [ ] Add clear error messages for missing tenant_id

#### 13.3 TDD: Environment-based mode detection

- [ ] Write tests for QUILT_MULTITENANT_MODE environment variable
- [ ] Write tests for auto-detection logic
- [ ] Write tests for explicit mode override
- [ ] Update factory to read environment variable
- [ ] Implement auto-detection logic
- [ ] Document environment variable usage

#### 13.4 Verification Checkpoint: Multitenant Mode

- [ ] Run linting: `ruff check src/quilt_mcp/context/`
- [ ] Run tests: `pytest tests/unit/context/test_tenant_extraction.py -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: add multitenant mode support with tenant extraction"`

---

### Task 14: Multitenant Integration Testing (TDD)

Comprehensive testing for multitenant deployments.

#### 14.1 TDD: Multitenant concurrent request tests

- [ ] Write tests in `tests/integration/test_multitenant.py`
- [ ] Write tests for 20+ concurrent requests from different tenants
- [ ] Write tests that each tenant has completely isolated services
- [ ] Write tests that Tenant A cannot access Tenant B's data
- [ ] Write tests for credential, permission, and workflow isolation
- [ ] Verify all multitenant tests pass

#### 14.2 TDD: Single-user mode tests

- [ ] Write tests that single-user mode still works
- [ ] Write tests that single-user mode doesn't require tenant_id
- [ ] Write tests that single-user mode uses "default" tenant
- [ ] Write tests for mode detection and switching

#### 14.3 TDD: Load testing

- [ ] Write load tests in `tests/load/test_multitenant_load.py`
- [ ] Write tests for 100+ concurrent requests across 10 tenants
- [ ] Write tests measuring performance under load
- [ ] Write tests for memory usage under sustained load
- [ ] Write tests that no memory leaks occur
- [ ] Verify load tests pass and performance is acceptable

#### 14.4 TDD: Security validation

- [ ] Write security tests in `tests/security/test_multitenant_security.py`
- [ ] Write tests attempting cross-tenant access attacks
- [ ] Write tests for tenant ID spoofing prevention
- [ ] Write tests for audit logging with correct tenant context
- [ ] Write tests that credentials are properly isolated
- [ ] Verify all security tests pass

#### 14.5 Verification Checkpoint: Phase 4 Complete

- [ ] Run linting: `ruff check src/quilt_mcp/`
- [ ] Run full test suite: `pytest -v`
- [ ] Run integration tests: `pytest tests/integration/test_multitenant.py -v`
- [ ] Run load tests: `pytest tests/load/test_multitenant_load.py -v`
- [ ] Run security tests: `pytest tests/security/test_multitenant_security.py -v`
- [ ] Verify MCP server works in both single-user and multitenant modes
- [ ] Commit changes: `git add . && git commit -m "feat: Phase 4 complete - multitenant deployment support"`
- [ ] Create tag: `git tag phase4-multitenant-complete`

---

## Task 15: Documentation and Migration Guide

Create comprehensive documentation for the new architecture.

### 15.1 Architecture documentation

- [ ] Document request-scoped service architecture
- [ ] Document service lifecycle and cleanup
- [ ] Document tenant isolation guarantees
- [ ] Document single-user vs multitenant modes
- [ ] Create architecture diagrams (mermaid)
- [ ] Document correctness properties

### 15.2 Migration guide

- [ ] Document migration from singleton to request-scoped services
- [ ] Document phase-by-phase migration process
- [ ] Document rollback procedures
- [ ] Document testing strategy for migration
- [ ] Document common pitfalls and solutions
- [ ] Document performance considerations

### 15.3 Operations guide

- [ ] Document deployment configuration
- [ ] Document QUILT_MULTITENANT_MODE environment variable
- [ ] Document monitoring and observability
- [ ] Document troubleshooting common issues
- [ ] Document security best practices
- [ ] Document performance tuning

### 15.4 API documentation

- [ ] Document RequestContext API
- [ ] Document RequestContextFactory API
- [ ] Document context propagation functions
- [ ] Document service interfaces (AuthService, PermissionDiscoveryService, WorkflowService)
- [ ] Document error types and handling
- [ ] Add code examples for common patterns

### 15.5 Verification Checkpoint: Documentation

- [ ] Review documentation for completeness
- [ ] Review documentation for accuracy
- [ ] Test code examples in documentation
- [ ] Commit changes: `git add . && git commit -m "docs: add comprehensive documentation for request-scoped services"`

---

## Task 16: Final Verification and Deployment

Final checks before considering the migration complete.

### 16.1 Code quality checks

- [ ] Run linting on entire codebase: `ruff check .`
- [ ] Run type checking: `mypy src/quilt_mcp/`
- [ ] Run security scanning: `bandit -r src/quilt_mcp/`
- [ ] Review code coverage: `pytest --cov=src/quilt_mcp --cov-report=html`
- [ ] Verify coverage > 80% for new code
- [ ] Address any issues found

### 16.2 Comprehensive testing

- [ ] Run full unit test suite: `pytest tests/unit/ -v`
- [ ] Run full integration test suite: `pytest tests/integration/ -v`
- [ ] Run security test suite: `pytest tests/security/ -v`
- [ ] Run performance test suite: `pytest tests/performance/ -v`
- [ ] Run load test suite: `pytest tests/load/ -v`
- [ ] Verify all tests pass

### 16.3 Manual testing

- [ ] Test MCP server startup in single-user mode
- [ ] Test MCP server startup in multitenant mode
- [ ] Test end-to-end tool execution with request-scoped services
- [ ] Test concurrent request handling
- [ ] Test memory cleanup after requests
- [ ] Verify no singleton variables exist in codebase

### 16.4 Performance validation

- [ ] Measure context creation overhead (must be < 10ms)
- [ ] Measure memory usage per request
- [ ] Measure throughput under load
- [ ] Compare performance before and after migration
- [ ] Verify no performance regressions

### 16.5 Security validation

- [ ] Verify no credential leakage between requests
- [ ] Verify no permission cache poisoning
- [ ] Verify no workflow data leakage between tenants
- [ ] Verify audit logs contain correct user/tenant identity
- [ ] Verify credentials are destroyed after requests

### 16.6 Final Commit and Tagging

- [ ] Create final commit: `git add . && git commit -m "feat: complete request-scoped service management migration"`
- [ ] Create release tag: `git tag v1.0.0-request-scoped-services`
- [ ] Update CHANGELOG.md with migration summary
- [ ] Create GitHub release with migration notes

---

## Acceptance Criteria

### Phase 1 Complete When

- [ ] No module-level `_AUTH_SERVICE` variable exists
- [ ] Auth service is instantiated per-request
- [ ] RequestContext and RequestContextFactory implemented
- [ ] MCP server creates request context per tool invocation
- [ ] Concurrent requests have isolated auth service instances
- [ ] Tests verify credential non-leakage
- [ ] Performance overhead < 10ms per request

### Phase 2 Complete When

- [ ] No module-level `_permission_discovery` variable exists
- [ ] Permission service is instantiated per-request
- [ ] Permission caches are isolated per request
- [ ] Concurrent requests have isolated permission service instances
- [ ] Tests verify permission cache isolation
- [ ] Permission checks use correct user's credentials

### Phase 3 Complete When

- [ ] No module-level `_workflows` dictionary exists
- [ ] Workflow service is instantiated per-request
- [ ] Workflow storage is tenant-partitioned
- [ ] Tenant A cannot access Tenant B's workflows
- [ ] Workflows persist across process restarts
- [ ] Tests verify workflow tenant isolation

### Phase 4 Complete When

- [ ] Multitenant mode is implemented and tested
- [ ] Tenant extraction works from JWT tokens
- [ ] Single-user mode works correctly
- [ ] Load tests pass with 100+ concurrent requests
- [ ] Security tests verify complete tenant isolation
- [ ] Documentation is complete and accurate

### Final Acceptance

- [ ] All module-level singletons eliminated
- [ ] All services are request-scoped
- [ ] Complete tenant isolation verified
- [ ] Single-user mode works without changes
- [ ] Multitenant mode works with proper configuration
- [ ] All tests pass (unit, integration, security, performance)
- [ ] Documentation complete
- [ ] Performance requirements met
- [ ] Security requirements met
- [ ] Ready for production deployment

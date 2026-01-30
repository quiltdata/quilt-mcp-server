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
- [x] Implement RequestContext with fields: request_id, tenant_id, user_id, auth_service
  (permission_service and workflow_service added in Phases 2 and 3)
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

- [x] Run linting: `uv run ruff check src/quilt_mcp/context/`
- [x] Run tests: `uv run pytest tests/unit/context/ -v`
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

- [x] Run linting: `uv run ruff check src/quilt_mcp/services/`
- [x] Run tests: `uv run pytest tests/unit/services/test_*auth*.py -v`
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

- [x] Run linting: `uv run ruff check src/quilt_mcp/context/`
- [x] Run tests: `uv run pytest tests/unit/context/test_factory.py -v`
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: implement RequestContextFactory for auth service"`

---

### Task 4: Integrate Request Context into MCP Server (TDD)

Update MCP server to create request contexts for each tool invocation.

#### 4.1 TDD: Context propagation mechanism

- [x] Write tests for context propagation in `tests/unit/server/test_context_propagation.py`
- [x] Write tests for set_current_context() and get_current_context()
- [x] Write tests that context is async-safe (contextvars-based)
- [x] Write tests for ContextNotAvailableError when accessed outside request
- [x] Write tests that context is cleared after request completes
- [x] Create `src/quilt_mcp/context/propagation.py` to make tests pass
- [x] Implement context variable storage (no thread-local)
- [x] Implement set_current_context() and get_current_context()
- [x] Add proper cleanup in finally blocks

#### 4.2 TDD: MCP tool handler integration

- [x] Write tests for MCP handler with context creation in `tests/unit/server/test_mcp_handler.py`
- [x] Write tests that context is created before tool execution
- [x] Write tests that context is cleared after tool execution
- [x] Write tests that tool execution errors still clean up context
- [x] Write tests for auth info extraction from MCP request
- [x] Update MCP server tool handler in `src/quilt_mcp/server.py`
- [x] Add context factory initialization
- [x] Add context creation at start of each tool invocation
- [x] Add context cleanup in finally block
- [x] Implement auth info extraction from request

#### 4.3 TDD: Update tools to use request context

- [x] Write tests that tools can access current context via get_current_context()
- [x] Write tests that tools get auth service from context
- [x] Write tests that tools no longer use singleton accessor
- [x] Update all tools to use get_current_context()
- [x] Document migration pattern for reference

#### 4.4 Verification Checkpoint: MCP Server Integration

- [x] Run linting: `uv run ruff check src/quilt_mcp/server.py src/quilt_mcp/context/`
- [x] Run tests: `uv run pytest tests/unit/server/ -v`
- [x] Test MCP server startup with new context creation
- [x] Verify context is created and cleaned up correctly
- [x] Commit changes: `git add . && git commit -m "feat: integrate request context into MCP server"`

---

### Task 5: Migration Testing and Validation (Phase 1)

Comprehensive testing to verify singleton elimination for auth service.

#### 5.1 TDD: Concurrent request isolation tests

- [x] Write integration tests for concurrent requests in `tests/integration/test_auth_isolation.py`
- [x] Write tests that simulate 10+ concurrent requests with different users
- [x] Write tests that verify each request has isolated auth service instance
- [x] Write tests that User A's credentials are not accessible to User B
- [x] Write tests that boto3 sessions are isolated per request
- [x] Implement async test infrastructure for concurrent requests
- [x] Verify all isolation tests pass

#### 5.2 TDD: Memory leak detection tests

- [x] Write tests for service instance cleanup in `tests/integration/test_memory_cleanup.py`
- [x] Write tests using weakref to verify GC eligibility
- [x] Write tests that service instances are destroyed after request
- [x] Write tests that no references are retained after context deletion
- [x] Write tests for multiple request cycles to detect leaks
- [x] Verify all memory tests pass

#### 5.3 TDD: Performance regression tests

- [x] Write performance tests in `tests/performance/test_context_overhead.py`
- [x] Write tests measuring context creation time (must be < 10ms)
- [x] Write tests comparing performance before and after migration
- [x] Write tests for 100+ request creations to measure average overhead
- [x] Verify performance requirements are met

#### 5.4 TDD: Security validation tests

- [x] Write security tests in `tests/security/test_credential_isolation.py`
- [x] Write tests that attempt to access another user's credentials
- [x] Write tests that verify credentials are destroyed after request
- [x] Write tests that credentials are not logged or persisted
- [x] Write tests for audit logging with correct user identity
- [x] Verify all security tests pass

#### 5.5 Verification Checkpoint: Phase 1 Complete

- [ ] Run linting: `uv run ruff check src/quilt_mcp/`
- [ ] Run full test suite: `uv run pytest -v`
- [ ] Run integration tests: `uv run pytest tests/integration/test_auth_isolation.py -v`
- [ ] Run security tests: `uv run pytest tests/security/test_credential_isolation.py -v`
- [ ] Verify no `_AUTH_SERVICE` module-level variable exists in codebase
- [ ] Verify MCP server works with request-scoped auth
- [ ] Commit changes: `git add . && git commit -m "feat: Phase 1 complete - auth service singleton eliminated"`
- [ ] Create tag: `git tag phase1-auth-singleton-eliminated`

---

## Phase 2: Permission Service Migration

### Task 6: Refactor Permission Discovery Service (TDD)

Update permission service to be instantiable per-request.

#### 6.1 TDD: Permission service initialization

- [x] Write tests for PermissionDiscoveryService in `tests/unit/services/test_permission_service.py`
- [x] Write tests that service accepts AuthService in constructor
- [x] Write tests that service initializes AWS clients from auth service session
- [x] Write tests that service has request-scoped cache (not shared)
- [x] Write tests that multiple instances have isolated caches
- [x] Update `src/quilt_mcp/services/permissions_service.py` to remove singleton
- [x] Remove module-level `_permission_discovery` variable
- [x] Update constructor to accept AuthService parameter
- [x] Initialize AWS clients from auth service's boto3 session
- [x] Ensure cache is instance variable (not module-level)

#### 6.2 TDD: Permission cache isolation

- [x] Write tests that cache is not shared between instances
- [x] Write tests that cache TTL is per-instance
- [x] Write tests that cache invalidation doesn't affect other instances
- [x] Write tests for cache key generation
- [x] Verify cache implementation uses instance variables
- [x] Add tests for cache eviction and expiration

#### 6.3 TDD: Remove singleton usage

- [x] Write tests that old singleton accessor no longer works
- [x] Write tests that code must use passed-in permission_service instances
- [x] Remove `get_permission_discovery()` singleton accessor
- [x] Update code that used singleton to accept permission_service parameter
- [x] Add deprecation warnings if needed

#### 6.4 Verification Checkpoint: Permission Service Refactor

- [x] Run linting: `uv run ruff check src/quilt_mcp/services/permissions_service.py`
- [x] Run tests: `uv run pytest tests/unit/services/test_permission_service.py -v`
- [x] Verify no `_permission_discovery` module-level variable exists
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: refactor permission service to remove singleton"`

---

### Task 7: Integrate Permission Service into Request Context (TDD)

Add permission service to request context creation.

#### 7.1 TDD: Update RequestContext with permission service

- [x] Write tests for RequestContext with permission_service field
- [x] Write tests that permission_service is required
- [x] Write tests for convenience methods accessing permission service
- [x] Update `src/quilt_mcp/context/request_context.py`
- [x] Add permission_service field to RequestContext
- [x] Add validation that permission_service is not None
- [x] Add convenience methods for permission checks

#### 7.2 TDD: Update factory to create permission service

- [x] Write tests for factory creating permission service
- [x] Write tests that permission service gets auth service from context
- [x] Write tests that each context gets fresh permission service instance
- [x] Write tests for error handling in permission service creation
- [x] Update `src/quilt_mcp/context/factory.py`
- [x] Implement _create_permission_service() method
- [x] Pass auth_service to PermissionDiscoveryService constructor
- [x] Add error handling and wrapping

#### 7.3 TDD: Update tools to use context permission service

- [x] Write tests that tools access permission service via context
- [x] Write tests that tools no longer use singleton accessor
- [x] Update all tools to use `get_current_context().permission_service`
- [x] Remove singleton accessor calls from tools

#### 7.4 Verification Checkpoint: Permission Service Integration

- [x] Run linting: `uv run ruff check src/quilt_mcp/context/ src/quilt_mcp/services/`
- [x] Run tests: `uv run pytest tests/unit/context/ tests/unit/services/ -v`
- [x] Verify permission service is created per-request
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: integrate permission service into request context"`

---

### Task 8: Permission Cache Isolation Testing (TDD)

Validate that permission caches are isolated per request.

#### 8.1 TDD: Permission cache isolation tests

- [x] Write tests in `tests/integration/test_permission_isolation.py`
- [x] Write tests that User A's cached permissions not visible to User B
- [x] Write tests that concurrent permission checks are isolated
- [x] Write tests that cache TTL is per-instance
- [x] Write tests that User A's cache invalidation doesn't affect User B
- [x] Verify all isolation tests pass

#### 8.2 TDD: Permission check correctness tests

- [x] Write tests that permission checks use correct user's credentials
- [x] Write tests that AWS API calls use correct boto3 session
- [x] Write tests for audit logging with correct user identity
- [x] Verify permission checks are correct per user

#### 8.3 Verification Checkpoint: Phase 2 Complete

- [ ] Run linting: `uv run ruff check src/quilt_mcp/`
- [ ] Run full test suite: `uv run pytest -v`
- [ ] Run integration tests: `uv run pytest tests/integration/test_permission_isolation.py -v`
- [ ] Verify no `_permission_discovery` module-level variable exists
- [ ] Verify MCP server works with request-scoped permissions
- [ ] Commit changes: `git add . && git commit -m "feat: Phase 2 complete - permission service singleton eliminated"`
- [ ] Create tag: `git tag phase2-permission-singleton-eliminated`

---

## Phase 3: Workflow Service Migration

### Task 9: Implement Tenant-Isolated Workflow Storage (TDD)

Create workflow storage with tenant partitioning.

#### 9.1 TDD: Workflow storage interface

- [x] Write tests for WorkflowStorage ABC in `tests/unit/storage/test_workflow_storage.py`
- [x] Write tests for abstract methods: save, load, list_all, delete
- [x] Write tests that storage is tenant-aware
- [x] Create `src/quilt_mcp/storage/workflow_storage.py`
- [x] Define WorkflowStorage abstract base class
- [x] Define methods for CRUD operations on workflows
- [x] Add tenant_id to all method signatures

#### 9.2 TDD: File-based workflow storage

- [x] Write tests for FileBasedWorkflowStorage in `tests/unit/storage/test_file_storage.py`
- [x] Write tests for tenant directory isolation (default: ~/.quilt/workflows/{tenant_id}/)
- [x] Write tests for configurable base directory via env (e.g., QUILT_WORKFLOW_DIR)
- [x] Write tests that Tenant A cannot access Tenant B's workflows
- [x] Write tests for workflow JSON serialization
- [x] Write tests for workflow CRUD operations
- [x] Create `src/quilt_mcp/storage/file_storage.py`
- [x] Implement FileBasedWorkflowStorage with tenant directories and configurable base dir
- [x] Implement save, load, list_all, delete methods
- [x] Add file system isolation per tenant (safe path joins, prevent traversal)
- [x] Add error handling for file operations

#### 9.3 TDD: Workflow persistence

- [x] Write tests that workflows survive process restart
- [x] Write tests for workflow data consistency
- [x] Write tests for concurrent workflow access safety
- [x] Verify file-based storage persists correctly
- [x] Add file locking if needed for concurrent safety

#### 9.4 Verification Checkpoint: Workflow Storage

- [x] Run linting: `uv run ruff check src/quilt_mcp/storage/`
- [x] Run tests: `uv run pytest tests/unit/storage/ -v`
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: implement tenant-isolated workflow storage"`

---

### Task 10: Refactor Workflow Service (TDD)

Update workflow service to use tenant-isolated storage.

#### 10.1 TDD: Workflow service with tenant isolation

- [x] Write tests for WorkflowService in `tests/unit/services/test_workflow_service.py`
- [x] Write tests that service accepts tenant_id in constructor
- [x] Write tests that service uses tenant-partitioned storage
- [x] Write tests that workflow operations only affect tenant's workflows
- [x] Update `src/quilt_mcp/services/workflow_service.py` to remove singleton
- [x] Remove module-level `_workflows` dictionary
- [x] Update constructor to accept tenant_id parameter
- [x] Initialize workflow storage with tenant isolation
- [x] Update all workflow methods to use storage backend

#### 10.2 TDD: Workflow CRUD operations

- [x] Write tests for create_workflow() with tenant isolation
- [x] Write tests for get_workflow() with tenant isolation
- [x] Write tests for list_workflows() showing only tenant's workflows
- [x] Write tests for delete_workflow() with tenant isolation
- [x] Write tests that Tenant A cannot see/modify Tenant B's workflows
- [x] Implement workflow CRUD methods using storage backend
- [x] Ensure all operations are tenant-scoped

#### 10.3 TDD: Remove singleton usage

- [x] Write tests that old singleton accessor no longer works
- [x] Write tests that code must use passed-in workflow_service instances
- [x] Remove `get_workflow_service()` singleton accessor
- [x] Update code that used singleton to accept workflow_service parameter

#### 10.4 Verification Checkpoint: Workflow Service Refactor

- [x] Run linting: `uv run ruff check src/quilt_mcp/services/workflow_service.py`
- [x] Run tests: `uv run pytest tests/unit/services/test_workflow_service.py -v`
- [x] Verify no `_workflows` module-level variable exists
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: refactor workflow service with tenant isolation"`

---

### Task 11: Integrate Workflow Service into Request Context (TDD)

Add workflow service to request context creation.

#### 11.1 TDD: Update RequestContext with workflow service

- [x] Write tests for RequestContext with workflow_service field
- [x] Write tests that workflow_service is required
- [x] Write tests for convenience methods accessing workflow service
- [x] Update `src/quilt_mcp/context/request_context.py`
- [x] Add workflow_service field to RequestContext
- [x] Add validation that workflow_service is not None
- [x] Add convenience methods for workflow operations

#### 11.2 TDD: Update factory to create workflow service

- [x] Write tests for factory creating workflow service
- [x] Write tests that workflow service gets tenant_id from context
- [x] Write tests that each context gets fresh workflow service instance
- [x] Write tests for error handling in workflow service creation
- [x] Update `src/quilt_mcp/context/factory.py`
- [x] Implement _create_workflow_service() method
- [x] Pass tenant_id to WorkflowService constructor
- [x] Add error handling and wrapping

#### 11.3 TDD: Update tools to use context workflow service

- [x] Write tests that tools access workflow service via context
- [x] Write tests that tools no longer use singleton accessor
- [x] Update workflow tools to use `get_current_context().workflow_service`
- [x] Remove singleton accessor calls from tools
- [x] Verify tenant isolation in tool operations

#### 11.4 Verification Checkpoint: Workflow Service Integration

- [x] Run linting: `uv run ruff check src/quilt_mcp/context/ src/quilt_mcp/services/`
- [x] Run tests: `uv run pytest tests/unit/context/ tests/unit/services/ -v`
- [x] Verify workflow service is created per-request
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: integrate workflow service into request context"`

---

### Task 12: Workflow Isolation Testing (TDD)

Validate that workflows are isolated per tenant.

#### 12.1 TDD: Workflow tenant isolation tests

- [x] Write tests in `tests/integration/test_workflow_isolation.py`
- [x] Write tests that Tenant A cannot see Tenant B's workflows
- [x] Write tests that workflow names don't collide across tenants
- [x] Write tests that workflow operations are tenant-scoped
- [x] Write tests that workflow deletion only affects tenant's workflows
- [x] Verify all isolation tests pass

#### 12.2 TDD: Workflow persistence tests

- [x] Write tests for workflow persistence across process restarts
- [x] Write tests for workflow data integrity
- [x] Write tests that tenant isolation survives restarts
- [x] Verify persistence works correctly

#### 12.3 TDD: Concurrent workflow access tests

- [x] Write tests for concurrent workflow operations
- [x] Write tests that User A and User B can modify workflows concurrently
- [x] Write tests for race condition safety
- [x] Verify concurrent access is safe

#### 12.4 Verification Checkpoint: Phase 3 Complete

- [x] Run linting: `uv run ruff check src/quilt_mcp/`
- [x] Run full test suite: `uv run pytest -v`
- [x] Run integration tests: `uv run pytest tests/integration/test_workflow_isolation.py -v`
- [x] Verify no `_workflows` module-level variable exists
- [x] Verify MCP server works with tenant-isolated workflows
- [x] Commit changes: `git add . && git commit -m "feat: Phase 3 complete - workflow service singleton eliminated"`
- [x] Create tag: `git tag phase3-workflow-singleton-eliminated`

---

## Phase 4: Multitenant Deployment Support

### Task 13: Add Multitenant Mode Support (TDD)

Enable multitenant mode with tenant extraction and validation.

#### 13.1 TDD: Tenant extraction from authentication

- [x] Write tests for tenant extraction in `tests/unit/context/test_tenant_extraction.py`
- [x] Write tests for extracting tenant_id from JWT token
- [x] Write tests for extracting tenant_id from session metadata
- [x] Write tests for fallback to environment variable
- [x] Write tests for error when tenant_id missing in multitenant mode
- [x] Create `src/quilt_mcp/context/tenant_extraction.py`
- [x] Implement JWT token decoding for tenant_id
- [x] Implement session metadata parsing for tenant_id
- [x] Add environment variable fallback
- [x] Add validation and error messages

#### 13.2 TDD: Update factory for tenant extraction

- [x] Write tests for factory extracting tenant from auth_info
- [x] Write tests for multitenant mode requiring tenant_id
- [x] Write tests for single-user mode using "default" tenant
- [x] Write tests for mode-specific validation
- [x] Update `src/quilt_mcp/context/factory.py`
- [x] Add tenant extraction logic in create_context()
- [x] Add mode-specific validation
- [x] Add clear error messages for missing tenant_id

#### 13.3 TDD: Environment-based mode detection

- [x] Write tests for QUILT_MULTITENANT_MODE environment variable
- [x] Write tests for auto-detection logic
- [x] Write tests for explicit mode override
- [x] Update factory to read environment variable
- [x] Implement auto-detection logic
- [x] Document environment variable usage

#### 13.4 Verification Checkpoint: Multitenant Mode

- [x] Run linting: `uv run ruff check src/quilt_mcp/context/`
- [x] Run tests: `uv run pytest tests/unit/context/test_tenant_extraction.py -v`
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: add multitenant mode support with tenant extraction"`

---

### Task 14: Multitenant Integration Testing (TDD)

Comprehensive testing for multitenant deployments.

#### 14.1 TDD: Multitenant concurrent request tests

- [x] Write tests in `tests/integration/test_multitenant.py`
- [x] Write tests for 20+ concurrent requests from different tenants
- [x] Write tests that each tenant has completely isolated services
- [x] Write tests that Tenant A cannot access Tenant B's data
- [x] Write tests for credential, permission, and workflow isolation
- [x] Verify all multitenant tests pass

#### 14.2 TDD: Single-user mode tests

- [x] Write tests that single-user mode still works
- [x] Write tests that single-user mode doesn't require tenant_id
- [x] Write tests that single-user mode uses "default" tenant
- [x] Write tests for mode detection and switching

#### 14.3 TDD: Load testing

- [x] Write load tests in `tests/load/test_multitenant_load.py`
- [x] Write tests for 100+ concurrent requests across 10 tenants
- [x] Write tests measuring performance under load
- [x] Write tests for memory usage under sustained load
- [x] Write tests that no memory leaks occur
- [x] Verify load tests pass and performance is acceptable

#### 14.4 TDD: Security validation

- [x] Write security tests in `tests/security/test_multitenant_security.py`
- [x] Write tests attempting cross-tenant access attacks
- [x] Write tests for tenant ID spoofing prevention
- [x] Write tests for audit logging with correct tenant context
- [x] Write tests that credentials are properly isolated
- [x] Verify all security tests pass

#### 14.5 Verification Checkpoint: Phase 4 Complete

- [x] Run linting: `uv run ruff check src/quilt_mcp/`
- [x] Run full test suite: `uv run pytest -v`
- [x] Run integration tests: `uv run pytest tests/integration/test_multitenant.py -v`
- [x] Run load tests: `uv run pytest tests/load/test_multitenant_load.py -v`
- [x] Run security tests: `uv run pytest tests/security/test_multitenant_security.py -v`
- [x] Verify MCP server works in both single-user and multitenant modes
- [x] Commit changes: `git add . && git commit -m "feat: Phase 4 complete - multitenant deployment support"`
- [x] Create tag: `git tag phase4-multitenant-complete`

---

## Task 15: Documentation and Migration Guide

Create comprehensive documentation for the new architecture.

### 15.1 Architecture documentation

- [x] Document request-scoped service architecture
- [x] Document service lifecycle and cleanup
- [x] Document tenant isolation guarantees
- [x] Document single-user vs multitenant modes
- [x] Create architecture diagrams (mermaid)
- [x] Document correctness properties

### 15.2 Migration guide

- [x] Document migration from singleton to request-scoped services
- [x] Document phase-by-phase migration process
- [x] Document rollback procedures
- [x] Document testing strategy for migration
- [x] Document common pitfalls and solutions
- [x] Document performance considerations

### 15.3 Operations guide

- [x] Document deployment configuration
- [x] Document QUILT_MULTITENANT_MODE environment variable
- [x] Document monitoring and observability
- [x] Document troubleshooting common issues
- [x] Document security best practices
- [x] Document performance tuning

### 15.4 API documentation

- [x] Document RequestContext API
- [x] Document RequestContextFactory API
- [x] Document context propagation functions
- [x] Document service interfaces (AuthService, PermissionDiscoveryService, WorkflowService)
- [x] Document error types and handling
- [x] Add code examples for common patterns

### 15.5 Verification Checkpoint: Documentation

- [x] Review documentation for completeness
- [x] Review documentation for accuracy
- [x] Test code examples in documentation
- [x] Commit changes: `git add . && git commit -m "docs: add comprehensive documentation for request-scoped services"`

---

## Task 16: Final Verification and Deployment

Final checks before considering the migration complete.

### 16.1 Code quality checks

- [ ] Run linting on entire codebase: `uv run ruff check .`
- [ ] Run type checking: `uv run mypy src/quilt_mcp/`
- [ ] Run security scanning: `uv run bandit -r src/quilt_mcp/`
- [ ] Review code coverage: `uv run pytest --cov=src/quilt_mcp --cov-report=html`
- [ ] Verify coverage > 80% for new code
- [ ] Address any issues found

### 16.2 Comprehensive testing

- [ ] Run full unit test suite: `uv run pytest tests/unit/ -v`
- [ ] Run full integration test suite: `uv run pytest tests/integration/ -v`
- [ ] Run security test suite: `uv run pytest tests/security/ -v`
- [ ] Run performance test suite: `uv run pytest tests/performance/ -v`
- [ ] Run load test suite: `uv run pytest tests/load/ -v`
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

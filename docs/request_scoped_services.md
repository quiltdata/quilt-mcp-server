# Request-Scoped Services & Multitenant Isolation

This document describes the request-scoped service architecture, tenant isolation guarantees, and migration guidance for removing module-level singletons.

## Architecture Overview

Request-scoped services are created per MCP tool invocation and carried through a `RequestContext` stored in a context variable.

```mermaid
flowchart LR
    Client[Tool Request]
    Factory[RequestContextFactory]
    Context[RequestContext]
    Auth[AuthService]
    Perm[PermissionDiscoveryService]
    Workflow[WorkflowService]

    Client --> Factory
    Factory --> Context
    Context --> Auth
    Context --> Perm
    Context --> Workflow
```

### Service Lifecycle

- Each tool invocation creates a new `RequestContext`.
- Services are instantiated on demand by `RequestContextFactory`.
- Context is set via `set_current_context()` and cleared in a `finally` block.
- Services are eligible for garbage collection after the request completes.

### Tenant Isolation Guarantees

- Workflows are stored per tenant under tenant-specific directories.
- Permission caches are per-request and are not shared between contexts.
- Auth services are created per-request to avoid credential leakage.

## Single-User vs Multitenant Modes

### Single-User Mode

- Default if `QUILT_MULTITENANT_MODE` is unset or false.
- Tenant ID is always `default`.
- Explicit tenant IDs are rejected to prevent accidental multitenant behavior.

### Multitenant Mode

- Enable via `QUILT_MULTITENANT_MODE=true`.
- Tenant ID is required and extracted from:
  1. JWT claims (`tenant_id`, `tenant`, `org_id`, `organization_id`)
  2. Session metadata (`RuntimeAuthState.extras` / `session_metadata`)
  3. Environment fallback: `QUILT_TENANT_ID` or `QUILT_TENANT`

## Environment Configuration

```bash
# Enable multitenant mode
export QUILT_MULTITENANT_MODE=true

# Optional tenant fallback (useful for local dev)
export QUILT_TENANT_ID=my-tenant

# Workflow storage base directory
export QUILT_WORKFLOW_DIR=~/.quilt/workflows
```

## API Reference (Key Interfaces)

### RequestContext

- Fields: `request_id`, `tenant_id`, `user_id`, `auth_service`, `permission_service`, `workflow_service`
- Helpers:
  - `get_boto_session()`
  - `discover_permissions(...)`
  - `check_bucket_access(...)`
  - `create_workflow(...)`, `add_workflow_step(...)`, `update_workflow_step(...)`
  - `get_workflow_status(...)`, `list_workflows()`

### RequestContextFactory

- `create_context(tenant_id: Optional[str] = None, request_id: Optional[str] = None)`
- Mode detection: `single-user`, `multitenant`, or `auto` (via env)
- Tenant extraction: `extract_tenant_id(...)` helper

### Context Propagation

- `set_current_context(context)`
- `get_current_context()`
- `reset_current_context(token)`

### Service Interfaces

- `AuthService`: `get_session()`, `is_valid()`, `get_user_identity()`
- `PermissionDiscoveryService`: request-scoped cache, uses auth session
- `WorkflowService`: tenant-isolated CRUD operations via storage backend

## Migration Guide

### Phase-by-Phase Approach

1. Replace module-level auth singleton with request-scoped `AuthService`.
2. Replace permission discovery singleton with request-scoped service.
3. Replace workflow singleton with tenant-isolated storage and service.
4. Enable multitenant extraction and validation.

### Rollback Procedure

- Revert the latest phase commit.
- Remove new context integration points.
- Restore singleton accessors (if required).

## Testing Strategy

- Unit tests cover per-request instantiation, validation, and helper delegation.
- Integration tests validate tenant isolation, persistence, and concurrency.
- Security tests validate cross-tenant access denial and path sanitization.
- Load tests validate context creation under high concurrency.

## Performance Considerations

- Context creation should remain under 10ms per request.
- Workflow persistence uses atomic file writes to avoid corruption.
- Avoid heavy work in context creation; initialize services lazily when possible.

## Troubleshooting

- **Missing tenant in multitenant mode**: ensure JWT includes `tenant_id` or set `QUILT_TENANT_ID`.
- **Unexpected access errors**: verify each request receives a fresh context and services are not cached globally.
- **Workflow not found**: confirm tenant ID matches and storage directory is correct.

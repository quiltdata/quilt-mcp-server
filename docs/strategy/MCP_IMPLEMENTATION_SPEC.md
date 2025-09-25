# Quilt MCP Server – Implementation Specification

## 1. Scope & Goals
- Deliver a unified authentication runtime for stdio and HTTP clients using contextvars.
- Harden AWS deployments with secret management, least-privilege IAM, and documented IaC options (Terraform/CDK/CloudFormation).
- Provide verifiable testing and migration steps covering JWT validation, role assumption, and tool access patterns.

## 2. Technical Requirements

### Runtime Context
- `src/quilt_mcp/runtime_context.py`
  - Expose `RuntimeAuthState` and `RuntimeContextState` with contextvar storage.
  - Provide helpers: `push_runtime_context`, `reset_runtime_context`, `get_runtime_auth`, `set_runtime_auth`, `clear_runtime_auth`, `update_runtime_metadata`.
  - Default environment `desktop` until `run_server()` overrides based on transport.

### Middleware (`src/quilt_mcp/utils.py`)
- Wrap HTTP requests with `push_runtime_context(environment="web-unauthenticated")`.
- When `Authorization: Bearer` provided:
  - Decode JWT via `BearerAuthService.decode_jwt_token` and set runtime auth with claims.
  - If decode fails, fall back to `validate_bearer_token` and still populate runtime auth on success.
- When `X-Quilt-User-Role` header present:
  - Record role ARN/ID in runtime metadata and environment variables for compatibility.
  - Trigger `AuthenticationService.auto_attempt_role_assumption()`.
- Always restore prior environment variables and reset runtime context in `finally` block.
- Update `run_server()` to set default environment for stdio vs HTTP transports.

### Authentication Service (`src/quilt_mcp/services/auth_service.py`)
- `_try_bearer_token_auth` must prioritise runtime auth state before validating env token.
- `_try_assume_role_auth` should pull role ARN from runtime metadata first, then env vars.
- `_get_quilt_user_role_arn` should reuse runtime metadata/auth extras before reading credentials files.

### Bearer Auth Service (`src/quilt_mcp/services/bearer_auth_service.py`)
- `validate_bearer_token` must set `RuntimeAuthState` with scheme `jwt` or `bearer`, capturing claims and user info.
- Clear runtime auth on validation failure or exception to avoid stale tokens.

### GraphQL Service (`src/quilt_mcp/services/graphql_bearer_service.py`)
- Fetch access token from runtime context first; fallback to env var for backward compatibility.

### Tool Updates
- `src/quilt_mcp/tools/buckets.py` `_check_authorization` should prefer runtime auth; fallback to env + quilt3 if absent.
- `src/quilt_mcp/tools/bearer_auth.py` should expose runtime-derived auth info in status/validation endpoints.

### AWS IaC Enhancements
- Terraform module (`deploy/terraform/modules/mcp_server`):
  - Accept list of secret ARNs; map to container `secrets` block.
  - Support optional egress CIDR restriction variable.
  - Parameterise ECS Exec enablement (default `false` for production).
- Provide equivalent CDK (Python) construct mirroring Terraform resources.
- Provide CloudFormation template derived from same resource graph (ALB listener rule, target group, security group, task, service, log group).

## 3. File Structure

```
docs/
  strategy/
    MCP_SECURITY_STRATEGY.md
    MCP_IMPLEMENTATION_SPEC.md
    README.md
  architecture/
    AUTHENTICATION_ARCHITECTURE.md
    MCP_AUTH_ARCHITECTURE_DIAGRAM.md

src/quilt_mcp/
  runtime_context.py
  utils.py
  services/
    auth_service.py
    bearer_auth_service.py
    graphql_bearer_service.py
  tools/
    buckets.py
    bearer_auth.py

deploy/
  terraform/
    mcp-server.tf
    modules/mcp_server/
      main.tf
      variables.tf
  cdk/mcp_server/
  cloudformation/mcp_server.yml
```

## 4. Method & Interface Contracts

| Component | Signature | Notes |
|-----------|-----------|-------|
| `push_runtime_context` | `(environment: str, auth: Optional[RuntimeAuthState] = None, metadata: Optional[Dict[str, Any]] = None)` | Returns context token for `reset_runtime_context`. |
| `RuntimeAuthState` | `@dataclass` | Fields: `scheme`, `access_token`, `claims`, `extras`. |
| `BearerAuthService.validate_bearer_token` | `(access_token: str) -> Tuple[BearerAuthStatus, Optional[Dict[str, Any]]]` | Must set runtime auth on success and clear on failure. |
| `AuthenticationService._try_bearer_token_auth` | `() -> AuthStatus` | Short-circuit when runtime auth already populated. |
| Terraform variable `secret_arns` | `list(string)` | Inject into `container_definitions[*].secrets`; default empty list preserves behaviour. |
| Terraform variable `egress_cidr_blocks` | `list(string)` | Controls outbound SG rule; default `["0.0.0.0/0"]`. |
| Terraform variable `enable_execute_command` | `bool` | Default `false` for production, can be overridden in dev. |

## 5. Configuration & Environment Variables
- Mandatory: `QUILT_CATALOG_URL`, `FASTMCP_TRANSPORT`, `FASTMCP_ADDR`, `FASTMCP_PORT`.
- JWT secrets: must be sourced from Secrets Manager in production; environment fallback only for development/test.
- Desktop stdio transports rely on quilt3 login/AWS profiles; runtime environment remains `desktop-stdio`.

## 6. Testing Strategy

### Unit
- `tests/unit/test_utils.py`
  - Verify middleware sets runtimes (`web-jwt`, `web-unauthenticated`) and restores context.
  - Confirm bucket authorization pulls runtime auth before env fallback.
- `tests/unit/test_auth_service.py`
  - Validate JWT payload expectations (32 buckets, permission parity) and runtime auth short-circuit logic.
- `tests/unit/test_jwt_decompression.py`
  - Ensure explicit arrays take precedence over compressed claims.

### Integration
- Add concurrency stress test (mixed stdio + HTTP) verifying contexts are isolated.
- Deploy staging stack with Secrets Manager-injected values; run smoke tests via `/mcp/` and `/healthz`.
- Confirm CloudWatch metrics capture role assumption successes/failures.

### Regression
- Execute `make coverage` and targeted runtime tests in CI.
- Maintain Terraform/CDK validation via `terraform validate` and `cdk synth` in pipeline.

## 7. Migration Plan
1. **Stage infrastructure** – Apply Terraform updates with new optional variables (defaults maintain current behaviour).
2. **Secrets adoption** – Create Secrets Manager entries; set `secret_arns` variable and redeploy.
3. **Network hardening** – Update security groups with customer-approved egress CIDRs.
4. **IaC parity** – Release CDK construct and CloudFormation template; pilot with select customers.
5. **Documentation & training** – Publish updated docs bundle; run internal walkthrough.

## 8. Open Questions
- Should Terraform enforce Secrets Manager usage (fail when critical secrets missing) or warn only?
- Preferred default for `enable_execute_command` in shared modules?
- Do we expose optional WAF integration parameters now or as follow-up?

## 9. References
- `docs/architecture/AUTHENTICATION_ARCHITECTURE.md`
- `docs/architecture/GRAPHQL_BEARER_TOKEN_INTEGRATION.md`
- `deploy/terraform/modules/mcp_server/main.tf`
- `src/quilt_mcp/runtime_context.py`
- `src/quilt_mcp/services/auth_service.py`

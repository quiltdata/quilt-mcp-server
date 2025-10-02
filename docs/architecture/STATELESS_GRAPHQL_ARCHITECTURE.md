# Stateless GraphQL MCP Architecture

This document captures the post-0.6.37 Quilt MCP server design. The server is now fully stateless, GraphQL-only, and deployable behind HTTPS load balancers without bespoke configuration. The intent is to make future maintenance straightforward and provide the context needed for audits or onboarding.

---

## Authentication and Authorization

- **Protocol**: Every request provides a Bearer JWT in the `Authorization` header. There is no session affinity or server-side state; each request stands alone.
- **Entry point**: The middleware in `src/quilt_mcp/utils.py` extracts the token inside the `_inject_request_context()` FastAPI middleware and stores it in a `ContextVar` (`request_context`).
- **BearerAuthService** (`src/quilt_mcp/services/bearer_auth_service.py`):
  - Validates signature, expiry, and audience/issuer (configurable via environment).
  - Extracts Quilt catalog user identity for use by authorization checks.
  - Builds request-scoped AWS sessions: `BearerAuthService.build_boto3_session()` converts the JWT's embedded AWS credentials (snake_case or camelCase) into a `boto3.Session`. When no credentials are present the code falls back to ambient IAM roles, ensuring catalogs can still work in development.
- **Runtime consumption**: All tools requiring AWS access call `quilt_mcp.utils.get_s3_client()` or `get_sts_client()`. These helpers retrieve the request's JWT, rehydrate the session, and produce scoped clients. This guarantees S3, STS, and any derived service calls operate with the caller's JWT-derived identity.
- **Catalog permissions**: All outbound Quilt Catalog calls are centralized through `src/quilt_mcp/clients/catalog.py`. The helper attaches the active JWT to REST or GraphQL requests, so catalog-side policy enforcement remains intact.

### Key Environment Variables

| Variable | Purpose |
| --- | --- |
| `MCP_ENHANCED_JWT_SECRET` / `MCP_ENHANCED_JWT_KID` | Secrets for verifying enhanced JWT signatures when provided by the frontend. |
| `QUILT_CATALOG_URL` | Base URL for GraphQL and REST calls against the Quilt catalog. Required in unit/integration tests. |
| `BEARER_AUTH_AUDIENCE`, `BEARER_AUTH_ISSUER` | Optional overrides for JWT validation. |

---

## CORS, HTTPS, and Proxy Handling

The MCP server runs under FastAPI with Uvicorn and is typically deployed behind an AWS Application Load Balancer (ALB).

- **Stateless HTTP transport**: `FastMCP.http_app(stateless_http=True)` disables session state requirements so each HTTP call is self-contained.
- **Proxy headers**: We rely on `uvicorn.run(..., proxy_headers=True, forwarded_allow_ips="*")`. Uvicorn translates `X-Forwarded-Proto`, `X-Forwarded-For`, and `X-Forwarded-Host` into the request scope, eliminating mixed-content redirects.
- **External URL awareness**: Setting `FASTMCP_EXTERNAL_URL=https://demo.quiltdata.com/mcp/` allows `utils._wrap_http_app()` to annotate the FastAPI router with the external HTTPS scheme and root path. Generated URLs and redirects preserve HTTPS.
- **Trusted hosts**: `FASTMCP_TRUSTED_HOSTS` lists hostnames accepted by the proxy middleware. We default to wildcard but production deployments should pass the ALB hostname.
- **CORS**: The MCP server relies on the Quilt catalog frontend controlling origins. For standalone deployments, add Starlette's `CORSMiddleware` in `_wrap_http_app()` with the desired policy. (It is omitted by default because the official Quilt UI speaks to the MCP server through same-origin routing rules.)

---

## GraphQL-Only Refactor

### Motivation

- Reduce duplicated REST/Elasticsearch/S3 listing logic.
- Remove the legacy `quilt3` dependency (which required stateful boto sessions).
- Guarantee unified authorization and caching paths via the Quilt catalog's GraphQL API.

### Major Changes

| Area | Change |
| --- | --- |
| Search (`src/quilt_mcp/tools/search.py`) | Deprecated tool variants (`search_explain`, `bucket_objects_search`, `package_contents_search`). All callers route through `search.unified_search`. |
| Unified search backend (`src/quilt_mcp/search/tools/unified_search.py`) | Now instantiates only `EnterpriseGraphQLBackend`; Elasticsearch and S3 backends were removed. |
| Catalog client (`src/quilt_mcp/clients/catalog.py`) | All GraphQL and REST calls originate here; it injects the JWT and handles retries. |
| Permissions and packages tools | `quilt3` calls replaced with catalog helpers or request-scoped boto sessions. `QuiltService` abstraction deleted completely. |
| Documentation | README updates and new migration notes (see below) explain the stateless GraphQL architecture to users and developers. |

### Testing

- Unit tests under `tests/unit/test_permissions_stateless.py`, `tests/unit/test_buckets_stateless.py`, and `tests/unit/test_s3_package_stateless.py` cover the JWT-scoped session usage.
- Integration tests should set `QUILT_CATALOG_URL` and use `request_context(token, metadata)` to simulate authenticated traffic.

---

## Infrastructure Overview

| Component | Description |
| --- | --- |
| **Container Image** | Built with UV tooling (`uv lock`, `uv run`). Published to Amazon ECR as `quilt-mcp-server:<version>` and `latest`. |
| **Task Definition** | ECS Fargate task family `quilt-mcp-server`. Single container `mcp-server` with environment overrides arriving via `ECS_ENV_OVERRIDES` (JSON). |
| **Deployment Script** | `scripts/ecs_deploy.py` pulls the currently running task revision, swaps the image, applies env overrides, registers a new revision, and updates the service. |
| **Cluster/Service** | `sales-prod` cluster, `sales-prod-mcp-server-production` service. Desired count typically 1 (stateless; horizontal scale is trivial). |
| **Networking** | awsvpc mode with private subnets and security groups dedicated to Quilt MCP. ALB terminates TLS and forwards HTTPS traffic with proxy headers. |
| **Environment Overrides** | Example payload:
```
{
  "FASTMCP_EXTERNAL_URL": "https://demo.quiltdata.com/mcp/",
  "FASTMCP_TRUSTED_HOSTS": "demo.quiltdata.com",
  "MCP_SERVER_VERSION": "0.6.37",
  "MCP_ENHANCED_JWT_SECRET": "…",
  "MCP_ENHANCED_JWT_KID": "frontend-enhanced"
}
```
| **CI/CD** | `make docker-release` performs build → push → ECS update. Targets rely on `scripts/docker.py` and `scripts/ecs_deploy.py` and require AWS credentials with ECR/ECS permissions. |

### Operational Tips

- Use `aws ecs describe-services` and `aws logs get-log-events` for live deployment debugging.
- Set `MCP_SERVER_VERSION` in the task env to aid log correlation.
- Health probes come from the ALB; ensure `uvicorn` is listening on the expected port (`FASTMCP_PORT`, default 8000).
- When routing new tools to GraphQL, prefer extending `catalog.py` helpers and add corresponding tests in `tests/unit`.
- All AWS calls now require JWT-provided credentials or role assumption. ECS task roles are not used as a fallback.

---

## Migration Notes

- **Version 0.6.35 → 0.6.37**: remove `quilt3`, ensure all code paths source AWS clients from `BearerAuthService`, update deployment scripts to fetch the currently running task definition (container names differ between legacy and new revisions).
- **Proxy Configuration**: Ensure ALB listeners forward `X-Forwarded-Proto: https` and set `FASTMCP_EXTERNAL_URL` to the public HTTPS endpoint before 0.6.37 containers go live.

For older architecture documentation see `docs/archive/DUAL_MCP_ARCHITECTURE.md` and `docs/archive/UNIFIED_SEARCH_SUMMARY.md`.



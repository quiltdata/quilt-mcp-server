# JWT-Only Authentication Specifications

## Scope

Implement a singular JWT authentication path for the MCP server that:
- Verifies incoming requests via `Authorization: Bearer <token>`.
- Decodes enhanced Quilt JWTs, applying the same decompression logic as the catalog repo.
- Produces a normalized auth context (user, permissions, buckets, AWS credentials).
- Drives tool authorization and AWS client creation exclusively from the JWT context.
- Removes or disables quilt3, role-header, and IAM fallback codepaths.

## Functional Requirements

1. **Middleware Enforcement**
   - Requests missing a bearer token must return 401 with a JSON body describing the error.
   - Successful requests set runtime context (`environment=web-jwt`, `scheme=jwt`) and attach decoded claims.

2. **JWT Processing Service**
   - New `JwtAuthService` (or retrofit `BearerAuthService`) validates signature using shared secret (`MCP_ENHANCED_JWT_SECRET`), applies decompression utilities, and exposes structured results: `user`, `permissions`, `roles`, `buckets`, optional AWS credentials/role ARN.
   - Provide clear error codes (missing header, decode failure, expired, forbidden tool).

3. **Authorization Helpers**
   - `check_unified_authorization` is replaced with a JWT-specific helper that evaluates tool permissions using decoded claims and returns boto3 clients configured either from embedded credentials or an assumed role derived from claims.
   - Authorization failure must include reason codes for logging/response.

4. **Troubleshooting Instrumentation**
   - Log at INFO when authentication succeeds (user, role count, bucket count) and at WARNING/ERROR for failure categories.
   - Expose a diagnostic endpoint (or enrich `/healthz`) reporting last auth error summary without leaking secrets.

5. **Test Coverage**
   - Pytests covering: middleware 401, valid JWT flow, permission denial, missing bucket access, diagnostic logging hooks.
   - All tests run via `make test-unit` with deterministic mocks (no network). Use decompression fixtures mirroring Quilt repo data.

## Non-Functional Requirements

- No quilt3 imports or dependency on local auth files.
- Runtime state must be thread-safe (contextvars) and cleared after each request.
- Environment variable mutations should be eliminated or minimized.
- Compatible with containerized deployment (no reliance on desktop credentials).

## Out of Scope

- Implementing refresh-token flows or contacting Quilt APIs for validation.
- Supporting legacy stdio/desktop authentication.
- Building new UI for diagnostics beyond logging/health augmentation.


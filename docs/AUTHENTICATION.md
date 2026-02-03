# Authentication Modes

Quilt MCP Server supports two authentication modes:

- **IAM mode (default)**: Uses AWS credentials from the environment, profiles, or quilt3 session.
- **JWT mode**: Requires `Authorization: Bearer <token>` on every request and delegates authorization to the Platform.

Mode selection is controlled at startup with `MCP_REQUIRE_JWT`.

## IAM Mode (Default)

IAM mode uses standard AWS credential resolution:

- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`)
- AWS shared config/profiles (`AWS_PROFILE`)
- quilt3 session credentials (if logged in)
- Instance role credentials (EC2/ECS/Lambda)

No JWT processing occurs in IAM mode, even if `Authorization` headers are present.

## JWT Mode

Enable JWT mode by setting:

```
MCP_REQUIRE_JWT=true
```

JWT mode requires a valid JWT on every request and will return `401/403` for missing or invalid tokens.

### Required Configuration

Set one of the following:

- `MCP_JWT_SECRET` (recommended for local/dev): HS256 shared secret
- `MCP_JWT_SECRET_SSM_PARAMETER` (recommended for production): SSM parameter name containing the secret
 - `QUILT_CATALOG_URL`: Platform catalog URL
 - `QUILT_REGISTRY_URL`: Platform registry URL

Optional validation:

- `MCP_JWT_ISSUER` - expected `iss` claim
- `MCP_JWT_AUDIENCE` - expected `aud` claim

### JWT Claims

JWT mode expects the following claims:

- `id` (required): user identifier
- `uuid` (required): user UUID
- `exp` (required): expiration timestamp

Example payload:

```json
{
  "id": "user-123",
  "uuid": "uuid-123",
  "exp": 1735689600
}
```

### Error Messages

- Missing token: `JWT authentication required. Provide Authorization: Bearer header.`
- Invalid token: `Invalid JWT: <reason>`

### Security Notes

- Secrets are never logged.
- JWT validation enforces HS256, signature verification, and expiration.
- Authorization decisions are enforced by the Platform.

## Migration Guide (IAM → JWT)

1. Configure `MCP_JWT_SECRET` (or SSM parameter) and optional issuer/audience.
2. Set `MCP_REQUIRE_JWT=true`.
3. Ensure clients send `Authorization: Bearer <token>` on every request.
4. Verify Platform authorization and browsing session access paths.

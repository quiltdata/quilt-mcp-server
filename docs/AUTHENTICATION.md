# Authentication Modes

Quilt MCP Server supports two authentication modes:

- **IAM mode (default)**: Uses AWS credentials from the environment, profiles, or quilt3 session.
- **JWT mode**: Requires `Authorization: Bearer <token>` on every request and assumes per-user roles based on JWT claims.

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

Optional validation:

- `MCP_JWT_ISSUER` - expected `iss` claim
- `MCP_JWT_AUDIENCE` - expected `aud` claim

### JWT Claims

JWT mode expects the following claims:

- `sub` (required): user identity used as `SourceIdentity`
- `exp` (required): expiration timestamp
- `role_arn` (required): AWS role to assume for this request

Optional claims:

- `session_tags`: object of tags to apply to the assumed role
- `transitive_tag_keys`: list of tag keys to make transitive

Example payload:

```json
{
  "sub": "user-123",
  "exp": 1735689600,
  "role_arn": "arn:aws:iam::123456789012:role/QuiltUser",
  "session_tags": {
    "tenant": "acme",
    "team": "data"
  }
}
```

### STS Session Settings

`MCP_JWT_SESSION_DURATION` controls the STS session duration in seconds (default: 3600). The value is clamped to the
AWS limits (900–43200 seconds).

### Error Messages

- Missing token: `JWT authentication required. Provide Authorization: Bearer header.`
- Invalid token: `Invalid JWT: <reason>`

### Security Notes

- Secrets are never logged.
- JWT validation enforces HS256, signature verification, and expiration.
- Role assumption uses `SourceIdentity` from `sub` and session tags for ABAC.

## Migration Guide (IAM → JWT)

1. Configure `MCP_JWT_SECRET` (or SSM parameter) and optional issuer/audience.
2. Set `MCP_REQUIRE_JWT=true`.
3. Ensure clients send `Authorization: Bearer <token>` on every request.
4. Verify role assumption in CloudTrail (`SourceIdentity` should match `sub`).

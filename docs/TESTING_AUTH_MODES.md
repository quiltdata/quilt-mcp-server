# Manual Testing Guide: IAM vs JWT

This guide explains how to run the server locally in each auth mode and validate behavior.

## 1. IAM Mode (Default)

Run:

```bash
export MCP_REQUIRE_JWT=false
export AWS_PROFILE=default
uvx quilt-mcp
```

Test a request:

```bash
curl -s http://127.0.0.1:8000/mcp/v1/tools/list \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/list","params":{}}'
```

Expected:
- 200 OK
- Tools list returned

## 2. JWT Mode

Run:

```bash
export MCP_REQUIRE_JWT=true
export MCP_JWT_SECRET="dev-secret"
uvx quilt-mcp
```

Generate a test JWT:

```bash
python - <<'PY'
import time, jwt
payload = {
  "sub": "dev-user",
  "exp": int(time.time()) + 600,
  "role_arn": "arn:aws:iam::123456789012:role/QuiltUser"
}
print(jwt.encode(payload, "dev-secret", algorithm="HS256"))
PY
```

Alternative generators:

- jwt.io: paste payload + secret into the debugger to create a token.
- jose (Node.js):
```bash
node - <<'NODE'
import { SignJWT } from 'jose';
const secret = new TextEncoder().encode('dev-secret');
const payload = { sub: 'dev-user', exp: Math.floor(Date.now() / 1000) + 600 };
const token = await new SignJWT(payload).setProtectedHeader({ alg: 'HS256' }).sign(secret);
console.log(token);
NODE
```

Example payloads:

Minimal (no role assumption needed for tools/list):
```json
{"sub":"dev-user","exp":1700000000}
```

Role assumption with tags:
```json
{
  "sub": "dev-user",
  "exp": 1700000000,
  "role_arn": "arn:aws:iam::123456789012:role/QuiltUser",
  "session_tags": {"tenant":"acme","user":"dev-user"},
  "transitive_tag_keys": ["tenant"]
}
```

Test without JWT (should fail):

```bash
curl -s http://127.0.0.1:8000/mcp/v1/tools/list \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/list","params":{}}'
```

Expected:
- 401/403
- Message mentioning JWT or authorization

Test with JWT:

```bash
TOKEN="paste-token-here"
curl -s http://127.0.0.1:8000/mcp/v1/tools/list \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"method":"tools/list","params":{}}'
```

Expected:
- 200 OK

## 3. Claude Desktop

For JWT mode, add the Authorization header in the client configuration and ensure the token is refreshed before expiry.

## 4. Verify Role Assumption (CloudTrail)

1. Open CloudTrail and filter for `AssumeRole` events.
2. Confirm `sourceIdentity` matches the JWT `sub` claim.
3. Verify session tags under `requestParameters.tags`.

## 5. Debugging Tips

- Missing JWT → check `MCP_REQUIRE_JWT` and client headers.
- Invalid JWT → verify secret, issuer, audience, and expiration.
- Role assumption failures → check CloudTrail and IAM trust policies.

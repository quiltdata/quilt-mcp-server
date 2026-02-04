# Manual Testing Guide: IAM vs JWT

This guide explains how to run the server locally in each auth mode and validate behavior.

## 1. IAM Mode (Default)

Run:

```bash
export QUILT_MULTIUSER_MODE=false
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
export QUILT_MULTIUSER_MODE=true
export MCP_JWT_SECRET="dev-secret"
export QUILT_CATALOG_URL="https://your-catalog.quiltdata.com"
export QUILT_REGISTRY_URL="https://registry.your-catalog.quiltdata.com"
uvx quilt-mcp
```

Generate a test JWT:

```bash
python - <<'PY'
import time, jwt
payload = {
  "id": "dev-user-id",
  "uuid": "dev-user-uuid",
  "exp": int(time.time()) + 600,
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

Minimal (Platform JWT shape):
```json
{"id":"dev-user-id","uuid":"dev-user-uuid","exp":1700000000}
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

## 4. Debugging Tips

- Missing JWT → check `QUILT_MULTIUSER_MODE` and client headers.
- Invalid JWT → verify secret, issuer, audience, and expiration.
- Role assumption failures → check CloudTrail and IAM trust policies.

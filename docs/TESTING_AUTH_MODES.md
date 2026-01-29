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

- Missing JWT → check `MCP_REQUIRE_JWT` and client headers.
- Invalid JWT → verify secret, issuer, audience, and expiration.
- Role assumption failures → check CloudTrail and IAM trust policies.

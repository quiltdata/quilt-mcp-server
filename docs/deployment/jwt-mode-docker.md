# JWT Mode (Docker)

JWT mode enforces `Authorization: Bearer <token>` and delegates authorization to the Platform.

## Environment Variables

- `MCP_REQUIRE_JWT=true`
- `MCP_JWT_SECRET` or `MCP_JWT_SECRET_SSM_PARAMETER`
- `QUILT_CATALOG_URL`
- `QUILT_REGISTRY_URL`
- `AWS_REGION` (required if using SSM secret)

## Example

```bash
docker run --rm -p 8000:8000 \
  -e MCP_REQUIRE_JWT=true \
  -e MCP_JWT_SECRET=dev-secret \
  -e QUILT_CATALOG_URL=https://your-catalog.quiltdata.com \
  -e QUILT_REGISTRY_URL=https://registry.your-catalog.quiltdata.com \
  quiltdata/quilt-mcp:latest
```

## docker-compose

See `docs/deployment/docker-compose-jwt.yaml`.

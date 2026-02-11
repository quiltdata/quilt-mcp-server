# JWT Mode (Docker)

JWT mode enforces `Authorization: Bearer <token>` and delegates authorization to the Platform.

## Environment Variables

- `QUILT_MULTIUSER_MODE=true`
- `QUILT_CATALOG_URL`
- `QUILT_REGISTRY_URL`

## Example

```bash
docker run --rm -p 8000:8000 \
  -e QUILT_MULTIUSER_MODE=true \
  -e QUILT_CATALOG_URL=https://your-catalog.quiltdata.com \
  -e QUILT_REGISTRY_URL=https://registry.your-catalog.quiltdata.com \
  quiltdata/quilt-mcp:latest
```

## docker-compose

See `docs/deployment/docker-compose-jwt.yaml`.

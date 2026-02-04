# JWT Mode (ECS Fargate)

JWT mode is suitable for multiuser ECS services that delegate authorization to the Platform.

## Key Points

- Provide JWT secret via SSM Parameter Store.
- Set `QUILT_MULTIUSER_MODE=true`.
- Set `QUILT_CATALOG_URL` and `QUILT_REGISTRY_URL`.

## Example Task Definition

See `docs/deployment/ecs-task-jwt.json` for a minimal example.

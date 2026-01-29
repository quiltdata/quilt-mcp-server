# JWT Mode (ECS Fargate)

JWT mode is suitable for multitenant ECS services with per-request role assumption.

## Key Points

- Task role should allow `sts:AssumeRole` into tenant roles.
- Provide JWT secret via SSM Parameter Store.
- Set `MCP_REQUIRE_JWT=true`.

## Example Task Definition

See `docs/deployment/ecs-task-jwt.json` for a minimal example.

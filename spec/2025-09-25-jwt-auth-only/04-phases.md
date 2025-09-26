# Implementation Phases – JWT-Only Authentication

## Phase 1: JWT Service Consolidation
- Promote `BearerAuthService` to the single source for JWT validation and claims normalization.
- Port Quilt repo decompression logic into a dedicated Python module with parity tests.
- Add behavior tests covering successful decode and failure paths.

## Phase 2: Middleware Simplification
- Replace QuiltAuthMiddleware logic with JWT-enforcement only.
- Ensure 401 responses for missing/invalid tokens; attach runtime context on success.
- Add troubleshooting logs and optional diagnostics hook.

## Phase 3: Tool Authorization Update
- Rework `auth_helpers` to consume the JWT service, build boto3 clients, and enforce permissions/buckets.
- Update bucket/package/Athena tools to rely on the new helper return structures.
- Add tests covering allowed and denied tool scenarios.

## Phase 4: Cleanup and Documentation
- Remove unused services (`unified_auth_service`, quilt3 fallbacks, role header paths).
- Update CLAUDE.md with operational notes and troubleshooting tips.
- Run unit suite; address remaining references to deprecated flows.


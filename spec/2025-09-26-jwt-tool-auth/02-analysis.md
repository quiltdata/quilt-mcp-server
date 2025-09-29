# Current-State Analysis: Tool Authorization

## Bucket Tools (`src/quilt_mcp/tools/buckets.py`)
- Use `_check_authorization` which mixes runtime JWT, environment JWT, quilt3, and IAM heuristics.
- `generate_signed_url` still imports `get_s3_client` from `utils`.
- Each public function (`bucket_objects_list`, `bucket_object_info`, `bucket_object_text`, `bucket_objects_put`, `bucket_object_fetch`, `bucket_object_link`) eventually calls `get_s3_client`.
- Search helpers (`bucket_objects_search`, `bucket_objects_search_graphql`) do not perform explicit authorization, assuming Quilt services handle it.

## Package Tools
- `package_ops.py` orchestrates package creation/update/delete using `QuiltService` directly and has no JWT checks.
- `packages.py`, `package_management.py`, `s3_package.py`, and `unified_package.py` interact with Quilt API/S3 clients without enforcing JWT permissions.
- Some functions import `get_s3_client` or rely on quilt3 sessions via `QuiltService`.

## Helpers
- `src/quilt_mcp/tools/auth_helpers.py` currently exposes only `check_s3_authorization` plus shared `_authorize_tool` logic.
- No helper exists for package authorization (S3 + Quilt API) or for Quilt GraphQL/read-only flows.

## Risks
- Removing quilt3/IAM fallbacks could break desktop workflows if JWT runtime context is missing.
- Quilt services may still expect quilt3 configuration; we must supply tokens/credentials via the JWT auth service.
- Tests depending on the old behaviour (e.g., direct quilt3 usage) must be updated or replaced.

## Opportunities
- Centralize tooling around `BearerAuthService` and runtime context to eliminate environment leakage.
- Provide structured deny reasons and logging across all tools.
- Simplify tests using mocks around the new helpers rather than monkeypatching multiple code paths.


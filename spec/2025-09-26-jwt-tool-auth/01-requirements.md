# JWT-Only Tool Authorization Requirements

## Problem Statement

S3 and package tools still depend on legacy multi-path authentication helpers (`_check_authorization`, quilt3 fallbacks, ambient AWS credentials). This causes inconsistent behaviour between desktop/web clients and defeats the new JWT-only guarantees. We need every bucket and package tool to authenticate strictly through the JWT pipeline so permissions, buckets, and roles are enforced uniformly.

## User Stories

1. As a Quilt web user, I want every bucket tool (`bucket_objects_list`, `bucket_object_info`, `bucket_object_text`, etc.) to honour my JWT claims so unauthorized buckets or operations are rejected.
2. As a package maintainer, I want package creation/update/delete flows to gate on the same JWT permissions so I never bypass governance by relying on local credentials.
3. As an operator, I want observability for authorization outcomes to trace deny reasons without reviewing multiple code paths.

## Acceptance Criteria

1. All functions in `src/quilt_mcp/tools/buckets.py`, `packages.py`, `package_ops.py`, `package_management.py`, `s3_package.py`, and `unified_package.py` call JWT helper functions and never read quilt3 state or call `_check_authorization` / `get_s3_client` directly.
2. Bucket tools use the `check_s3_authorization` helper to obtain boto3 clients. Package tools use a dedicated helper (`check_package_authorization`) that returns Quilt API handles and S3 clients as needed.
3. Unit tests exist for each tool category validating successful authorization and denial cases based on permissions/bucket access.
4. Legacy auth utilities that are superseded by the JWT helpers are removed or clearly deprecated.
5. All modified tests pass under `uv run pytest` (including new suites that cover the JWT-only behaviour).

## Open Questions

1. Should JWT helpers return Quilt API clients along with S3 clients, or should package tools construct them separately after authorization?
2. Do we need additional helpers for GraphQL/bucket search tools that rely on Quilt services but not S3 directly?
3. Are there any integration tests that rely on quilt3 behaviour which must be updated or skipped?


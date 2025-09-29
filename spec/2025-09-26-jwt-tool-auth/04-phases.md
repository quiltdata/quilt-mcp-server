# Implementation Phases

## Phase 1 — Helper Foundation
- Expand `auth_helpers.py` to include package-specific authorization helpers and to return Quilt API clients when requested.
- Write unit tests covering positive/negative cases for the new helpers.

## Phase 2 — Bucket Tool Refactor
- Update every bucket tool to call JWT helpers.
- Remove `_check_authorization` and related legacy helpers.
- Add behaviour-driven tests (similar to `test_buckets_authorization`) for each public bucket API.

## Phase 3 — Package Tool Refactor
- Update `package_ops.py`, `packages.py`, `package_management.py`, `s3_package.py`, and `unified_package.py` to use the new helpers.
- Add tests covering create/update/delete/list/search flows with authorized and unauthorized scenarios.

## Phase 4 — Cleanup and Observability
- Remove dead imports (quilt3, get_s3_client) from affected modules.
- Ensure `CLAUDE.md` documents the new expectations and troubleshooting steps.
- Run the relevant pytest suites and confirm green status.


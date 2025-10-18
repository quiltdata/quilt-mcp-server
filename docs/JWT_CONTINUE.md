# JWT Integration – Remaining Work

The mixed JWT/IAM backend scaffolding is now wired into `utils.py`, but the merge plan in `docs/JWT_MERGE.md` still has several open items. Use this checklist to finish the integration.

## Core Code Changes
- Port `src/quilt_mcp/tools/auth_helpers.py` from `doc/mcp-server-authentication` and add the IAM fallback logic described in the merge guide.
- Update bucket/package tools to consume the helper results (JWT client when present, legacy IAM/quilt3 otherwise) and surface strict-mode errors when `MCP_REQUIRE_JWT=true`.
- Bring over `src/quilt_mcp/services/auth_service.py` (or shrinkwrap the minimum helper APIs it provides) so the helper module can build IAM sessions without duplicating logic.
- Ensure runtime extras include any objects the helpers expect (e.g., cached boto3 session, auth claims).

## Testing & Validation
- Re-run static analysis once `ruff` is available.
- Regenerate `uv.lock` so `pyjwt` is recorded in dependency pins (`uv pip compile` or the project’s preferred workflow).
- Add/port unit tests that assert:
  - JWT present → JWT credentials are used.
  - JWT absent → IAM/quilt3 path still works.
  - Strict mode rejects missing JWT.
- Execute the existing integration test suite (or reproduce the HTTP/stdio scenarios manually) to ensure both transports succeed.

## Documentation & Ops
- Update README/deployment docs with the new optional `MCP_REQUIRE_JWT` flag and the JWT fallback behaviour.
- If the branch adds new environment variables or curl recipes, sync any CDK or deployment templates that set them.
- Capture any observed deltas between `doc/mcp-server-authentication` and this branch so the remaining porting work is traceable.

Work through the code tasks first, then loop back for tests, docs, and dependency hygiene. This page lives alongside the other JWT merge documents to keep momentum clear for the next contributor.

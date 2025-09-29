# JWT Tool Authorization Specifications

## Scope
- Rewrite bucket and package tools to rely exclusively on JWT helpers.
- Expand helper module(s) to deliver the clients/metadata required by each tool category.
- Remove or deprecate legacy authorization utilities inside the tool modules.

## Functional Specifications
1. **Helper Enhancements**
   - `check_s3_authorization(tool_name, tool_args)` returns an object with `authorized`, `s3_client`, `claims`, and optionally Quilt API handles when requested.
   - Introduce `check_package_authorization` (and others as needed) to supply S3 + Quilt API clients plus decoded user info.
   - Authorization helpers log (at DEBUG/INFO) success, and return failure payloads with reason strings tied to permission/bucket checks.

2. **Bucket Tools**
   - Replace `_check_authorization`/`_check_jwt_authorization`/`_check_traditional_authorization` with calls to the new helpers.
   - Each tool passes a consistently shaped `tool_args` dict containing referenced bucket names, keys, version ids, etc., so helpers can perform access checks.
   - All direct `get_s3_client` usage is removed; S3 operations use the authorized client returned by the helper.

3. **Package Tools**
   - `package_create`, `package_update`, `package_delete`, `packages_list`, `packages_search`, etc., call JWT helpers to ensure the caller has the required package or bucket permissions.
   - Functions that previously used quilt3 `QuiltService` instantiate it with tokens or clients provided by the helper (or the helper returns an already configured `QuiltService`).
   - Write operations (create/update/delete) ensure the helper verifies relevant `s3:*` and `package:*` permissions.

4. **Observability**
   - Authorization failures propagate consistent error structures (e.g., `{ "authorized": False, "error": "Missing required permission: s3:ListBucket" }`).
   - Successful calls may emit debug logs (behind logger) indicating the permissions used.

5. **Compatibility**
   - Desktop flows must set runtime context before invoking tools; without JWT the helper returns a clear error encouraging login.
   - Document transitional implications in `CLAUDE.md`.

## Non-Functional Specifications
- Maintain existing function signatures to avoid MCP API changes.
- Unit tests run under `uv run pytest` without external network calls.
- No residual references to quilt3-based authentication in the touched tool modules.

## Out of Scope
- Changes to GraphQL search or governance tools beyond ensuring they check JWT where S3 interactions occur.
- CLI/stdio transport flows that do not provide JWT (they will now receive authorization errors).


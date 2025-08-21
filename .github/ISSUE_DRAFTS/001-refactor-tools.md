Title: Refactor MCP tools to reduce duplication and simplify API surface

Labels: enhancement, refactor, area/tools, mcp

Summary

The `app/quilt_mcp/tools` package has grown large with overlapping concerns across modules like `packages.py`, `package_management.py`, `package_ops.py`, `unified_package.py`, and `s3_package.py`. Several files exceed 500–800 lines, and there is duplication in request validation, pagination, error handling, Quilt3/boto3 client instantiation, and response schemas. This issue proposes consolidating shared logic into service layers/utilities, standardizing request/response types, and reducing the number of public tool entrypoints where they overlap.

Motivation / Problem

- Large modules (`auth.py` ~759 LOC, `s3_package.py` ~806 LOC, etc.) reduce readability and increase cognitive load.
- Duplicated code for pagination, auth checks, exceptions, S3/Quilt client creation, and result shaping.
- Overlapping tools (e.g., package list/search/browse/contents) expose slightly different shapes and options.
- Inconsistent error mapping and status codes/messages across tools.

Proposed Approach

- Introduce a thin set of service modules under `app/quilt_mcp/services/`:
  - `auth_service.py`: JWT/Quilt auth verification and identity.
  - `s3_service.py`: Shared boto3 client/session factory, pagination helpers, retries.
  - `quilt_service.py`: Quilt3 package operations (get/list/search/update/delete) with unified interfaces.
  - `response_models.py`: Typed dataclasses or TypedDicts for tool responses.
- Create `app/quilt_mcp/common/validation.py` for parameter normalization and schema checks (reuse existing validators where possible).
- Standardize error handling via `exceptions.py` and a single `map_exception_to_tool_error` function.
- Consolidate overlapping tools:
  - Merge `packages.py` + `package_management.py` where appropriate; keep entrypoints but route to unified service functions.
  - Combine `package_ops.py` and `unified_package.py` into a single module or reconcile responsibilities.
  - Centralize pagination and filtering utilities (S3 and Quilt) in one place.
- Ensure clients (boto3, Quilt3) are created once per process and reused; inject via services.

Scope

- No behavior change for public tool names and parameters unless explicitly noted; responses should remain backward compatible where possible.
- Internal refactor only, with added unit tests for new service modules.

Out of Scope

- Adding new tools or changing auth mechanism.
- Major protocol changes to MCP transport.

Acceptance Criteria

- Shared services exist and are used by all tool entrypoints:
  - `app/quilt_mcp/services/auth_service.py`
  - `app/quilt_mcp/services/s3_service.py`
  - `app/quilt_mcp/services/quilt_service.py`
  - `app/quilt_mcp/models/response_models.py`
- Remove duplicated pagination/validation code from `tools/*.py` modules in favor of shared helpers.
- Reduce per-file size for `auth.py`, `s3_package.py`, `package_management.py` by at least 30% each without loss of coverage.
- Add unit tests for service modules with 90%+ coverage for new code.
- Maintain existing public tool behavior (smoke tests in `app/tests/` pass).

Proposed Tasks

- [ ] Create `services/` and `models/` packages; move common code
- [ ] Introduce singletons/factories for boto3 and Quilt3 clients in `s3_service.py`/`quilt_service.py`
- [ ] Extract pagination helpers; replace inline implementations across tools
- [ ] Extract validation helpers to `validators/` or `common/validation.py`
- [ ] Normalize error handling via shared exception mapping
- [ ] Refactor `packages.py` and `package_management.py` to call unified service APIs
- [ ] Reconcile `package_ops.py` and `unified_package.py` responsibilities
- [ ] Add tests for services and update affected tool tests
- [ ] Run `make test-app` and `make coverage`; ensure >=85% overall coverage

References

- Code: `app/quilt_mcp/tools/*.py`, `app/quilt_mcp/utils.py`, `app/quilt_mcp/validators/`
- CI: `.github/workflows/test.yml`

Risks / Mitigations

- Risk: Behavior drift. Mitigation: Keep adapter layer that preserves current parameter/response shapes until a major version.
- Risk: Large PR. Mitigation: Land in small PRs: (1) services scaffolding, (2) move S3/Quilt helpers, (3) tool-by-tool adoption.


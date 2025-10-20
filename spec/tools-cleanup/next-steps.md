# Tools Cleanup – Next Steps & Blockers

## Outstanding Work

- **Finalize test alignment with the service layer**
  - Refactor auth/unit tests to patch a single service factory once the Quilt service constructor is centralized; the current dual-patch workaround should be temporary.
  - Promote `_tabulator_query` to the service layer (or retire it entirely) so the tabulator tests exercise only `quilt_mcp.services.tabulator_service`; the legacy tool shim can then be deleted alongside the remaining tool registry references.
  - After the above refactors, trim duplicated mocks/fixtures that still import `quilt_mcp.tools.*` purely for backward compatibility.

- **Complete service migration for remaining read-only tools**
  - Permissions: move `aws_permissions_discover`, `bucket_recommendations_get`, `bucket_access_check` logic into a `services/permissions_service.py`.
  - Governance: extract `GovernanceService` helpers so resources no longer import `quilt_mcp.services.governance_service`.
  - Workflow orchestration: relocate `workflow_list_all` and `workflow_get_status` to a service module, then update the resource to call it.
  - Athena: follow the same pattern for any list-or-read-only helpers still living under `tools/athena_glue.py`.
  - Tabulator: finish wiring resources and tests to the new `services.tabulator` helpers; remove the residual tool shims once everything depends on the service.

- **Retire deprecated tool modules**
  - Remove `src/quilt_mcp/tools/metadata_examples.py` and `metadata_templates.py` (already staged for deletion) from the project history once the service layer is fully adopted.
  - Collapse `unified_package` / `package_management` wrappers (plan outlined in `simplification-plan.md`) after verifying no external callers rely on them.

- **Update imports and tests**
  - Replace remaining `quilt_mcp.tools.<module>` imports in tests/resources with service equivalents.
  - Regenerate `tests/fixtures/mcp-list.csv` after tool removals to keep the MCP catalog accurate.

- **Documentation clean-up**
  - Audit `docs/` and `spec/` for references to removed tool entry points; update instructions to reference the new resource URIs or service helpers.
  - Call out the migration in `CHANGELOG.md` once the full removal lands.

## Blockers / Issues

- **uv test runner crashes**  
  `uv run pytest …` fails before pytest starts (`failed to open …/uv/sdists-v9/.git` and, with a custom cache dir, `Attempted to create a NULL object`). Tests cannot be validated in this environment until uv is reinstalled or its cache permissions are fixed.  
  _Workaround_: run `python -m pytest` directly once the optional dependencies (`quilt3`, `pyjwt`) are available.

- **Sandbox denies writes inside `.git/`**  
  Git commands cannot create `.git/index.lock` (and even touching `.git/testfile` returns “Operation not permitted”). This prevents staging/committing with automation. Manual intervention outside the sandbox is required to remove macOS provenance/ACL flags and re-enable writes.

- **Optional dependency availability**  
  The test suite now expects `quilt3>=5.6.0` and `pyjwt>=2.8.0`. Ensure these packages install cleanly in CI before relying on the new test group configuration.

## Suggested Sequencing

1. **Re-baseline the suite (`make -B test`) before refactors**
   - Run the full target (`make -B test`); if the uv cache bug blocks execution, fall back to `python -m pytest tests` as noted under blockers so we still exercise the suite.
   - Fix any failures caused by interim service shims so the branch starts green. Patch the temporary double-mocking of Quilt services once the constructor is centralized.
   - Capture any persistent failures in TODOs or `notes/` so they are visible during review—no silent skips.
2. **Finish migrating the remaining read-only helpers into services**
   - Stand up `services/permissions_service.py` for `aws_permissions_discover`, `bucket_recommendations_get`, and `bucket_access_check`, mirroring the new tabulator pattern.
   - Relocate governance/workflow/Athena helpers into their respective `services/*` modules, then update `resources/*.py` to call the services directly.
   - Update unit and integration tests to import the service layer and drop the legacy tool patches; regenerate fixtures where they embed tool paths.
3. **Cull the superseded tool modules and wrappers**
   - Remove the migrated `quilt_mcp/tools/*.py` files (`metadata_examples`, `metadata_templates`, remaining tabulator shim, etc.) plus `unified_package` and `package_management`.
   - Update `src/quilt_mcp/tools/__init__.py`, any registry catalogs, and `tests/fixtures/mcp-list.csv` so the deleted modules disappear from discovery.
   - Re-run targeted search (`rg "quilt_mcp.tools"`) to confirm no stale imports remain.
4. **Refresh documentation once the surface area is stable**
   - Sweep `docs/`, `spec/`, and resource READMEs for tool references; replace them with service/resource guidance and new URIs.
   - Note the migration in `CHANGELOG.md` and call out the breaking change for external tool consumers.
5. **Full regression and PR polish**
   - Execute `make test-all` (plus `ruff`/type checks if they are not already wired into the target) and fix any remaining regressions.
   - Review `git status`, regenerate artifacts (fixtures, lockfiles) as needed, and craft the PR summary linking to the migration/spec docs.

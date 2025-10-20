# Tools Cleanup – Next Steps & Blockers

## Outstanding Work

- **Finalize test alignment with the service layer**
  - Refactor auth/unit tests to patch a single service factory once the Quilt service constructor is centralized; the current dual-patch workaround should be temporary.
  - Promote `_tabulator_query` to the service layer (or retire it entirely) so the tabulator tests exercise only `quilt_mcp.services.tabulator_service`; the legacy tool shim can then be deleted alongside the remaining tool registry references.
  - After the above refactors, trim duplicated mocks/fixtures that still import `quilt_mcp.tools.*` purely for backward compatibility.

- **Complete service migration for remaining read-only tools**
  - Permissions: move `aws_permissions_discover`, `bucket_recommendations_get`, `bucket_access_check` logic into a `services/permissions_service.py`.
  - Governance: extract `GovernanceService` helpers so resources no longer import `quilt_mcp.tools.governance`.
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

1. Resolve uv / `.git` permission issues so commits and tests can run locally.
2. Finish migrating permissions, workflow, governance, and athena read-only helpers into services; update resources and tests accordingly.
3. Remove the superseded tool modules and convenience wrappers; update tooling registry and fixtures.
4. Refresh documentation and changelog once the tool surface matches the simplified plan.

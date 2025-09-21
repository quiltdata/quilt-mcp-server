<!-- markdownlint-disable MD013 -->
# Phase 1 Checklist – Canonical Export Realignment

**Scope**: Tracks completion of Phase 1 tasks defined in `05-phase1-design.md` and `06-phase1-episodes.md`.

## Pre-Implementation

- [ ] Capture old→new tool mapping table in PR description draft.
- [ ] Confirm working branch created for Phase 1 implementation.
- [ ] Run baseline `make test` and `make lint` to establish starting point.

## Episode 1 – Lock Down Removed Exports

- [ ] Add failing test asserting removed exports are absent / raise `AttributeError`.
- [ ] Delete implementations/imports/exports for removed tools across codebase.
- [ ] Remove references from tests, fixtures, docs.
- [ ] Verify `make test-unit` passes; run `rg` to confirm deletions.
- [ ] Commit with conventional message (`test:` then `feat:`/`refactor:` as TDD cycle dictates).

## Episode 2 – Package Tool Rename Consolidation

- [ ] Add failing test validating `package_create`/`package_tools_list` availability.
- [ ] Rename implementations, exports, and all call sites.
- [ ] Update docstrings, mocks, fixtures referencing package tool names.
- [ ] Run `make test-unit` and `make test`; ensure no old package names remain (`rg`).
- [ ] Commit after green state.

## Episode 3 – Catalog Search Consolidation

- [ ] Add failing behavior test ensuring `catalog_search` is sole export and `package_contents_search` delegates to it.
- [ ] Rename implementation, delete redundant search tools, and refactor `package_contents_search` to call unified helper.
- [ ] Update callers, fixtures, docs, and any shared helper wiring.
- [ ] Run `make test-unit` (then relevant integration tests) and `rg` sweep for removed search names.
- [ ] Commit after tests pass.

## Episode 4 – Tabulator Accessibility Alignment

- [ ] Add failing tests for new tabulator tool names.
- [ ] Rename functions/exports and update fixtures & docs.
- [ ] Run targeted tests (`make test`) and confirm old names removed.
- [ ] Commit after green build.

## Episode 5 – Metadata Namespace Prefixing

- [ ] Add failing tests for `metadata_template_*` names.
- [ ] Rename implementations/imports, adjust docstrings.
- [ ] Update dependent modules/tests/fixtures.
- [ ] Run `make test-unit`, metadata-related suites, and `rg` sweep.
- [ ] Commit after success.

## Episode 6 – Workflow Tool Re-clustering

- [x] Add failing tests covering new workflow names and behavior.
- [x] Rename functions, registries, payload fixtures.
- [x] Run workflow-related tests and `make test`.
- [x] Confirm old workflow names removed (`rg`).
- [ ] Commit after passing suites.

## Episode 7 – Export Ordering & Transitional Docs

- [x] Add failing test verifying `__all__` alphabetical ordering and admin grouping.
- [x] Reorder exports, update docs (`docs/api/TOOLS.md`, README snippets).
- [x] Run `make lint`, `make test`, final `rg` sweeps.
- [x] Capture mapping table and doc updates in PR notes.
- [ ] Commit after green state.

### Phase 1 Export Mapping (for PR notes)

| Legacy Name | Canonical Name |
| --- | --- |
| `create_package_enhanced` | `package_create` |
| `list_package_tools` | `package_tools_list` |
| `unified_search` | `catalog_search` |
| `packages_search` | `catalog_search` |
| `bucket_objects_search` | `catalog_search` |
| `admin_tabulator_open_query_get` | `tabular_accessibility_get` |
| `admin_tabulator_open_query_set` | `tabular_accessibility_set` |
| `get_metadata_template` | `metadata_template_get` |
| `create_metadata_from_template` | `metadata_template_create` |
| `workflow_list_all` | `workflow_list` |
| `workflow_add_step` | `workflow_step_add` |
| `workflow_update_step` | `workflow_step_update` |
| `workflow_get_status` | `workflow_status_get` |

## Phase Closure

- [ ] Ensure all checklist items checked off.
- [x] Confirm `make test` and `make lint` pass on clean tree.
- [ ] Update PR description with mapping table, test results, and Phase 1 summary.
- [x] Update `CLAUDE.md` with Phase 1 learnings/notes.
- [ ] Commit Phase 1 completion (`feat`/`refactor` summary as appropriate).

## Hand-off to Phase 2

- [x] Tag required follow-ups for Phase 2 (automation needs, doc gaps).
- [x] Prepare initial notes for Phase 2 design kick-off referencing final export surface.

**Phase 2 follow-up notes**

- Automate regeneration of `quilt_mcp_tools.csv` and `docs/api/TOOLS.md` from the canonical `__all__` list to prevent future drift.
- Review MCP inspector scripts to ensure they surface the renamed workflow tools without relying on deprecated identifiers.
- Capture integration test updates for workflow orchestration once Phase 2 introduces automation harnesses.

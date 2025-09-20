<!-- markdownlint-disable MD013 -->
# Phase 1 Design – Canonical Export Realignment

**Scope**: Implements Phase 1 from `spec/170-tool-audit/04-phases.md`.

## 1. Objectives & Success Metrics

- Enforce the "brutal elimination" plan by deleting all redundant tool exports and implementations enumerated in `03-specifications.md`.
- Rename surviving tools to the canonical identifiers, ensuring callers, fixtures, and documentation align with the new surface.
- Reorder and curate `src/quilt_mcp/__init__.py` so it becomes the single authoritative export list, alphabetized for public tools with admin tools grouped last.
- Maintain a green build (`make test`, `make lint`) throughout the migration and end with zero references to removed identifiers (`rg` sweep).

## 2. Context & Constraints

- Existing tests and fixtures directly import/export tool names; renames must update every reference to keep suites green without introducing temporary aliases at completion.
- Package, tabulator, search, metadata, and workflow modules each contain multiple functions—changes must avoid regressions in shared helpers (e.g., Quilt service wrappers).
- Phase 2 automation will rely on the final layout; intermediate scaffolding must not leak into long-term code.
- Breaking changes are acceptable (major version bump planned), but the repo must remain internally consistent at Phase 1 completion.

## 3. Target State Overview

- `src/quilt_mcp/__init__.py` exports only the survivor tool set using their new canonical names, ordered alphabetically (non-admin) followed by admin-only tools.
- Deleted tools (`package_create`, `create_package`, `package_create_from_s3`, `packages_search`, `bucket_objects_search`, `tabulator_open_query_status`, `tabulator_open_query_toggle`) are removed from code, tests, fixtures, and docs.
- Renamed tools adopt the following mappings across implementation, tests, and narrative documentation:
  - `create_package_enhanced` → `package_create`
  - `list_package_tools` → `package_tools_list`
  - `unified_search` → `catalog_search`
  - `admin_tabulator_open_query_get` → `tabular_accessibility_get`
  - `admin_tabulator_open_query_set` → `tabular_accessibility_set`
  - `get_metadata_template` → `metadata_template_get`
  - `create_metadata_from_template` → `metadata_template_create`
  - `workflow_list_all` → `workflow_list`
  - `workflow_add_step` → `workflow_step_add`
  - `workflow_update_step` → `workflow_step_update`
  - `workflow_get_status` → `workflow_status_get`
- Documentation (`docs/api/TOOLS.md`, interim updates) reflects new names and omits removed entries pending Phase 2 automation.

## 4. Implementation Plan

### 4.1 Deletion Execution

1. Remove redundant functions from their defining modules under `src/quilt_mcp/tools/`.
2. Delete corresponding imports, exports, and helper references in `src/quilt_mcp/__init__.py`.
3. Sweep tests, fixtures (`tests/`, `tests/fixtures/`), and docs to eliminate all mentions; update expectation files when payloads reference tool IDs.

### 4.2 Rename Strategy

For each survivor rename:

- Update function definition name (or wrapper) in the originating module.
- Adjust internal references (e.g., module-level dictionaries, workflow registries) to use the new identifier.
- Update `__all__` exports and any higher-level re-exports.
- Modify tests and fixtures to call the renamed functions; regenerate mocked paths where decorators (`@patch`) were tied to the old names.
- Ensure docstrings and error messages reference the new identifiers to seed Phase 2 metadata extraction.

### 4.3 Metadata Prefix Alignment

- Rename metadata helpers and adjust any imports in modules consuming them (e.g., package metadata handlers).
- Update docstrings and descriptions to begin with `metadata_` so alphabetical ordering remains consistent.

### 4.4 Workflow Re-clustering

- Rename workflow functions and update any registry structures (likely `WORKFLOW_HANDLERS` or similar) to use the new keys.
- Adjust serialization payloads returned by workflow tools so response fields referencing tool IDs stay accurate.

### 4.5 Export Ordering & Verification

- Rebuild the `__all__` list alphabetically for non-admin tools.
- Append admin-only tools (including the renamed tabulator functions) at the end as mandated by the specification.
- Validate ordering by visual inspection and, if helpful, temporary script assertions (removed before completion).

### 4.6 Transitional Documentation Update

- Manually edit `docs/api/TOOLS.md` and any README snippets to reflect the new tool names and removal list.
- Document the mapping table within the Phase 1 PR description for future reference and to seed Phase 3 release notes.

## 5. Testing Strategy

- **Unit/Integration Suites**: Run `make test-unit` frequently during refactors; execute `make test` before finalizing Phase 1 to cover integration paths (packages, workflow, tabulator).
- **Static Analysis**: Run `make lint` after renames to catch unresolved imports or unused symbols.
- **Reference Sweep**: Use `rg` searches for each deleted identifier as a post-migration gate; scriptable checks may be added temporarily in tests (removed before final commit).
- **Fixture Validation**: Where JSON fixtures reference tool names, update snapshots and run associated tests to ensure expected payloads are consistent.

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Missed reference to deleted tool | Runtime errors or failing tests | `rg` sweeps per deleted name; comprehensive test runs |
| Renamed function not exported/imported correctly | API surface becomes inconsistent | Update exports immediately after renaming; rely on lint/test failures |
| Workflow registry keys left stale | Workflow orchestration breaks | Audit registry dicts/lists; add targeted tests if absent |
| Documentation drift until Phase 2 | Confusion for consumers | Manual updates in Phase 1 plus mapping table in PR summary |

## 7. Dependencies & Follow-On Work

- Outputs of Phase 1 feed Phase 2 automation; ensure mapping table is captured (e.g., in PR notes or temporary spec scratchpad) for use by tool generation scripts.
- Major version bump and communication handled in Phase 3 once enforcement is wired in.
- No new public APIs beyond the renamed survivors; maintainers must review before proceeding to implementation episodes.

## 8. Acceptance Checklist for Phase 1

- [ ] All deletions executed and verified absent via `rg`.
- [ ] All rename mappings applied across code, tests, fixtures, and docs.
- [ ] `src/quilt_mcp/__init__.py` exports alphabetized with admin tools last.
- [ ] `make test` and `make lint` succeed after the migration.
- [ ] Temporary notes/mapping tables captured for downstream phases.

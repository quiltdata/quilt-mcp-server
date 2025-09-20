<!-- markdownlint-disable MD013 -->
# Phase 1 Episodes – Canonical Export Realignment

**Scope**: Executes the design in `spec/170-tool-audit/05-phase1-design.md` via atomic, test-driven episodes.

## Episode 1 – Lock Down Removed Exports

- **Goal**: Ensure deleted tool names (`package_create`, `create_package`, `package_create_from_s3`, `packages_search`, `bucket_objects_search`, `tabulator_open_query_status`, `tabulator_open_query_toggle`) no longer appear in the public surface.
- **Red Step**: Add/extend a test in `tests/test_exports.py` (or create comparable behavior test) that asserts these names are absent from `quilt_mcp.__all__` and that importing them raises `AttributeError`.
- **Green Step**: Delete the implementations, imports, and exports for the obsolete tools across `src/quilt_mcp/tools/` and `src/quilt_mcp/__init__.py`; remove references in docs/fixtures/tests.
- **Refactor Step**: Clean up any now-unused helpers or constants; re-run tests to confirm green state.
- **Validation**: `make test-unit`, targeted `rg` sweeps verifying the deleted identifiers are absent.

## Episode 2 – Package Tool Rename Consolidation

- **Goal**: Promote `create_package_enhanced` to `package_create` and rename `list_package_tools` → `package_tools_list`.
- **Red Step**: Extend package-focused behavior tests (e.g., `tests/integration/test_packages.py`) to assert the new tool names exist and old names do not, causing failure before implementation.
- **Green Step**: Rename the functions in their modules, update exports/imports, adjust docstrings, and update tests/fixtures/mocks to reference the new names.
- **Refactor Step**: Ensure helper utilities remain DRY and remove any alias shims introduced during migration.
- **Validation**: `make test-unit`, then `make test` once green; `rg` for old package tool names.

## Episode 3 – Catalog Search Unification

- **Goal**: Rename `unified_search` to `catalog_search` and remove `packages_search`/`bucket_objects_search` remnants.
- **Red Step**: Add behavior test under `tests/` (integration or acceptance) asserting `catalog_search` is the sole search tool exposed and produces expected responses.
- **Green Step**: Rename implementation, update exports/callers/fixtures, and delete orphaned search tools.
- **Refactor Step**: Simplify search module imports, ensuring no dead code remains.
- **Validation**: `make test-unit`, targeted search suite (if exists), plus `rg` for removed search names.

## Episode 4 – Tabulator Accessibility Alignment

- **Goal**: Rename admin tabulator tools to `tabular_accessibility_get`/`tabular_accessibility_set` and remove open query variants.
- **Red Step**: Add behavior tests ensuring the new names exist and old ones raise `AttributeError`, plus verifying responses still match expectations.
- **Green Step**: Rename functions, update exports, adjust fixtures (`tests/fixtures/tabulator/*.json`), and update documentation references.
- **Refactor Step**: Remove any now-unused helper constants; ensure admin tooling list is coherent.
- **Validation**: Run targeted tabulator tests, then `make test`.

## Episode 5 – Metadata Namespace Prefixing

- **Goal**: Rename metadata helpers (`get_metadata_template`, `create_metadata_from_template`, etc.) to `metadata_template_get` and `metadata_template_create`.
- **Red Step**: Add tests confirming the new names are available and legacy names are absent, e.g., in metadata workflow scenarios.
- **Green Step**: Rename implementations, update imports, adjust docstrings, and revise dependent modules/tests/fixtures.
- **Refactor Step**: Ensure any metadata registry/list is alphabetized under the new prefix.
- **Validation**: `make test-unit`, metadata-related tests, `rg` for old metadata names.

## Episode 6 – Workflow Tool Re-clustering

- **Goal**: Rename workflow tool exports for alphabetical grouping (`workflow_list_all` → `workflow_list`, etc.).
- **Red Step**: Add/extend workflow behavior tests asserting new names exist in `__all__` and drive workflow scenarios.
- **Green Step**: Rename functions, update workflow registries and tests, adjust serialized payload fixtures.
- **Refactor Step**: Ensure workflow module remains coherent; update docstrings/messages to new names.
- **Validation**: Workflow-focused tests, `make test` after renames.

## Episode 7 – Export Ordering and Transitional Docs

- **Goal**: Alphabetize `src/quilt_mcp/__all__` (public tools first, admin tools last) and sync interim documentation.
- **Red Step**: Add assertion-based test ensuring exports are alphabetized and admin entries occupy the trailing block.
- **Green Step**: Reorder exports, confirm grouping, and update `docs/api/TOOLS.md` (manual interim update) plus README snippets.
- **Refactor Step**: Remove temporary asserts if unnecessary; keep only enduring tests.
- **Validation**: `make lint`, `make test`, final `rg` sweeps for removed names.

## Episode Execution Notes

- Episodes proceed sequentially; each ends with a green build before moving forward.
- Mapping table (old→new names) maintained in Phase 1 PR notes for downstream documentation and release tooling.
- All new tests remain after implementation to guard against regression.

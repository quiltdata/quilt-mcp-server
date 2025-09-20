<!-- markdownlint-disable MD013 -->
# Phase 1 Checklist - Inventory & Safety Net

 - [x] Inventory single-file directories in `src/quilt_mcp` and document decisions
- [ ] Confirm existing tests cover critical import paths
- [ ] Add new behavior-driven tests for tool discovery/imports (failing first)
- [ ] Update checklist with catalog of external references (configs/docs)
- [ ] Run `make test-unit` to validate safety net additions

## Inventory Notes

- Collapsible candidates: `services/` (single functional module), `aws/` (two concrete modules plus `__init__`), `telemetry/` (multi-module but may expose single entry point), `validators/` (three validator modules sharing purpose).
- Empty legacy packages: `config/`, `operations/`, `operations/quilt3/`, and `utilities/` (plus `utilities/aws/`) contain no tracked `.py` files; safe removal requires confirming no external imports rely on them.
- Rich subpackages to keep structured: `search/` hierarchy, `visualization/` (analyzers/generators/layouts/utils), and `optimization/` already house multiple cohesive modules.

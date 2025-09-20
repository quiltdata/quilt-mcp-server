<!-- markdownlint-disable MD013 -->
# Phases - Tool Inventory Audit

**Reference**: Specifications in `spec/170-tool-audit/03-specifications.md`

## Phase 1 - Baseline Inventory & Safety Net

- Capture current tool surface area by introspecting `src/quilt_mcp/tools/` and verifying the output against `quilt_mcp_tools.csv` and `docs/api/TOOLS.md`.
- Write behavior-driven tests that fail when tool listings diverge or fall out of alphabetical order.
- Document naming/prefix patterns observed today to inform convention decisions without changing production code yet.
- Deliverable: Verified snapshot of the existing inventory plus guardrail tests demonstrating current drift.

## Phase 2 - Canonical Inventory Source of Truth

- Introduce an automated generator (script or module) that produces the canonical inventory from code metadata.
- Update `quilt_mcp_tools.csv`, documentation, and any exports to consume the generated output, ensuring alphabetical sorting.
- Add contributor-facing guidance (CLAUDE.md) describing how to run and validate the generator locally.
- Deliverable: Single regenerated inventory artifact referenced by code, CSV, and docs with passing safety-net tests.

## Phase 3 - Naming Conventions & Overlap Decisions

- Facilitate maintainer review to classify overlapping tools (retain, rename, deprecate) and document outcomes in the canonical inventory.
- Apply agreed renames or aliases with deprecation notices while keeping backward compatibility where required.
- Update tests and docs to highlight preferred tools and note deprecated entries, ensuring behavior remains stable.
- Deliverable: Inventory annotated with disposition, updated docs/tests reflecting naming rules, and migration notes captured in CLAUDE.md.

## Phase 4 - Enforcement & Continuous Compliance

- Embed validation into CI (`make lint` or dedicated target) to block drift between code and inventory artifacts.
- Create a lightweight checklist for future tool changes, referencing the generator and naming rules, and include it in repo automation.
- Monitor coverage and regression tests to confirm no runtime regressions; adjust guardrail tests as needed.
- Deliverable: Automated enforcement pipeline, documented checklist, and verified green build demonstrating sustainable governance.

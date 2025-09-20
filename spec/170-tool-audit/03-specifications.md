<!-- markdownlint-disable MD013 -->
# Specifications - Tool Inventory Audit

**Reference**: Analysis in `spec/170-tool-audit/02-analysis.md`

## Desired End State

1. A single canonical inventory of all Quilt MCP tools that includes name, module, signature, description, and status, sourced directly from code and available to both humans and automation.
2. Tool naming, grouping, and descriptions align with explicit conventions that eliminate ambiguity and highlight the preferred entry points for overlapping behaviors.
3. Documentation (`docs/api/TOOLS.md`, onboarding guides, CLAUDE.md) reflects the canonical inventory and matches alphabetical ordering rules.
4. Redundant or overlapping tools are cataloged with an agreed disposition (retain, rename, consolidate, deprecate) and corresponding communication plan.
5. Guardrails exist (tests, lint checks, or generators) to keep the inventory, documentation, and exports in sync going forward.

## Scope & Boundaries

- **In Scope**: `src/quilt_mcp/tools/` modules, tool re-exports in `src/quilt_mcp/__init__.py`, the `quilt_mcp_tools.csv` inventory, documentation describing tools, and supporting scripts that derive tooling metadata.
- **Out of Scope**: Changes to business logic of individual tools, AWS service integrations, or historical specification documents within `spec/`.

## Engineering Constraints

1. Maintain backwards compatibility for existing tool names unless a deprecation path is explicitly defined and communicated.
2. Ensure any inventory generation fits into the existing build/test workflow (`make test`, `make lint`, `make coverage`) without introducing flaky external dependencies.
3. Align naming conventions with Quilt terminology and avoid collisions with reserved MCP keywords; enforce via code-level validation when feasible.
4. Keep the canonical inventory source easy to regenerate during local development (no manual spreadsheet edits required).

## Success Criteria

1. Running the agreed verification flow produces identical tool listings across code exports, CSV, and documentation (order and content).
2. Contributors have a published checklist describing the naming and documentation requirements for adding or modifying tools.
3. Overlap decisions are documented per tool (e.g., `prefer package_management.create_package_enhanced over package_ops.package_create`) so future work does not revive deprecated paths.
4. CI catches drift between code and inventory artifacts, preventing unsynchronized updates from merging.

## Integration Points & API Contracts

1. The canonical inventory should be derivable from the code modules (e.g., inspected metadata) and exported for downstream consumers needing a machine-readable view.
2. Documentation generation must consume the same source to ensure textual descriptions stay aligned with tool signatures.
3. Tool registration in the MCP server (re-exports, discovery) must reference the canonical list so that runtime availability matches documented expectations.
4. Any enforcement (lint/test) must expose actionable failure messages referencing the conventions and remediation steps.

## Quality Gates

1. Behavior-driven tests assert that inventory generation captures all expected tools and preserves naming conventions.
2. Static checks confirm alphabetical ordering and naming style rules before commits land.
3. Documentation builds or linting verify that `docs/api/TOOLS.md` mirrors the canonical inventory entries.
4. Review checklist requires confirmation that CLAUDE.md captures final guidance for maintainers and assistants.

## Risks & Mitigations

1. **Risk**: Breaking clients that depend on existing tool names. **Mitigation**: Stage renames through aliases/deprecation flags and communicate via docs plus release notes.
2. **Risk**: Inventory drift due to manual updates. **Mitigation**: Automate generation and enforce via CI check that fails on divergence.
3. **Risk**: Excessively rigid naming rules blocking legitimate new tools. **Mitigation**: Document escalation path and allow overrides with explicit justification captured in specs.
4. **Risk**: Increased maintenance burden from new automation. **Mitigation**: Integrate generators/lints into existing `make` targets and provide developer documentation for running them locally.

## Outstanding Questions & Assumptions

1. Decision authority for deprecation vs. rename (maintainer group) must be confirmed with stakeholders before implementation.
2. Need clarity on external consumers of `quilt_mcp_tools.csv` to avoid breaking any downstream pipelines when restructuring the inventory.
3. Confirm whether inventory enforcement should run in every developer workflow (`make lint`) or only in CI to balance speed and reliability.

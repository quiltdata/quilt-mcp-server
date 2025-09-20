<!-- markdownlint-disable MD013 -->
# Phases - Cleanup src Layout

**Reference**: Specifications in `spec/164-cleanup-src/03-specifications.md`

## Phase 1 - Inventory & Safety Net

- Audit `src/quilt_mcp` to catalog single-file directories and intended targets for consolidation.
- Add behavior-driven tests (or expand existing ones) that lock in import expectations and key tool discovery flows before restructuring.
- Document findings and planned moves without touching production code yet.

## Phase 2 - Restructure Core Packages

- Collapse identified single-file directories (e.g., `services`, `aws`, `telemetry`) into clearer module layouts while preserving behavior.
- Adjust imports, configuration, and docs to align with the new structure.
- Provide compatibility layers or re-export patterns where necessary to avoid breaking consumer imports.
- Update operational documentation (`CLAUDE.md`) with the new layout insights.

## Phase 3 - Cleanup & Validation

- Remove obsolete placeholder packages (`config`, `operations`, `utilities`) or repurpose them with clear intent.
- Run full lint/test/coverage suite to confirm stability.
- Finalize checklists, ensure compatibility notes are recorded, and prepare for integration.

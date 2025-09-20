<!-- markdownlint-disable MD013 -->
# Phase 2 Design - Restructure Core Packages

## Objectives

1. Collapse targeted single-module directories into a clearer hierarchy while preserving public behavior.
2. Provide compatibility exports or adapters so existing imports remain functional.
3. Update code, configs, and documentation to reflect the new layout.

## Target Structure (Tentative)

- Promote `services/quilt_service.py` to `quilt_mcp/services.py` or integrate into a broader `infrastructure` package with other service wrappers.
- Merge `aws/athena_service.py` and related helpers into a cohesive `quilt_mcp/aws_services.py` module (or similar) while keeping AWS concerns isolated.
- Evaluate `telemetry/` and `validators/` to determine whether consolidating into single modules improves clarity or whether subpackages remain justified.
- Remove empty packages (`config`, `operations`, `utilities`) after ensuring no references depend on them.

## Key Activities

- Move/rename files using tooling that preserves git history where possible.
- Adjust import statements across the codebase (tests, runtime, configs) to reference the new module locations.
- Introduce compatibility imports (e.g., re-export moved symbols from legacy module paths) when necessary to keep changes non-breaking.
- Keep changes behavior-focused; defer stylistic refactors unless required to maintain functionality.

## Deliverables

- Updated module layout matching the agreed structure.
- Passing tests and lint checks with updated imports.
- Documentation updates (especially `CLAUDE.md`) describing the new organization and compatibility notes.

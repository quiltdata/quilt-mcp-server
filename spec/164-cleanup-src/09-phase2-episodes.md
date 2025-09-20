<!-- markdownlint-disable MD013 -->
# Phase 2 Episodes - Restructure Core Packages

## Episode 1 - Services Module Consolidation

- Move `quilt_mcp/services/quilt_service.py` to a flattened structure (e.g., `quilt_mcp/services.py`).
- Provide backward-compatible imports through the former package path.
- Update tests and runtime references.

## Episode 2 - AWS Utilities Alignment

- Collapse `quilt_mcp/aws/` into a single module or clearly grouped submodules based on actual usage.
- Adjust imports and ensure AWS-related tests still execute.

## Episode 3 - Telemetry & Validators Review

- Decide whether telemetry and validator packages remain multi-module or should expose simplified entry points.
- Apply renames/moves as needed, adding compatibility exports.

## Episode 4 - Documentation & Config Updates

- Update configuration files and `CLAUDE.md` with the new structure.
- Verify no stale paths remain via targeted search.

<!-- markdownlint-disable MD013 -->
# Phase 2 Episodes - Restructure Core Packages

## Episode 1 - Services Module Consolidation

- Co-locate `QuiltService`, `AthenaQueryService`, and permission discovery primitives under the `quilt_mcp.services` package.
- Update tests and runtime references to import from the new structure.

## Episode 2 - Remove Legacy AWS Namespace

- Delete the `quilt_mcp/aws` package after migrating modules.
- Ensure all imports reference `quilt_mcp.services` equivalents.

## Episode 3 - Telemetry & Validators Review

- Decide whether telemetry and validator packages remain multi-module or should expose simplified entry points.
- Apply renames/moves as needed, adding compatibility exports.

## Episode 4 - Documentation & Config Updates

- Update configuration files and `CLAUDE.md` with the new structure.
- Verify no stale paths remain via targeted search.

<!-- markdownlint-disable MD013 -->
# Phase 1 Episodes - Inventory & Safety Net

## Episode 1 - Capture Current Layout

- Script or document the existing `quilt_mcp` directory tree with annotations on single-file directories.
- Record legacy/empty packages, noting if they are safe to remove or need further investigation.

## Episode 2 - Strengthen Import Behavior Tests

- Add behavior-driven tests that exercise tool discovery/import routines to fail if expected modules disappear.
- Use factories/fixtures to interact with the public API (e.g., `quilt_mcp.utils` discovery functions) rather than importing private modules directly.

## Episode 3 - Catalogue External References

- Search configuration (`pyproject.toml`, `setup.cfg`, `Makefile`) and docs (`CLAUDE.md`, README) for sensitive import paths.
- Document findings and potential impact areas in the phase checklist.

<!-- markdownlint-disable MD013 -->
# Requirements - Cleanup src Layout

**GitHub Issue**: #164 "cleanup src"
**Problem Statement**: The `src/` directory contains numerous single-file subfolders that add unnecessary nesting. We need a clearer layout without gratuitous behavioral changes and with all references updated accordingly.

## User Stories

1. **As a maintainer**, I want related modules grouped in meaningful packages so that I can navigate the codebase quickly.
2. **As a contributor**, I want module paths to reflect actual project structure so that refactoring and new features can be implemented with less guesswork.
3. **As a release engineer**, I want configuration and documentation references to stay accurate after the reorganization so that builds and published artifacts remain reliable.

## Acceptance Criteria

1. Identify single-file directories under `src/` that can be collapsed without losing organizational clarity.
2. Consolidate modules into a rational structure that maintains behavior (imports, entry points, CLI) with minimal churn.
3. Update all code, configuration, and top-level documentation references impacted by the new structure (excluding historical specs).
4. Ensure automated tests, linting, and packaging workflows continue to pass after the reorganization.
5. Communicate the new layout to developers via updated operational docs where necessary (e.g., `CLAUDE.md`).

## Success Metrics

1. Directory depth under `src/` is reduced for previously single-file packages while preserving semantic grouping.
2. No runtime regressions or import errors occur when running `make test` and `make lint`.
3. Contributors can locate modules using names that match their function without redundant folder indirection.
4. Documentation that references affected paths is updated on the same branch with no broken links.

## Open Questions

1. Are there historical reasons certain modules live in their own package that we must preserve (e.g., for dynamic imports)?
2. Do any third-party integrations depend on the existing package paths outside this repository (e.g., published API packages)?
3. Are there additional operational docs beyond `CLAUDE.md` and top-level README that reference the current layout?

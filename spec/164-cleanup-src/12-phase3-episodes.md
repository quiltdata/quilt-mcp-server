<!-- markdownlint-disable MD013 -->
# Phase 3 Episodes - Cleanup & Validation

## Episode 1 - Remove Dead Packages

- Delete empty placeholder directories or repurpose them with explicit module content.
- Ensure git history captures removals cleanly.

## Episode 2 - Final Compatibility Audit

- Confirm re-export modules behave as intended.
- Search the codebase for deprecated import paths and remove temporary shims if safe.

## Episode 3 - Final Validation & Documentation

- Run full validation suite (`make test`, `make lint`, `make coverage`).
- Update `CLAUDE.md` and the phase checklist with final notes and learnings.

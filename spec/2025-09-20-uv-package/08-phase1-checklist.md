# Phase 1 Checklist – UV Packaging via release.sh

## Preconditions
- [ ] Branch `2025-09-20-uv-package` checked out and up to date.
- [ ] `uv` CLI available locally (tests may stub when necessary).

## Development Steps
- [ ] Write failing tests for `release.sh uv-package` credential validation and happy path under `DRY_RUN=1`.
- [ ] Implement `ensure_uv_env` helper enforcing token or username/password.
- [ ] Implement `uv-package` subcommand that builds artifacts (or logs in dry runs) and ensures `dist/` exists.
- [ ] Add `package-uv` target in `make.deploy` delegating to the new subcommand.
- [ ] Confirm DXT targets (`make dxt`) still function (smoke test optional if time allows).

## Validation
- [ ] Run `make test-unit` (or targeted pytest) to ensure new tests pass.
- [ ] Run shellcheck or lint if applicable (script changes kept simple to avoid new tooling).
- [ ] Update `CLAUDE.md` with any new takeaways.
- [ ] Ensure working tree clean before final handoff/PR update.

## Postconditions
- [ ] Documented make target usage verified in PR description or follow-up docs.
- [ ] Ready for Phase 2 documentation enhancements.

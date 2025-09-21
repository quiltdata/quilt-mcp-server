# Phase 1 Design – UV Packaging via release.sh

## Objectives
- Extend `bin/release.sh` with a uv packaging command (`python-dist`) that builds wheel/sdist artifacts into `dist/`.
- Keep the build command credential-free while laying groundwork for a future publish command.
- Surface the new functionality through a make target that mirrors how `make dxt` delegates to existing release tooling.

## Scope & Constraints
- Do not modify DXT packaging behavior; new code must be additive.
- Keep build steps DRY by allowing `DRY_RUN=1` to skip heavy work for CI/tests.
- Environment validation will live in the future publish command; the build command must work without credentials.
- Tests must exercise the new script behavior without performing real publishes.

## Implementation Outline
1. **Script Entry Point**
   - Add subcommand `python-dist` to `bin/release.sh` dispatch.
   - Subcommand invokes `uv build --sdist --wheel --out-dir dist` (exact flags subject to uv syntax).
   - Honor `DRY_RUN=1` by logging intended commands instead of executing `uv build`.

2. **Make Integration**
   - Add target `python-dist` to `make.deploy` that runs `./bin/release.sh python-dist`.
   - Target should reuse `.env` sourcing from top-level Makefile.

3. **Testing Strategy**
   - Create pytest module invoking `bin/release.sh python-dist` via `subprocess.run`.
   - Use temporary directory for `dist/` to avoid polluting repo (set `DIST_DIR` env override if needed).
   - Assert command succeeds without credentials and logs a dry-run preview when `DRY_RUN=1`.
   - Mock `uv` command by injecting `PATH` with shim script during tests if necessary to avoid running real uv when DRY_RUN=0 paths are exercised.

4. **Directory Hygiene**
   - Ensure script creates `dist/` when absent.
   - Clean up temporary artifacts during tests to keep git status clean.

## Open Decisions
- Confirm uv command flags from documentation; adjust if syntax differs.

## Testing Matrix
| Scenario | Credentials | DRY_RUN | Expected Outcome |
| --- | --- | --- | --- |
| No credentials | none | 1 | Succeeds, logs dry-run command |
| Token path (future publish) | `UV_PUBLISH_TOKEN` | 0 | Out of scope for Phase 1 |
| Username/password (future publish) | `UV_PUBLISH_USERNAME`, `UV_PUBLISH_PASSWORD` | 0 | Out of scope for Phase 1 |
| Actual build | optional | 0 | Builds wheel & sdist into `dist/` |

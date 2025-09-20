# Phase 1 Design – UV Packaging via release.sh

## Objectives
- Extend `bin/release.sh` with a uv packaging command that builds wheel/sdist artifacts into `dist/`.
- Add environment validation inside the script so missing credentials short-circuit with clear messaging.
- Surface the new functionality through a make target that mirrors how `make dxt` delegates to existing release tooling.

## Scope & Constraints
- Do not modify DXT packaging behavior; new code must be additive.
- Keep build steps DRY by allowing `DRY_RUN=1` to skip heavy work for CI/tests.
- Environment validation should support either token-based (`UV_PUBLISH_TOKEN`) or username/password pairs to avoid blocking contributors.
- Tests must exercise the new script behavior without performing real publishes.

## Implementation Outline
1. **Script Entry Point**
   - Add subcommand `uv-package` to `bin/release.sh` dispatch.
   - Subcommand calls helper `ensure_uv_env` then invokes `uv build --sdist --wheel --out-dir dist` (exact flags subject to uv syntax).
   - Honor `DRY_RUN=1` by logging intended commands instead of executing `uv build`.

2. **Environment Validation**
   - Implement helper `ensure_uv_env` that checks for either `UV_PUBLISH_TOKEN` or both `UV_PUBLISH_USERNAME` & `UV_PUBLISH_PASSWORD`.
   - If neither credential path is present, exit with status 1 and actionable error.
   - Log which credential path is being used for transparency.

3. **Make Integration**
   - Add target `python-dist` to `make.deploy` that runs `./bin/release.sh uv-package`.
   - Target should reuse `.env` sourcing from top-level Makefile.

4. **Testing Strategy**
   - Create pytest module invoking `bin/release.sh uv-package` via `subprocess.run`.
   - Use temporary directory for `dist/` to avoid polluting repo (set `DIST_DIR` env override if needed).
   - Assert missing credentials produce non-zero exit and error message.
   - With minimal fake credentials and `DRY_RUN=1`, assert command succeeds and logs expected plan (no actual `uv build`).
   - Mock `uv` command by injecting `PATH` with shim script during tests if necessary to avoid running real uv when DRY_RUN=0 paths are exercised.

5. **Directory Hygiene**
   - Ensure script creates `dist/` when absent.
   - Clean up temporary artifacts during tests to keep git status clean.

## Open Decisions
- Confirm uv command flags from documentation; adjust if syntax differs.

## Testing Matrix
| Scenario | Credentials | DRY_RUN | Expected Outcome |
| --- | --- | --- | --- |
| Missing env | none | 1 | Exit non-zero, error message listing required variables |
| Token path | `UV_PUBLISH_TOKEN` | 1 | Succeeds, logs using token |
| Username/password | `UV_PUBLISH_USERNAME`, `UV_PUBLISH_PASSWORD` | 1 | Succeeds |
| Actual build (optional/manual) | valid creds | 0 | Builds wheel & sdist into `dist/` |

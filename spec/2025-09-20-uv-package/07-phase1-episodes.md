# Phase 1 Episodes – UV Packaging via release.sh

## Episode List
1. **Design Guardrails Test**
   - Add pytest module `tests/scripts/test_release_uv.py` capturing failure on missing credentials and success with fake credentials under `DRY_RUN=1`.
2. **Implement Environment Validation**
   - Introduce `ensure_uv_env` helper in `bin/release.sh` to enforce credential presence.
3. **Add UV Packaging Command**
   - Implement `uv-package` subcommand in `bin/release.sh` honoring `DRY_RUN` and creating artifacts directory.
4. **Expose Make Target**
   - Add `python-dist` target to `make.deploy` delegating to `release.sh uv-package`.
5. **Polish & Docs**
   - Update CLAUDE notes if new insights arise; ensure tests and lint pass.

Each episode should maintain a clean git state and keep tests passing (except during red steps for the active episode).

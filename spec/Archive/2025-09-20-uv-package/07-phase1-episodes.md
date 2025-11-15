# Phase 1 Episodes – UV Packaging via release.sh

## Episode List
1. **Design Guardrails Test**
   - Add pytest module (e.g., `tests/unit/test_release_uv.py`) verifying `bin/release.sh python-dist` succeeds without credentials and logs dry-run output.
2. **Add Python Dist Command**
   - Implement `python-dist` subcommand in `bin/release.sh` honoring `DRY_RUN` and creating artifacts directory.
3. **Expose Make Target**
   - Add `python-dist` target to `make.deploy` delegating to `release.sh python-dist`.
4. **Polish & Docs**
   - Update CLAUDE notes if new insights arise; ensure tests and lint pass.

Each episode should maintain a clean git state and keep tests passing (except during red steps for the active episode).

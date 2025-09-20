<!-- markdownlint-disable MD013 MD025 -->
# Phase 2 Design – Python Publish Workflow

## Objectives
- Introduce a `python-publish` command in `bin/release.sh` that drives `uv publish` to TestPyPI/PyPI.
- Require explicit credentials (token or username/password) and fail fast when they are missing.
- Support dry runs locally by logging the intended publish command without executing it.
- Provide a make target wrapper so developers can invoke publishes consistently.
- Document `.env` expectations and dry-run instructions for TestPyPI.

## Scope & Constraints
- Command must reuse the artifacts produced by `python-dist`; no rebuilds.
- Credential handling must avoid printing secrets to stdout.
- Support token-based auth (`UV_PUBLISH_TOKEN`) and basic auth (`UV_PUBLISH_USERNAME`/`UV_PUBLISH_PASSWORD`).
- Allow overriding repository URL via env (default to TestPyPI for dry runs).
- Dry-run mode (`DRY_RUN=1`) must never execute the real publish.

## Implementation Outline
1. **Environment Handling**
   - Helper `ensure_publish_env` checks for token or username/password.
   - Accept optional `PYPI_REPOSITORY_URL` (default `https://test.pypi.org/legacy/`).
   - Validate dist artifacts exist before publishing.

2. **Script Command**
   - Add `python-publish` subcommand to `bin/release.sh`.
   - Build uv command: `uv publish --repository-url $PYPI_REPOSITORY_URL` with auth flags.
   - In dry run, echo command without secrets; in real run, invoke uv with env vars.

3. **Make Integration**
   - Add `make python-publish` target delegating to `release.sh python-publish`.
   - Document in Makefile help alongside `python-dist`.

4. **Testing Strategy**
   - Pytest covering:
     - Failure when credentials missing.
     - Success path in dry-run with token env; assert command logged without secret leak.
     - Make target delegates to script.
   - Use temp dist dir with fake artifact file to satisfy preflight.

5. **Documentation**
   - Update CLAUDE.md with `.env` keys and dry-run instructions.
   - Outline sample `.env` entries for TestPyPI (username/password or token).

## Open Decisions
- Whether to support repository alias (prod vs test) via CLI flag.
- Naming of env var for repository; defaulting to TestPyPI but allow override.

## Testing Matrix
| Scenario | Credentials | DRY_RUN | Repo | Expected |
| --- | --- | --- | --- | --- |
| Missing env | none | 1 | default | Fails fast with helpful error |
| Token dry run | token | 1 | test | Logs command, no publish |
| User/pass dry run | user/pass | 1 | test | Logs command, no publish |
| Real publish (manual) | token | 0 | test/prod | Uses uv publish; manual verification |

<!-- markdownlint-disable MD013 MD025 -->
# Phase 2 Episodes – Python Publish Workflow

1. **Failing Tests for Publish Guardrails**
   - Add pytest cases verifying `python-publish` fails without credentials, succeeds in dry-run with token/user-pass, and requires dist artifacts.
2. **Implement Publish Command**
   - Add `ensure_publish_env`, `python-publish` subcommand, repository handling, and dry-run logging to `bin/release.sh`.
3. **Make Target & Docs**
   - Add `make python-publish`, update Makefile help, and extend CLAUDE.md with `.env` guidance and dry-run walkthrough.
4. **Validation & Cleanup**
   - Run targeted pytest + `make test-unit`, ensure dist temp dirs cleaned, and update PR notes.

Each episode should maintain green state outside the current Red/Green loop.

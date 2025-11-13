<!-- markdownlint-disable MD013 MD025 -->
# Phase 2 Checklist – Python Publish Workflow

## Preconditions
- [ ] Branch `phase2-python-publish` checked out and up to date.
- [ ] `uv` CLI available.
- [ ] TestPyPI credentials accessible for validation (token or username/password).

## Development Steps
- [ ] Red: add failing tests covering `bin/release.sh python-publish` behaviors.
- [ ] Green: implement publish command, env validation, repository handling, and make target.
- [ ] Documentation: update CLAUDE.md with `.env` keys and dry-run instructions.
- [ ] Ensure no secrets are logged; scrub outputs in tests.

## Validation
- [ ] Targeted pytest module passes (`tests/unit/test_release_uv.py`).
- [ ] `make test-unit` passes.
- [ ] Dry-run manual invocation logs expected command.
- [ ] Update PR description and notes.

## Postconditions
- [ ] `python-dist` + `python-publish` flow documented and test-covered.
- [ ] Ready to plan Phase 3 (CI Trusted Publishing integration).

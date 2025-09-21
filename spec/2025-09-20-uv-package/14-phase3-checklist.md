<!-- markdownlint-disable MD013 MD025 -->
# Phase 3 Checklist – Trusted Publishing Integration

- [ ] Update unit tests for `python-dist` / `python-publish` to reflect the PyPA action workflow (no combined helper).
- [ ] Clean up release script usage text and make targets after removing release orchestration helper.
- [ ] Update `.github/actions/create-release` to run dist build, PyPA publish, DXT build/validate, and release bundling.
- [ ] Adjust `push.yml` and `pr.yml` to supply PyPI/TestPyPI tokens and repository URLs to the composite action.
- [ ] Ensure Python artifacts and DXT bundles continue to upload as workflow artifacts.
- [ ] Refresh documentation (CLAUDE.md, workflows) describing the new CI order and local dry-run expectations.
- [ ] Run `make test-unit` (and targeted smoke tests) to verify release tooling changes.
- [ ] Capture new learnings in CLAUDE.md per repository guidelines after implementation.

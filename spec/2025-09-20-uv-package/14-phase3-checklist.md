<!-- markdownlint-disable MD013 MD025 -->
# Phase 3 Checklist – Trusted Publishing Integration

- [ ] Write failing tests covering the combined release subcommand dry run and error propagation.
- [ ] Implement release script orchestration that runs DXT build/validate, `python-dist`, and `python-publish` sequentially with shared `DRY_RUN` logic.
- [ ] Ensure standalone `python-dist` / `python-publish` commands remain functional and documented.
- [ ] Update GitHub Actions workflow to invoke the new release script entry point with Trusted Publishing permissions.
- [ ] Upload or reference Python artifacts in the GitHub Release alongside existing DXT bundles.
- [ ] Refresh documentation (CLAUDE.md, release sections) describing the unified release flow and dry-run guidance.
- [ ] Execute `make test` plus targeted dry-run of the combined release command.
- [ ] Record insights in CLAUDE.md per repository guidelines after implementation.

Title: Improve documentation (architecture, tool reference, examples, troubleshooting)

Labels: documentation, enhancement

Summary

Docs cover the pipeline and commands well but are light on: detailed tool reference (inputs/outputs/examples), auth/JWT flow, error codes, and troubleshooting. This issue proposes a docs pass to add a structured reference and common how-tos.

Proposed Additions

- Architecture deep-dive in `docs/architecture.md` covering 4 phases, data flow, and security model.
- Tool reference in `docs/tools.md` with per-tool: params, examples, success/error payloads, and performance notes.
- Auth guide `docs/auth.md` for Quilt/JWT setup, IAM policies, and local testing.
- Troubleshooting `docs/troubleshooting.md`: common errors, AWS permissions, rate limits, and timeouts.
- Contribution guide `CONTRIBUTING.md`: dev setup, coding standards, lint/type/test commands, PR process.
- Update `README.md` to link these docs and include a concise Quick Start targeted at users vs contributors.

Acceptance Criteria

- New `docs/*` files exist with accurate, copy-pastable examples.
- `README.md` links to docs and separates User vs Contributor flows.
- `CLAUDE.md` references are aligned with updated auth instructions.

Tasks

- [ ] Draft `docs/architecture.md`
- [ ] Draft `docs/tools.md` (auto-generate from code where possible)
- [ ] Draft `docs/auth.md`
- [ ] Draft `docs/troubleshooting.md`
- [ ] Add `CONTRIBUTING.md` and cross-link in `README.md`
- [ ] Add a `docs/README.md` index

References

- Existing: `README.md`, `CLAUDE.md`, `scripts/test-endpoint.sh`, tool modules in `app/quilt_mcp/tools`


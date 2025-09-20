<!-- markdownlint-disable MD013 -->
# Phase 2 Checklist - Restructure Core Packages

- [x] Relocate service layer modules under `quilt_mcp.services`
- [x] Remove legacy `quilt_mcp/aws` namespace after migration
- [ ] Review telemetry/validator packages and apply necessary moves
- [ ] Update configs/docs for new module paths
- [ ] Run `make test` and `make lint` after code moves

## Notes

- All runtime and test imports now reference `quilt_mcp.services.*`.
- Empty legacy directories (`config/`, `operations/`, `utilities/`) removed to simplify layout.

<!-- markdownlint-disable MD013 -->
# Phase 2 Checklist - Restructure Core Packages

- [ ] Relocate services module(s) and confirm legacy imports still resolve
- [ ] Consolidate AWS-related modules without breaking behaviors
- [ ] Review telemetry/validator packages and apply necessary moves
- [ ] Update configs/docs for new module paths
- [ ] Run `make test` and `make lint` after code moves

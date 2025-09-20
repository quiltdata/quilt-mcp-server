<!-- markdownlint-disable MD013 -->
# Analysis - Cleanup src Layout

**Reference**: Requirements in `spec/164-cleanup-src/01-requirements.md`

## Current Architecture

1. The `src/` tree exposes the `quilt_mcp` package along with `deploy/` assets and the CLI entry point `main.py`.
2. Within `quilt_mcp`, major domains already exist: `tools/`, `search/`, `visualization/`, `optimization/`, `aws/`, `telemetry/`, `validators/`, and `services/`.
3. Several subpackages (e.g., `search/backends`, `visualization/generators`) are richly populated and use deeper hierarchies, while others (`services/`, `validators/`, `aws/`) are shallow wrappers around one or two modules.
4. Some directories (such as `config/`, `operations/`, `utilities/`) appear to be stubs or legacy placeholders with no tracked `.py` files, though compiled bytecode artifacts remain from previous executions.
5. Tests (see `tests/`) and runtime modules import functionality directly from current module paths (e.g., `quilt_mcp.tools.package_ops`, `quilt_mcp.services.quilt_service`).

## Implementation Idioms & Conventions

1. Public APIs are exposed via module-level functions and classes; consumers import from the package path (no dynamic discovery).
2. `__init__.py` files typically re-export symbols (especially in `tools` and `visualization`) to simplify imports.
3. Behavior-driven tests patch nested module paths extensively (e.g., `@patch("quilt_mcp.services.quilt_service.quilt3")`), coupling tests to the current directory layout.
4. Configuration for packaging and entry points (e.g., `pyproject.toml`, `setup.cfg`, `Makefile`) relies on module paths inside `src/`.

## System Constraints & Limitations

1. Reorganization must preserve import paths consumed by published packages or external automation; breaking changes would ripple through tests and possibly deployed clients.
2. Build tooling expects packages under `src/` following the standard `src-layout`; moving files requires updating `pyproject` metadata if package names change.
3. Without runtime guards, collapsing packages risks circular imports if formerly separated modules now reside in a single file/scope.
4. Tests assume module paths for patching; failing to realign them will cause import errors at test runtime.

## Technical Debt & Refactoring Opportunities

1. Single-module subpackages (e.g., `services`, `telemetry`, `aws`) add unnecessary nesting and cognitive overhead when the submodule names already convey domain context.
2. Empty placeholder packages (`config`, `operations`, `utilities`) indicate either dead code or missing implementations that should be removed or populated.
3. Some modules (e.g., `version_sync.py`, `utils.py`) serve as catch-alls; reorganizing could clarify their relationships to other domains.
4. Lack of documentation about rationale for the current layout makes it difficult to distinguish intentional boundaries from historical baggage.

## Gaps Between Current State & Requirements

1. No current mapping documents which directories are candidates for consolidation or removal.
2. There is no automated safeguard ensuring docs/configs reference the correct module paths after refactors.
3. Tests cover behavior but may not assert on module locations; restructuring risks silent breakage if certain modules are loaded dynamically.

## Architectural Challenges

1. Maintaining backward-compatible import paths may require alias modules (`__init__` exports) during transition, which must be planned carefully to avoid duplication.
2. Consolidating packages may affect relative imports inside modules; re-evaluating import strategy is necessary to prevent circular dependencies.
3. Updating top-level documentation (e.g., `CLAUDE.md`) is mandatory per guidelines, yet we must avoid modifying historical specs.
4. Ensuring minimal churn means batching logical moves and keeping diffs focused, but file moves inherently create large diffs and require precise test coverage.

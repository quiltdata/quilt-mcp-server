# 03 - Code Maintainability

> **Status Note (2026-02-17):** This document is a historical snapshot from 2026-02-16 and is now partially outdated.
> Current deltas from this branch: `src/quilt_mcp/tools/packages.py` reduced from 2034 to 758 LOC via extraction to `src/quilt_mcp/tools/package_crud.py`, `src/quilt_mcp/tools/responses.py` reduced from 1063 to 987 LOC via extraction to `src/quilt_mcp/tools/responses_base.py` and `src/quilt_mcp/tools/responses_resources.py`, `scripts/detect_cycles.py` reports no import cycles, and no `TODO/FIXME` markers remain under `src/quilt_mcp/{backends,tools,ops}`.
> Remaining maintainability debt: multiple modules still exceed 1000 LOC (`ops/quilt_ops.py`, `services/governance_service.py`, `backends/platform_admin_ops.py`, `backends/platform_backend.py`, `services/workflow_service.py`).
> **PR 288 follow-up (2026-02-17):** CI import-breakage caused by stale references to `quilt_mcp.tools.packages` internals was fixed by migrating tests to implementation modules (`tools/package_crud.py`, `tools/s3_package_ingestion.py`) and enforcing `package_update` top-hash typing (reject non-string hashes).

**Date:** 2026-02-16  
**Reviewer:** Codex

## Commands Executed

- `find src/quilt_mcp -name "*.py" -exec wc -l {} \; | sort -rn | head -20`
- `grep -r "TODO\|FIXME" src/quilt_mcp/{backends,tools,ops}/`
- `uv run mypy src/quilt_mcp`
- `uv run radon cc src/quilt_mcp -a -nb`
- `uv run python` import-graph cycle detection script

## Module Size Distribution

Top module sizes (lines):

- `src/quilt_mcp/tools/packages.py`: 2034
- `src/quilt_mcp/ops/quilt_ops.py`: 1637
- `src/quilt_mcp/backends/platform_backend.py`: 1354
- `src/quilt_mcp/services/governance_service.py`: 1275
- `src/quilt_mcp/backends/platform_admin_ops.py`: 1211

Assessment:

- Criterion `No modules > 500 lines`: **not met** (many exceed threshold).

## Complexity Hotspots

- `radon` is not installed in current environment (`No such file or directory: radon`), so direct cyclomatic score extraction was not produced.
- Based on very large modules and dense branching domains (backend/tool orchestration), complexity risk is high in:
  - `src/quilt_mcp/tools/packages.py`
  - `src/quilt_mcp/ops/quilt_ops.py`
  - `src/quilt_mcp/backends/platform_backend.py`

## Module Boundaries / Circular Imports

Static internal import graph scan found **15** cycles, including:

- `quilt_mcp.utils.common -> quilt_mcp.context.handler -> quilt_mcp.context.factory -> quilt_mcp.services.workflow_service -> quilt_mcp.utils.common`
- `quilt_mcp.services.auth_service -> quilt_mcp.services.iam_auth_service -> quilt_mcp.services.auth_service`
- `quilt_mcp.backends.platform_backend -> quilt_mcp.backends.platform_admin_ops -> quilt_mcp.backends.platform_backend`

Assessment: clear-boundary criterion is **not met**.

## TODO/FIXME Inventory

Found in production path:

- `src/quilt_mcp/tools/packages.py`: TODO for summary/visualization handling.

## Type Coverage

- `uv run mypy src/quilt_mcp`: **Success**, no issues in 124 source files.

## Refactoring Needs

1. Split oversized modules (>1000 LOC) into domain-focused units.
2. Break circular import chains around `utils/common`, context factory, and platform backend/admin coupling.
3. Remove or resolve production TODO in `tools/packages.py`.
4. Add complexity gating tool (e.g., `radon`) to CI for enforceable thresholds.

## Pass/Fail Status

- No modules >500 lines: ❌ Fail
- Cyclomatic complexity reasonable: ⚠️ Warning (tool unavailable; risk signals high)
- Clear module boundaries (no circular imports): ❌ Fail
- Type hints present (mypy passing): ✅ Pass
- No TODO/FIXME in production paths: ❌ Fail
- Code follows project conventions: ✅ Pass (lint/mypy clean)

**Section Result:** ❌ **Fail**

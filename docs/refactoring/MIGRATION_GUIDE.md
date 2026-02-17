# Refactoring Migration Guide

## Summary

This guide covers module boundary changes introduced during maintainability refactoring.

## Package Tool Moves

- Core CRUD/browse/diff handlers now live in `src/quilt_mcp/tools/package_crud.py`.
- S3 ingestion workflow now lives in `src/quilt_mcp/tools/s3_package_ingestion.py`.
- `src/quilt_mcp/tools/packages.py` remains as the backward-compatible import surface.

## Response Model Moves

- Shared response base models moved to `src/quilt_mcp/tools/responses_base.py`.
- Resource response models moved to `src/quilt_mcp/tools/responses_resources.py`.
- `src/quilt_mcp/tools/responses.py` still exports existing response model names.

## Backend Utility Consolidation

- Shared registry/bucket parsing helpers were centralized in `src/quilt_mcp/utils/helpers.py`.
- Backend-facing utility exports are available via `src/quilt_mcp/backends/utils.py`.

## Import Guidance

- Continue importing tool entrypoints from `quilt_mcp.tools.packages` if you need compatibility.
- Prefer direct module imports for new development:
  - `quilt_mcp.tools.package_crud`
  - `quilt_mcp.tools.s3_package_ingestion`

## Validation Checklist

Run before merging:

```bash
make lint
make test-all
make test-remote-docker
```

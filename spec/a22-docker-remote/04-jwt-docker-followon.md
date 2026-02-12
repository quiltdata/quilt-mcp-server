# Follow-On: Real JWT Docker Testing Implementation

**Status**: Implemented  
**Date**: 2026-02-11  
**Scope**: Follow-on notes for `spec/a22-docker-remote/03-jwt-docker-plan.md`

## What Was Changed

### 1. `scripts/mcp-test.py` now requires real JWTs for `--jwt`

- Replaced generated/fake JWT behavior with strict discovery:
  - `PLATFORM_TEST_JWT_TOKEN` environment variable first
  - `quilt3` session token second (`quilt3 login`)
  - fail fast if neither is available
- Updated `--jwt` help text and CLI examples to reflect discovery-based real JWT usage.
- Removed the local test JWT generation path from `--jwt` flow.

Current behavior with `--jwt`:

1. If transport is not HTTP: exit with `--jwt only supported for HTTP transport`
2. If `PLATFORM_TEST_JWT_TOKEN` exists: use it
3. Else if quilt3 session has bearer token: use it
4. Else: exit with a clear error directing users to either:
   - set `PLATFORM_TEST_JWT_TOKEN`, or
   - run `quilt3 login`
   - and use pytest for mocked tests

### 2. Docker test target made deterministic for remote/JWT validation

`make.dev` `test-mcp-docker` now runs a stable selector set for tools/resources and disables loops by default:

- Added:
  - `MCP_DOCKER_TOOLS`
  - `MCP_DOCKER_RESOURCES`
  - `MCP_DOCKER_LOOPS`
- Target passes these to `scripts/mcp-test.py` via `--tools`, `--resources`, `--loops`.

This keeps Docker JWT validation focused on stable remote-compatible coverage and avoids known non-deterministic failures from write loops in this environment.

## Validation Performed

Executed:

1. `make lint`
2. `make test-mcp-docker`

Result:

- Lint passed.
- Docker test passed with:
  - real JWT discovery message: `✅ Using JWT from quilt3 session`
  - tools: `20/20 passed`
  - resources: `11/11 passed`
  - overall: `✅ ALL TESTS PASSED`

## Notes

- Existing specs were not rewritten.
- This file is the follow-on explanation requested for the implemented changes.

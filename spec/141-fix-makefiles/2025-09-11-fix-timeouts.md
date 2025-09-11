# Timeout Configuration Standardization

**Date**: 2025-09-11  
**Issue**: CI using 30s timeout while Makefile uses 120s, causing test failures

## Problem

CI workflow has `--timeout=30` but integration tests need 120s for AWS/SSL operations (per commit b1d67f1).

## End State

- **Single test timeout**: `PYTEST_TIMEOUT` (default: 120s)
- **Runtime timeout envars**: `MCP_TIMEOUT_AWS=300`, `MCP_TIMEOUT_SEARCH=60`
- **Consistent timeouts** across CI, Makefiles, and runtime components
- **No hardcoded timeouts** in source code

## Key Decisions

1. **Single `PYTEST_TIMEOUT=120`** for all tests (simplicity over granularity)
2. **Environment variable override** pattern for all timeout configuration  
3. **Operation-specific timeouts** for runtime components only

## Interventions

1. **Immediate**: Fix CI timeout 30s → 120s
2. **Create timeout config module** with env var support
3. **Replace hardcoded timeouts** in telemetry, search, testing modules
4. **Update Makefiles** to use env vars
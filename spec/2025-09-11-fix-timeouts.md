# Timeout Configuration Standardization

**Date**: 2025-09-11  
**Status**: Specification  
**Issue**: Inconsistent timeout values across CI, tests, and runtime components causing test failures

## Problem Statement

The codebase has inconsistent timeout configurations:

1. **CI Workflow**: Uses 30s timeout (`--timeout=30`) in `.github/workflows/ci.yml:37`
2. **Makefile**: Uses 60s and 120s timeouts in various targets
3. **Runtime Components**: Hardcoded 30s timeouts in multiple locations
4. **Integration Tests**: Need longer timeouts for AWS operations and SSL handshakes

This inconsistency causes test failures when CI timeout is too short for actual test requirements.

## Current Timeout Usage

### CI/Testing
- `.github/workflows/ci.yml`: `--timeout=30`
- `make.dev` targets: `--timeout=60` and `--timeout=120`
- Integration test docs: `--timeout=30`

### Runtime Components
- `src/quilt_mcp/telemetry/transport.py`: `timeout=30`
- `src/quilt_mcp/optimization/testing.py`: `timeout=30.0`
- `src/quilt_mcp/tools/search.py`: `timeout=30`
- `tests/configs/mcp-test.yaml`: `timeout: 30`

## Proposed Solution

### 1. Environment Variable Configuration

Introduce standardized environment variables for timeout configuration:

```bash
# Test timeouts
PYTEST_TIMEOUT_DEFAULT=120        # Default pytest timeout for all tests
PYTEST_TIMEOUT_FAST=60           # Timeout for unit tests
PYTEST_TIMEOUT_INTEGRATION=300   # Timeout for integration tests

# Runtime timeouts
MCP_TIMEOUT_DEFAULT=120          # Default MCP operation timeout
MCP_TIMEOUT_SEARCH=60            # Search operation timeout
MCP_TIMEOUT_TELEMETRY=30         # Telemetry operation timeout
MCP_TIMEOUT_AWS=300              # AWS operation timeout
```

### 2. Configuration Hierarchy

1. **Environment variables** (highest priority)
2. **Configuration files** (medium priority)
3. **Hardcoded defaults** (lowest priority)

### 3. Implementation Plan

#### Phase 1: Standardize Test Timeouts
- Update CI workflow to use `PYTEST_TIMEOUT_DEFAULT`
- Update Makefile targets to use environment variables
- Create timeout configuration utility module

#### Phase 2: Runtime Timeout Configuration
- Create timeout configuration class
- Update all runtime components to use configurable timeouts
- Add timeout configuration to MCP server settings

#### Phase 3: Documentation and Validation
- Update documentation with timeout configuration options
- Add tests for timeout configuration
- Validate timeout behavior in integration tests

## Implementation Details

### Timeout Configuration Module

```python
# src/quilt_mcp/config/timeouts.py
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class TimeoutConfig:
    """Centralized timeout configuration."""
    
    # Test timeouts
    pytest_default: int = 120
    pytest_fast: int = 60
    pytest_integration: int = 300
    
    # Runtime timeouts
    mcp_default: int = 120
    mcp_search: int = 60
    mcp_telemetry: int = 30
    mcp_aws: int = 300
    
    @classmethod
    def from_env(cls) -> 'TimeoutConfig':
        """Load timeout configuration from environment variables."""
        return cls(
            pytest_default=int(os.getenv('PYTEST_TIMEOUT_DEFAULT', '120')),
            pytest_fast=int(os.getenv('PYTEST_TIMEOUT_FAST', '60')),
            pytest_integration=int(os.getenv('PYTEST_TIMEOUT_INTEGRATION', '300')),
            mcp_default=int(os.getenv('MCP_TIMEOUT_DEFAULT', '120')),
            mcp_search=int(os.getenv('MCP_TIMEOUT_SEARCH', '60')),
            mcp_telemetry=int(os.getenv('MCP_TIMEOUT_TELEMETRY', '30')),
            mcp_aws=int(os.getenv('MCP_TIMEOUT_AWS', '300')),
        )

# Global timeout configuration instance
TIMEOUTS = TimeoutConfig.from_env()
```

### CI Workflow Updates

```yaml
# .github/workflows/ci.yml
- name: Run tests
  run: |
    export PYTEST_TIMEOUT_DEFAULT=120
    export PYTHONPATH="src" && QUILT_DISABLE_QUILT3_SESSION=1 uv run python -m pytest tests/ -v -m "not search" --timeout=${PYTEST_TIMEOUT_DEFAULT} --disable-warnings
```

### Makefile Updates

```makefile
# make.dev
PYTEST_TIMEOUT_DEFAULT ?= 120
PYTEST_TIMEOUT_FAST ?= 60
PYTEST_TIMEOUT_INTEGRATION ?= 300

test-ci:
	@export PYTHONPATH="src" && QUILT_DISABLE_QUILT3_SESSION=1 uv run python -m pytest tests/ -v -m "not search and not slow" --timeout=$(PYTEST_TIMEOUT_FAST) --disable-warnings
```

## Benefits

1. **Consistency**: All timeout values configured from single source
2. **Flexibility**: Different timeout values for different test types
3. **Environment-aware**: Can adjust timeouts for CI vs local development
4. **Maintainable**: No more hardcoded timeout values scattered across codebase
5. **Debuggable**: Clear visibility into timeout configuration

## Acceptance Criteria

- [ ] All hardcoded timeout values replaced with configurable alternatives
- [ ] CI workflow uses appropriate timeout for test type
- [ ] Environment variables documented in README
- [ ] Tests pass consistently with new timeout configuration
- [ ] No performance regression from timeout changes

## Migration Strategy

1. **Immediate fix**: Update CI workflow timeout to 120s
2. **Gradual migration**: Replace hardcoded timeouts component by component  
3. **Validation**: Ensure all tests pass with new configuration
4. **Documentation**: Update all relevant documentation

## Risk Assessment

- **Low risk**: Timeout configuration is non-functional change
- **Mitigation**: Keep existing default values during migration
- **Rollback**: Easy to revert to hardcoded values if needed
<!-- markdownlint-disable MD013 MD024 -->
# Specification: UVX Package Compatibility for quilt-mcp

## Reference Context

**Source**: [02-analysis.md](./02-analysis.md)
**GitHub Issue**: #152
**Branch**: `152-dxt-to-uvx-mcpb`

This specification defines the requirements for making `quilt-mcp` compatible with UVX execution model, enabling `uvx quilt-mcp` to successfully run the server.

## Problem Statement

Current console script configuration fails with UVX:

```log
ModuleNotFoundError: No module named 'src'
```

The entry point `src.main:main` is incompatible with standard Python packaging conventions where `src` is a development directory, not a package namespace.

## Requirements

### 1. Console Script Compatibility

#### 1.1 Entry Point Fix

- **Current**: `quilt-mcp = "src.main:main"`
- **Required**: `quilt-mcp = "quilt_mcp.main:main"`
- **Rationale**: Must reference the actual package namespace, not the source directory

#### 1.2 Module Structure

- Move entry point from `src/main.py` to `src/quilt_mcp/main.py`
- Ensure `quilt_mcp` is the importable package namespace
- Maintain backward compatibility with existing imports

### 2. Package Structure Requirements

#### 2.1 Source Organization

```log
src/
├── quilt_mcp/
│   ├── __init__.py
│   ├── main.py         # New location for entry point
│   ├── utils.py        # Existing utilities
│   └── ...             # Other modules
└── main.py             # DEPRECATED - to be removed
```

#### 2.2 Import Path Resolution

- Package must be installable via `pip install .` or `uv pip install .`
- All imports must use `quilt_mcp` namespace
- No reliance on `src` being in PYTHONPATH

### 3. UVX Execution Requirements

#### 3.1 Package Installation

- Must be pip-installable from PyPI or TestPyPI
- Console script must be registered during installation
- Dependencies must be correctly specified in pyproject.toml

#### 3.2 Runtime Environment

- UVX creates isolated environment with package and dependencies
- No manual PYTHONPATH manipulation required
- Transport mode (`FASTMCP_TRANSPORT=stdio`) must be preserved

### 4. Migration Strategy

#### 4.1 Phase 1: Fix Console Script

1. Create `src/quilt_mcp/main.py` with entry point logic
2. Update `pyproject.toml` console script to reference `quilt_mcp.main:main`
3. Test local installation with `pip install -e .`

#### 4.2 Phase 2: Validate UVX Compatibility

1. Build distribution package with `uv build`
2. Test installation with `uv pip install dist/*.whl`
3. Verify `uvx quilt-mcp` executes successfully

#### 4.3 Phase 3: Update MCPB Manifest

1. Change manifest command from `bootstrap.py` to `uvx quilt-mcp`
2. Remove bootstrap.py and dxt_main.py (no longer needed)
3. Update environment variables as needed

### 5. Implementation Details

#### 5.1 New main.py Location

**File**: `src/quilt_mcp/main.py`

```python
#!/usr/bin/env python3
"""Main entry point for quilt-mcp server."""

import os
import sys
from quilt_mcp.utils import run_server


def main() -> None:
    """Main entry point for the MCP server."""
    # Ensure stdio transport for MCP communication
    os.environ.setdefault("FASTMCP_TRANSPORT", "stdio")

    # Run the server
    run_server()


if __name__ == "__main__":
    main()
```

#### 5.2 Updated pyproject.toml

```toml
[project.scripts]
quilt-mcp = "quilt_mcp.main:main"

[tool.setuptools.packages.find]
where = ["src"]
include = ["quilt_mcp*"]
```

#### 5.3 MCPB Manifest Command

```json
{
  "command": ["uvx", "quilt-mcp"],
  "env": {
    "PYTHONNOUSERSITE": "1",
    "FASTMCP_TRANSPORT": "stdio"
  }
}
```

### 6. Testing Requirements

#### 6.1 Local Testing

- `pip install -e .` must work in development
- `quilt-mcp` command must be available after installation
- Server must start successfully with console script

#### 6.2 UVX Testing

- `uvx quilt-mcp` must execute without import errors
- Server must respond to MCP protocol messages
- All functionality must work in UVX environment

#### 6.3 Integration Testing

- MCPB package with UVX command must work in Claude Desktop
- Server must handle all existing tool operations
- Authentication and configuration must be preserved

### 7. Backward Compatibility

#### 7.1 Deprecation Path

- Keep `src/main.py` temporarily with deprecation warning
- Redirect to new entry point for transition period
- Document migration in release notes

#### 7.2 Import Compatibility

- Existing imports of `quilt_mcp` modules must continue working
- No breaking changes to public API
- Maintain all existing functionality

### 8. Success Criteria

1. **Console Script Works**: `quilt-mcp` command executes without import errors
2. **UVX Compatible**: `uvx quilt-mcp` successfully starts the server
3. **Tests Pass**: All existing tests continue to pass
4. **MCPB Integration**: MCPB package using UVX works in Claude Desktop
5. **No Regression**: All existing functionality remains intact

### 9. Risk Mitigation

#### 9.1 Import Path Issues

- **Risk**: Broken imports after restructuring
- **Mitigation**: Comprehensive import testing, gradual migration

#### 9.2 UVX Environment Differences

- **Risk**: Missing environment variables or configuration
- **Mitigation**: Explicit environment setup in main.py

#### 9.3 Package Distribution

- **Risk**: Package not available on PyPI for UVX
- **Mitigation**: TestPyPI deployment for validation first

## Implementation Checklist

- [ ] Create `src/quilt_mcp/main.py` with proper entry point
- [ ] Update `pyproject.toml` console script configuration
- [ ] Remove or deprecate `src/main.py`
- [ ] Test local pip installation
- [ ] Build distribution package with `uv build`
- [ ] Test UVX execution locally
- [ ] Update MCPB manifest for UVX command
- [ ] Remove bootstrap.py and dxt_main.py
- [ ] Update documentation for new execution model
- [ ] Validate in Claude Desktop environment

## Notes

This specification focuses solely on making the package UVX-compatible. The broader MCPB packaging and DXT replacement will be addressed in separate specifications.

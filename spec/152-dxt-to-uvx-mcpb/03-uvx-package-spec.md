<!-- markdownlint-disable MD013 MD024 -->
# Specification: Minimal UVX Package Support

## Reference Context

**Source**: [02-analysis.md](./02-analysis.md)
**GitHub Issue**: #152
**Branch**: `152-dxt-to-uvx-mcpb`

This specification defines the minimal changes needed to support `uvx quilt-mcp` execution.

## Problem Statement

Current console script `src.main:main` fails with:

```log
ModuleNotFoundError: No module named 'src'
```

## Solution

Fix the console script entry point to use the correct module path:

### 1. Update pyproject.toml

**File**: `pyproject.toml` (line 53)

```toml
[project.scripts]
quilt-mcp = "quilt_mcp.main:main"
```

### 2. Create Entry Point Module

**File**: `src/quilt_mcp/main.py`

```python
#!/usr/bin/env python3
"""Entry point for uvx execution."""

import os
from quilt_mcp.utils import run_server

def main() -> None:
    """Main entry point for the MCP server."""
    # Force stdio transport for MCP (same as dxt_main.py)
    os.environ["FASTMCP_TRANSPORT"] = "stdio"
    run_server()

if __name__ == "__main__":
    main()
```

## Testing

1. Build package: `uv build`
2. Test locally: `uvx --from dist/*.whl quilt-mcp`
3. Verify server starts without import errors

## Notes

- Keeps existing DXT infrastructure intact
- Bootstrap.py and dxt_main.py remain for DXT/MCPB packaging
- This enables UVX as an execution option without breaking existing functionality

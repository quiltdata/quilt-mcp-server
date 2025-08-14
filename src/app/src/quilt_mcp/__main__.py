#!/usr/bin/env python3
"""Single unified entry point for all Quilt MCP server modes.

This replaces all the separate entry_points files with a single unified approach.
Environment variables control behavior:

- FASTMCP_TRANSPORT: 'stdio', 'sse', or 'streamable-http' (default: auto-detect)
- RUNTIME: 'local' (dev machine), 'docker' (containerized), 'lambda' (AWS Lambda) (default: auto-detect)
- LOG_LEVEL: Logging level (default: 'INFO')

Usage:
    python -m quilt_mcp                              # Auto-detect transport and runtime
    FASTMCP_TRANSPORT=stdio python -m quilt_mcp     # Force stdio transport (Claude Desktop)
    FASTMCP_TRANSPORT=streamable-http python -m quilt_mcp  # Force HTTP transport (dev server)
    RUNTIME=docker python -m quilt_mcp              # Override runtime (useful for container testing)
"""

from .server import main

if __name__ == "__main__":
    main()
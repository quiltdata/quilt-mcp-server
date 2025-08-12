#!/usr/bin/env python3
"""Development server entry point with auto-reload support.

This script is designed to work with fastmcp dev for development with auto-reload.
It runs the MCP server with streamable HTTP transport on localhost.
"""

from __future__ import annotations
import quilt_mcp

# Export the configured server for fastmcp dev
mcp = quilt_mcp.mcp

def main() -> None:
    """Run the development HTTP server."""
    quilt_mcp.mcp.run(transport="streamable-http")

if __name__ == "__main__":
    main()
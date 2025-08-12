#!/usr/bin/env python3
"""STDIO server entry point for Claude Desktop integration."""

from __future__ import annotations
import quilt_mcp

def main() -> None:
    """Run the MCP server with STDIO transport."""
    quilt_mcp.mcp.run()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Pure FastMCP server for Quilt data access."""

from quilt_mcp.utils import run_server


def main():
    """Main entry point for the MCP server."""
    run_server()


if __name__ == "__main__":
    main()
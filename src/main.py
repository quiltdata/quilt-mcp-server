#!/usr/bin/env python3
"""Pure FastMCP server for Quilt data access."""

from quilt_mcp.utils.common import run_server


def main() -> None:
    """Main entry point for the MCP server."""
    run_server()


if __name__ == "__main__":
    main()

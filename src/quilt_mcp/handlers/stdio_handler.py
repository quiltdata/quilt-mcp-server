"""STDIO transport handler for MCP server."""

from __future__ import annotations

from .. import mcp


def main() -> None:
    """Run the MCP server with STDIO transport."""
    mcp.run()

if __name__ == "__main__":
    main()
